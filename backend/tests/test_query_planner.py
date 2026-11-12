"""Unit & Integration Test Suite for Phase 6.1 (QueryPlanner & QueryPlanIR).

Tests:
- Tier 1: ParameterRegistry & QueryPlanIR cross-field invariants (14 tests).
- Tier 2: QueryPlanner integration across intents, precedence, and representative queries (11 tests).
"""

import math
import uuid
import pytest
from pydantic import ValidationError

from app.services.parameter_registry import (
    ParameterBuilder,
    ParameterRegistry,
    SupportedScalar,
)
from app.services.query_plan_ir import (
    ColumnRefIR,
    AggregateFunctionIR,
    ProjectionIR,
    PredicateIR,
    HavingIR,
    OrderByIR,
    RelationInstance,
    JoinIR,
    QueryPlanIR,
    QueryPlanner,
    get_query_planner,
)
from app.services.context_engine import get_context_engine


# ===========================================================================
# Tier 1: Unit Tests (ParameterRegistry & Structured IR Validation)
# ===========================================================================

class TestParameterRegistryAndIRValidation:
    """Tier 1 Unit tests for parameter immutability and IR invariants."""

    def test_parameter_builder_scalar_registration(self):
        """Test 1: ParameterBuilder successfully registers primitive immutable scalars."""
        builder = ParameterBuilder()
        k0 = builder.register("Active", "VARCHAR")
        k1 = builder.register(6, "INTEGER")
        k2 = builder.register(3.98, "FLOAT")
        k3 = builder.register(True, "BOOLEAN")
        k4 = builder.register(None, "VARCHAR")

        assert k0 == "param_0"
        assert k1 == "param_1"
        assert k2 == "param_2"
        assert k3 == "param_3"
        assert k4 == "param_4"

        reg = builder.build()
        assert len(reg) == 5
        assert reg.get_binding("param_0") == "Active"
        assert reg.get_binding("param_1") == 6
        assert reg.get_binding("param_2") == 3.98
        assert reg.get_binding("param_3") is True
        assert reg.get_binding("param_4") is None

    def test_parameter_builder_rejects_mutable_containers(self):
        """Test 2: ParameterBuilder rejects mutable containers (list, dict, set)."""
        builder = ParameterBuilder()
        with pytest.raises(TypeError, match="must be an immutable scalar"):
            builder.register(["Active", "Probation"], "VARCHAR")

        with pytest.raises(TypeError, match="must be an immutable scalar"):
            builder.register({"status": "Active"}, "VARCHAR")

        with pytest.raises(TypeError, match="must be an immutable scalar"):
            builder.register({"Active", "Inactive"}, "VARCHAR")

    def test_parameter_registry_mappingproxy_immutability(self):
        """Test 3: ParameterRegistry.bindings rejects in-place item mutation."""
        builder = ParameterBuilder()
        builder.register("Active", "VARCHAR")
        reg = builder.build()

        with pytest.raises(TypeError, match="'mappingproxy' object does not support item assignment"):
            reg.bindings["param_0"] = "Hacked"

        with pytest.raises(TypeError, match="'mappingproxy' object does not support item assignment"):
            reg.types["param_0"] = "TEXT"

    def test_parameter_registry_pydantic_serialization(self):
        """Test 4: ParameterRegistry supports model_dump, model_dump_json, and round-tripping."""
        builder = ParameterBuilder()
        builder.register("Active", "VARCHAR")
        builder.register(6, "INTEGER")
        reg = builder.build()

        dumped = reg.model_dump()
        assert dumped == {
            "bindings": {"param_0": "Active", "param_1": 6},
            "types": {"param_0": "VARCHAR", "param_1": "INTEGER"},
        }

        json_str = reg.model_dump_json()
        assert '"param_0":"Active"' in json_str

        # Round-trip deserialization
        reg2 = ParameterRegistry(**dumped)
        assert reg2.get_binding("param_0") == "Active"
        assert reg2.get_binding("param_1") == 6
        assert isinstance(reg2.bindings, type(reg.bindings))

    def test_parameter_registry_non_finite_float_rejection(self):
        """Test 5: ParameterRegistry rejects NaN, +Infinity, and -Infinity."""
        builder = ParameterBuilder()
        with pytest.raises(ValueError, match="NaN and Infinity are prohibited"):
            builder.register(float("nan"), "FLOAT")

        with pytest.raises(ValueError, match="NaN and Infinity are prohibited"):
            builder.register(float("inf"), "FLOAT")

        with pytest.raises(ValueError, match="NaN and Infinity are prohibited"):
            builder.register(float("-inf"), "FLOAT")

    def test_parameter_registry_boolean_rejection_on_numeric_types(self):
        """Test 6: ParameterRegistry rejects booleans for INTEGER and FLOAT column types."""
        builder = ParameterBuilder()
        with pytest.raises(TypeError, match="expected INTEGER for column type"):
            builder.register(True, "INTEGER")

        with pytest.raises(TypeError, match="expected FLOAT/numeric for column type"):
            builder.register(False, "FLOAT")

    def test_query_plan_ir_sequence_immutability(self):
        """Test 7: QueryPlanIR sequence attributes (tuples) cannot be mutated in place."""
        builder = ParameterBuilder()
        k0 = builder.register("Active", "VARCHAR")
        reg = builder.build()

        plan = QueryPlanIR(
            intent="FILTER",
            anchor_relation="students",
            relation_instances=(
                RelationInstance(instance_id="rel_0", table_name="students", alias="s"),
            ),
            projections=(
                ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),
            ),
            predicates=(
                PredicateIR(
                    column=ColumnRefIR(table_alias="s", column_name="academic_status"),
                    operator="=",
                    parameter_keys=(k0,),
                    is_negated=False,
                ),
            ),
            parameter_registry=reg,
        )

        with pytest.raises(AttributeError):
            plan.relation_instances.append(RelationInstance(instance_id="rel_1", table_name="courses", alias="c"))

        with pytest.raises(TypeError):
            plan.projections[0] = ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="first_name"))

        with pytest.raises(ValidationError):
            plan.limit = 50

    def test_ir_validation_duplicate_alias_rejection(self):
        """Test 8: QueryPlanIR rejects duplicate relation aliases."""
        builder = ParameterBuilder()
        reg = builder.build()

        with pytest.raises(ValidationError, match="Duplicate relation alias declared: 's'"):
            QueryPlanIR(
                intent="GENERAL_QUERY",
                anchor_relation="students",
                relation_instances=(
                    RelationInstance(instance_id="rel_0", table_name="students", alias="s"),
                    RelationInstance(instance_id="rel_1", table_name="courses", alias="s"),
                ),
                projections=(
                    ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),
                ),
                parameter_registry=reg,
            )

    def test_ir_validation_join_additional_predicates(self):
        """Test 9: JoinIR additional_predicates validates referenced columns and aliases."""
        builder = ParameterBuilder()
        k0 = builder.register("Completed", "VARCHAR")
        reg = builder.build()

        # Valid additional predicate on JoinIR
        join = JoinIR(
            left_alias="co",
            left_column="offering_id",
            right_alias="e",
            right_column="offering_id",
            join_type="LEFT",
            additional_predicates=(
                PredicateIR(
                    column=ColumnRefIR(table_alias="e", column_name="enrollment_status"),
                    operator="=",
                    parameter_keys=(k0,),
                    is_negated=False,
                ),
            ),
        )
        assert len(join.additional_predicates) == 1

        # Invalid alias inside additional predicate
        with pytest.raises(ValidationError, match="Unknown table alias 'fake'"):
            QueryPlanIR(
                intent="GENERAL_QUERY",
                anchor_relation="course_offerings",
                relation_instances=(
                    RelationInstance(instance_id="rel_0", table_name="course_offerings", alias="co"),
                    RelationInstance(instance_id="rel_1", table_name="enrollments", alias="e"),
                ),
                projections=(
                    ProjectionIR(expression_node=ColumnRefIR(table_alias="co", column_name="section")),
                ),
                joins=(
                    JoinIR(
                        left_alias="co",
                        left_column="offering_id",
                        right_alias="e",
                        right_column="offering_id",
                        join_type="LEFT",
                        additional_predicates=(
                            PredicateIR(
                                column=ColumnRefIR(table_alias="fake", column_name="enrollment_status"),
                                operator="=",
                                parameter_keys=(k0,),
                                is_negated=False,
                            ),
                        ),
                    ),
                ),
                parameter_registry=reg,
            )

    def test_ir_validation_canonical_operator_negation(self):
        """Test 10: PredicateIR enforces canonical operator negation and rejects redundant negation."""
        col = ColumnRefIR(table_alias="s", column_name="roll_number")

        # Canonical inequality: = with is_negated=True
        pred_neq = PredicateIR(column=col, operator="=", parameter_keys=("param_0",), is_negated=True)
        assert pred_neq.is_negated is True

        # Explicit rejection of != and <> base operators
        with pytest.raises(ValidationError):
            PredicateIR(column=col, operator="!=", parameter_keys=("param_0",))

        with pytest.raises(ValidationError):
            PredicateIR(column=col, operator="<>", parameter_keys=("param_0",))

        # Redundant negation on ordered comparison: < with is_negated=True
        with pytest.raises(ValidationError, match="Redundant negation on ordered comparison"):
            PredicateIR(column=col, operator="<", parameter_keys=("param_0",), is_negated=True)

        # Canonical IS NOT NULL: IS NULL with is_negated=True
        pred_is_not_null = PredicateIR(column=col, operator="IS NULL", parameter_keys=(), is_negated=True)
        assert pred_is_not_null.operator == "IS NULL"
        assert pred_is_not_null.is_negated is True

    def test_predicate_operator_cardinality_validation(self):
        """Test 11: PredicateIR validates parameter key cardinality per operator."""
        col = ColumnRefIR(table_alias="s", column_name="cgpa")

        # IS NULL with parameter keys -> REJECTED
        with pytest.raises(ValidationError, match="requires exactly 0 parameter keys"):
            PredicateIR(column=col, operator="IS NULL", parameter_keys=("param_0",))

        # = with 0 or 2 keys -> REJECTED
        with pytest.raises(ValidationError, match="requires exactly 1 parameter key"):
            PredicateIR(column=col, operator="=", parameter_keys=())

        with pytest.raises(ValidationError, match="requires exactly 1 parameter key"):
            PredicateIR(column=col, operator="=", parameter_keys=("param_0", "param_1"))

        # BETWEEN with 1 key -> REJECTED
        with pytest.raises(ValidationError, match="requires exactly 2 parameter keys"):
            PredicateIR(column=col, operator="BETWEEN", parameter_keys=("param_0",))

        # IN with 0 keys -> REJECTED
        with pytest.raises(ValidationError, match="requires at least 1 parameter key"):
            PredicateIR(column=col, operator="IN", parameter_keys=())

    def test_ir_validation_unused_and_unregistered_parameters(self):
        """Test 12: QueryPlanIR rejects unregistered or unused parameters."""
        builder = ParameterBuilder()
        builder.register("Active", "VARCHAR")
        reg = builder.build()

        col = ColumnRefIR(table_alias="s", column_name="academic_status")

        # Unregistered parameter reference
        with pytest.raises(ValidationError, match="Referenced parameter keys not registered"):
            QueryPlanIR(
                intent="FILTER",
                anchor_relation="students",
                relation_instances=(
                    RelationInstance(instance_id="rel_0", table_name="students", alias="s"),
                ),
                projections=(
                    ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),
                ),
                predicates=(
                    PredicateIR(column=col, operator="=", parameter_keys=("param_99",)),
                ),
                parameter_registry=reg,
            )

        # Unused registered parameter
        with pytest.raises(ValidationError, match="Unused registered parameter keys present"):
            QueryPlanIR(
                intent="FILTER",
                anchor_relation="students",
                relation_instances=(
                    RelationInstance(instance_id="rel_0", table_name="students", alias="s"),
                ),
                projections=(
                    ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),
                ),
                predicates=(),
                parameter_registry=reg,
            )

    def test_ir_validation_limit_strict_integer_and_boundary(self):
        """Test 13: QueryPlanIR rejects LIMIT 0, negative limits, floats, booleans, and >100."""
        builder = ParameterBuilder()
        reg = builder.build()

        def make_plan(limit_val):
            return QueryPlanIR(
                intent="FILTER",
                anchor_relation="students",
                relation_instances=(
                    RelationInstance(instance_id="rel_0", table_name="students", alias="s"),
                ),
                projections=(
                    ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),
                ),
                limit=limit_val,
                parameter_registry=reg,
            )

        with pytest.raises(ValidationError, match="Invalid LIMIT: must be a positive integer >= 1"):
            make_plan(0)

        with pytest.raises(ValidationError, match="Invalid LIMIT: must be a positive integer >= 1"):
            make_plan(-5)

        with pytest.raises(ValidationError, match="LIMIT exceeds maximum allowed global limit of 100"):
            make_plan(101)

        with pytest.raises(ValidationError, match="LIMIT must be a strict integer"):
            make_plan(5.5)

        with pytest.raises(ValidationError, match="LIMIT must be a strict integer"):
            make_plan(True)

    def test_ir_validation_offset_bounds(self):
        """Test 14: QueryPlanIR enforces non-negative OFFSET, MAX_OFFSET = 1000, and deterministic unique ordering."""
        builder = ParameterBuilder()
        reg = builder.build()

        def make_student_plan(offset_val, order_by_items=None):
            obs = tuple(order_by_items) if order_by_items is not None else ()
            return QueryPlanIR(
                intent="FILTER",
                anchor_relation="students",
                relation_instances=(
                    RelationInstance(instance_id="rel_0", table_name="students", alias="s"),
                ),
                projections=(
                    ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),
                ),
                order_by=obs,
                offset=offset_val,
                parameter_registry=reg,
            )

        # 1. OFFSET < 0 is rejected
        with pytest.raises(ValidationError, match="OFFSET must be a non-negative integer >= 0"):
            make_student_plan(-1, [OrderByIR(target=ColumnRefIR(table_alias="s", column_name="roll_number"), direction="ASC")])

        # 2. OFFSET > 1000 is rejected
        with pytest.raises(ValidationError, match="Invalid OFFSET: exceeds maximum allowed offset of 1000"):
            make_student_plan(1001, [OrderByIR(target=ColumnRefIR(table_alias="s", column_name="roll_number"), direction="ASC")])

        # 3. OFFSET > 0 without order_by is rejected
        with pytest.raises(ValidationError, match="OFFSET > 0 requires deterministic ORDER BY"):
            make_student_plan(10, order_by_items=[])

        # 4. OFFSET = 0 allows empty or non-unique ordering
        plan0 = make_student_plan(0, order_by_items=[])
        assert plan0.offset == 0

        # 5. Non-unique ORDER BY alone with OFFSET > 0 is rejected
        with pytest.raises(ValidationError, match="requires deterministic ORDER BY containing a verified unique candidate key"):
            make_student_plan(10, [OrderByIR(target=ColumnRefIR(table_alias="s", column_name="cgpa"), direction="DESC")])

        # 6. Existing unique ORDER BY with OFFSET > 0 is accepted
        plan_valid_offset = make_student_plan(
            10,
            [
                OrderByIR(target=ColumnRefIR(table_alias="s", column_name="cgpa"), direction="DESC"),
                OrderByIR(target=ColumnRefIR(table_alias="s", column_name="roll_number"), direction="ASC"),
            ],
        )
        assert plan_valid_offset.offset == 10

        # Boundary max offset 1000 is accepted with deterministic ordering
        plan1000 = make_student_plan(1000, [OrderByIR(target=ColumnRefIR(table_alias="s", column_name="roll_number"), direction="ASC")])
        assert plan1000.offset == 1000

        # 7. Enrollment grain pagination
        plan_enrollment = QueryPlanIR(
            intent="FILTER",
            anchor_relation="enrollments",
            relation_instances=(
                RelationInstance(instance_id="rel_0", table_name="enrollments", alias="e"),
            ),
            projections=(
                ProjectionIR(expression_node=ColumnRefIR(table_alias="e", column_name="enrollment_id")),
            ),
            order_by=(
                OrderByIR(target=ColumnRefIR(table_alias="e", column_name="enrollment_id"), direction="ASC"),
            ),
            offset=20,
            parameter_registry=reg,
        )
        assert plan_enrollment.offset == 20

        # 8. Student-marks composite candidate key pagination
        # Incomplete candidate key: assessment_id alone -> REJECTED
        with pytest.raises(ValidationError, match="requires deterministic ORDER BY containing a verified unique candidate key"):
            QueryPlanIR(
                intent="FILTER",
                anchor_relation="student_marks",
                relation_instances=(
                    RelationInstance(instance_id="rel_0", table_name="student_marks", alias="sm"),
                ),
                projections=(
                    ProjectionIR(expression_node=ColumnRefIR(table_alias="sm", column_name="marks_obtained")),
                ),
                order_by=(
                    OrderByIR(target=ColumnRefIR(table_alias="sm", column_name="assessment_id"), direction="ASC"),
                ),
                offset=15,
                parameter_registry=reg,
            )

        # Full composite candidate key: (assessment_id, enrollment_id) -> ACCEPTED
        plan_sm = QueryPlanIR(
            intent="FILTER",
            anchor_relation="student_marks",
            relation_instances=(
                RelationInstance(instance_id="rel_0", table_name="student_marks", alias="sm"),
            ),
            projections=(
                ProjectionIR(expression_node=ColumnRefIR(table_alias="sm", column_name="marks_obtained")),
            ),
            order_by=(
                OrderByIR(target=ColumnRefIR(table_alias="sm", column_name="assessment_id"), direction="ASC"),
                OrderByIR(target=ColumnRefIR(table_alias="sm", column_name="enrollment_id"), direction="ASC"),
            ),
            offset=15,
            parameter_registry=reg,
        )
        assert plan_sm.offset == 15

        # 9. Grouped aggregate pagination
        # Grouped query ordered only by AVG(cgpa) without grouping candidate key -> REJECTED
        with pytest.raises(ValidationError, match="OFFSET > 0 on grouped query requires deterministic ORDER BY"):
            QueryPlanIR(
                intent="COMPARISON",
                anchor_relation="departments",
                relation_instances=(
                    RelationInstance(instance_id="rel_0", table_name="departments", alias="d"),
                    RelationInstance(instance_id="rel_1", table_name="students", alias="s"),
                ),
                projections=(
                    ProjectionIR(expression_node=ColumnRefIR(table_alias="d", column_name="code")),
                    ProjectionIR(
                        expression_node=AggregateFunctionIR(
                            function_name="AVG",
                            column_ref=ColumnRefIR(table_alias="s", column_name="cgpa"),
                        ),
                    ),
                ),
                joins=(
                    JoinIR(
                        left_alias="d",
                        left_column="department_id",
                        right_alias="s",
                        right_column="department_id",
                        join_type="INNER",
                    ),
                ),
                group_by=(
                    ColumnRefIR(table_alias="d", column_name="department_id"),
                    ColumnRefIR(table_alias="d", column_name="code"),
                ),
                order_by=(
                    OrderByIR(
                        target=AggregateFunctionIR(
                            function_name="AVG",
                            column_ref=ColumnRefIR(table_alias="s", column_name="cgpa"),
                        ),
                        direction="DESC",
                    ),
                ),
                offset=10,
                parameter_registry=reg,
            )

        # Grouped query ordered by AVG(cgpa) and grouping candidate key d.code -> ACCEPTED
        plan_grp = QueryPlanIR(
            intent="COMPARISON",
            anchor_relation="departments",
            relation_instances=(
                RelationInstance(instance_id="rel_0", table_name="departments", alias="d"),
                RelationInstance(instance_id="rel_1", table_name="students", alias="s"),
            ),
            projections=(
                ProjectionIR(expression_node=ColumnRefIR(table_alias="d", column_name="code")),
                ProjectionIR(
                    expression_node=AggregateFunctionIR(
                        function_name="AVG",
                        column_ref=ColumnRefIR(table_alias="s", column_name="cgpa"),
                    ),
                ),
            ),
            joins=(
                JoinIR(
                    left_alias="d",
                    left_column="department_id",
                    right_alias="s",
                    right_column="department_id",
                    join_type="INNER",
                ),
            ),
            group_by=(
                ColumnRefIR(table_alias="d", column_name="department_id"),
                ColumnRefIR(table_alias="d", column_name="code"),
            ),
            order_by=(
                OrderByIR(
                    target=AggregateFunctionIR(
                        function_name="AVG",
                        column_ref=ColumnRefIR(table_alias="s", column_name="cgpa"),
                    ),
                    direction="DESC",
                ),
                OrderByIR(target=ColumnRefIR(table_alias="d", column_name="code"), direction="ASC"),
            ),
            offset=10,
            parameter_registry=reg,
        )
        assert plan_grp.offset == 10


