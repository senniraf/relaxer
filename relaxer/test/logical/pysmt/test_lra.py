import unittest

from pysmt.shortcuts import Symbol, Plus, Real, Times, LE, LT, Equals, Minus
from pysmt.typing import REAL

from relaxer.logical.pysmt.lra import NormalFormTransformer


class TestNormalFormTransformer(unittest.TestCase):
    def test_explicit_1_coefficient(self):
        x = Symbol("x", REAL)
        formula = x
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(normal_form, Times(Real(1), x))

    def test_minus(self):
        x_0 = Symbol("x_0", REAL)
        x_1 = Symbol("x_1", REAL)
        formula = Minus(x_0, x_1)
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(normal_form, Plus(Times(Real(1), x_0), Times(Real(-1), x_1)))

    def test_minus_constant(self):
        formula = Minus(Real(2), Real(1))
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(normal_form, Real(1))

    def test_times_constant_left(self):
        x = Symbol("x", REAL)
        formula = Times(x, Real(2))
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(normal_form, Times(Real(2), x))

    def test_times_multiple_constants_left(self):
        x = Symbol("x", REAL)
        formula = Times(x, Real(2), Real(3))
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(normal_form, Times(Real(6), x))

    def test_times_nested(self):
        x = Symbol("x", REAL)
        formula = Times(Real(2), Real(3), Times(Real(2), x))
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(normal_form, Times(Real(12), x))

    def test_plus_alphabetic_ordering(self):
        x_0 = Symbol("x_0", REAL)
        x_1 = Symbol("x_1", REAL)
        formula = Plus(x_1, x_0)
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(normal_form, Plus(Times(Real(1), x_0), Times(Real(1), x_1)))

    def test_plus_summarize_coefficients(self):
        x_0 = Symbol("x_0", REAL)
        x_1 = Symbol("x_1", REAL)
        formula = Plus(Times(Real(2), x_0), Times(Real(3), x_1), Times(Real(4), x_0))
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(normal_form, Plus(Times(Real(6), x_0), Times(Real(3), x_1)))

    def test_plus_nested(self):
        x_0 = Symbol("x_0", REAL)
        x_1 = Symbol("x_1", REAL)
        formula = Plus(Plus(x_0, x_1), Real(2))
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(
            normal_form, Plus(Real(2), Times(Real(1), x_0), Times(Real(1), x_1))
        )

    def test_distributivity(self):
        x_0 = Symbol("x_0", REAL)
        x_1 = Symbol("x_1", REAL)

        formula = Times(Plus(Times(Real(2), x_0), x_1), Real(2), Plus(Real(2), Real(3)))
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(normal_form, Plus(Times(Real(20), x_0), Times(Real(10), x_1)))

    def test_distributivity_with_constant_and_variable(self):
        x = Symbol("x", REAL)

        formula = Times(Plus(x, Real(2)), Real(2))
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(normal_form, Plus(Real(4), Times(Real(2), x)))

    def test_minus_plus_combination(self):
        x_0 = Symbol("x_0", REAL)
        x_1 = Symbol("x_1", REAL)
        x_2 = Symbol("x_2", REAL)
        formula = Minus(x_0, Plus(x_1, Times(x_2, Real(2))))
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(
            normal_form,
            Plus(Times(Real(1), x_0), Times(Real(-1), x_1), Times(Real(-2), x_2)),
        )

    def test_minus_nested_plus(self):
        x_0 = Symbol("x_0", REAL)
        x_1 = Symbol("x_1", REAL)
        formula = Minus(Plus(Real(3), Times(x_1)), Plus(Real(2), x_0))
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(
            normal_form, Plus(Real(1), Times(Real(-1), x_0), Times(Real(1), x_1))
        )

    def test_minus_alphabetic_ordering(self):
        x_0 = Symbol("x_0", REAL)
        x_1 = Symbol("x_1", REAL)
        formula = Minus(x_1, x_0)
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(normal_form, Plus(Times(Real(-1), x_0), Times(Real(1), x_1)))

    def test_lower_equal_constants_right(self):
        self._inequality_constants_right_template(LE)

    def test_lower_than_constants_right(self):
        self._inequality_constants_right_template(LT)

    def test_equals_constants_right(self):
        self._inequality_constants_right_template(Equals)

    def _inequality_constants_right_template(self, operator):
        x_0 = Symbol("x_0", REAL)
        x_1 = Symbol("x_1", REAL)
        formula = operator(Plus(Times(Real(2), x_1), Real(3)), Plus(x_0, Real(2)))
        sut = NormalFormTransformer()
        normal_form = sut.walk(formula)
        self.assertEquals(
            normal_form,
            operator(
                Plus(Times(Real(-1), x_0), Times(Real(2), x_1)), Plus(x_0, Real(-1))
            ),
        )
