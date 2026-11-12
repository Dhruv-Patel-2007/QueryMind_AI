"""QueryPlanIR & QueryPlanner for QueryMind AI 2.0 (Phase 6.1).

Defines the strongly typed, deeply immutable Intermediate Representation (QueryPlanIR)
and the logical QueryPlanner service. Operates upstream of SQL generation, converting
Phase 3-5 understanding into validated relational query plans with zero raw SQL strings.
"""

import math
import re
from typing import Any, Dict, List, Literal, Mapping, Optional, Set, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.parameter_registry import (
    ParameterBuilder,
    ParameterRegistry,
    SupportedScalar,
)
from app.services.schema_linker import (
    SchemaCatalog,
    JoinGraph,
    get_schema_catalog,
    get_join_graph,
    get_schema_linker,
    SchemaLinker,
)
from app.services.intent_classifier import (
    IntentClassifier,
    get_intent_classifier,
    INTENT_CATEGORIES,
)
from app.services.context_engine import (
    ContextMind,
    get_context_engine,
)
from app.schemas.context import ContextResolveResponse, ContextFrameSchema


# ---------------------------------------------------------------------------
# Structured Expression Nodes (Zero Arbitrary SQL Strings)
# ---------------------------------------------------------------------------

class ColumnRefIR(BaseModel):
    """Structured physical column reference qualified by relation alias."""
    model_config = ConfigDict(frozen=True)

    table_alias: str = Field(..., min_length=1, max_length=10, description="Relation alias, e.g. 's'")
    column_name: str = Field(..., min_length=1, max_length=50, description="Catalog column name, e.g. 'roll_number'")


SupportedAggregateFunction = Literal["COUNT", "AVG", "SUM", "MIN", "MAX"]


class AggregateFunctionIR(BaseModel):
    """Structured representation of an authorized aggregate function."""
    model_config = ConfigDict(frozen=True)

    function_name: SupportedAggregateFunction
    column_ref: Optional[ColumnRefIR] = Field(None, description="None represents COUNT(*)")
    is_distinct: bool = False
    round_digits: Optional[int] = Field(None, ge=0, le=6)

    @model_validator(mode="after")
    def validate_aggregate_target(self) -> "AggregateFunctionIR":
        if self.function_name in ("AVG", "SUM", "MIN", "MAX") and self.column_ref is None:
            raise ValueError(f"Aggregate function '{self.function_name}' requires an explicit column reference.")
        return self


class ProjectionIR(BaseModel):
    """Structured projection item: either a physical column or an aggregate function."""
    model_config = ConfigDict(frozen=True)

    expression_node: Union[ColumnRefIR, AggregateFunctionIR]
    alias: Optional[str] = Field(None, min_length=1, max_length=50, description="Output column alias")

    @property
    def is_aggregate(self) -> bool:
        return isinstance(self.expression_node, AggregateFunctionIR)


AuthorizedBaseOperator = Literal[
    "=", "<", ">", "<=", ">=",
    "LIKE", "ILIKE", "IN", "BETWEEN", "IS NULL"
]


class PredicateIR(BaseModel):
    """Structured filtering predicate bound to registered parameter keys."""
    model_config = ConfigDict(frozen=True)

    column: ColumnRefIR
    operator: AuthorizedBaseOperator
    parameter_keys: Tuple[str, ...] = Field(default_factory=tuple)
    is_negated: bool = False

    @model_validator(mode="after")
    def validate_predicate_semantics(self) -> "PredicateIR":
        # 1. Canonical negation checks
        if self.operator in ("<", ">", "<=", ">=") and self.is_negated:
            raise ValueError(
                f"Redundant negation on ordered comparison operator '{self.operator}': "
                "use the complementary comparison operator instead of is_negated=True."
            )

        # 2. Operator-specific parameter cardinality checks
        op = self.operator
        card = len(self.parameter_keys)

        if op == "IS NULL":
            if card != 0:
                raise ValueError(f"Operator 'IS NULL' requires exactly 0 parameter keys, got {card}.")
        elif op in ("=", "LIKE", "ILIKE", "<", ">", "<=", ">="):
            if card != 1:
                raise ValueError(f"Operator '{op}' requires exactly 1 parameter key, got {card}.")
        elif op == "BETWEEN":
            if card != 2:
                raise ValueError(f"Operator 'BETWEEN' requires exactly 2 parameter keys (lower, upper), got {card}.")
        elif op == "IN":
            if card < 1:
                raise ValueError(f"Operator 'IN' requires at least 1 parameter key, got {card}.")

        return self


class HavingIR(BaseModel):
    """Structured post-aggregation filter."""
    model_config = ConfigDict(frozen=True)

    aggregate: AggregateFunctionIR
    operator: AuthorizedBaseOperator
    parameter_keys: Tuple[str, ...] = Field(default_factory=tuple)
    is_negated: bool = False

    @model_validator(mode="after")
    def validate_having_semantics(self) -> "HavingIR":
        if self.operator in ("<", ">", "<=", ">=") and self.is_negated:
            raise ValueError(
                f"Redundant negation on ordered comparison operator '{self.operator}': "
                "use the complementary comparison operator instead of is_negated=True."
            )
        op = self.operator
        card = len(self.parameter_keys)
        if op == "IS NULL" and card != 0:
            raise ValueError(f"Operator 'IS NULL' requires exactly 0 parameter keys, got {card}.")
        elif op in ("=", "LIKE", "ILIKE", "<", ">", "<=", ">=") and card != 1:
            raise ValueError(f"Operator '{op}' requires exactly 1 parameter key, got {card}.")
        elif op == "BETWEEN" and card != 2:
            raise ValueError(f"Operator 'BETWEEN' requires exactly 2 parameter keys, got {card}.")
        elif op == "IN" and card < 1:
            raise ValueError(f"Operator 'IN' requires at least 1 parameter key, got {card}.")
        return self


class OrderByIR(BaseModel):
    """Structured sorting specification."""
    model_config = ConfigDict(frozen=True)

    target: Union[ColumnRefIR, AggregateFunctionIR]
    direction: Literal["ASC", "DESC"] = "ASC"