# ===========================================================================
# Tier 2: Integration Tests (QueryPlanner & Phase 1-5 Integration)
# ===========================================================================

class TestQueryPlannerIntegration:
    """Tier 2 Integration tests verifying QueryPlanner across all 7 intents and exit precedence."""

    @pytest.fixture(autouse=True)
    def setup_session(self):
        self.planner = get_query_planner()
        self.session_id = str(uuid.uuid4())

    def test_planner_intent_mapping_aggregate(self):
        """Test 15: Planner maps AGGREGATE intent to AggregateFunctionIR."""
        plan = self.planner.plan(self.session_id, "How many students are enrolled in Computer Science?")
        assert isinstance(plan, QueryPlanIR)
        assert plan.intent == "AGGREGATE"
        assert any(p.is_aggregate for p in plan.projections)

    def test_planner_intent_mapping_ranking(self):
        """Test 16: Planner maps RANKING intent with deterministic tie-breaker."""
        plan = self.planner.plan(self.session_id, "Top 5 students by CGPA")
        assert isinstance(plan, QueryPlanIR)
        assert plan.intent == "RANKING"
        assert plan.limit == 5
        # User metric ranking first, unique tie-breaker second
        assert len(plan.order_by) >= 2
        assert plan.order_by[0].target.column_name == "cgpa"
        assert plan.order_by[0].direction == "DESC"
        assert plan.order_by[-1].target.column_name == "roll_number"
        assert plan.order_by[-1].direction == "ASC"

    def test_planner_intent_mapping_filter(self):
        """Test 17: Planner maps FILTER intent to predicates with default 100 cap."""
        plan = self.planner.plan(self.session_id, "Show active students in semester 6")
        assert isinstance(plan, QueryPlanIR)
        assert plan.intent == "FILTER"
        assert plan.limit == 100
        assert len(plan.predicates) >= 1

    def test_planner_intent_mapping_comparison(self):
        """Test 18: Planner maps COMPARISON intent to departmental grouping."""
        plan = self.planner.plan(self.session_id, "Compare average CGPA across departments")
        assert isinstance(plan, QueryPlanIR)
        assert plan.intent == "COMPARISON"
        assert len(plan.group_by) >= 1

    def test_planner_intent_mapping_trend(self):
        """Test 19: Planner maps TREND intent to temporal term dimensions."""
        plan = self.planner.plan(self.session_id, "Enrollment trend of students across academic years")
        assert isinstance(plan, QueryPlanIR)
        assert plan.intent == "TREND"

    def test_planner_intent_mapping_general_query(self):
        """Test 20: Planner maps GENERAL_QUERY using Anchor Entity Preservation Rule."""
        plan = self.planner.plan(
            self.session_id,
            "List all courses offered in Spring 2024 with their instructors and enrolled students",
        )
        assert isinstance(plan, QueryPlanIR)
        assert plan.anchor_relation == "course_offerings"
        # Dependent child joins must be LEFT JOIN
        left_joins = [j for j in plan.joins if j.join_type == "LEFT"]
        assert len(left_joins) >= 1

    def test_planner_intent_mapping_what_if(self):
        """Test 21: Planner maps WHAT_IF simulation intent."""
        plan = self.planner.plan(self.session_id, "Simulate if probation threshold was 2.8 instead of 2.5")
        assert isinstance(plan, QueryPlanIR)
        assert plan.intent == "WHAT_IF"

    def test_planner_global_cap_enforcement(self):
        """Test 22: Planner enforces effective_limit = min(user_limit, 100)."""
        # User asks for 500 rows -> clamped to 100
        plan500 = self.planner.plan(self.session_id, "Top 500 students by CGPA")
        assert isinstance(plan500, QueryPlanIR)
        assert plan500.limit == 100

        # Unconstrained query -> defaults to 100
        plan_unconstrained = self.planner.plan(self.session_id, "Show all students")
        assert isinstance(plan_unconstrained, QueryPlanIR)
        assert plan_unconstrained.limit == 100

        # User asks for 10 rows -> 10
        plan10 = self.planner.plan(self.session_id, "Top 10 students by CGPA")
        assert isinstance(plan10, QueryPlanIR)
        assert plan10.limit == 10

    def test_planner_context_slot_inheritance(self):
        """Test 23: Planner inherits active entity and filter context slots across turns."""
        ce = get_context_engine()
        sid = str(uuid.uuid4())

        # Turn 1: AI department
        ce.resolve_turn(sid, "Show students in the AI department.")
        # Turn 2: Follow-up
        plan = self.planner.plan(sid, "Now show their attendance.")
        assert isinstance(plan, QueryPlanIR)
        assert any(
            p.column.column_name == "code" or p.column.table_alias == "d"
            for p in plan.predicates
        )

    def test_planner_deterministic_exit_precedence(self):
        """Test 24: Planner enforces deterministic exit precedence (OOD before Clarification)."""
        # Priority 2: OOD query containing blacklisted term "hostel"
        res_ood = self.planner.plan(self.session_id, "What is the average hostel fee?")
        assert isinstance(res_ood, dict)
        assert res_ood["status"] == "unsupported"

        # Priority 3: Disconnected entity "Science Hall"
        res_disc = self.planner.plan(self.session_id, "Course offerings in building Science Hall")
        assert isinstance(res_disc, dict)
        assert res_disc["status"] == "unsupported"

        # Priority 4: Attribute ambiguity "status"
        res_ambig = self.planner.plan(self.session_id, "Show status of CS department")
        assert isinstance(res_ambig, dict)
        assert res_ambig["status"] == "clarification_needed"

    def test_planner_all_15_examples_ir_generation(self):
        """Test 25: QueryPlanner successfully compiles all 15 approved representative SQL examples."""
        examples = [
            "Show active students in semester 6",
            "How many students are enrolled in Computer Science?",
            "List all courses offered in Spring 2024 with their instructors and enrolled students",
            "Average CGPA of students by department",
            "List all instructors in the Electrical Engineering department",
            "Find students with CGPA greater than 3.5 on probation",
            "Count of courses by department",
            "Top 5 students by CGPA",
            "Top 3 courses with highest average attendance",
            "Students who failed any course",
            "Total credits offered by each department",
            "Assessments for Database Management Systems in Fall 2023",
            "Active students in semester 6 with CGPA above 3.0",
            "Find all students in Artificial Intelligence department with their courses and grades",
            "Course offerings scheduled in classroom Hall-101 with section and term",
        ]

        for idx, nl in enumerate(examples, 1):
            sid = str(uuid.uuid4())
            res = self.planner.plan(sid, nl)
            assert isinstance(res, QueryPlanIR), f"Example {idx} ('{nl}') failed to produce QueryPlanIR: {res}"
            assert res.limit is not None
            assert res.limit <= 100
            assert len(res.projections) >= 1
            assert len(res.relation_instances) >= 1

    def test_planner_grouped_aggregate_department_cgpa_ordering(self):
        """Test 26: Grouped aggregate query uses grouping candidate key and never appends source-row keys."""
        plan = self.planner.plan(self.session_id, "Average CGPA of students by department")
        assert isinstance(plan, QueryPlanIR)
        assert len(plan.group_by) >= 1

        # Must have department candidate key (d.code) in ORDER BY
        ordered_col_names = [
            ob.target.column_name
            for ob in plan.order_by
            if isinstance(ob.target, ColumnRefIR)
        ]
        assert "code" in ordered_col_names

        # Must NEVER append students.roll_number to grouped query ORDER BY
        assert "roll_number" not in ordered_col_names
        for ob in plan.order_by:
            if isinstance(ob.target, ColumnRefIR):
                assert ob.target.table_alias != "s", f"Source-row column '{ob.target.column_name}' found in grouped ORDER BY!"

    def test_planner_grouped_aggregate_user_order_preserved_without_duplicate(self):
        """Test 27: Grouped query does not append duplicate tie-breaker when grouping key already ordered."""
        plan = self.planner.plan(self.session_id, "Count of courses by department")
        assert isinstance(plan, QueryPlanIR)
        code_order_count = sum(
            1 for ob in plan.order_by
            if isinstance(ob.target, ColumnRefIR) and ob.target.column_name == "code"
        )
        assert code_order_count == 1

    def test_planner_offset_exceeds_1000_rejection(self):
        """Test 28: Planner rejects queries with OFFSET > 1000 deterministically."""
        res = self.planner.plan(self.session_id, "Show active students offset 1050")
        assert isinstance(res, dict)
        assert res["status"] == "error"
        assert "exceeds maximum allowed offset of 1000" in res["error_message"]

    def test_planner_grouped_query_no_safe_tie_breaker_clarification(self):
        """Test 29: Grouped query with non-unique grouping and offset > 0 returns clarification_needed."""
        # Query grouped by academic_year (non-candidate key in terms) with offset > 0
        res = self.planner.plan(self.session_id, "Enrollment trend of students across academic years offset 20")
        assert isinstance(res, dict)
        assert res["status"] == "clarification_needed"
        assert "A safe deterministic ordering cannot be established" in res["clarification_message"]

    def test_planner_enrollment_grain_pagination_integration(self):
        """Test 30: End-to-end planner integration for enrollment-grain query with OFFSET > 0."""
        plan = self.planner.plan(
            self.session_id,
            "Rank course offerings with enrolled students by attendance offset 10",
        )
        assert isinstance(plan, QueryPlanIR)
        assert plan.offset == 10
        # Preserves user ordering first (attendance_percentage DESC)
        assert len(plan.order_by) >= 2
        assert isinstance(plan.order_by[0].target, ColumnRefIR)
        assert plan.order_by[0].target.column_name == "attendance_percentage"
        assert plan.order_by[0].direction == "DESC"
        # Deterministic tie-breaker appended (enrollment_id ASC)
        assert isinstance(plan.order_by[-1].target, ColumnRefIR)
        assert plan.order_by[-1].target.column_name == "enrollment_id"
        assert plan.order_by[-1].target.table_alias == "e"
        assert plan.order_by[-1].direction == "ASC"

    def test_planner_student_marks_grain_pagination_integration(self):
        """Test 31: End-to-end planner integration for student-marks-grain query with OFFSET > 0."""
        plan = self.planner.plan(
            self.session_id,
            "Rank student marks by marks obtained offset 10",
        )
        # 1. Valid QueryPlanIR returned
        assert isinstance(plan, QueryPlanIR)
        # 2. OFFSET == 10
        assert plan.offset == 10
        # 3. Result grain is student_marks
        assert plan.anchor_relation == "student_marks"

        order_by_cols = [
            (ob.target.column_name, ob.direction)
            for ob in plan.order_by
            if isinstance(ob.target, ColumnRefIR)
        ]
        # 4 & 5. Both composite candidate-key columns present as deterministic ascending tie-breakers
        assert ("assessment_id", "ASC") in order_by_cols
        assert ("enrollment_id", "ASC") in order_by_cols
        # 6. mark_id is not used as a substitute
        assert "mark_id" not in [c[0] for c in order_by_cols]
        # 7. students.roll_number is not incorrectly appended
        assert "roll_number" not in [c[0] for c in order_by_cols]
        # 8. User-requested ordering (marks_obtained DESC) is preserved as first sort key
        assert order_by_cols[0] == ("marks_obtained", "DESC")

    def test_planner_student_grain_query_not_misclassified_as_student_marks(self):
        """Test 32: Regression test verifying ordinary student-grain query retains student candidate key."""
        plan = self.planner.plan(
            self.session_id,
            "Show active students in semester 6 offset 10",
        )
        assert isinstance(plan, QueryPlanIR)
        assert plan.offset == 10
        assert plan.anchor_relation == "students"

        order_by_cols = [
            (ob.target.column_name, ob.direction)
            for ob in plan.order_by
            if isinstance(ob.target, ColumnRefIR)
        ]
        # Student candidate key roll_number ASC is appended
        assert ("roll_number", "ASC") in order_by_cols
        # student_marks composite keys must not be present
        assert "assessment_id" not in [c[0] for c in order_by_cols]
        assert "enrollment_id" not in [c[0] for c in order_by_cols]

    def test_semantic_boundary_query_1_students_with_marks_above_80(self):
        """Test 33: Boundary verification - 'Show students with marks above 80 offset 10'."""
        plan = self.planner.plan(
            self.session_id,
            "Show students with marks above 80 offset 10",
        )
        assert isinstance(plan, QueryPlanIR)
        assert plan.offset == 10
        assert plan.anchor_relation == "students"
        order_by_cols = [
            (ob.target.column_name, ob.direction)
            for ob in plan.order_by
            if isinstance(ob.target, ColumnRefIR)
        ]
        assert ("roll_number", "ASC") in order_by_cols
        assert "assessment_id" not in [c[0] for c in order_by_cols]
        assert "enrollment_id" not in [c[0] for c in order_by_cols]
        assert "mark_id" not in [c[0] for c in order_by_cols]

    def test_semantic_boundary_query_2_students_whose_marks_above_80(self):
        """Test 34: Boundary verification - 'Show students whose marks are above 80 offset 10'."""
        plan = self.planner.plan(
            self.session_id,
            "Show students whose marks are above 80 offset 10",
        )
        assert isinstance(plan, QueryPlanIR)
        assert plan.offset == 10
        assert plan.anchor_relation == "students"
        order_by_cols = [
            (ob.target.column_name, ob.direction)
            for ob in plan.order_by
            if isinstance(ob.target, ColumnRefIR)
        ]
        assert ("roll_number", "ASC") in order_by_cols
        assert "assessment_id" not in [c[0] for c in order_by_cols]
        assert "enrollment_id" not in [c[0] for c in order_by_cols]
        assert "mark_id" not in [c[0] for c in order_by_cols]

    def test_semantic_boundary_query_3_students_whose_scores_exceed_90(self):
        """Test 35: Boundary verification - 'List students whose scores exceed 90 offset 10'."""
        plan = self.planner.plan(
            self.session_id,
            "List students whose scores exceed 90 offset 10",
        )
        assert isinstance(plan, QueryPlanIR)
        assert plan.offset == 10
        assert plan.anchor_relation == "students"
        order_by_cols = [
            (ob.target.column_name, ob.direction)
            for ob in plan.order_by
            if isinstance(ob.target, ColumnRefIR)
        ]
        assert ("roll_number", "ASC") in order_by_cols
        assert "assessment_id" not in [c[0] for c in order_by_cols]
        assert "enrollment_id" not in [c[0] for c in order_by_cols]
        assert "mark_id" not in [c[0] for c in order_by_cols]

    def test_semantic_boundary_query_4_marks_obtained_by_each_student(self):
        """Test 36: Boundary verification - 'Show marks obtained by each student offset 10'."""
        plan = self.planner.plan(
            self.session_id,
            "Show marks obtained by each student offset 10",
        )
        assert isinstance(plan, QueryPlanIR)
        assert plan.offset == 10
        assert plan.anchor_relation == "student_marks"
        order_by_cols = [
            (ob.target.column_name, ob.direction)
            for ob in plan.order_by
            if isinstance(ob.target, ColumnRefIR)
        ]
        assert ("marks_obtained", "DESC") == order_by_cols[0]
        assert ("assessment_id", "ASC") in order_by_cols
        assert ("enrollment_id", "ASC") in order_by_cols
        assert "mark_id" not in [c[0] for c in order_by_cols]
        assert "roll_number" not in [c[0] for c in order_by_cols]

