"""SQLGenerator for QueryMind AI 2.0 (Phase 6.2).

Deterministic AST-backed SQL compiler translating validated QueryPlanIR instances
into parameterized SQLite queries and immutable parameter bindings using SQLGlot 30.30.0.
"""

from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple
from pydantic import BaseModel, ConfigDict, model_serializer
import sqlglot
from sqlglot import exp

from app.services.parameter_registry import (
    PARAMETER_KEY_PATTERN,
    ParameterRegistry,
    SupportedScalar,
)
from app.services.query_plan_ir import (
    AggregateFunctionIR,
    ColumnRefIR,
    HavingIR,
    JoinIR,
    PredicateIR,
    ProjectionIR,
    QueryPlanIR,
)


class GeneratedSQL(BaseModel):
    """Immutable result container representing compiled SQL and parameter bindings.

    Implements controlled public-interface immutability:
    - Top-level attributes cannot be reassigned (ConfigDict(frozen=True)).
    - Parameters and parameter types are exposed via read-only MappingProxyType views.
    - Public access to the .ast property returns an isolated defensive copy (via .copy()),
      preventing downstream callers from mutating internal AST state.
    - Private underscore-prefixed attributes store immutable internal tuples.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    sql: str
    _parameters_tuple: Tuple[Tuple[str, SupportedScalar], ...] = ()
    _types_tuple: Tuple[Tuple[str, str], ...] = ()
    _ast: exp.Select

    def __init__(
        self,
        sql: str,
        parameters: Dict[str, SupportedScalar],
        parameter_types: Dict[str, str],
        ast: exp.Select,
        **data: Any,
    ) -> None:
        super().__init__(sql=sql, **data)
        object.__setattr__(self, "_parameters_tuple", tuple(sorted(parameters.items())))
        object.__setattr__(self, "_types_tuple", tuple(sorted(parameter_types.items())))
        object.__setattr__(self, "_ast", ast.copy())

    @property
    def parameters(self) -> Mapping[str, SupportedScalar]:
        """Read-only mapping proxy of bound query parameters."""
        return MappingProxyType(dict(self._parameters_tuple))

    @property
    def parameter_types(self) -> Mapping[str, str]:
        """Read-only mapping proxy of parameter catalog data types."""
        return MappingProxyType(dict(self._types_tuple))

    @property
    def ast(self) -> exp.Select:
        """Returns a defensive deep copy of the underlying SQLGlot AST node."""
        return self._ast.copy()

    @model_serializer
    def ser_model(self) -> Dict[str, Any]:
        """Pydantic v2 JSON serialization compatibility."""
        return {
            "sql": self.sql,
            "parameters": dict(self._parameters_tuple),
            "parameter_types": dict(self._types_tuple),
        }


class SQLGenerator:
    """Deterministic AST-backed SQL compiler translating QueryPlanIR into parameterized SQLite queries."""

    def __init__(self, dialect: str = "sqlite") -> None:
        self.dialect = dialect

    def generate(self, plan: QueryPlanIR, *, probe_pagination: bool = False) -> GeneratedSQL:
        """Compiles a validated QueryPlanIR into a deterministic GeneratedSQL instance.

        Args:
            plan: Statically validated QueryPlanIR.
            probe_pagination: If True, adds 1 to effective limit for single-roundtrip pagination probing.

        Returns:
            GeneratedSQL container with formatted SQL, parameter mappings, and defensive AST copy.
        """
        if not isinstance(plan, QueryPlanIR):
            raise TypeError(f"Expected QueryPlanIR instance, got {type(plan).__name__}")

        # 1. Parameter Accounting & Validation across WHERE, HAVING, and JOIN ON
        referenced_keys: Set[str] = set()
        for pred in plan.predicates:
            referenced_keys.update(pred.parameter_keys)
        for h in plan.having:
            referenced_keys.update(h.parameter_keys)
        for j in plan.joins:
            for p in j.additional_predicates:
                referenced_keys.update(p.parameter_keys)

        for k in referenced_keys:
            if not PARAMETER_KEY_PATTERN.match(k):
                raise ValueError(f"Invalid parameter key format: '{k}'. Must match pattern '^param_\\d+$'.")

        registry_keys = set(plan.parameter_registry.bindings.keys())

        missing = referenced_keys - registry_keys
        if missing:
            raise ValueError(f"Referenced parameter keys missing from ParameterRegistry: {sorted(missing)}")

        unused = registry_keys - referenced_keys
        if unused:
            raise ValueError(f"ParameterRegistry contains unused parameter keys: {sorted(unused)}")

        # 2. Build SELECT projections
        select_exprs = [self._compile_projection(p) for p in plan.projections]

        # 3. Build FROM clause
        if not plan.relation_instances:
            raise ValueError("QueryPlanIR must contain at least one relation instance.")
        from_rel = plan.relation_instances[0]
        from_table = exp.Table(
            this=exp.to_identifier(from_rel.table_name),
            alias=exp.TableAlias(this=exp.to_identifier(from_rel.alias)),
        )

        query = exp.Select().select(*select_exprs).from_(from_table)

        # 4. Build JOIN clauses
        alias_to_table = {r.alias: r.table_name for r in plan.relation_instances}
        if plan.joins:
            join_nodes = []
            for j in plan.joins:
                r_table = alias_to_table.get(j.right_alias)
                if not r_table:
                    raise ValueError(f"Unknown right alias '{j.right_alias}' in joins.")
                join_table = exp.Table(
                    this=exp.to_identifier(r_table),
                    alias=exp.TableAlias(this=exp.to_identifier(j.right_alias)),
                )
                on_cond = exp.EQ(
                    this=exp.column(j.left_column, table=j.left_alias),
                    expression=exp.column(j.right_column, table=j.right_alias),
                )
                if j.additional_predicates:
                    for add_p in j.additional_predicates:
                        on_cond = exp.and_(on_cond, self._compile_predicate(add_p))
                join_nodes.append(exp.Join(this=join_table, on=on_cond, kind=j.join_type))
            query.set("joins", join_nodes)

        # 5. Build WHERE clause
        if plan.predicates:
            where_conds = [self._compile_predicate(p) for p in plan.predicates]
            if len(where_conds) == 1:
                query.set("where", exp.Where(this=where_conds[0]))
            else:
                query.set("where", exp.Where(this=exp.and_(*where_conds)))

        # 6. Build GROUP BY clause
        if plan.group_by:
            group_exprs = [
                exp.column(g.column_name, table=g.table_alias)
                for g in plan.group_by
            ]
            query.set("group", exp.Group(expressions=group_exprs))

        # 7. Build HAVING clause
        if plan.having:
            having_conds = [self._compile_having(h) for h in plan.having]
            if len(having_conds) == 1:
                query.set("having", exp.Having(this=having_conds[0]))
            else:
                query.set("having", exp.Having(this=exp.and_(*having_conds)))

        # 8. Build ORDER BY clause
        if plan.order_by:
            order_exprs = []
            for ob in plan.order_by:
                if isinstance(ob.target, ColumnRefIR):
                    target_expr = exp.column(
                        ob.target.column_name,
                        table=ob.target.table_alias,
                    )
                elif isinstance(ob.target, AggregateFunctionIR):
                    target_expr = self._compile_aggregate(ob.target)
                else:
                    raise TypeError(f"Unsupported OrderBy target type: {type(ob.target).__name__}")

                is_desc = (ob.direction == "DESC")
                order_exprs.append(
                    exp.Ordered(
                        this=target_expr,
                        desc=is_desc,
                        nulls_first=not is_desc,
                    )
                )
            query.set("order", exp.Order(expressions=order_exprs))

        # 9. Build LIMIT and OFFSET (Preserving Phase 6.0 Contract)
        if plan.limit is not None and plan.limit <= 0:
            raise ValueError(f"Invalid LIMIT: must be a positive integer >= 1, got {plan.limit}")

        base_limit = min(plan.limit, 100) if plan.limit is not None else 100
        effective_limit = base_limit + 1 if probe_pagination else base_limit

        query.set("limit", exp.Limit(expression=exp.Literal.number(effective_limit)))

        if plan.offset is not None and plan.offset > 0:
            query.set("offset", exp.Offset(expression=exp.Literal.number(plan.offset)))

        # 10. Post-Compilation AST Placeholder Parity Audit
        ast_placeholders = {p.this for p in query.find_all(exp.Placeholder)}
        if ast_placeholders != registry_keys:
            raise ValueError(
                f"AST placeholder set {ast_placeholders} does not match parameter registry keys {registry_keys}."
            )

        sql_str = query.sql(dialect=self.dialect)

        return GeneratedSQL(
            sql=sql_str,
            parameters=dict(plan.parameter_registry.bindings),
            parameter_types=dict(plan.parameter_registry.types),
            ast=query,
        )

    def _compile_projection(self, proj: ProjectionIR) -> exp.Expression:
        if isinstance(proj.expression_node, ColumnRefIR):
            expr_node = exp.column(
                proj.expression_node.column_name,
                table=proj.expression_node.table_alias,
            )
        elif isinstance(proj.expression_node, AggregateFunctionIR):
            expr_node = self._compile_aggregate(proj.expression_node)
        else:
            raise TypeError(f"Unsupported projection expression node: {type(proj.expression_node).__name__}")

        if proj.alias:
            return exp.alias_(expr_node, alias=exp.to_identifier(proj.alias))
        return expr_node

    def _compile_aggregate(self, agg: AggregateFunctionIR) -> exp.Expression:
        func = agg.function_name
        if agg.column_ref is None:
            arg = exp.Star()
        else:
            col = exp.column(
                agg.column_ref.column_name,
                table=agg.column_ref.table_alias,
            )
            arg = exp.Distinct(expressions=[col]) if agg.is_distinct else col

        if func == "COUNT":
            node = exp.Count(this=arg)
        elif func == "AVG":
            node = exp.Avg(this=arg)
        elif func == "SUM":
            node = exp.Sum(this=arg)
        elif func == "MIN":
            node = exp.Min(this=arg)
        elif func == "MAX":
            node = exp.Max(this=arg)
        else:
            raise ValueError(f"Unsupported aggregate function: '{func}'")

        if agg.round_digits is not None:
            node = exp.Round(this=node, decimals=exp.Literal.number(agg.round_digits))

        return node

    def _compile_predicate(self, pred: PredicateIR) -> exp.Expression:
        col = exp.column(
            pred.column.column_name,
            table=pred.column.table_alias,
        )
        return self._compile_condition(col, pred.operator, pred.parameter_keys, pred.is_negated)

    def _compile_having(self, having: HavingIR) -> exp.Expression:
        agg = self._compile_aggregate(having.aggregate)
        return self._compile_condition(agg, having.operator, having.parameter_keys, having.is_negated)

    def _compile_condition(
        self,
        target_expr: exp.Expression,
        op: str,
        parameter_keys: Tuple[str, ...],
        is_negated: bool,
    ) -> exp.Expression:
        if op == "=":
            pk = exp.Placeholder(this=parameter_keys[0])
            return exp.NEQ(this=target_expr, expression=pk) if is_negated else exp.EQ(this=target_expr, expression=pk)
        elif op == "<":
            if is_negated:
                raise ValueError("Negated ordered comparison '<' is prohibited; use complementary '>=' instead.")
            return exp.LT(this=target_expr, expression=exp.Placeholder(this=parameter_keys[0]))
        elif op == ">":
            if is_negated:
                raise ValueError("Negated ordered comparison '>' is prohibited; use complementary '<=' instead.")
            return exp.GT(this=target_expr, expression=exp.Placeholder(this=parameter_keys[0]))
        elif op == "<=":
            if is_negated:
                raise ValueError("Negated ordered comparison '<=' is prohibited; use complementary '>' instead.")
            return exp.LTE(this=target_expr, expression=exp.Placeholder(this=parameter_keys[0]))
        elif op == ">=":
            if is_negated:
                raise ValueError("Negated ordered comparison '>=' is prohibited; use complementary '<' instead.")
            return exp.GTE(this=target_expr, expression=exp.Placeholder(this=parameter_keys[0]))
        elif op == "LIKE":
            cond = exp.Like(this=target_expr, expression=exp.Placeholder(this=parameter_keys[0]))
            return exp.not_(cond) if is_negated else cond
        elif op == "ILIKE":
            cond = exp.ILike(this=target_expr, expression=exp.Placeholder(this=parameter_keys[0]))
            return exp.not_(cond) if is_negated else cond
        elif op == "IN":
            pks = [exp.Placeholder(this=k) for k in parameter_keys]
            cond = exp.In(this=target_expr, expressions=pks)
            return exp.not_(cond) if is_negated else cond
        elif op == "BETWEEN":
            cond = exp.Between(
                this=target_expr,
                low=exp.Placeholder(this=parameter_keys[0]),
                high=exp.Placeholder(this=parameter_keys[1]),
            )
            return exp.not_(cond) if is_negated else cond
        elif op == "IS NULL":
            cond = exp.Is(this=target_expr, expression=exp.null())
            return exp.not_(cond) if is_negated else cond
        else:
            raise ValueError(f"Unsupported base operator: '{op}'")


_generator_instance: Optional[SQLGenerator] = None


def get_sql_generator() -> SQLGenerator:
    """Singleton accessor for SQLGenerator."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = SQLGenerator()
    return _generator_instance