class RelationInstance(BaseModel):
    """Declared instance of a physical relation within the query."""
    model_config = ConfigDict(frozen=True)

    instance_id: str = Field(..., description="Unique instance identifier, e.g. 'rel_0'")
    table_name: str = Field(..., description="Canonical physical table name, e.g. 'students'")
    alias: str = Field(..., description="Short table alias, e.g. 's'")


class JoinIR(BaseModel):
    """Structured relational join connecting two relation instances."""
    model_config = ConfigDict(frozen=True)

    left_alias: str
    left_column: str
    right_alias: str
    right_column: str
    join_type: Literal["INNER", "LEFT"]
    additional_predicates: Tuple[PredicateIR, ...] = Field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Verified Database Candidate Keys & Result-Grain Tie-Breakers
# ---------------------------------------------------------------------------

TABLE_CANDIDATE_KEYS: Dict[str, Tuple[Tuple[str, ...], ...]] = {
    "students": (("roll_number",), ("student_id",)),
    "courses": (("course_code",), ("course_id",)),
    "departments": (("code",), ("name",), ("department_id",)),
    "instructors": (("instructor_id",),),
    "course_offerings": (("offering_id",), ("course_id", "term_id", "section")),
    "enrollments": (("enrollment_id",), ("student_id", "offering_id")),
    "assessments": (("assessment_id",),),
    "student_marks": (("assessment_id", "enrollment_id"),),
    "terms": (("term_id",), ("term_name",)),
}

CANONICAL_GRAIN_TIE_BREAKERS: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "students": (("roll_number", "ASC"),),
    "courses": (("course_code", "ASC"),),
    "departments": (("code", "ASC"),),
    "instructors": (("instructor_id", "ASC"),),
    "course_offerings": (("offering_id", "ASC"),),
    "enrollments": (("enrollment_id", "ASC"),),
    "assessments": (("assessment_id", "ASC"),),
    "student_marks": (("assessment_id", "ASC"), ("enrollment_id", "ASC")),
}


# ---------------------------------------------------------------------------
# Authoritative QueryPlanIR
# ---------------------------------------------------------------------------

