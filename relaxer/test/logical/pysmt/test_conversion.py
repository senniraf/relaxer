import unittest
from fractions import Fraction

from pysmt.shortcuts import And, Not, Symbol
from pysmt.typing import REAL

from relaxer.logical.lra import Inequality, InequalitySymbol, Sum, Summand, Variable
from relaxer.logical.pysmt.conversion import pysmt_conjunction_to_inequalities


class TestConversion(unittest.TestCase):
    def test_pysmt_conjunction_to_inequality(self):
        a, b, c, d = (
            Symbol("a", REAL),
            Symbol("b", REAL),
            Symbol("c", REAL),
            Symbol("d", REAL),
        )

        input_formula = And(
            0 <= a,
            0 <= b,
            0 <= c,
            0 <= d,
            a + b <= 4,
            2 < -d + c - b,
            d < 4,
            Not(-b <= 2),
            a - b - c <= 3,
            Not(3 < a),
        )

        expected_output = {
            Inequality(
                Sum((Summand(Fraction(1), Variable("a")),)),
                InequalitySymbol.GreaterEqual,
                Fraction(0),
            ),
            Inequality(
                Sum((Summand(Fraction(1), Variable("b")),)),
                InequalitySymbol.GreaterEqual,
                Fraction(0),
            ),
            Inequality(
                Sum((Summand(Fraction(1), Variable("c")),)),
                InequalitySymbol.GreaterEqual,
                Fraction(0),
            ),
            Inequality(
                Sum((Summand(Fraction(1), Variable("d")),)),
                InequalitySymbol.GreaterEqual,
                Fraction(0),
            ),
            Inequality(
                Sum(((Fraction(1), Variable("a")), (Fraction(1), Variable("b")))),  # type: ignore
                InequalitySymbol.LessEqual,
                Fraction(4),
            ),
            Inequality(
                Sum(((Fraction(-1), Variable("d")), (Fraction(1), Variable("c")), (Fraction(-1), Variable("b")))),  # type: ignore
                InequalitySymbol.GreaterThan,
                Fraction(2),
            ),
            Inequality(
                Sum((Summand(Fraction(1), Variable("d")),)),
                InequalitySymbol.LessThan,
                Fraction(4),
            ),
            Inequality(
                Sum((Summand(Fraction(-1), Variable("b")),)),
                InequalitySymbol.GreaterThan,
                Fraction(2),
            ),
            Inequality(
                Sum(((Fraction(1), Variable("a")), (Fraction(-1), Variable("b")), (Fraction(-1), Variable("c")))),  # type: ignore
                InequalitySymbol.LessEqual,
                Fraction(3),
            ),
            Inequality(
                Sum((Summand(Fraction(1), Variable("a")),)),
                InequalitySymbol.LessEqual,
                Fraction(3),
            ),
        }

        output = pysmt_conjunction_to_inequalities(input_formula)

        self.assertEquals(output, expected_output)
