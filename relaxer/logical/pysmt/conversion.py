from fractions import Fraction
from numbers import Real
from typing import List, Set, Tuple

import pysmt.shortcuts as pysmt
from pysmt.fnode import FNode
from pysmt.typing import REAL

from relaxer.logical.constraint_system import TimedRelaxedTraceConstraints
from relaxer.logical.formula import TRUE, And, BooleanConstant, Formula, Not, Or
from relaxer.logical.lra import (
    DNFFormula,
    Inequality,
    InequalitySymbol,
    Sum,
    Summand,
    Variable,
    variable_from_string,
)


def trace_constraints_to_pysmt(
    trace_constraints: TimedRelaxedTraceConstraints,
) -> FNode:
    relaxation_constraints = [
        variable_to_pysmt(var) >= 0 for var in trace_constraints.relaxation_vars
    ]
    deltas = [variable_to_pysmt(var) for var in trace_constraints.delta_variables]
    trace_formula = pysmt.And(
        [inequality_to_pymst(ineq) for ineq in trace_constraints.all_inequalities]
        + [variable_to_pysmt(var) >= 0 for var in trace_constraints.delta_variables]
    )
    properties_formula = pysmt.And(
        (
            formula_to_pysmt(formula)
            for formula in trace_constraints.all_property_formulas
        )
    )

    return pysmt.And(
        pysmt.ForAll(deltas, pysmt.Implies(trace_formula, properties_formula)),
        *relaxation_constraints,
    )


def formula_to_pysmt(input: Formula) -> FNode:
    if isinstance(input, And):
        return pysmt.And((formula_to_pysmt(argument) for argument in input.arguments))
    elif isinstance(input, Or):
        return pysmt.Or((formula_to_pysmt(argument) for argument in input.arguments))
    elif isinstance(input, Not):
        return pysmt.Not((formula_to_pysmt(input.argument)))
    elif isinstance(input, BooleanConstant):
        if input == TRUE:
            return pysmt.TRUE()
        return pysmt.FALSE()
    elif isinstance(input, Inequality):
        return inequality_to_pymst(input)

    raise ValueError(f"Unknown Formula: {input}")


def inequality_to_pymst(ineq: Inequality) -> FNode:
    summands = (summand_to_pymst(summand) for summand in ineq.left.summands)
    sum = pysmt.Plus(pysmt.Real(0), *summands)

    if ineq.symbol == InequalitySymbol.GreaterThan:
        return pysmt.GT(sum, pysmt.Real(ineq.right))
    elif ineq.symbol == InequalitySymbol.GreaterEqual:
        return pysmt.GE(sum, pysmt.Real(ineq.right))
    elif ineq.symbol == InequalitySymbol.LessEqual:
        return pysmt.LE(sum, pysmt.Real(ineq.right))
    elif ineq.symbol == InequalitySymbol.LessThan:
        return pysmt.LT(sum, pysmt.Real(ineq.right))
    else:
        raise ValueError(f"Unsupported InequalitySymbol: {ineq.symbol}")


def summand_to_pymst(summand: Summand) -> FNode:
    var = variable_to_pysmt(summand.var)
    coefficient = summand.coefficient

    return coefficient * var


def variable_to_pysmt(var: Variable) -> FNode:
    return pysmt.Symbol(var.identifier, REAL)


def dnf_from_pysmt(pysmt_dnf: FNode) -> DNFFormula:
    conjunctions = pysmt_dnf.args()
    if pysmt_dnf.is_and() or not pysmt_dnf.is_bool_op():
        conjunctions = [pysmt_dnf]

    constraints = set()
    for conjunction in conjunctions:
        constraints.add(frozenset(pysmt_conjunction_to_inequalities(conjunction)))

    return DNFFormula(terms=tuple(constraints))


def pysmt_conjunction_to_inequalities(conjunction: FNode) -> Set[Inequality]:
    if not conjunction.is_bool_op():
        return {inequality_from_pysmt(conjunction)}

    assert conjunction.is_and()

    inequalities = set(
        (inequality_from_pysmt(pysmt_inequality))
        for pysmt_inequality in conjunction.args()
    )
    return inequalities


def inequality_from_pysmt(pysmt_inequality: FNode) -> Inequality:
    left, symbol, right = get_inequality_triple(pysmt_inequality)

    if right.is_constant():
        bound = pysmt_to_constant_value(right)
        variables = left
    elif left.is_constant():
        bound = pysmt_to_constant_value(left)
        variables = right
        symbol = symbol.turned()
    else:
        bound = 0
        variables = pysmt.Minus(left, right)

    sum = Sum(tuple(pysmt_to_summands(variables)))

    return Inequality(left=sum, symbol=symbol, right=bound)  # type: ignore


def pysmt_to_summands(pysmt_sum: FNode) -> List[Summand]:
    if pysmt_sum.is_symbol():
        return [Summand(Fraction(1), pysmt_to_variable(pysmt_sum))]

    if pysmt_sum.is_times():
        pysmt_coeff = pysmt_sum.arg(0)
        pysmt_var = pysmt_sum.arg(1)

        if not pysmt_coeff.is_constant():
            # coefficient is right
            pysmt_coeff = pysmt_sum.arg(1)
            pysmt_var = pysmt_sum.arg(0)

        coefficient = pysmt_to_constant_value(pysmt_coeff)
        var = pysmt_to_variable(pysmt_var)

        return [Summand(coefficient, var)]

    if pysmt_sum.is_minus():
        left = pysmt_sum.arg(0)
        negated = pysmt_sum.arg(1)

        return pysmt_to_summands(left) + pysmt_to_summands(-1 * negated)

    if not pysmt_sum.is_plus():
        raise ValueError(
            f"Unexpected relation {pysmt_sum}. Expected linear real relation."
        )

    summands = []
    for arg in pysmt_sum.args():
        summands += pysmt_to_summands(arg)
    return summands


def pysmt_to_variable(symbol: FNode):
    return variable_from_string(symbol.symbol_name())


def pysmt_to_constant_value(constant: FNode) -> Real:
    value = constant.constant_value()
    if constant.is_int_constant():
        value = Fraction(constant.constant_value(), 1)
    return value


def get_inequality_triple(literal: FNode) -> Tuple[FNode, InequalitySymbol, FNode]:
    """Extracts the components of the inequality from the given literal.

    Args:
        literal (FNode): The literal to extract the inequality from.

    Returns:
        Tuple[FNode, _Operator, FNode]: A triple of the form (left, operator, right).
    """

    inequality = literal
    negated = literal.is_not()
    if negated:
        inequality = literal.arg(0)

    if not (inequality.is_lt or inequality.is_le):
        raise ValueError(f"Unexpected literal f{literal} in LRA-Formula")

    if inequality.is_lt() and not negated:
        return inequality.arg(0), InequalitySymbol.LessThan, inequality.arg(1)
    elif inequality.is_le() and not negated:
        return inequality.arg(0), InequalitySymbol.LessEqual, inequality.arg(1)
    elif inequality.is_lt() and negated:
        return inequality.arg(0), InequalitySymbol.GreaterEqual, inequality.arg(1)
    else:
        # inequality.is_le() and negated
        return inequality.arg(0), InequalitySymbol.GreaterThan, inequality.arg(1)