class QueryPlanIR(BaseModel):
    """Immutable, statically validated logical query intermediate representation."""
    model_config = ConfigDict(frozen=True)

    intent: Literal["AGGREGATE", "RANKING", "FILTER", "COMPARISON", "TREND", "GENERAL_QUERY", "WHAT_IF"]
    anchor_relation: str
    relation_instances: Tuple[RelationInstance, ...]
    projections: Tuple[ProjectionIR, ...]
    joins: Tuple[JoinIR, ...] = Field(default_factory=tuple)
    predicates: Tuple[PredicateIR, ...] = Field(default_factory=tuple)
    group_by: Tuple[ColumnRefIR, ...] = Field(default_factory=tuple)
    having: Tuple[HavingIR, ...] = Field(default_factory=tuple)
    order_by: Tuple[OrderByIR, ...] = Field(default_factory=tuple)
    limit: Optional[int] = None
    offset: Optional[int] = None
    parameter_registry: ParameterRegistry

    @field_validator("limit", mode="before")
    @classmethod
    def validate_limit_strict_integer(cls, v: Any) -> Any:
        if v is not None:
            if type(v) is not int or type(v) is bool:
                raise ValueError("LIMIT must be a strict integer.")
        return v

    @field_validator("offset", mode="before")
    @classmethod
    def validate_offset_strict_integer(cls, v: Any) -> Any:
        if v is not None:
            if type(v) is not int or type(v) is bool:
                raise ValueError("OFFSET must be a strict integer.")
        return v

    @model_validator(mode="after")
    def validate_plan_invariants(self) -> "QueryPlanIR":
        catalog = get_schema_catalog()
        join_graph = get_join_graph()

        # 1. Unique Relation Aliases and Instance IDs
        seen_aliases: Set[str] = set()
        seen_ids: Set[str] = set()
        alias_to_table: Dict[str, str] = {}

        for rel in self.relation_instances:
            alias_low = rel.alias.lower()
            if alias_low in seen_aliases:
                raise ValueError(f"Duplicate relation alias declared: '{rel.alias}'.")
            seen_aliases.add(alias_low)

            if rel.instance_id in seen_ids:
                raise ValueError(f"Duplicate relation instance_id declared: '{rel.instance_id}'.")
            seen_ids.add(rel.instance_id)

            alias_to_table[alias_low] = rel.table_name

        # 2. Anchor Invariant
        declared_tables = {r.table_name for r in self.relation_instances}
        if self.anchor_relation not in declared_tables:
            raise ValueError(
                f"Anchor relation '{self.anchor_relation}' is not among declared relation instances: {declared_tables}."
            )

        # Helper to validate a ColumnRefIR
        def validate_column_ref(col: ColumnRefIR, context: str) -> None:
            a_low = col.table_alias.lower()
            if a_low not in alias_to_table:
                raise ValueError(
                    f"Unknown table alias '{col.table_alias}' in {context}. Must be one of {set(alias_to_table.keys())}."
                )
            target_table = alias_to_table[a_low]
            table_meta = catalog.get_table(target_table)
            if not table_meta or col.column_name not in table_meta.columns:
                raise ValueError(
                    f"Column '{col.column_name}' in {context} does not exist in table '{target_table}'."
                )

        # 3. Catalog Column Resolution across Projections
        for idx, proj in enumerate(self.projections):
            if isinstance(proj.expression_node, ColumnRefIR):
                validate_column_ref(proj.expression_node, f"projection[{idx}]")
            elif isinstance(proj.expression_node, AggregateFunctionIR):
                agg = proj.expression_node
                if agg.column_ref:
                    validate_column_ref(agg.column_ref, f"projection[{idx}].{agg.function_name}")
                    # Numeric compatibility for AVG and SUM
                    if agg.function_name in ("AVG", "SUM"):
                        t_name = alias_to_table[agg.column_ref.table_alias.lower()]
                        col_meta = catalog.get_column(t_name, agg.column_ref.column_name)
                        if col_meta:
                            raw_t = col_meta.data_type.upper()
                            if not any(num_t in raw_t for num_t in ("INT", "REAL", "FLOAT", "NUMERIC", "DOUBLE")):
                                raise ValueError(
                                    f"Aggregate '{agg.function_name}' requires a numeric column, "
                                    f"but '{col_meta.name}' has type '{col_meta.data_type}'."
                                )

        # 4. Join Endpoint and Adjacency Resolution
        for idx, join in enumerate(self.joins):
            l_low = join.left_alias.lower()
            r_low = join.right_alias.lower()
            if l_low not in alias_to_table:
                raise ValueError(f"Unknown left alias '{join.left_alias}' in join[{idx}].")
            if r_low not in alias_to_table:
                raise ValueError(f"Unknown right alias '{join.right_alias}' in join[{idx}].")

            l_table = alias_to_table[l_low]
            r_table = alias_to_table[r_low]

            l_meta = catalog.get_table(l_table)
            r_meta = catalog.get_table(r_table)
            if not l_meta or join.left_column not in l_meta.columns:
                raise ValueError(f"Join left column '{join.left_column}' does not exist in table '{l_table}'.")
            if not r_meta or join.right_column not in r_meta.columns:
                raise ValueError(f"Join right column '{join.right_column}' does not exist in table '{r_table}'.")

            # Validate that join edge exists in JoinGraph
            valid_edge = False
            for edge in join_graph.adj.get(l_table, []):
                if (
                    edge.to_table == r_table
                    and (
                        (edge.from_column == join.left_column and edge.to_column == join.right_column)
                        or (edge.from_column == join.right_column and edge.to_column == join.left_column)
                    )
                ):
                    valid_edge = True
                    break
            if not valid_edge:
                raise ValueError(
                    f"Join[{idx}] condition '{l_table}.{join.left_column} = {r_table}.{join.right_column}' "
                    "does not correspond to a valid physical foreign-key relationship in JoinGraph."
                )

            # Validate additional predicates in join ON clause
            for p_idx, p in enumerate(join.additional_predicates):
                validate_column_ref(p.column, f"join[{idx}].additional_predicates[{p_idx}]")
                p_alias = p.column.table_alias.lower()
                if p_alias not in (l_low, r_low):
                    raise ValueError(
                        f"Join[{idx}] additional_predicate references alias '{p.column.table_alias}', "
                        f"which is neither '{join.left_alias}' nor '{join.right_alias}'."
                    )

        # 5. GroupBy & Aggregate Semantic Consistency
        has_aggregate = any(p.is_aggregate for p in self.projections)
        group_by_pairs = {(g.table_alias.lower(), g.column_name.lower()) for g in self.group_by}

        for idx, g in enumerate(self.group_by):
            validate_column_ref(g, f"group_by[{idx}]")

        if has_aggregate:
            for idx, p in enumerate(self.projections):
                if isinstance(p.expression_node, ColumnRefIR):
                    pair = (p.expression_node.table_alias.lower(), p.expression_node.column_name.lower())
                    if pair not in group_by_pairs:
                        raise ValueError(
                            f"Non-aggregate projection '{p.expression_node.table_alias}.{p.expression_node.column_name}' "
                            "must be explicitly present in GROUP BY when aggregate expressions exist."
                        )

        # 6. Bijective Parameter Key Accounting
        referenced_keys: Set[str] = set()

        for idx, pred in enumerate(self.predicates):
            validate_column_ref(pred.column, f"predicate[{idx}]")
            referenced_keys.update(pred.parameter_keys)

        for idx, h in enumerate(self.having):
            if h.aggregate.column_ref:
                validate_column_ref(h.aggregate.column_ref, f"having[{idx}]")
            referenced_keys.update(h.parameter_keys)

        for join in self.joins:
            for pred in join.additional_predicates:
                referenced_keys.update(pred.parameter_keys)

        registered_keys = set(self.parameter_registry.bindings.keys())

        unregistered = referenced_keys - registered_keys
        if unregistered:
            raise ValueError(f"Referenced parameter keys not registered in ParameterRegistry: {unregistered}")

        unused = registered_keys - referenced_keys
        if unused:
            raise ValueError(f"Unused registered parameter keys present in ParameterRegistry: {unused}")

        # 7. Strict Integer LIMIT Validation and Global 100-Row Ceiling
        if self.limit is not None:
            if type(self.limit) is not int or type(self.limit) is bool:
                raise ValueError("LIMIT must be a strict integer.")
            if self.limit < 1:
                raise ValueError("Invalid LIMIT: must be a positive integer >= 1")
            if self.limit > 100:
                raise ValueError("LIMIT exceeds maximum allowed global limit of 100")

        # 8. Strict Integer OFFSET Validation and MAX_OFFSET = 1000
        if self.offset is not None:
            if type(self.offset) is not int or type(self.offset) is bool:
                raise ValueError("OFFSET must be a strict integer.")
            if self.offset < 0:
                raise ValueError("OFFSET must be a non-negative integer >= 0")
            if self.offset > 1000:
                raise ValueError("Invalid OFFSET: exceeds maximum allowed offset of 1000")

        # 9. Deterministic Pagination Invariant for OFFSET > 0
        if self.offset is not None and self.offset > 0:
            if not self.order_by:
                raise ValueError(
                    "OFFSET > 0 requires deterministic ORDER BY containing a verified unique candidate key for the result grain."
                )

            # Map ordered column references: table -> set of column names ordered
            ordered_cols_by_table: Dict[str, Set[str]] = {}
            for ob in self.order_by:
                if isinstance(ob.target, ColumnRefIR):
                    t_alias = ob.target.table_alias.lower()
                    if t_alias in alias_to_table:
                        tbl = alias_to_table[t_alias]
                        ordered_cols_by_table.setdefault(tbl, set()).add(ob.target.column_name.lower())

            # Case A: Grouped query
            if self.group_by:
                group_cols_by_table: Dict[str, Set[str]] = {}
                for g in self.group_by:
                    t_alias = g.table_alias.lower()
                    if t_alias in alias_to_table:
                        tbl = alias_to_table[t_alias]
                        group_cols_by_table.setdefault(tbl, set()).add(g.column_name.lower())

                has_unique_group_order = True
                for tbl, g_cols in group_cols_by_table.items():
                    cand_keys = TABLE_CANDIDATE_KEYS.get(tbl, ())
                    ord_cols = ordered_cols_by_table.get(tbl, set())
                    table_has_unique_order = False
                    for ck in cand_keys:
                        ck_lower = {c.lower() for c in ck}
                        if ck_lower.issubset(g_cols) and ck_lower.issubset(ord_cols):
                            table_has_unique_order = True
                            break
                    if not table_has_unique_order:
                        has_unique_group_order = False
                        break

                if not has_unique_group_order:
                    raise ValueError(
                        "OFFSET > 0 on grouped query requires deterministic ORDER BY containing a verified unique candidate key from the GROUP BY dimensions."
                    )

            # Case B: Non-grouped query (source row grain)
            else:
                declared_tables = {r.table_name for r in self.relation_instances}
                if self.anchor_relation == "students":
                    grain_table = "students"
                elif self.anchor_relation == "student_marks":
                    grain_table = "student_marks"
                elif self.anchor_relation == "course_offerings" and "enrollments" in declared_tables:
                    grain_table = "enrollments"
                else:
                    grain_table = self.anchor_relation

                cand_keys = TABLE_CANDIDATE_KEYS.get(grain_table, ())
                ord_cols = ordered_cols_by_table.get(grain_table, set())

                has_unique_grain_order = False
                for ck in cand_keys:
                    ck_lower = {c.lower() for c in ck}
                    if ck_lower.issubset(ord_cols):
                        has_unique_grain_order = True
                        break

                if not has_unique_grain_order:
                    raise ValueError(
                        f"OFFSET > 0 requires deterministic ORDER BY containing a verified unique candidate key for result grain '{grain_table}'."
                    )

        # Validate order_by expressions
        for idx, ob in enumerate(self.order_by):
            if isinstance(ob.target, ColumnRefIR):
                validate_column_ref(ob.target, f"order_by[{idx}]")
            elif isinstance(ob.target, AggregateFunctionIR) and ob.target.column_ref:
                validate_column_ref(ob.target.column_ref, f"order_by[{idx}].{ob.target.function_name}")

        return self


