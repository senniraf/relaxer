from fractions import Fraction
from numbers import Real
from typing import Collection, Dict, Protocol, Sequence, Set, Tuple

from relaxer.logical.lra import DNFFormula, Inequality, RelaxationVariable
from relaxer.statistics import StatsRecorder, MethodUser


class DisjunctiveOptimizer(MethodUser, StatsRecorder, Protocol):
    def maximize_relaxation(
        self,
        objectives: Sequence[RelaxationVariable],
        constraints: DNFFormula,
        strict_epsilon: Fraction,
    ) -> Tuple[Set[Tuple[Real]], bool]:
        """Maximizes the relaxations and returns a set of optimal solutions and a boolean value which indicates whether the solutions are supported.

        Args:
            objectives (Sequence[RelaxationVariable]): The relaxations which should be maximized
            constraints (DNFFormula): The timed constraints for the relaxations in DNF.
            strict_epsilon (Fraction): The value which is used for converting a strict inequality into a non-strict: "ax < b" -> "ax <= b - strict_epsilon"

        Returns:
            Tuple[Set[Tuple[Real]], bool]: The solutions and a boolean value whether they are supported.
        """
        ...


class ConjunctiveOptimizer(MethodUser, StatsRecorder, Protocol):
    def maximize_con_relaxation(
        self,
        objectives: Sequence[RelaxationVariable],
        conj_constraints: Collection[Inequality],
        strict_epsilon: Fraction,
        i: int,
    ) -> Tuple[Set[Tuple[Real]], bool]:
        """Maximizes the relaxations and returns a set of optimal solutions and a boolean value which indicates whether the solutions are supported.

        Args:
            objectives (Sequence[RelaxationVariable]): The relaxations which should be maximized
            constraints (DNFFormula): The timed constraints for the relaxations which are conjunctive (no disjunction is given).
            strict_epsilon (Fraction): The value which is used for converting a strict inequality into a non-strict: "ax < b" -> "ax <= b - strict_epsilon"
            i (int): The index of the conjunctive constraint.

        Returns:
            Tuple[Set[Tuple[Real]], bool]: The solutions and a boolean value whether they are supported.
        """
        ...


class HybridOptimizer:
    """A hybrid optimizer which uses a disjunctive optimizer for disjunctive constraints and a conjunctive optimizer for conjunctive constraints."""

    def __init__(
        self, dis_optimizer: DisjunctiveOptimizer, con_optimizer: ConjunctiveOptimizer
    ) -> None:
        self._dis_optimizer = dis_optimizer
        self._con_optimizer = con_optimizer
        self._used_optimizer: MethodUser

    def maximize_relaxation(
        self,
        objectives: Sequence[RelaxationVariable],
        constraints: DNFFormula,
        strict_epsilon: Fraction,
    ) -> Tuple[Set[Tuple[Real]], bool]:
        if len(constraints.terms) == 1:
            self._used_optimizer = self._con_optimizer
            return self._con_optimizer.maximize_con_relaxation(
                objectives, constraints.terms[0], strict_epsilon, 0
            )

        self._used_optimizer = self._dis_optimizer
        return self._dis_optimizer.maximize_relaxation(
            objectives, constraints, strict_epsilon
        )

    @property
    def stats(self) -> Dict[str, float]:
        return {
            **self._dis_optimizer.stats,
            **self._con_optimizer.stats,
        }

    @property
    def used_method(self) -> str:
        return self._used_optimizer.used_method
