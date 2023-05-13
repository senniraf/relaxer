from typing import (
    Callable,
    Collection,
    Dict,
    FrozenSet,
    Iterable,
    Optional,
    Sequence,
    Set,
    Tuple,
)

from uppyyl_simulator.backend.ast.parsers.uppaal_xml_model_parser import (
    uppaal_xml_to_system,
)
from uppyyl_simulator.backend.simulator.simulator import Simulator as UppyylSimulator

from relaxer.ta import (
    BooleanAnd,
    BooleanNot,
    BooleanOr,
    Clock,
    ClockConstraint,
    Edge,
    Expression,
    Location,
    LocationPredicate,
    Operator,
    SymbolicState,
)
from relaxer.tracing.system import SystemState, SystemTransition
from relaxer.tracing.uppyyl.relaxation import GuardRelaxation, InvariantRelaxation


class UppyylSystemState:
    def __init__(
        self, uppyyl_state, invariant_relaxations: Dict[InvariantRelaxation, int]
    ):
        self._uppyyl_state = uppyyl_state
        self._invariant_relaxations = invariant_relaxations

    @property
    def uppyyl(self):
        return self._uppyyl_state

    @property
    def symbolic(self) -> SymbolicState:
        locations = set(
            (
                self._location_from_uppyyl_location(location, process)
                for process, location in self._uppyyl_state.location_state.items()
            )
        )

        return SymbolicState(frozenset(locations))

    def _location_from_uppyyl_location(self, location, process: str) -> Location:
        invariants: Set[ClockConstraint] = set()
        for uppyyl_invariant in location.invariants:
            invariant = self.clock_constraints_from_uppyyl(
                uppyyl_invariant, location.parent.declaration.clocks, process
            )
            is_relaxed, relaxation_id = self._uppyl_invariant_relaxed(
                uppyyl_invariant, location.id
            )

            if is_relaxed:
                invariant = ClockConstraint(
                    invariant.clock, invariant.operator, invariant.limit, relaxation_id
                )

            invariants.add(invariant)

        is_urgent = location.urgent or location.committed

        return Location(
            id=location.id,
            process=process,
            name=location.name,
            urgent=is_urgent,
            invariants=frozenset(invariants),
        )

    def clock_constraints_from_uppyyl(
        self, constraint, local_clocks: Iterable[str], process: str
    ) -> ClockConstraint:
        expression = constraint.ast["expr"]
        return self.clock_constraint_from_uppyyl_expression(
            expression, expression["left"]["name"], local_clocks, process
        )

    def _uppyl_invariant_relaxed(
        self, constraint, location_id: str
    ) -> Tuple[bool, Optional[int]]:
        rel = InvariantRelaxation.create(
            location_id=location_id,
            uppaal_clock_constraint=constraint.text,
        )
        if rel in self._invariant_relaxations:
            return True, self._invariant_relaxations[rel]
        return False, None

    def clock_constraint_from_uppyyl_expression(
        self,
        expression,
        clock_name: str,
        local_clocks: Iterable[str],
        process: str,
    ) -> ClockConstraint:
        clock = UppyylSystemState._to_clock(clock_name, local_clocks, process)
        op = UppyylSystemState._operator_from_uppyyl_expression(expression)
        limit = self._expression_to_int(expression["right"], process)
        return ClockConstraint(clock=clock, operator=op, limit=limit)  # type: ignore

    def _expression_to_int(self, expression, process: str) -> int:
        astType = expression["astType"]
        if astType == "Integer":
            return expression["val"]
        if astType == "Variable":
            variable_name = expression["name"]
            variable = self._uppyyl_state.get(variable_name)
            return int(variable.val)
        if astType == "BinaryExpr":
            op = expression["op"]
            operation = UppyylSystemState._uppyyl_int_op_to_int_operation[op]
            return operation(
                self._expression_to_int(expression["left"], process),
                self._expression_to_int(expression["right"], process),
            )

        raise ValueError(f"Unsupported expression: {expression}")

    _uppyyl_int_op_to_int_operation: Dict[str, Callable[[int, int], int]] = {
        "Add": lambda x, y: x + y,
        "Sub": lambda x, y: x - y,
        "Mult": lambda x, y: x * y,
        "Div": lambda x, y: x // y,
        "RShift": lambda x, y: x >> y,
        "LShift": lambda x, y: x << y,
        "Mod": lambda x, y: x % y,
        "Minimum": min,
        "Maximum": max,
    }

    @staticmethod
    def _to_clock(clock_name: str, local_clocks: Iterable[str], process: str):
        clock_process = process
        if clock_name not in local_clocks:
            clock_process = None

        clock = Clock(name=clock_name, process=clock_process)
        return clock

    @staticmethod
    def _operator_from_uppyyl_expression(expression) -> Operator:
        """
        Converts an operator from a uppzl expression to a symbolic operator.
        """
        op = expression["op"]
        if op == "GreaterThan":
            return Operator.GreaterThan
        elif op == "GreaterEqual":
            return Operator.GreaterEqual
        elif op == "Equal":
            return Operator.Equal
        elif op == "LessEqual":
            return Operator.LessEqual
        elif op == "LessThan":
            return Operator.LessThan
        elif op == "NotEqual":
            return Operator.NotEqual
        else:
            raise ValueError(f"Unknown operator: {op}")