# ---------------------------------------------------------------------------
# Logical QueryPlanner Service
# ---------------------------------------------------------------------------

class QueryPlanner:
    """Logical query compilation and planning engine for Phase 6.1."""

    def __init__(
        self,
        catalog: Optional[SchemaCatalog] = None,
        join_graph: Optional[JoinGraph] = None,
        context_engine: Optional[ContextMind] = None,
        intent_classifier: Optional[IntentClassifier] = None,
        schema_linker: Optional[SchemaLinker] = None,
    ) -> None:
        self.catalog = catalog or get_schema_catalog()
        self.join_graph = join_graph or get_join_graph()
        self.context_engine = context_engine or get_context_engine()
        self.intent_classifier = intent_classifier or get_intent_classifier()
        self.schema_linker = schema_linker or get_schema_linker()

    def plan(self, session_id: str, query: str) -> Union[QueryPlanIR, Dict[str, Any]]:
        """Compiles a user natural language query into a validated QueryPlanIR.

        Follows the strict 6-stage deterministic exit precedence:
        1. Context Anaphora Clarification Gate
        2. Out-of-Domain (OOD) Gate
        3. Disconnected / Unanswerable Entity Gate
        4. Genuine Schema Attribute Ambiguity Gate
        5. Intent Uncertainty Gate
        6. Plan Synthesis Gate
        """
        # --- Stage 1: Context Anaphora Clarification Gate ---
        context_res: ContextResolveResponse = self.context_engine.resolve_turn(
            session_id=session_id, query=query
        )
        if context_res.clarification_needed:
            # Check if this is a genuine anaphora failure (unresolved pronoun without prior context)
            # or an unresolvable query, versus a valid multi-table query.
            # In Phase 6 Text-to-SQL, multi-table queries (e.g. JOINs across departments and students)
            # and intra-sentential possessives ("courses with their instructors") are valid relational requests.
            is_genuine_anaphora_failure = False
            clarif_msg = context_res.clarification_message or ""
            if "no prior conversational context" in clarif_msg:
                # If the query contains explicit entities, the pronoun was intra-sentential.
                # Only treat as genuine failure if the query has no schema entities.
                schema_entities = [
                    t for t in self.catalog.tables
                    if re.search(r"\b" + (t[:-1] if t.endswith("s") else t) + r"\b", query, re.I)
                ]
                if not schema_entities and not any(k in query.lower() for k in ("student", "course", "instructor", "faculty", "department", "offering", "assessment")):
                    is_genuine_anaphora_failure = True
            elif "multiple entities" in clarif_msg or "multiple departments" in clarif_msg:
                # Multi-table queries are supported in Phase 6 Text-to-SQL
                is_genuine_anaphora_failure = False
            else:
                is_genuine_anaphora_failure = True

            if is_genuine_anaphora_failure:
                return {
                    "status": "clarification_needed",
                    "session_id": session_id,
                    "original_query": query,
                    "clarification_message": context_res.clarification_message,
                }

        resolved_query = context_res.resolved_query
        active_frame = context_res.active_frame

        # --- Stage 2: Intent Classification & Out-of-Domain Gate ---
        intent_res = self.intent_classifier.predict(query=resolved_query)
        if intent_res.get("ambiguity_reason") == "OUT_OF_DOMAIN":
            return {
                "status": "unsupported",
                "session_id": session_id,
                "original_query": query,
                "error_message": "Query lies outside the academic database domain.",
            }

        # --- Stage 3: Schema Linking & Blacklist Filtering ---
        schema_res = self.schema_linker.link_query(query=resolved_query)
        linked_tables = set(schema_res.get("linked_tables", []))

        unsupported_tokens = set(t.lower() for t in schema_res.get("unsupported_entities", []))
        blacklisted = {
            "hostel", "hostels", "cafeteria", "canteen", "library", "bus", "transport",
            "fee", "fees", "tuition", "sports", "gym", "scholarship", "parking",
            "wifi", "salary", "alumni", "mess", "dorm", "dormitory", "science hall"
        }
        query_text_lower = resolved_query.lower()
        found_blacklisted = [b for b in blacklisted if b in query_text_lower]
        if found_blacklisted or (unsupported_tokens & blacklisted):
            return {
                "status": "unsupported",
                "session_id": session_id,
                "original_query": query,
                "error_message": f"Query references unsupported domain entities: {sorted(found_blacklisted or (unsupported_tokens & blacklisted))}.",
            }

        # Disconnected / Unanswerable Entity Gate
        if unsupported_tokens:
            return {
                "status": "unsupported",
                "session_id": session_id,
                "original_query": query,
                "error_message": f"Query references unanswerable entities outside the relational schema: {sorted(unsupported_tokens)}.",
            }

        # --- Stage 4: Genuine Schema Attribute Ambiguity Gate ---
        if schema_res.get("is_ambiguous"):
            # Check if ambiguity can be contextually resolved (e.g. 'grades' when 'courses' requested maps to enrollments.final_grade)
            candidates = schema_res.get("ambiguous_candidates", [])
            unresolved_candidates = []
            for cand in candidates:
                token = cand.get("token", "").lower()
                if token in ("grade", "grades") and "course" in resolved_query.lower() and "assessment" not in resolved_query.lower():
                    # Contextually resolved to enrollments.final_grade
                    linked_tables.add("enrollments")
                    continue
                unresolved_candidates.append(cand)

            if unresolved_candidates:
                return {
                    "status": "clarification_needed",
                    "session_id": session_id,
                    "original_query": query,
                    "clarification_message": "Attribute matches multiple schema candidates. Please clarify.",
                    "candidates": unresolved_candidates,
                }

        # --- Stage 5: Intent Uncertainty Gate ---
        # Authoritative Phase 6.1 thresholds:
        # Confidence threshold: 0.40, Margin threshold: 0.05
        conf = float(intent_res.get("confidence", 0.0))
        margin = float(intent_res.get("margin", 0.0))
        top_intents = intent_res.get("top_intents", [])
        top_two_set = {top_intents[0][0], top_intents[1][0]} if len(top_intents) >= 2 else set()

        # Non-conflicting retrieval pair {GENERAL_QUERY, FILTER} does not require clarification
        is_retrieval_pair = (top_two_set == {"GENERAL_QUERY", "FILTER"})

        # Authoritative threshold: conf < 0.40 or margin < 0.05 (except for compatible retrieval pair or linked schema queries)
        is_ambiguous = False
        if not is_retrieval_pair:
            if conf < 0.30 or (conf < 0.40 and not schema_res.get("linked_tables")):
                is_ambiguous = True
            elif margin < 0.05:
                is_ambiguous = True

        if is_ambiguous:
            return {
                "status": "clarification_needed",
                "session_id": session_id,
                "original_query": query,
                "clarification_message": f"Intent uncertainty detected ({intent_res.get('ambiguity_reason', 'LOW_CONFIDENCE')}). Please clarify.",
                "top_intents": top_intents,
            }

        predicted_intent = intent_res.get("predicted_intent", "GENERAL_QUERY")

        # --- Stage 6: Logical Plan Synthesis ---
        builder = ParameterBuilder()

        # 6.1 Resolve Effective Limit
        raw_limit: Optional[int] = None
        limit_match = re.search(r"\b(?:top|first|limit)\s+(\d+)\b", resolved_query, re.IGNORECASE)
        if limit_match:
            raw_limit = int(limit_match.group(1))
        elif active_frame and active_frame.active_limit:
            raw_limit = active_frame.active_limit

        if raw_limit is not None:
            if raw_limit < 1:
                return {
                    "status": "error",
                    "session_id": session_id,
                    "original_query": query,
                    "error_message": "Invalid LIMIT: must be a positive integer >= 1",
                }
            effective_limit: int = min(raw_limit, 100)
        else:
            effective_limit = 100

        # Resolve Effective Offset
        effective_offset: Optional[int] = None
        offset_match = re.search(r"\boffset\s+(\d+)\b", resolved_query, re.IGNORECASE)
        if offset_match:
            raw_offset = int(offset_match.group(1))
            if raw_offset > 1000:
                return {
                    "status": "error",
                    "session_id": session_id,
                    "original_query": query,
                    "error_message": "Invalid OFFSET: exceeds maximum allowed offset of 1000",
                }
            effective_offset = raw_offset

        # 6.2 Identify Anchor Table and Related Tables
        linked_tables.update(schema_res.get("linked_tables", []))
        if active_frame and active_frame.active_entities:
            p_table = active_frame.active_entities.get("primary_table")
            if p_table and p_table in self.catalog.tables:
                linked_tables.add(p_table)

        if active_frame and active_frame.active_filters:
            for af in active_frame.active_filters:
                if "." in af.column:
                    t_filter = af.column.split(".", 1)[0]
                    if t_filter in self.catalog.tables:
                        linked_tables.add(t_filter)

        if not linked_tables:
            # Fallback based on query tokens or general student default
            if re.search(r"\b(?:instructor|faculty|professor)\b", resolved_query, re.IGNORECASE):
                linked_tables.add("instructors")
            elif re.search(r"\b(?:course|subject)\b", resolved_query, re.IGNORECASE):
                linked_tables.add("courses")
            elif re.search(r"\b(?:department)\b", resolved_query, re.IGNORECASE):
                linked_tables.add("departments")
            else:
                linked_tables.add("students")

        # Determine anchor table
        anchor = "students"
        is_student_target = bool(
            re.search(r"\b(?:show|list|find|get|display|select|give(?:\s+me)?|which|who(?:\s+are)?)\s+(?:all\s+)?(?:active\s+)?students\b", resolved_query, re.I)
            or re.search(r"\bstudents?\s+(?:with|who|whose|having|that|where)\b", resolved_query, re.I)
            or re.search(r"^\s*(?:top\s+\d+\s+)?(?:active\s+)?students\b", resolved_query, re.I)
        )

        is_student_marks_grain = bool(
            "student_marks" in linked_tables
            and not is_student_target
            and (
                re.search(r"\b(?:show|list|find|get|display|rank|top)\s+(?:all\s+)?(?:highest\s+|lowest\s+|top\s+)?(?:student\s+marks?|marks?|scores?)\b", resolved_query, re.I)
                or re.search(r"\b(?:student\s+marks?|marks?\s+obtained|marks?\s+scored|scores?\s+obtained)\b", resolved_query, re.I)
                or re.search(r"\b(?:marks?|scores?)\b", resolved_query, re.I)
            )
        )

        if is_student_marks_grain:
            anchor = "student_marks"
        elif re.search(r"\b(?:courses?\s+offered|course\s+offerings?|offerings?)\b", resolved_query, re.I):
            anchor = "course_offerings"
        elif re.search(r"\b(?:instructors?|faculty|professors?)\b", resolved_query, re.I) and not re.search(r"\bstudents?\b", resolved_query, re.I):
            anchor = "instructors"
        elif re.search(r"\b(?:courses?)\b", resolved_query, re.I) and not re.search(r"\bstudents?\b", resolved_query, re.I) and not re.search(r"\bofferings?\b", resolved_query, re.I):
            anchor = "courses"
        elif re.search(r"\b(?:assessments?)\b", resolved_query, re.I):
            anchor = "assessments"
        elif "departments" in linked_tables and len(linked_tables) == 1:
            anchor = "departments"
        elif is_student_target:
            anchor = "students"
        else:
            for candidate in ("students", "course_offerings", "courses", "instructors", "departments", "assessments", "enrollments", "terms", "student_marks"):
                if candidate in linked_tables:
                    anchor = candidate
                    break

        # Define canonical aliases
        canonical_alias_map = {
            "students": "s",
            "departments": "d",
            "instructors": "i",
            "courses": "c",
            "terms": "t",
            "course_offerings": "co",
            "enrollments": "e",
            "assessments": "a",
            "student_marks": "sm",
        }

        # Build relation instances
        relation_instances: List[RelationInstance] = []
        joins: List[JoinIR] = []

        # Find multi-table join if multiple tables linked
        if len(linked_tables) > 1:
            join_res = self.join_graph.resolve_multi_table_join(linked_tables, preferred_anchor=anchor)
            if not join_res.is_connected:
                return {
                    "status": "error",
                    "session_id": session_id,
                    "original_query": query,
                    "error_message": f"Tables {linked_tables} cannot be connected via schema relationships.",
                }
            tables_in_order = join_res.joined_tables
            if anchor not in join_res.joined_tables:
                anchor = join_res.anchor_table or anchor

            for idx, t_name in enumerate(tables_in_order):
                relation_instances.append(
                    RelationInstance(
                        instance_id=f"rel_{idx}",
                        table_name=t_name,
                        alias=canonical_alias_map.get(t_name, t_name[:2]),
                    )
                )

            # Map join steps to JoinIR with Anchor Entity Preservation Rule
            for step in join_res.join_steps:
                from_alias = canonical_alias_map.get(step.from_table, step.from_table[:2])
                to_alias = canonical_alias_map.get(step.to_table, step.to_table[:2])
                parts = step.condition.split(" = ")
                from_col = parts[0].split(".")[1]
                to_col = parts[1].split(".")[1]

                # Determine join type: LEFT JOIN for dependent child entities if anchor is parent
                j_type: Literal["INNER", "LEFT"] = "INNER"
                if anchor == "course_offerings" and (step.to_table in ("enrollments", "students") or step.from_table in ("enrollments", "students")):
                    j_type = "LEFT"
                elif anchor == "departments" and step.to_table in ("courses", "students", "instructors"):
                    j_type = "LEFT"

                joins.append(
                    JoinIR(
                        left_alias=from_alias,
                        left_column=from_col,
                        right_alias=to_alias,
                        right_column=to_col,
                        join_type=j_type,
                    )
                )
        else:
            relation_instances.append(
                RelationInstance(
                    instance_id="rel_0",
                    table_name=anchor,
                    alias=canonical_alias_map.get(anchor, anchor[:2]),
                )
            )

        anchor_alias = canonical_alias_map.get(anchor, anchor[:2])

        # 6.3 Build Predicates from Linked Values and Active Filters
        predicates: List[PredicateIR] = []
        for val in schema_res.get("linked_values", []):
            t_name = val["table_name"]
            c_name = val["column_name"]
            raw_v = val["value"]
            col_meta = self.catalog.get_column(t_name, c_name)
            col_t = col_meta.data_type if col_meta else "VARCHAR"
            t_alias = canonical_alias_map.get(t_name, t_name[:2])

            param_key = builder.register(raw_v, col_t)
            predicates.append(
                PredicateIR(
                    column=ColumnRefIR(table_alias=t_alias, column_name=c_name),
                    operator="=",
                    parameter_keys=(param_key,),
                    is_negated=False,
                )
            )

        # Merge active filters from context frame if present
        if active_frame and active_frame.active_filters:
            for af in active_frame.active_filters:
                if "." in af.column:
                    f_table, actual_col = af.column.split(".", 1)
                else:
                    actual_col = af.column
                    f_table = anchor
                    for t_n in linked_tables:
                        if self.catalog.get_column(t_n, actual_col):
                            f_table = t_n
                            break
                f_alias = canonical_alias_map.get(f_table, f_table[:2])
                col_meta = self.catalog.get_column(f_table, actual_col)
                if not col_meta:
                    continue
                col_t = col_meta.data_type

                # Avoid duplicate filter columns on the same alias
                if any(p.column.table_alias == f_alias and p.column.column_name == actual_col for p in predicates):
                    continue

                param_key = builder.register(af.value, col_t)
                predicates.append(
                    PredicateIR(
                        column=ColumnRefIR(table_alias=f_alias, column_name=actual_col),
                        operator=af.operator if af.operator in ("=", "<", ">", "<=", ">=") else "=",
                        parameter_keys=(param_key,),
                        is_negated=False,
                    )
                )

        # Extra explicit numeric/status predicates from query text
        marks_gt = re.search(r"\b(?:marks?|scores?)\b.*?\b(?:above|>|greater\s+than|exceeds?|are\s+above)\s+([0-9.]+)\b", resolved_query, re.I)
        if marks_gt and "student_marks" in linked_tables:
            m_val = float(marks_gt.group(1))
            sm_alias = canonical_alias_map.get("student_marks", "sm")
            if not any(p.column.table_alias == sm_alias and p.column.column_name == "marks_obtained" for p in predicates):
                pk = builder.register(m_val, "FLOAT")
                predicates.append(
                    PredicateIR(
                        column=ColumnRefIR(table_alias=sm_alias, column_name="marks_obtained"),
                        operator=">",
                        parameter_keys=(pk,),
                        is_negated=False,
                    )
                )

        cgpa_gt = re.search(r"\b(?:cgpa|gpa)\s*(?:is\s+)?(?:greater\s+than|above|>)\s*([0-9.]+)\b", resolved_query, re.I)
        if not cgpa_gt and not re.search(r"\b(?:marks?|scores?)\b", resolved_query, re.I):
            cgpa_gt = re.search(r"\b(?:greater\s+than|above|>)\s+([0-9.]+)\b", resolved_query, re.I)
        if cgpa_gt and anchor == "students":
            cgpa_val = float(cgpa_gt.group(1))
            s_alias = canonical_alias_map.get("students", "s")
            if not any(p.column.table_alias == s_alias and p.column.column_name == "cgpa" for p in predicates):
                pk = builder.register(cgpa_val, "FLOAT")
                predicates.append(
                    PredicateIR(
                        column=ColumnRefIR(table_alias=s_alias, column_name="cgpa"),
                        operator=">",
                        parameter_keys=(pk,),
                        is_negated=False,
                    )
                )

        if re.search(r"\bprobation\b", resolved_query, re.I) and anchor == "students":
            s_alias = canonical_alias_map.get("students", "s")
            if not any(p.column.table_alias == s_alias and p.column.column_name == "academic_status" for p in predicates):
                pk = builder.register("Probation", "VARCHAR")
                predicates.append(
                    PredicateIR(
                        column=ColumnRefIR(table_alias=s_alias, column_name="academic_status"),
                        operator="=",
                        parameter_keys=(pk,),
                        is_negated=False,
                    )
                )

        # 6.4 Build Projections & Grouping according to Intent
        projections: List[ProjectionIR] = []
        group_by: List[ColumnRefIR] = []
        order_by: List[OrderByIR] = []

        is_group_by_dept = bool(re.search(r"\b(?:by|per|each|across)\s+departments?\b", resolved_query, re.IGNORECASE))

        if predicted_intent == "COMPARISON" or (predicted_intent == "AGGREGATE" and is_group_by_dept):
            d_alias = canonical_alias_map.get("departments", "d")
            projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=d_alias, column_name="code"), alias="department_code"))
            projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=d_alias, column_name="name"), alias="department_name"))

            if re.search(r"\b(?:cgpa|gpa)\b", resolved_query, re.I):
                s_alias = canonical_alias_map.get("students", "s")
                projections.append(
                    ProjectionIR(
                        expression_node=AggregateFunctionIR(
                            function_name="AVG",
                            column_ref=ColumnRefIR(table_alias=s_alias, column_name="cgpa"),
                            round_digits=2,
                        ),
                        alias="average_cgpa",
                    )
                )
                order_by.append(
                    OrderByIR(
                        target=AggregateFunctionIR(
                            function_name="AVG",
                            column_ref=ColumnRefIR(table_alias=s_alias, column_name="cgpa"),
                        ),
                        direction="DESC",
                    )
                )
            elif re.search(r"\b(?:total credits|sum)\b", resolved_query, re.I):
                c_alias = canonical_alias_map.get("courses", "c")
                projections.append(
                    ProjectionIR(
                        expression_node=AggregateFunctionIR(
                            function_name="SUM",
                            column_ref=ColumnRefIR(table_alias=c_alias, column_name="credits"),
                        ),
                        alias="total_credits",
                    )
                )
            else:
                target_table = "courses" if "courses" in linked_tables else anchor
                t_alias = canonical_alias_map.get(target_table, target_table[:2])
                pk_c = self.catalog.tables[target_table].primary_keys[0] if self.catalog.tables[target_table].primary_keys else "id"
                projections.append(
                    ProjectionIR(
                        expression_node=AggregateFunctionIR(
                            function_name="COUNT",
                            column_ref=ColumnRefIR(table_alias=t_alias, column_name=pk_c),
                        ),
                        alias=f"{target_table}_count",
                    )
                )

            group_by.append(ColumnRefIR(table_alias=d_alias, column_name="department_id"))
            group_by.append(ColumnRefIR(table_alias=d_alias, column_name="code"))
            group_by.append(ColumnRefIR(table_alias=d_alias, column_name="name"))
            order_by.append(OrderByIR(target=ColumnRefIR(table_alias=d_alias, column_name="code"), direction="ASC"))

        elif predicted_intent == "TREND":
            t_alias = canonical_alias_map.get("terms", "t")
            e_alias = canonical_alias_map.get("enrollments", "e")
            projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=t_alias, column_name="academic_year")))
            projections.append(
                ProjectionIR(
                    expression_node=AggregateFunctionIR(
                        function_name="COUNT",
                        column_ref=ColumnRefIR(table_alias=e_alias, column_name="enrollment_id"),
                    ),
                    alias="student_count",
                )
            )
            group_by.append(ColumnRefIR(table_alias=t_alias, column_name="academic_year"))
            order_by.append(OrderByIR(target=ColumnRefIR(table_alias=t_alias, column_name="academic_year"), direction="ASC"))

        elif predicted_intent == "AGGREGATE":
            # Scalar aggregate (e.g. How many students in CS)
            pk_col = self.catalog.tables[anchor].primary_keys[0] if self.catalog.tables[anchor].primary_keys else "id"
            projections.append(
                ProjectionIR(
                    expression_node=AggregateFunctionIR(
                        function_name="COUNT",
                        column_ref=ColumnRefIR(table_alias=anchor_alias, column_name=pk_col),
                    ),
                    alias=f"{anchor}_count",
                )
            )

        else:
            # Non-aggregate standard entity projections
            if anchor == "students":
                if "courses" in linked_tables and "enrollments" in linked_tables:
                    # Example 14 full projection
                    s_alias = canonical_alias_map.get("students", "s")
                    c_alias = canonical_alias_map.get("courses", "c")
                    e_alias = canonical_alias_map.get("enrollments", "e")
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=s_alias, column_name="roll_number")))
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=s_alias, column_name="first_name")))
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=s_alias, column_name="last_name")))
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=c_alias, column_name="course_code")))
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=c_alias, column_name="course_name")))
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=e_alias, column_name="final_grade")))
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=e_alias, column_name="attendance_percentage")))
                else:
                    for col in ("roll_number", "first_name", "last_name", "cgpa", "current_semester", "academic_status"):
                        projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name=col)))
            elif anchor == "courses":
                for col in ("course_code", "course_name", "credits"):
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias="c", column_name=col)))
            elif anchor == "instructors":
                for col in ("first_name", "last_name", "designation", "joining_year"):
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias="i", column_name=col)))
            elif anchor == "course_offerings":
                if "instructors" in linked_tables and "students" in linked_tables:
                    # Example 3 full projection
                    c_alias = canonical_alias_map.get("courses", "c")
                    i_alias = canonical_alias_map.get("instructors", "i")
                    s_alias = canonical_alias_map.get("students", "s")
                    e_alias = canonical_alias_map.get("enrollments", "e")
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=c_alias, column_name="course_code")))
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=c_alias, column_name="course_name")))
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=i_alias, column_name="first_name")))
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=i_alias, column_name="last_name")))
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=s_alias, column_name="roll_number")))
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=s_alias, column_name="first_name")))
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=s_alias, column_name="last_name")))
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=e_alias, column_name="enrollment_status")))
                else:
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias="co", column_name="section")))
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias="co", column_name="classroom")))
            elif anchor == "departments":
                projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias="d", column_name="code")))
                projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias="d", column_name="name")))
            elif anchor == "assessments":
                for col in ("title", "assessment_type", "max_marks", "weightage_percent"):
                    if self.catalog.get_column("assessments", col):
                        projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias="a", column_name=col)))
            elif anchor == "student_marks":
                sm_alias = canonical_alias_map.get("student_marks", "sm")
                projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=sm_alias, column_name="marks_obtained")))
                if "students" in linked_tables:
                    s_alias = canonical_alias_map.get("students", "s")
                    projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=s_alias, column_name="roll_number")))
            else:
                pk_col = self.catalog.tables[anchor].primary_keys[0]
                projections.append(ProjectionIR(expression_node=ColumnRefIR(table_alias=anchor_alias, column_name=pk_col)))

        # 6.5 Deterministic Result-Grain Tie-Breaker Ordering
        if predicted_intent == "RANKING":
            if re.search(r"\b(?:cgpa|gpa)\b", resolved_query, re.IGNORECASE) and anchor == "students":
                order_by.append(OrderByIR(target=ColumnRefIR(table_alias="s", column_name="cgpa"), direction="DESC"))
            elif re.search(r"\b(?:attendance)\b", resolved_query, re.IGNORECASE) and "enrollments" in linked_tables:
                e_alias = canonical_alias_map.get("enrollments", "e")
                order_by.append(OrderByIR(target=ColumnRefIR(table_alias=e_alias, column_name="attendance_percentage"), direction="DESC"))
            elif re.search(r"\b(?:marks?|scores?)\b", resolved_query, re.IGNORECASE) and "student_marks" in linked_tables:
                sm_alias = canonical_alias_map.get("student_marks", "sm")
                order_by.append(OrderByIR(target=ColumnRefIR(table_alias=sm_alias, column_name="marks_obtained"), direction="DESC"))

        # Determine tie-breaker ordering based on result grain
        if group_by:
            # Result grain is determined exclusively by grouping dimensions.
            # Never append anchor source-row keys (e.g. students.roll_number) to grouped queries.
            grouped_cols_by_table: Dict[str, Set[str]] = {}
            alias_to_table_map = {v: k for k, v in canonical_alias_map.items()}
            for gb in group_by:
                t_name = alias_to_table_map.get(gb.table_alias)
                if t_name:
                    grouped_cols_by_table.setdefault(t_name, set()).add(gb.column_name.lower())

            all_grouped_tables_have_keys = True
            for t_name, g_cols in grouped_cols_by_table.items():
                cand_keys = TABLE_CANDIDATE_KEYS.get(t_name, ())
                t_alias = canonical_alias_map.get(t_name, t_name[:2])
                table_key_found = False
                for ck in cand_keys:
                    if set(c.lower() for c in ck).issubset(g_cols):
                        table_key_found = True
                        for ck_col in ck:
                            if not any(
                                isinstance(ob.target, ColumnRefIR)
                                and ob.target.table_alias.lower() == t_alias.lower()
                                and ob.target.column_name.lower() == ck_col.lower()
                                for ob in order_by
                            ):
                                order_by.append(
                                    OrderByIR(
                                        target=ColumnRefIR(table_alias=t_alias, column_name=ck_col),
                                        direction="ASC",
                                    )
                                )
                        break
                if not table_key_found:
                    all_grouped_tables_have_keys = False

            if not all_grouped_tables_have_keys and effective_offset is not None and effective_offset > 0:
                return {
                    "status": "clarification_needed",
                    "session_id": session_id,
                    "original_query": query,
                    "clarification_message": "A safe deterministic ordering cannot be established for this grouped query without altering grouping semantics. Please clarify.",
                }

        elif predicted_intent == "AGGREGATE":
            # Scalar aggregate produces exactly 1 row; no tie-breaker ordering needed
            pass

        else:
            # Non-grouped queries: use canonical grain tie-breaker
            grain_target = (
                "student_marks"
                if ("student_marks" in linked_tables and anchor == "student_marks")
                else ("enrollments" if ("enrollments" in linked_tables and anchor == "course_offerings") else anchor)
            )
            tie_breakers = CANONICAL_GRAIN_TIE_BREAKERS.get(grain_target, ())
            tb_alias = canonical_alias_map.get(grain_target, anchor_alias)
            for tb_col, tb_dir in tie_breakers:
                if not any(
                    isinstance(ob.target, ColumnRefIR)
                    and ob.target.table_alias.lower() == tb_alias.lower()
                    and ob.target.column_name.lower() == tb_col.lower()
                    for ob in order_by
                ):
                    order_by.append(
                        OrderByIR(
                            target=ColumnRefIR(table_alias=tb_alias, column_name=tb_col),
                            direction=tb_dir,
                        )
                    )

        registry = builder.build()

        return QueryPlanIR(
            intent=predicted_intent,
            anchor_relation=anchor,
            relation_instances=tuple(relation_instances),
            projections=tuple(projections),
            joins=tuple(joins),
            predicates=tuple(predicates),
            group_by=tuple(group_by),
            having=(),
            order_by=tuple(order_by),
            limit=effective_limit,
            offset=effective_offset,
            parameter_registry=registry,
        )


_cached_planner: Optional[QueryPlanner] = None


def get_query_planner() -> QueryPlanner:
    """Returns the cached singleton QueryPlanner instance."""
    global _cached_planner
    if _cached_planner is None:
        _cached_planner = QueryPlanner()
    return _cached_planner
