from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from numbers import Real
from typing import Collection, Sequence, Tuple

from relaxer.logical.formula import Atom


@dataclass(frozen=True)
class Variable(ABC):
    @property
    @abstractmethod
    def identifier(self) -> str:
        ...

    def __str__(self) -> str:
        return self.identifier

    def __hash__(self) -> int:
        return hash(self.identifier)

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, Variable):
            return False
        return self.identifier == __o.identifier


@dataclass(frozen=True, eq=False)
class DeltaVariable(Variable):
    depth: int

    @property
    def identifier(self) -> str:
        return f"delta_{self.depth}"

    def __hash__(self) -> int:
        return super().__hash__()


@dataclass(frozen=True, eq=False)
class RelaxationVariable(Variable):
    relaxation_idx: int

    @property
    def identifier(self) -> str:
        return f"relax_{self.relaxation_idx}"

    def __hash__(self) -> int:
        return super().__hash__()


def variable_from_string(s: str) -> Variable:
    prefix = s[:6]
    if prefix == "delta_":
        components = s.split("_")
        return DeltaVariable(int(components[1]))

    if prefix == "relax_":
        components = s.split("_")
        return RelaxationVariable(int(components[1]))

    raise ValueError(f'Cannot parse variable from string "{s}"')


class InequalitySymbol(Enum):
    GreaterThan = ">"
    LessThan = "<"
    GreaterEqual = ">="
    LessEqual = "<="

    def __str__(self) -> str:
        return self.value

    def turned(self) -> "InequalitySymbol":
        """Turns the inequality symbol around.

        Returns:
            InequalitySymbol: The turned inequality symbol.
        """
        if self == InequalitySymbol.GreaterThan:
            return InequalitySymbol.LessThan
        if self == InequalitySymbol.LessThan:
            return InequalitySymbol.GreaterThan
        if self == InequalitySymbol.GreaterEqual:
            return InequalitySymbol.LessEqual
        else:
            # self == InequalitySymbol.LessEqual
            return InequalitySymbol.GreaterEqual

    @staticmethod
    def from_string(s: str) -> "InequalitySymbol":
        return InequalitySymbol(s)


@dataclass(frozen=True)
class Summand:
    coefficient: Real
    var: Variable


@dataclass(frozen=True)
class Sum:
    summands: Tuple[Summand]

    @property
    def is_empty(self) -> bool:
        return len(self.summands) == 0

    def __str__(self) -> str:
        if self.is_empty:
            return "0"
        return " + ".join(
            (f"{summand.coefficient}*{summand.var}" for summand in self.summands)
        )

    def __eq__(self, other) -> bool:
        for summand in set(self.summands + other.summands):
            if self.summands.count(summand) != other.summands.count(summand):
                return False
        return True

    @staticmethod
    def from_string(s: str) -> "Sum":
        summands = []
        for summand_str in s.split("+"):
            summand_str = summand_str.strip()
            if summand_str == "0":
                continue
            coefficient, var_str = summand_str.split("*")
            coefficient = float(coefficient)
            var = variable_from_string(var_str)
            summands.append(Summand(coefficient, var))  # type: ignore

        return Sum(tuple(summands))


@dataclass(frozen=True)
class Inequality(Atom):
    left: Sum
    symbol: InequalitySymbol
    right: Real

    def __str__(self) -> str:
        return f"{self.left} {self.symbol} {self.right}"

    @property
    def is_strict(self) -> bool:
        return (
            self.symbol == InequalitySymbol.GreaterThan
            or self.symbol == InequalitySymbol.LessThan
        )

    @staticmethod
    def from_string(s: str) -> "Inequality":
        splits = s.split()
        right_str = splits[-1]
        symbol_str = splits[-2]
        left_str = " ".join(splits[:-2])
        left = Sum.from_string(left_str)
        right = float(right_str)
        return Inequality(left, InequalitySymbol(symbol_str), right)  # type: ignore


@dataclass
class DNFFormula:
    terms: Sequence[Collection[Inequality]]

    def __str__(self) -> str:
        terms_str = []
        for term in self.terms:
            terms_str.append("\n".join((f"\t{constraint}" for constraint in term)))
        return "\nOR\n".join(terms_str)

    @staticmethod
    def from_string(s: str) -> "DNFFormula":
        terms = []
        for term_str in s.split("OR"):
            constraints = []
            for constraint_str in term_str.split("\n"):
                clean_constraint_str = constraint_str.strip()
                if clean_constraint_str == "":
                    continue
                constraints.append(Inequality.from_string(clean_constraint_str))
            terms.append(tuple(constraints))
        return DNFFormula(tuple(terms))