class UppyylSystemTransition:
    def __init__(
        self,
        uppyyl_transition,
        invariant_relaxations: Dict[InvariantRelaxation, int],
        guard_relaxations: Dict[GuardRelaxation, int],
    ) -> None:
        self._uppyyl_transition = uppyyl_transition
        self._source = UppyylSystemState(
            uppyyl_transition.source_state, invariant_relaxations
        )
        self._target = UppyylSystemState(
            uppyyl_transition.target_state, invariant_relaxations
        )
        self._guard_relaxations = guard_relaxations

    @property
    def source(self) -> SystemState:
        return self._source

    @property
    def target(self) -> SystemState:
        return self._target

    @property
    def edges(self) -> FrozenSet[Edge]:
        edges: Set[Edge] = set()
        for process, edge in self._uppyyl_transition.triggered_edges.items():
            if edge is None:
                continue

            guards = self._guards_from_uppyyl_edge(edge, process)
            resets = self._resets_from_uppyyl_edge(edge, process)

            edges.add(
                Edge(
                    source_id=edge.source.id,
                    target_id=edge.target.id,
                    process=process,
                    guards=frozenset(guards),
                    resets=frozenset(resets),
                )
            )

        return frozenset(edges)

    def _guards_from_uppyyl_edge(self, edge, process: str) -> Set[ClockConstraint]:
        """
        Extracts the List of guards from a uppyyl edge.
        """
        guards: Set[ClockConstraint] = set()

        for uppyyl_guard in edge.clock_guards:
            guard = self._source.clock_constraints_from_uppyyl(
                uppyyl_guard, edge.parent.declaration.clocks, process
            )

            is_relaxed, relaxation_id = self._uppyl_guard_relaxed(
                uppyyl_guard, edge.source.id, edge.target.id
            )
            if is_relaxed:
                guard = ClockConstraint(
                    guard.clock, guard.operator, guard.limit, relaxation_id
                )

            guards.add(guard)

        return guards

    def _resets_from_uppyyl_edge(self, edge, process: str) -> Set[Clock]:
        """
        Converts a uppyyl transition to a list of resets.
        """
        resets: Set[Clock] = set()

        for reset in edge.resets:
            clock_name = reset.ast["expr"]["left"]["name"]
            clock_process = process
            if clock_name not in edge.parent.declaration.clocks:  # type: ignore
                clock_process = None

            resets.add(Clock(name=clock_name, process=clock_process))

        return resets

    def _uppyl_guard_relaxed(
        self, constraint, source_id: str, target_id: str
    ) -> Tuple[bool, Optional[int]]:
        rel = GuardRelaxation.create(
            source_id=source_id,
            target_id=target_id,
            uppaal_clock_constraint=constraint.text,
        )
        if rel in self._guard_relaxations:
            return True, self._guard_relaxations[rel]
        return False, None


