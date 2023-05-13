from fractions import Fraction
from math import inf
from numbers import Real
from typing import Collection, Dict, Sequence, Set, Tuple
import numpy as np
from scipy.optimize import linprog

from relaxer.logical.lra import (
    DNFFormula,
    Inequality,
    InequalitySymbol,
    RelaxationVariable,
    Variable,
    Sum,
    Summand,
    Variable,
)
from relaxer.optimization.pareto import ParetoSet


class ScalarizationOptimizer:
    def __init__(self, weights: Sequence[Sequence[float]]) -> None:
        # we use a dict for weights because its keys behaves like an ordered set
        self._weights = [tuple(weight_vector) for weight_vector in weights]

    def maximize_relaxation(
        self,
        objectives: Sequence[RelaxationVariable],
        constraints: DNFFormula,
        strict_epsilon: Fraction,
    ) -> Tuple[Set[Tuple[Real]], bool]:

        solutions = ParetoSet()
        for conj_constraints in constraints.terms:
            self._maximize_con_relaxation(
                conj_constraints, objectives, strict_epsilon, solutions
            )

        return solutions.to_set(), False

    def maximize_con_relaxation(
        self,
        conj_constraints: Collection[Inequality],
        objectives: Sequence[RelaxationVariable],
        strict_epsilon: Fraction,
    ) -> Tuple[Set[Tuple[Real]], bool]:

        solutions = ParetoSet()
        self._maximize_con_relaxation(
            conj_constraints, objectives, strict_epsilon, solutions
        )

        return solutions.to_set(), False

    @property
    def stats(self) -> Dict[str, float]:
        return {}

    @property
    def used_method(self) -> str:
        return "Disjunctive weighted sum"

    def _maximize_con_relaxation(
        self,
        conj_constraints: Collection[Inequality],
        objectives: Sequence[RelaxationVariable],
        strict_epsilon: Fraction,
        solutions: ParetoSet,
    ) -> None:
        A, b = ScalarizationOptimizer._to_A_b(
            objectives, conj_constraints, strict_epsilon
        )

        mask_vector, addition_vector = self._bounded_vectors(A)
        if np.array_equal(mask_vector, np.zeros(len(objectives))):
            # All variables unbounded
            return set([tuple(addition_vector)])  # type: ignore

        for weight_vector in self._weights:
            c = -1.0 * np.array(weight_vector) * mask_vector
            if np.array_equal(c, np.zeros(len(objectives))):
                continue

            res = linprog(c, A_ub=A, b_ub=b)

            if not res.success:
                if res.status == 2:
                    # Problem infeasible
                    continue
                if res.status == 3:
                    # Problem unbounded
                    continue

                raise RuntimeError(f"Unsuccessful optimization: {res.message}")

            x = tuple(res.x + addition_vector)

            solutions.add(x)

    @staticmethod
    def _to_A_b(
        objectives: Sequence[RelaxationVariable],
        inequalities: Collection[Inequality],
        strict_epsilon: Fraction,
    ) -> Tuple[np.ndarray, np.ndarray]:
        var_to_idx: Dict[Variable, int] = {
            var: var.relaxation_idx for var in objectives
        }

        n = len(inequalities)
        m = len(objectives)
        A = np.zeros((n, m), dtype=Fraction)
        b = np.zeros(n, dtype=Fraction)

        for i, inequality in enumerate(inequalities):
            factor = Fraction(1.0)
            if (
                inequality.symbol == InequalitySymbol.GreaterEqual
                or inequality.symbol == InequalitySymbol.GreaterThan
            ):
                factor = Fraction(-1.0)

            offset = Fraction(0)

            if inequality.is_strict:
                offset = strict_epsilon

            b[i] = inequality.right * factor - offset

            for summand in inequality.left.summands:
                idx = var_to_idx[summand.var]

                A[i][idx] = A[i][idx] + factor * summand.coefficient

        return A, b

    def _bounded_vectors(self, A: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        unbounded_idxs = []
        _, m = A.shape
        for idx in range(m):
            bounded = False
            for coeff in A[:, idx]:
                if coeff > 0:
                    bounded = True
                    break

            if not bounded:
                unbounded_idxs.append(idx)

        if len(unbounded_idxs) == m:
            return np.zeros(m), inf * np.ones(m)

        mask_vector = np.ones(m)
        addition_vector = np.zeros(m)

        for idx in unbounded_idxs:
            mask_vector[idx] = 0
            addition_vector[idx] = inf

        return mask_vector, addition_vector
