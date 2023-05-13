from dataclasses import dataclass
from fractions import Fraction
from math import inf
from numbers import Real
from typing import Dict, Optional, Set, Tuple

import pysmt.shortcuts
from pysmt.fnode import FNode
from relaxer.logical.lra import InequalitySymbol

from relaxer.logical.pysmt.conversion import (
    get_inequality_triple,
    pysmt_to_constant_value,
)


def propagate_real_intervals_cnf(cnf_formula: FNode) -> FNode:
    atoms = pysmt.shortcuts.get_atoms(cnf_formula)

    if cnf_formula.is_not() or not cnf_formula.is_bool_op():
        return cnf_formula

    if cnf_formula.is_or():
        return _rewrite_clause(cnf_formula, {}, atoms)[0]

    if not cnf_formula.is_and():
        raise ValueError(f"Formula not in CNF: {cnf_formula}")

    clauses = set(cnf_formula.args())
    unit_intervals = {}

    changed_clause = True
    while changed_clause:
        rewritten_clauses = set()
        _add_unit_intervals(unit_intervals, clauses, atoms)
        _add_implied_intervals(unit_intervals, atoms)
        changed_clause = False
        for clause in clauses:
            rewritten_clause, changed = _rewrite_clause(clause, unit_intervals, atoms)
            changed_clause = changed_clause or changed

            if rewritten_clause.is_false():
                return pysmt.shortcuts.FALSE()
            if rewritten_clause.is_true():
                continue

            rewritten_clauses.add(rewritten_clause)

        clauses = rewritten_clauses

    out_cnf = pysmt.shortcuts.And(clauses)
    assert pysmt.shortcuts.is_valid(pysmt.shortcuts.Iff(out_cnf, cnf_formula))
    return out_cnf


@dataclass
class Bound:
    value: Real
    is_strict: bool


class Interval:
    def __init__(
        self, upper: Bound = Bound(inf, False), lower: Bound = Bound(-inf, False)  # type: ignore
    ) -> None:
        self._upper = upper
        self._lower = lower

    @property
    def upper(self) -> Bound:
        return self._upper

    @property
    def lower(self) -> Bound:
        return self._lower

    def tighten(self, upper: Optional[Bound] = None, lower: Optional[Bound] = None):
        if upper is not None:
            self.tighten_upper(upper)

    def tighten_upper(self, upper: Bound):
        if upper.value > self._upper.value:
            return

        if upper.value == self._upper.value and not upper.is_strict:
            return

        self._upper = upper

    def tighten_lower(self, lower: Bound):
        if lower.value < self._lower.value:
            return

        if lower.value == self._lower.value and not lower.is_strict:
            return

        self._lower = lower

    def __repr__(self):
        lower_c = "[" if not self.lower.is_strict else "("
        upper_c = "]" if not self.upper.is_strict else ")"

        return f"{lower_c}{self.lower.value}, {self.upper.value}{upper_c}"


def _add_unit_intervals(
    unit_intervals: Dict[FNode, Interval], clauses: Set[FNode], atoms: Set[FNode]
) -> None:
    for clause in clauses:
        if clause.is_or() or clause.is_true():
            continue

        atom = clause
        if atom.is_not():
            atom = atom.arg(0)

        if atom not in atoms:
            raise ValueError(f"Formula is not in CNF, got clause: {clause}")

        left, op, right = get_inequality_triple(clause)

        variables: FNode
        bound: Bound
        is_lower: bool
        if not (left.is_constant() or right.is_constant()):
            if left in unit_intervals:
                var_to_add = right
                bound_var = left
                is_lower = (
                    op == InequalitySymbol.LessEqual or op == InequalitySymbol.LessThan
                )
            elif right in unit_intervals:
                var_to_add = left
                bound_var = right
                is_lower = (
                    op == InequalitySymbol.GreaterEqual
                    or op == InequalitySymbol.GreaterThan
                )
            else:
                continue

            is_strict = (
                op == InequalitySymbol.LessThan or op == InequalitySymbol.GreaterThan
            )

            variables = var_to_add
            bound = (
                unit_intervals[bound_var].lower
                if is_lower
                else unit_intervals[bound_var].upper
            )
            if is_strict:
                bound = Bound(bound.value, True)
        else:
            variables, bound, is_lower = _get_bound(left, op, right)

        if variables not in unit_intervals:
            unit_intervals[variables] = Interval()

        if is_lower:
            unit_intervals[variables].tighten_lower(bound)
        else:
            unit_intervals[variables].tighten_upper(bound)


