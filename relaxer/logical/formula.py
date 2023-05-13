from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import FrozenSet, Set


class Formula(ABC):
    @property
    @abstractmethod
    def atoms(self) -> Set["Atom"]:
        ...

    @property
    def is_atom(self) -> bool:
        return False


class Atom(Formula, ABC):
    @property
    def atoms(self) -> Set["Atom"]:
        return set([self])

    @property
    def is_atom(self) -> bool:
        return True


@dataclass(frozen=True)
class Or(Formula):
    arguments: FrozenSet[Formula]

    @property
    def atoms(self) -> Set[Atom]:
        atoms: Set[Atom] = set()
        for arg in self.arguments:
            atoms.update(arg.atoms)
        return atoms

    def __str__(self) -> str:
        return " OR ".join((f"({argument})" for argument in self.arguments))


@dataclass(frozen=True)
class And(Formula):
    arguments: FrozenSet[Formula]

    @property
    def atoms(self) -> Set[Atom]:
        atoms: Set[Atom] = set()
        for arg in self.arguments:
            atoms.update(arg.atoms)
        return atoms

    def __str__(self) -> str:
        return " AND ".join((f"({argument})" for argument in self.arguments))


@dataclass(frozen=True)
class Not(Formula):
    argument: Formula

    @property
    def atoms(self) -> Set[Atom]:
        return self.argument.atoms

    def __str__(self) -> str:
        return f"NOT({self.argument})"


@dataclass(frozen=True)
class BooleanConstant(Atom):
    value: bool

    def __str__(self) -> str:
        if self.value == False:
            return "FALSE"
        return "TRUE"


TRUE = BooleanConstant(True)
FALSE = BooleanConstant(False)
