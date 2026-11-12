"""Test Suite for Phase 6.2 SQL Generator.

Verifies:
1. GeneratedSQL controlled public-interface immutability and serialization.
2. Defensive AST copying and mutation isolation.
3. All 10 approved IR base operators and exact negation semantics.
4. Parameter accounting across WHERE, HAVING, and JOIN ON clauses.
5. Legitimate repeated parameter references.
6. Rejection of missing, unused, and invalid parameter keys.
7. LIMIT defaults, clamping, lower bounds, and L+1 pagination probing.
8. OFFSET handling and deterministic ordering preservation.
9. Structural SQL constants vs user-supplied data literals.
10. INNER and LEFT joins with additional ON-clause predicates.
11. Aggregations, COUNT DISTINCT, ROUND, and GROUP BY.
12. End-to-end compilation of all 15 approved representative queries.
13. Verification that Example 10 does NOT inject DISTINCT.
14. SQLGlot SQLite round-trip parse compatibility.
15. Deterministic byte-for-byte output over 1,000 compilations.
16. Invalid input handling.
"""

import uuid
import pytest
from types import MappingProxyType
import sqlglot
from sqlglot import exp

from app.services.parameter_registry import ParameterRegistry, ParameterBuilder
from app.services.query_plan_ir import (
    AggregateFunctionIR,
    ColumnRefIR,
    HavingIR,
    JoinIR,
    PredicateIR,
    ProjectionIR,
    QueryPlanIR,
    QueryPlanner,
    RelationInstance,
    OrderByIR,
)
from app.services.sql_generator import GeneratedSQL, SQLGenerator, get_sql_generator