class UppyylTASystem:
    def __init__(
        self,
        path: str,
        inv_relax: Sequence[InvariantRelaxation],
        guard_relax: Sequence[GuardRelaxation],
    ) -> None:
        self._inv_relax: Dict[InvariantRelaxation, int] = self._init_relaxation_dict(
            inv_relax
        )
        offset = len(inv_relax)
        self._guard_relax: Dict[GuardRelaxation, int] = self._init_relaxation_dict(
            guard_relax, offset
        )

        self._transition_cache: Dict[SymbolicState, Tuple[SystemTransition, ...]] = {}

        with open(path, "r") as f:
            self._system = uppaal_xml_to_system(f.read())

        simulator = UppyylSimulator()
        simulator.set_system(self._system)

        self._initial_state = UppyylSystemState(simulator.system_state, self._inv_relax)

    def _init_relaxation_dict(self, relaxations: Iterable, offset: int = 0):
        return {relax: offset + relax_id for relax_id, relax in enumerate(relaxations)}

    @property
    def initial_state(self) -> SystemState:
        return self._initial_state

    @property
    def num_of_relaxations(self) -> int:
        return len(self._inv_relax) + len(self._guard_relax)

    def safety_properties(self, state: SystemState) -> Tuple[Expression, ...]:
        return tuple(
            (
                UppyylTASystem._safety_properties_from_uppyyl_query(query, state)
                for query in self._system.queries
            )
        )

    def outgoing_transitions(self, state: SystemState) -> Collection[SystemTransition]:
        if not isinstance(state, UppyylSystemState):
            raise ValueError()

        uppyyl_transitions = UppyylSimulator.get_all_potential_transitions(state.uppyyl)

        return [
            UppyylSystemTransition(
                uppyyl_transition, self._inv_relax, self._guard_relax
            )
            for uppyyl_transition in uppyyl_transitions
        ]

    @staticmethod
    def _safety_properties_from_uppyyl_query(query, uppyyl_state) -> Expression:
        formula = query.formula
        forall = formula.ast
        if forall["astType"] != "PropAll":
            raise UnsupportedQueryError(formula.text)

        always = forall["prop"]
        if always["astType"] != "PropGlobally":
            raise UnsupportedQueryError(formula.text)

        predicate = always["prop"]
        if predicate["astType"] != "Predicate":
            raise UnsupportedQueryError(formula.text)

        expr = predicate["expr"]
        if (
            expr["astType"] == "UnaryExpr"
            and expr["op"] == "LogNot"
            and expr["expr"]["astType"] == "DeadlockExpr"
        ):
            raise UnsupportedQueryError(formula.text)
        try:
            return UppyylTASystem._uppyyl_expression_to_expression(expr, uppyyl_state)
        except UnsupportedQueryError:
            raise UnsupportedQueryError(formula.text)

    @staticmethod
    def _uppyyl_expression_to_expression(expr, state: UppyylSystemState) -> Expression:
        if expr["astType"] == "BinaryExpr":
            if expr["op"] in {
                "GreaterThan",
                "GreaterEqual",
                "Equal",
                "LessEqual",
                "LessThan",
            }:
                # Clock Constraint expected
                left = expr["left"]

                process_name = ""
                local_clocks = []
                clock_name = left.get("name", "")

                if left["astType"] == "BinaryExpr":
                    if left["op"] == "Dot":
                        process = left["left"]
                        variable = left["right"]

                        if (
                            process["astType"] != "Variable"
                            or variable["astType"] != "Variable"
                        ):
                            raise UnsupportedQueryError(expr)

                        process_name = process["name"]
                        clock_name = variable["name"]
                        local_clocks = [clock_name]

                    elif left["astType"] != "Variable":
                        raise UnsupportedQueryError(expr)

                return state.clock_constraint_from_uppyyl_expression(
                    expr, clock_name, local_clocks, process_name
                )

            elif expr["op"] == "Dot":
                # Location predicate expected
                process_name = expr["left"]["name"]
                location_name = expr["right"]["name"]

                process_uppyyl_locations = state.uppyyl.location_state[
                    process_name
                ].parent.locations

                for location in process_uppyyl_locations.values():
                    if location.name == location_name:
                        return LocationPredicate(location.id)

            elif expr["op"] == "LogOr":
                return BooleanOr(
                    UppyylTASystem._uppyyl_expression_to_expression(
                        expr["left"], state
                    ),
                    UppyylTASystem._uppyyl_expression_to_expression(
                        expr["right"], state
                    ),
                )

            elif expr["op"] == "LogAnd":
                return BooleanAnd(
                    UppyylTASystem._uppyyl_expression_to_expression(
                        expr["left"], state
                    ),
                    UppyylTASystem._uppyyl_expression_to_expression(
                        expr["right"], state
                    ),
                )

            raise UnsupportedQueryError()

        elif expr["astType"] == "UnaryExpr":
            if expr["op"] == "LogNot":
                return BooleanNot(
                    UppyylTASystem._uppyyl_expression_to_expression(expr["expr"], state)
                )

            raise UnsupportedQueryError()

        elif expr["astType"] == "BracketExpr":
            return UppyylTASystem._uppyyl_expression_to_expression(expr["expr"], state)

        else:
            raise UnsupportedQueryError()


class UnsupportedQueryError(ValueError):
    pass


def get_relaxation_for_bounds_of_system(
    path: str, only_upper=False
) -> Tuple[Sequence[InvariantRelaxation], Sequence[GuardRelaxation]]:
    with open(path, "r") as f:
        system = uppaal_xml_to_system(f.read())
    invariant_relaxations = []
    guard_relaxations = []

    simulator = UppyylSimulator()
    simulator.set_system(system)
    initial_state = UppyylSystemState(simulator.system_state, {})

    active_templates = set(
        (l.parent for l in initial_state.uppyyl.location_state.values())
    )

    for template in active_templates:
        for l_id, location in template.locations.items():
            for invariant in location.invariants:
                cc = initial_state.clock_constraints_from_uppyyl(invariant, [], "")
                if only_upper and not (
                    cc.operator is Operator.LessEqual
                    or cc.operator is Operator.LessThan
                ):
                    continue

                invariant_relaxations.append(
                    InvariantRelaxation.create(
                        uppaal_clock_constraint=invariant.text,
                        location_id=l_id,
                    )
                )

        for edge in template.edges.values():
            for guard in edge.clock_guards:
                cc = initial_state.clock_constraints_from_uppyyl(guard, [], "")
                if only_upper and not (
                    cc.operator is Operator.LessEqual
                    or cc.operator is Operator.LessThan
                ):
                    continue

                guard_relaxations.append(
                    GuardRelaxation.create(
                        uppaal_clock_constraint=guard.text,
                        source_id=edge.source.id,
                        target_id=edge.target.id,
                    )
                )

    return invariant_relaxations, guard_relaxations
