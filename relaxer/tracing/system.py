from typing import Collection, FrozenSet, Iterable, Protocol

from relaxer.ta import Edge, Expression, SymbolicState


class SystemState(Protocol):
    @property
    def symbolic(self) -> SymbolicState:
        ...


class SystemTransition(Protocol):
    @property
    def source(self) -> SystemState:
        ...

    @property
    def target(self) -> SystemState:
        ...

    @property
    def edges(self) -> FrozenSet[Edge]:
        ...


class TASystem(Protocol):
    @property
    def initial_state(self) -> SystemState:
        ...

    @property
    def num_of_relaxations(self) -> int:
        ...

    def outgoing_transitions(self, state: SystemState) -> Collection[SystemTransition]:
        ...

    def safety_properties(self, state: SystemState) -> Iterable[Expression]:
        ...