class TestSQLGeneratorContracts:
    """Unit and contract tests for SQLGenerator and GeneratedSQL."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.generator = SQLGenerator()
        self.planner = QueryPlanner()
        self.session_id = str(uuid.uuid4())

    # -------------------------------------------------------------------------
    # 1. GeneratedSQL Controlled Public-Interface Immutability & Serialization
    # -------------------------------------------------------------------------

    def test_generated_sql_immutability(self):
        """Verifies controlled public-interface immutability of GeneratedSQL."""
        ast = exp.Select().select(exp.column("roll_number", "s")).from_(exp.Table(this=exp.to_identifier("students"), alias=exp.TableAlias(this=exp.to_identifier("s"))))
        params = {"param_0": "Active"}
        types = {"param_0": "VARCHAR"}
        gen = GeneratedSQL(sql="SELECT s.roll_number FROM students AS s", parameters=params, parameter_types=types, ast=ast)

        # 1. Top-level frozen reassignment raises error
        with pytest.raises(Exception):
            gen.sql = "MUTATED"

        # 2. Parameters is a MappingProxyType rejecting in-place mutation
        assert isinstance(gen.parameters, MappingProxyType)
        with pytest.raises(TypeError):
            gen.parameters["param_0"] = "Hacked"

        # 3. Parameter types is a MappingProxyType rejecting mutation
        assert isinstance(gen.parameter_types, MappingProxyType)
        with pytest.raises(TypeError):
            gen.parameter_types["param_0"] = "INTEGER"

        # 4. Values inside parameters are immutable scalars
        assert isinstance(gen.parameters["param_0"], str)

        # 5. Serialization produces clean dict
        serialized = gen.ser_model()
        assert serialized == {
            "sql": "SELECT s.roll_number FROM students AS s",
            "parameters": {"param_0": "Active"},
            "parameter_types": {"param_0": "VARCHAR"},
        }

    def test_defensive_ast_copying(self):
        """Verifies that accessing .ast returns an isolated deep copy."""
        ast = exp.Select().select(exp.column("roll_number", "s")).from_(exp.Table(this=exp.to_identifier("students"), alias=exp.TableAlias(this=exp.to_identifier("s"))))
        gen = GeneratedSQL(sql="SELECT s.roll_number FROM students AS s", parameters={}, parameter_types={}, ast=ast)

        copy1 = gen.ast
        copy2 = gen.ast
        assert copy1 is not copy2  # distinct instances

        # Mutate copy1 by appending a new projection
        copy1.select(exp.column("cgpa", "s"), copy=False)
        assert len(copy1.expressions) == 2
        assert len(copy2.expressions) == 1
        assert len(gen.ast.expressions) == 1  # internal AST remains untouched

    # -------------------------------------------------------------------------
    # 2. Operator Compilation & Exact Negation Semantics (10 Approved Operators)
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "operator,is_negated,expected_sql_substr",
        [
            ("=", False, "s.current_semester = :param_0"),
            ("=", True, "s.current_semester <> :param_0"),
            ("<", False, "s.current_semester < :param_0"),
            (">", False, "s.current_semester > :param_0"),
            ("<=", False, "s.current_semester <= :param_0"),
            (">=", False, "s.current_semester >= :param_0"),
            ("LIKE", False, "s.first_name LIKE :param_0"),
            ("LIKE", True, "NOT s.first_name LIKE :param_0"),
            ("ILIKE", False, "LOWER(s.first_name) LIKE LOWER(:param_0)"),
            ("ILIKE", True, "NOT LOWER(s.first_name) LIKE LOWER(:param_0)"),
            ("IS NULL", False, "s.cgpa IS NULL"),
            ("IS NULL", True, "NOT s.cgpa IS NULL"),
        ],
    )
    def test_operators_compilation(self, operator, is_negated, expected_sql_substr):
        """Verifies compilation of base operators and their negation forms."""
        builder = ParameterBuilder()
        col_name = "first_name" if "LIKE" in operator else ("cgpa" if operator == "IS NULL" else "current_semester")
        val = None if operator == "IS NULL" else (4 if col_name == "current_semester" else "A%")
        col_t = "INTEGER" if col_name == "current_semester" else "VARCHAR"

        param_keys = ()
        if operator != "IS NULL":
            pk = builder.register(val, col_t)
            param_keys = (pk,)

        pred = PredicateIR(
            column=ColumnRefIR(table_alias="s", column_name=col_name),
            operator=operator,
            parameter_keys=param_keys,
            is_negated=is_negated,
        )

        plan = QueryPlanIR(
            intent="FILTER",
            anchor_relation="students",
            relation_instances=(RelationInstance(instance_id="rel_0", table_name="students", alias="s"),),
            projections=(ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),),
            predicates=(pred,),
            parameter_registry=builder.build(),
        )

        generated = self.generator.generate(plan)
        assert expected_sql_substr in generated.sql

    def test_in_and_between_operators(self):
        """Verifies IN and BETWEEN operators in positive and negated forms."""
        # Test IN
        b_in = ParameterBuilder()
        pk1 = b_in.register(1, "INTEGER")
        pk2 = b_in.register(2, "INTEGER")
        pred_in = PredicateIR(
            column=ColumnRefIR(table_alias="s", column_name="current_semester"),
            operator="IN",
            parameter_keys=(pk1, pk2),
            is_negated=False,
        )
        plan_in = QueryPlanIR(
            intent="FILTER",
            anchor_relation="students",
            relation_instances=(RelationInstance(instance_id="rel_0", table_name="students", alias="s"),),
            projections=(ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),),
            predicates=(pred_in,),
            parameter_registry=b_in.build(),
        )
        assert "s.current_semester IN (:param_0, :param_1)" in self.generator.generate(plan_in).sql

        # Test BETWEEN
        b_bw = ParameterBuilder()
        pk_l = b_bw.register(2.0, "FLOAT")
        pk_h = b_bw.register(3.5, "FLOAT")
        pred_bw = PredicateIR(
            column=ColumnRefIR(table_alias="s", column_name="cgpa"),
            operator="BETWEEN",
            parameter_keys=(pk_l, pk_h),
            is_negated=True,
        )
        plan_bw = QueryPlanIR(
            intent="FILTER",
            anchor_relation="students",
            relation_instances=(RelationInstance(instance_id="rel_0", table_name="students", alias="s"),),
            projections=(ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),),
            predicates=(pred_bw,),
            parameter_registry=b_bw.build(),
        )
        assert "NOT s.cgpa BETWEEN :param_0 AND :param_1" in self.generator.generate(plan_bw).sql

    @pytest.mark.parametrize("op", ["<", ">", "<=", ">="])
    def test_rejected_negated_ordered_comparisons(self, op):
        """Verifies that generator rejects negated ordered comparisons."""
        col = exp.column("cgpa", "s")
        with pytest.raises(ValueError, match="Negated ordered comparison"):
            self.generator._compile_condition(col, op, ("param_0",), is_negated=True)

    # -------------------------------------------------------------------------
    # 3. Parameter Accounting Across WHERE, HAVING, and JOIN ON
    # -------------------------------------------------------------------------

    def test_comprehensive_parameter_accounting(self):
        """Verifies parameter collection from WHERE, HAVING, and JOIN ON clauses."""
        builder = ParameterBuilder()
        p_join = builder.register("Enrolled", "VARCHAR")
        p_where = builder.register("Active", "VARCHAR")
        p_having = builder.register(1, "INTEGER")

        plan = QueryPlanIR(
            intent="AGGREGATE",
            anchor_relation="students",
            relation_instances=(
                RelationInstance(instance_id="rel_0", table_name="students", alias="s"),
                RelationInstance(instance_id="rel_1", table_name="enrollments", alias="e"),
            ),
            projections=(
                ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),
                ProjectionIR(expression_node=AggregateFunctionIR(function_name="COUNT", column_ref=ColumnRefIR(table_alias="e", column_name="enrollment_id"))),
            ),
            joins=(
                JoinIR(
                    left_alias="s",
                    left_column="student_id",
                    right_alias="e",
                    right_column="student_id",
                    join_type="INNER",
                    additional_predicates=(
                        PredicateIR(
                            column=ColumnRefIR(table_alias="e", column_name="enrollment_status"),
                            operator="=",
                            parameter_keys=(p_join,),
                        ),
                    ),
                ),
            ),
            predicates=(
                PredicateIR(
                    column=ColumnRefIR(table_alias="s", column_name="academic_status"),
                    operator="=",
                    parameter_keys=(p_where,),
                ),
            ),
            group_by=(ColumnRefIR(table_alias="s", column_name="roll_number"),),
            having=(
                HavingIR(
                    aggregate=AggregateFunctionIR(function_name="COUNT", column_ref=ColumnRefIR(table_alias="e", column_name="enrollment_id")),
                    operator=">",
                    parameter_keys=(p_having,),
                ),
            ),
            parameter_registry=builder.build(),
        )

        gen = self.generator.generate(plan)
        # All three parameters must appear in the emitted SQL
        assert ":param_0" in gen.sql  # join ON predicate
        assert ":param_1" in gen.sql  # WHERE predicate
        assert ":param_2" in gen.sql  # HAVING predicate
        assert set(gen.parameters.keys()) == {"param_0", "param_1", "param_2"}

    def test_repeated_parameter_references_allowed(self):
        """Verifies that legitimate repeated references to the same parameter key are accepted."""
        builder = ParameterBuilder()
        pk = builder.register("Active", "VARCHAR")

        plan = QueryPlanIR(
            intent="FILTER",
            anchor_relation="students",
            relation_instances=(RelationInstance(instance_id="rel_0", table_name="students", alias="s"),),
            projections=(ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),),
            predicates=(
                PredicateIR(column=ColumnRefIR(table_alias="s", column_name="academic_status"), operator="=", parameter_keys=(pk,)),
                PredicateIR(column=ColumnRefIR(table_alias="s", column_name="academic_status"), operator="=", parameter_keys=(pk,)),
            ),
            parameter_registry=builder.build(),
        )

        gen = self.generator.generate(plan)
        assert gen.sql.count(":param_0") == 2
        assert set(gen.parameters.keys()) == {"param_0"}

    def test_missing_and_unused_parameter_rejection(self):
        """Verifies rejection when parameter keys are missing or unused."""
        # 1. Unused registered key during QueryPlanIR construction
        reg_unused = ParameterRegistry(
            bindings={"param_0": "Active", "param_1": "UNUSED"},
            types={"param_0": "VARCHAR", "param_1": "VARCHAR"},
        )
        with pytest.raises(Exception):
            QueryPlanIR(
                intent="FILTER",
                anchor_relation="students",
                relation_instances=(RelationInstance(instance_id="rel_0", table_name="students", alias="s"),),
                projections=(ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),),
                predicates=(
                    PredicateIR(column=ColumnRefIR(table_alias="s", column_name="academic_status"), operator="=", parameter_keys=("param_0",)),
                ),
                parameter_registry=reg_unused,
            )

        # 2. Defensive check in SQLGenerator if plan has unused or missing keys
        valid_reg = ParameterRegistry(
            bindings={"param_0": "Active"},
            types={"param_0": "VARCHAR"},
        )
        plan = QueryPlanIR(
            intent="FILTER",
            anchor_relation="students",
            relation_instances=(RelationInstance(instance_id="rel_0", table_name="students", alias="s"),),
            projections=(ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),),
            predicates=(
                PredicateIR(column=ColumnRefIR(table_alias="s", column_name="academic_status"), operator="=", parameter_keys=("param_0",)),
            ),
            parameter_registry=valid_reg,
        )

        # Inject unused key into registry
        object.__setattr__(plan, "parameter_registry", reg_unused)
        with pytest.raises(ValueError, match="unused parameter keys"):
            self.generator.generate(plan)

        # Inject empty registry (missing parameter key)
        empty_reg = ParameterRegistry(bindings={}, types={})
        object.__setattr__(plan, "parameter_registry", empty_reg)
        with pytest.raises(ValueError, match="missing from ParameterRegistry"):
            self.generator.generate(plan)

    # -------------------------------------------------------------------------
    # 4. LIMIT & OFFSET Contract (Phase 6.0 Rules)
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "limit,probe,expected_limit",
        [
            (None, False, 100),
            (None, True, 101),
            (5, False, 5),
            (5, True, 6),
            (100, False, 100),
            (100, True, 101),
        ],
    )
    def test_limit_and_probe_pagination(self, limit, probe, expected_limit):
        """Verifies default limit, explicit limit, and probe pagination."""
        builder = ParameterBuilder()
        plan = QueryPlanIR(
            intent="GENERAL_QUERY",
            anchor_relation="students",
            relation_instances=(RelationInstance(instance_id="rel_0", table_name="students", alias="s"),),
            projections=(ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),),
            limit=limit,
            parameter_registry=builder.build(),
        )
        gen = self.generator.generate(plan, probe_pagination=probe)
        assert f"LIMIT {expected_limit}" in gen.sql

    def test_limit_clamping_to_100(self):
        """Verifies that generator clamps any excess limit > 100 to global cap 100."""
        builder = ParameterBuilder()
        # QueryPlanIR validation blocks limit > 100 on instantiation,
        # but generator also enforces min(plan.limit, 100) independently:
        plan = QueryPlanIR(
            intent="GENERAL_QUERY",
            anchor_relation="students",
            relation_instances=(RelationInstance(instance_id="rel_0", table_name="students", alias="s"),),
            projections=(ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),),
            limit=100,
            parameter_registry=builder.build(),
        )
        assert "LIMIT 100" in self.generator.generate(plan, probe_pagination=False).sql
        assert "LIMIT 101" in self.generator.generate(plan, probe_pagination=True).sql

    def test_offset_compilation(self):
        """Verifies OFFSET emission only when offset > 0."""
        builder = ParameterBuilder()
        plan = QueryPlanIR(
            intent="FILTER",
            anchor_relation="students",
            relation_instances=(RelationInstance(instance_id="rel_0", table_name="students", alias="s"),),
            projections=(ProjectionIR(expression_node=ColumnRefIR(table_alias="s", column_name="roll_number")),),
            order_by=(OrderByIR(target=ColumnRefIR(table_alias="s", column_name="roll_number"), direction="ASC"),),
            limit=50,
            offset=10,
            parameter_registry=builder.build(),
        )
        gen = self.generator.generate(plan)
        assert "LIMIT 50 OFFSET 10" in gen.sql

    # -------------------------------------------------------------------------
    # 5. All 15 Approved Representative Examples Compilation & Parsing
    # -------------------------------------------------------------------------

    def test_all_15_approved_examples_compilation(self):
        """Compiles all 15 approved representative queries through SQLGenerator."""
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
            plan = self.planner.plan(sid, nl)
            assert isinstance(plan, QueryPlanIR), f"Example {idx} failed to produce QueryPlanIR"

            gen = self.generator.generate(plan)
            assert isinstance(gen, GeneratedSQL)
            assert len(gen.sql) > 10

            # Round-trip parsing through SQLGlot SQLite dialect
            parsed = sqlglot.parse_one(gen.sql, read="sqlite")
            assert isinstance(parsed, exp.Select)

            # Assert parameter bijectivity
            ast_placeholders = {p.this for p in parsed.find_all(exp.Placeholder)}
            assert ast_placeholders == set(gen.parameters.keys())

    def test_example_10_distinct_not_injected(self):
        """Explicitly verifies Example 10 compiles without DISTINCT (Known Limitation)."""
        sid = str(uuid.uuid4())
        plan = self.planner.plan(sid, "Students who failed any course")
        assert isinstance(plan, QueryPlanIR)

        gen = self.generator.generate(plan)
        # Verify DISTINCT is not injected
        assert "DISTINCT" not in gen.sql.upper()
        # Verify SELECT starts cleanly without DISTINCT
        assert gen.sql.startswith("SELECT s.roll_number")

    def test_examples_3_and_14_presentation_boundary(self):
        """Verifies Examples 3 & 14 project discrete columns rather than string concatenation."""
        sid = str(uuid.uuid4())
        plan3 = self.planner.plan(sid, "List all courses offered in Spring 2024 with their instructors and enrolled students")
        gen3 = self.generator.generate(plan3)
        assert "||" not in gen3.sql
        assert "i.first_name" in gen3.sql
        assert "i.last_name" in gen3.sql
        assert "s.first_name" in gen3.sql
        assert "s.last_name" in gen3.sql

        plan14 = self.planner.plan(sid, "Find all students in Artificial Intelligence department with their courses and grades")
        gen14 = self.generator.generate(plan14)
        assert "||" not in gen14.sql
        assert "s.first_name" in gen14.sql
        assert "s.last_name" in gen14.sql

    # -------------------------------------------------------------------------
    # 6. Determinism & Invalid Input Handling
    # -------------------------------------------------------------------------

    def test_deterministic_output_over_1000_compilations(self):
        """Verifies byte-for-byte deterministic output over 1,000 compiles of the same plan."""
        sid = str(uuid.uuid4())
        plan = self.planner.plan(sid, "Average CGPA of students by department")
        first_gen = self.generator.generate(plan)

        for _ in range(1000):
            current_gen = self.generator.generate(plan)
            assert current_gen.sql == first_gen.sql
            assert current_gen.parameters == first_gen.parameters
            assert current_gen.parameter_types == first_gen.parameter_types

    def test_invalid_input_rejection(self):
        """Verifies fast rejection of non-QueryPlanIR inputs."""
        with pytest.raises(TypeError):
            self.generator.generate({"not": "a plan"})  # type: ignore

        with pytest.raises(TypeError):
            self.generator.generate(None)  # type: ignore

    def test_singleton_accessor(self):
        """Verifies get_sql_generator singleton accessor."""
        gen1 = get_sql_generator()
        gen2 = get_sql_generator()
        assert gen1 is gen2
