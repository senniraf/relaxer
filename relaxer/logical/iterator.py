from collections import deque
from fractions import Fraction
from numbers import Real
from typing import (
    Deque,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
)

from relaxer.logical.constraint_system import TimedRelaxedTraceConstraints
from relaxer.logical.formula import FALSE, TRUE, And, Formula, Not, Or
from relaxer.logical.lra import (
    DeltaVariable,
    Inequality,
    InequalitySymbol,
    RelaxationVariable,
    Sum,
    Summand,
    Variable,
)
from relaxer.statistics import MethodUser
from relaxer.ta import (
    BooleanAnd,
    BooleanNot,
    BooleanOr,
    Clock,
    ClockConstraint,
    Edge,
    Expression,
    LocationPredicate,
    Operator,
    SymbolicState,
)
from relaxer.tracing.system import SystemState, SystemTransition, TASystem


class TraceIterator(MethodUser, Protocol):
    @property
    def relaxation_variables(self) -> Sequence[RelaxationVariable]:
        ...

    def __iter__(self) -> "TraceIterator":
        ...

    def __next__(self) -> TimedRelaxedTraceConstraints:
        ...


class DFSTraceIterator:
    """Trace iterator that iterates over all possible traces of a timed automaton system and generates the corresponding trace constraints."""

    def __init__(
        self,
        system: TASystem,
        depth: int,
    ) -> None:
        """Initialize the trace iterator.

        Args:
            system (TASystem): The timed automaton system.
            depth (int): The depth of the traces.
        """
        self._depth = depth

        self._system = system

        self._relaxations = [
            RelaxationVariable(idx) for idx in range(self._system.num_of_relaxations)
        ]
        self._delta_vars = [DeltaVariable(i) for i in range(self._depth + 1)]

        self._symbolic_trace: List[SymbolicState]
        self._clock_resets: Dict[Clock, List[int]]
        self._trace_ineqs: List[Set[Inequality]]
        self._property_formulas: List[Set[Formula]]

        self._transition_stack: Deque[Tuple[int, SystemTransition]]

    @property
    def used_method(self) -> str:
        return "DFS"

    @property
    def relaxation_variables(self) -> Sequence[RelaxationVariable]:
        return self._relaxations

    def __iter__(self) -> TraceIterator:
        self._clock_resets = {}
        self._trace_ineqs = []
        self._property_formulas = []
        self._symbolic_trace = []

        self._transition_stack = deque()

        current_state_depth = 0
        initial_state = self._system.initial_state
        self._trace_ineqs.append(set())
        self._property_formulas.append(set())
        self._encode_state(current_state_depth, initial_state)
        self._symbolic_trace.append(initial_state.symbolic)

        current_state_depth += 1
        if current_state_depth > self._depth:
            return self

        for transition in self._system.outgoing_transitions(initial_state):
            self._transition_stack.append((current_state_depth, transition))

        return self

    def __next__(self) -> TimedRelaxedTraceConstraints:
        if len(self._transition_stack) == 0:
            raise StopIteration

        target_state_depth, transition = self._transition_stack.pop()
        self._copy_clock_resets(target_state_depth)
        self._trace_ineqs = self._trace_ineqs[:target_state_depth]
        self._property_formulas = self._property_formulas[:target_state_depth]
        self._symbolic_trace = self._symbolic_trace[:target_state_depth]

        self._trace_ineqs.append(set())
        self._property_formulas.append(set())
        self._encode_transition(target_state_depth, transition)
        self._encode_state(target_state_depth, transition.target)
        self._symbolic_trace.append(transition.target.symbolic)

        target_state_depth += 1
        if target_state_depth <= self._depth:
            next_transitions = self._system.outgoing_transitions(transition.target)

            for next_transition in next_transitions:
                self._transition_stack.append((target_state_depth, next_transition))

        symbolic_trace = tuple(self._symbolic_trace)
        relaxation_vars = frozenset(self._relaxations)
        delta_vars = tuple(self._delta_vars[:target_state_depth])
        inequalities = tuple((frozenset(ineqs) for ineqs in self._trace_ineqs))
        property_formulas = tuple(
            (frozenset(formulas) for formulas in self._property_formulas)
        )

        return TimedRelaxedTraceConstraints(
            symbolic_trace, relaxation_vars, delta_vars, inequalities, property_formulas
        )

    def _encode_state(self, current_depth: int, state: SystemState):
        self._encode_safety_properties(current_depth, state)
        self._encode_locations(current_depth, state.symbolic)

    def _encode_transition(self, target_state_depth: int, transition: SystemTransition):
        self._encode_guards(target_state_depth, transition.edges)
        self._encode_resets(target_state_depth, transition.edges)

    def _encode_deadlock(self, state_depth: int):
        self._property_formulas[state_depth].add(FALSE)

    def _encode_locations(self, current_depth: int, state: SymbolicState):
        for location in state.locations:
            for invariant in location.invariants:
                # c_i_j ~ b
                summands = self._substitute_clock(current_depth, invariant.clock)
                encoded_rel = self._encoded_relaxation(invariant)
                if encoded_rel is not None:
                    summands.append(encoded_rel)
                self._encode_clock_constraint(current_depth, invariant, summands)

                # c_i_j + d_i_j ~ b
                summands.append(Summand(1, self._delta_vars[current_depth]))  # type: ignore
                self._encode_clock_constraint(current_depth, invariant, summands)

            if location.urgent:
                self._encode_urgent(current_depth)

    def _encode_guards(self, target_depth: int, edges: Iterable[Edge]):
        for edge in edges:
            for guard in edge.guards:
                # c_i_[j-1] + delta_i_[j-1] ~ b
                summands = self._substitute_clock(target_depth - 1, guard.clock) + [
                    Summand(1, self._delta_vars[target_depth - 1])  # type: ignore
                ]
                encoded_rel = self._encoded_relaxation(guard)
                if encoded_rel is not None:
                    summands.append(encoded_rel)

                self._encode_clock_constraint(target_depth, guard, summands)

    def _encode_resets(self, target_depth: int, edges: Iterable[Edge]):
        for edge in edges:
            for reset in edge.resets:
                if reset not in self._clock_resets:
                    self._clock_resets[reset] = []

                self._clock_resets[reset].append(target_depth)

    def _encode_safety_properties(
        self,
        current_depth: int,
        state: SystemState,
    ):
        # TODO: Use safety_property skeleton
        for property in self._system.safety_properties(state):
            self._property_formulas[current_depth].update(
                (
                    self._encoded_property(
                        property,
                        current_depth,
                        state.symbolic,
                        (),
                    ),
                    self._encoded_property(
                        property,
                        current_depth,
                        state.symbolic,
                        (self._delta_vars[current_depth],),
                    ),
                )
            )

    def _encode_urgent(self, current_depth: int):
        delta_sum = Sum((Summand(Fraction(1), self._delta_vars[current_depth]),))
        self._trace_ineqs[current_depth].update(
            (
                Inequality(left=delta_sum, symbol=InequalitySymbol.LessEqual, right=0),  # type: ignore
                Inequality(
                    left=delta_sum, symbol=InequalitySymbol.GreaterEqual, right=0  # type: ignore
                ),
            )
        )

    def _encode_clock_constraint(
        self,
        current_depth: int,
        constraint: ClockConstraint,
        summands: List[Summand],
    ):
        encoded = DFSTraceIterator._encoded_clock_constraint(constraint, summands)
        self._trace_ineqs[current_depth].update(encoded)

    def _encoded_property(
        self,
        property: Expression,
        current_depth: int,
        state: SymbolicState,
        deltas_to_add: Iterable[Variable],
    ) -> Formula:
        if isinstance(property, BooleanOr):
            return Or(
                frozenset(
                    (
                        self._encoded_property(
                            property.left,
                            current_depth,
                            state,
                            deltas_to_add,
                        ),
                        self._encoded_property(
                            property.right,
                            current_depth,
                            state,
                            deltas_to_add,
                        ),
                    )
                ),
            )

        elif isinstance(property, BooleanAnd):
            return And(
                frozenset(
                    (
                        self._encoded_property(
                            property.left,
                            current_depth,
                            state,
                            deltas_to_add,
                        ),
                        self._encoded_property(
                            property.right,
                            current_depth,
                            state,
                            deltas_to_add,
                        ),
                    )
                )
            )

        elif isinstance(property, BooleanNot):
            return Not(
                self._encoded_property(
                    property.argument,
                    current_depth,
                    state,
                    deltas_to_add,
                )
            )

        elif isinstance(property, LocationPredicate):
            location_id = property.location_id
            if location_id in (location.id for location in state.locations):
                return TRUE
            return FALSE

        elif isinstance(property, ClockConstraint):
            summands = self._substitute_clock(current_depth, property.clock) + [
                Summand(Fraction(1, 1), delta_var) for delta_var in deltas_to_add
            ]

            inequalities = DFSTraceIterator._encoded_clock_constraint(
                property, summands
            )

            return And(frozenset(inequalities))

        raise ValueError(f"Unknown property expression: {property}")

    @staticmethod
    def _encoded_clock_constraint(
        constraint: ClockConstraint,
        summands: List[Summand],
    ) -> Iterator[Inequality]:
        clock_sum = Sum(tuple(summands))

        if constraint.operator == Operator.Equal:
            # (a + b == c) <=> (a + b <= c) and (a + b >= c)
            yield Inequality(
                left=clock_sum,
                symbol=InequalitySymbol.GreaterEqual,
                right=constraint.limit,
            )

            yield Inequality(
                left=clock_sum,
                symbol=InequalitySymbol.LessEqual,
                right=constraint.limit,
            )

        elif (
            constraint.operator == Operator.GreaterThan
            or constraint.operator == Operator.GreaterEqual
        ):
            symbol = InequalitySymbol.GreaterEqual
            if constraint.operator == Operator.GreaterThan:
                symbol = InequalitySymbol.GreaterThan

            yield Inequality(
                left=clock_sum,
                symbol=symbol,
                right=constraint.limit,
            )

        elif (
            constraint.operator == Operator.LessThan
            or constraint.operator == Operator.LessEqual
        ):
            symbol = InequalitySymbol.LessEqual
            if constraint.operator == Operator.LessThan:
                symbol = InequalitySymbol.LessThan

            yield Inequality(
                left=clock_sum,
                symbol=symbol,
                right=constraint.limit,
            )

        else:
            raise RuntimeError(
                f"Operator {constraint.operator} not supported for clock constraint encoding"
            )

    def _encoded_relaxation(self, constraint: ClockConstraint) -> Optional[Summand]:
        if constraint.is_relaxed:
            relaxation_var = self._relaxations[constraint.relaxation_idx]  # type: ignore because this is checked by is_relaxed
            coefficient = DFSTraceIterator._coefficient_from_operator(
                constraint.operator
            )

            return Summand(coefficient, relaxation_var)

    def _substitute_clock(self, current_depth: int, clock: Clock) -> List[Summand]:
        """Substitute the clock at the current depth with a sum of all delta variables since the last reset before the current depth.

        Args:
            current_depth (int): The current depth of the clock
            clock (Clock): The clock to substitute

        Returns:
            List[Summand]: A list of summands of delta variables since the last reset of the clock
        """
        # Every clock is reset at the initial state
        last_reset = 0
        if clock in self._clock_resets:
            # If the clock was reset after the initial state, get the last reset before current_depth
            for reset in self._clock_resets[clock]:
                if reset > current_depth:
                    break
                last_reset = reset

        last_reset = last_reset

        # Return summands of deltas since the last reset
        return [
            Summand(Fraction(1, 1), delta_var)
            for delta_var in self._delta_vars[last_reset:current_depth]
        ]

    def _copy_clock_resets(self, until_depth: int):
        for clock in self._clock_resets:
            new_resets = []
            for reset in self._clock_resets[clock]:
                if reset >= until_depth:
                    break

                new_resets.append(reset)
            self._clock_resets[clock] = new_resets

    @staticmethod
    def _coefficient_from_operator(operator: Operator) -> Real:
        if operator == Operator.GreaterThan or operator == Operator.GreaterEqual:
            # (d_0 + d_1 + ... >= b - p) <=> (d_0 + d_1 + ... + p >= b)
            return Fraction(1)

        # (d_0 + d_1 + ... <= b + p) <=> (d_0 + d_1 + ... - p <= b)
        return Fraction(-1)
