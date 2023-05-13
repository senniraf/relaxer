from collections import defaultdict
from fractions import Fraction
from typing import Tuple
from numpy import append
from pysmt.fnode import FNode
from pysmt.walkers import IdentityDagWalker
from pysmt.formula import FormulaManager
import pysmt.operators


class NormalFormTransformer(IdentityDagWalker):
    """Transforms the predicates of a linear arithmetic formula with quantifiers into an equivalent normal form.
    Every predicate will be of the form:

    Σaᵢxᵢ ~ b

    where aᵢ are real constants, xᵢ are real variables, b is a real constant and ~ is in {<, ≤, =}.
    """

    @property
    def _manager(self) -> FormulaManager:
        return self.env.formula_manager

    def walk_le(self, formula, args, **kwargs):
        return self._inequality_constants_right(self._manager.LE, args)

    def walk_lt(self, formula, args, **kwargs):
        return self._inequality_constants_right(self._manager.LT, args)

    def walk_equals(self, formula, args, **kwargs):
        return self._inequality_constants_right(self._manager.Equals, args)

    def walk_plus(self, formula, args, **kwargs):
        var_coeff = defaultdict(lambda: Fraction(0))
        constant = Fraction(0)
        for arg in args:
            if arg.is_real_constant():
                constant += Fraction(arg.constant_value())
                continue

            if arg.is_plus():
                for summand in arg.args():
                    if summand.is_real_constant():
                        constant += Fraction(summand.constant_value())
                        continue

                    coefficient, variable = self._coefficient_variable_pair(summand)
                    var_coeff[variable] += coefficient
                continue

            assert arg.is_times()
            coefficient, variable = self._coefficient_variable_pair(arg)

            var_coeff[variable] += coefficient

        summands = (
            self._manager.Times(self._manager.Real(coefficient), variable)
            for variable, coefficient in sorted(
                filter(lambda item: item[1] != 0, var_coeff.items()),
                key=lambda item: item[0].symbol_name(),
            )
        )

        if constant == 0:
            return self._manager.Plus(summands)

        return self._manager.Plus(self._manager.Real(constant), *summands)

    def walk_minus(self, formula, args, **kwargs):
        minuend = args[0]
        subtrahend = args[1]
        if (
            subtrahend.is_real_constant()
            or subtrahend.is_symbol()
            or subtrahend.is_times()
        ):
            return self.walk_plus(formula, [minuend, self._flip_sign(subtrahend)])

        if not subtrahend.is_plus():
            raise self._not_lra_error(formula)

        summands = [minuend]
        for summand in subtrahend.args():
            summands.append(self._flip_sign(summand))

        return self.walk_plus(formula, summands)

    def walk_times(self, formula, args, **kwargs):
        coefficient = Fraction(1)
        variable = None
        for factor in args:
            if factor.is_real_constant():
                coefficient *= Fraction(factor.constant_value())
                continue

            if factor.is_plus():
                # Distribute the coefficient over the summands
                # Because we only allow linear arithmetic there is only one sum in the multiplication
                summands = []
                sum = factor
                factor = Fraction(1)

                for constant in args:
                    if constant == sum:
                        continue
                    if not constant.is_real_constant():
                        raise self._not_lra_error(formula)

                    factor *= Fraction(constant.constant_value())

                for summand in sum.args():
                    if summand.is_real_constant():
                        summands.append(
                            self._manager.Real(
                                Fraction(summand.constant_value()) * factor
                            )
                        )
                        continue

                    if summand.is_symbol():
                        summands.append(
                            self._manager.Times(self._manager.Real(factor), summand)
                        )
                        continue

                    if not summand.is_times():
                        raise self._not_lra_error(formula)

                    coefficient, variable = self._coefficient_variable_pair(summand)
                    summands.append(
                        self._manager.Times(
                            self._manager.Real(coefficient * factor),
                            variable,
                        )
                    )

                return self._manager.Plus(*summands)

            if factor.is_times():
                inner_coefficient, variable = self._coefficient_variable_pair(factor)
                coefficient *= inner_coefficient
                continue

            assert factor.is_symbol()
            if variable is not None:
                raise self._not_lra_error(formula)
            variable = factor

        if variable == None:
            return self._manager.Real(coefficient)

        return self._manager.Times(self._manager.Real(coefficient), variable)

    def walk_symbol(self, formula, args, **kwargs):
        if not formula.symbol_type().is_real_type():
            return super().walk_symbol(formula, args, **kwargs)

        return self._manager.Times(self._manager.Real(1), formula)

    def _inequality_constants_right(self, operator, args) -> FNode:
        left = args[0]
        right = args[1]
        intermediate_left = self.walk_minus(
            self._manager.Minus(left, right), [left, right]
        )

        if intermediate_left.is_real_constant():
            return operator(
                self._manager.Real(0),
                self._manager.Real(-1 * intermediate_left.constant_value()),
            )

        new_right = self._manager.Real(0)
        new_left = intermediate_left
        if intermediate_left.is_plus() and intermediate_left.arg(0).is_real_constant():
            new_right = self._manager.Real(
                -1 * intermediate_left.arg(0).constant_value()
            )
            new_left = self._manager.Plus(*intermediate_left.args()[1:])

        return operator(new_left, new_right)

    def _not_lra_error(self, formula):
        return ValueError(f"Formula {formula} is not of type linear real arithmetic")

    def _flip_sign(self, formula: FNode):
        if formula.is_symbol():
            return self._manager.Times(self._manager.Real(-1), formula)

        if formula.is_real_constant():
            return self._manager.Real(-1 * Fraction(formula.constant_value()))

        assert formula.is_times()
        coefficient, variable = self._coefficient_variable_pair(formula)
        return self._manager.Times(
            self._manager.Real(-1 * coefficient),
            variable,
        )

    def _coefficient_variable_pair(
        self, multiplication: FNode
    ) -> Tuple[Fraction, FNode]:
        assert multiplication.is_times()
        coefficient = multiplication.arg(0)
        variable = multiplication.arg(1)
        assert coefficient.is_real_constant()
        assert variable.is_symbol()
        return Fraction(coefficient.constant_value()), variable


class Simplifier(NormalFormTransformer):
    """Simplifies a LRA formula by removing contradictions and
    tautologies. The method is sound but not complete."""

    def __init__(self) -> None:
        super().__init__()

    @property
    def _manager(self):
        return self.env.formula_manager

    def walk_and(self, formula, args, **kwargs):
        lower_bounds = {}
        upper_bounds = {}
        for arg in args:
            lra_predicate = arg
            negated = False
            if arg.is_not():
                negated = True
                lra_predicate = arg.arg(0)

            if not (
                lra_predicate.is_equals()
                or lra_predicate.is_le()
                or lra_predicate.is_lt()
            ):
                return formula

        return formula

    def walk_or(self, formula, args, **kwargs):
        if True in args:
            return self._manager.TRUE()
        return self._manager.Or(args)