def _add_implied_intervals(
    unit_intervals: Dict[FNode, Interval], atoms: Set[FNode]
) -> None:
    for atom in atoms:
        left, _, right = get_inequality_triple(atom)
        if not (left.is_constant() or right.is_constant()):
            continue

        variables = left
        if left.is_constant():
            variables = right

        if not variables.is_plus():
            continue

        summands = variables.args()
        skip = False
        interval = Interval(
            upper=Bound(0.0, False), lower=Bound(0.0, False)  # type: ignore
        )

        for summand in summands:
            coefficient = 1

            if summand.is_times():
                for arg in summand.args():
                    if arg.is_symbol():
                        summand = arg

                    if arg.is_real_constant():
                        coefficient = pysmt_to_constant_value(arg)

            if coefficient == 0:
                break

            if summand not in unit_intervals:
                skip = True
                break

            summand_interval = unit_intervals[summand]

            low = summand_interval.lower.value * coefficient
            up = summand_interval.upper.value * coefficient

            if low <= up:
                interval.upper.value += up
                interval.lower.value += low
                interval.upper.is_strict = (
                    interval.upper.is_strict or summand_interval.upper.is_strict
                )
                interval.lower.is_strict = (
                    interval.lower.is_strict or summand_interval.lower.is_strict
                )
            else:
                interval.upper.value += low
                interval.lower.value += up
                interval.upper.is_strict = (
                    interval.upper.is_strict or summand_interval.lower.is_strict
                )
                interval.lower.is_strict = (
                    interval.lower.is_strict or summand_interval.upper.is_strict
                )

        if skip:
            continue

        unit_intervals[variables] = interval


def _rewrite_clause(
    clause: FNode, unit_intervals: Dict[FNode, Interval], atoms: Set[FNode]
) -> Tuple[FNode, bool]:
    if clause.is_not() and clause.arg(0) in atoms:
        return clause, False

    if clause in atoms:
        return clause, False

    if not clause.is_or():
        raise ValueError(f"Clause is not disjunction: {clause}")

    changed = False

    out_literals = set()
    for literal in clause.args():
        left, op, right = get_inequality_triple(literal)
        if not (left.is_constant() or right.is_constant()):
            out_literals.add(literal)
            continue

        variables, bound, is_lower = _get_bound(left, op, right)

        if variables in unit_intervals:
            interval = unit_intervals[variables]
            if is_lower:
                if bound.value < interval.lower.value:
                    # literal is satisfied by unit interval => clause is satisfied
                    return pysmt.shortcuts.TRUE(), True

                if bound.value == interval.lower.value and (
                    interval.lower.is_strict or not bound.is_strict
                ):
                    # literal is satisfied by unit interval => clause is satisfied
                    return pysmt.shortcuts.TRUE(), True

                if bound.value > interval.upper.value:
                    # literal is contradicting with unit interval => skip literal
                    changed = True
                    continue

                if bound.value == interval.upper.value and (
                    bound.is_strict or interval.upper.is_strict
                ):
                    # literal is contradicting with unit interval => skip literal
                    changed = True
                    continue

            else:
                if bound.value > interval.upper.value:
                    # literal is satisfied by unit interval => clause is satisfied
                    return pysmt.shortcuts.TRUE(), True

                if bound.value == interval.upper.value and (
                    interval.upper.is_strict or not bound.is_strict
                ):
                    # literal is satisfied by unit interval => clause is satisfied
                    return pysmt.shortcuts.TRUE(), True

                if bound.value < interval.lower.value:
                    # literal is contradicting with unit interval => skip literal
                    changed = True
                    continue

                if bound.value == interval.lower.value and (
                    bound.is_strict or interval.lower.is_strict
                ):
                    # literal is contradicting with unit interval => skip literal
                    changed = True
                    continue

        out_literals.add(literal)

    if len(out_literals) == 0:
        return pysmt.shortcuts.FALSE(), True

    return pysmt.shortcuts.Or(out_literals), changed


def _get_bound(
    left: FNode, op: InequalitySymbol, right: FNode
) -> Tuple[FNode, Bound, bool]:
    # (constant > variables)     -> upper, strict
    # (constant >= variables)    -> upper
    # (constant <= variables)    -> lower
    # (constant < variables)     -> lower, strict
    # (variables < constant)     -> upper, strict
    # (variables <= constant)    -> upper
    # (variables >= constant)    -> lower
    # (variables > constant)     -> lower, strict

    bound = Fraction()
    variables = None

    is_lower = True
    is_strict = False

    constant_left = left.is_constant()
    if constant_left:
        bound = pysmt_to_constant_value(left)
        variables = right
        if op == InequalitySymbol.GreaterThan or op == InequalitySymbol.GreaterEqual:
            is_lower = False
    else:
        bound = pysmt_to_constant_value(right)
        variables = left
        if op == InequalitySymbol.LessThan or op == InequalitySymbol.LessEqual:
            is_lower = False

    if op == InequalitySymbol.GreaterThan or op == InequalitySymbol.LessThan:
        is_strict = True

    return variables, Bound(value=bound, is_strict=is_strict), is_lower
