from abc import ABC
from dataclasses import dataclass
from enum import Enum
from numbers import Real
from typing import FrozenSet, Optional


class Expression(ABC):
    pass


@dataclass
class BooleanOr(Expression):
    left: Expression
    right: Expression


@dataclass
class BooleanAnd(Expression):
    left: Expression
    right: Expression


@dataclass
class BooleanNot(Expression):
    argument: Expression


class SafetyPropertyAtom(Expression):
    pass


class Operator(Enum):
    GreaterThan = ">"
    LessThan = "<"
    GreaterEqual = ">="
    LessEqual = "<="
    Equal = "=="
    NotEqual = "!="

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Clock:
    name: str
    process: Optional[str] = None

    def __str__(self) -> str:
        prefix = ""
        if self.process != None:
            prefix = f"{self.process}."
        return f"{prefix}{self.name}"


@dataclass(frozen=True)
class ClockConstraint(SafetyPropertyAtom):
    clock: Clock
    operator: Operator
    limit: Real
    relaxation_idx: Optional[int] = None

    @property
    def is_relaxed(self) -> bool:
        return self.relaxation_idx != None

    def __str__(self) -> str:
        suffix = ""
        if self.is_relaxed:
            suffix = f" \u00B1 rel_{self.relaxation_idx}"
        return f"{self.clock} {self.operator} {self.limit}{suffix}"


@dataclass(frozen=True)
class Edge:
    target_id: str
    source_id: str
    process: str
    guards: FrozenSet[ClockConstraint]
    resets: FrozenSet[Clock]


@dataclass(frozen=True)
class Location:
    id: str
    process: str
    name: str
    urgent: bool
    invariants: FrozenSet[ClockConstraint]


@dataclass(frozen=True)
class LocationPredicate(SafetyPropertyAtom):
    location_id: str


@dataclass(frozen=True)
class SymbolicState:
    locations: FrozenSet[Location]

    def __str__(self) -> str:
        sorted_string = sorted((f"{l.process}.{l.name}" for l in self.locations))
        locs_string = ", ".join(sorted_string)
        return f"({locs_string})"
