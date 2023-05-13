from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Sequence, Set, Tuple

from relaxer.logical.formula import Formula
from relaxer.logical.lra import Inequality, RelaxationVariable, Variable
from relaxer.ta import SymbolicState


@dataclass
class TimedRelaxedTraceConstraints:
    symbolic_trace: Tuple[SymbolicState]
    relaxation_vars: FrozenSet[RelaxationVariable]
    delta_variables: Tuple[Variable]
    inequalities: Tuple[FrozenSet[Inequality]]
    property_formulas: Tuple[FrozenSet[Formula]]

    @property
    def all_inequalities(self) -> Set[Inequality]:
        return set().union(*self.inequalities)

    @property
    def all_property_formulas(self) -> Set[Formula]:
        return set().union(*self.property_formulas)

    def to_json(self) -> Dict[str, Any]:
        return {
            "trace": [str(state) for state in self.symbolic_trace],
            "inequalities": [str(ineq) for ineq in self.all_inequalities],
            "property_formulas": [
                str(prop_formula) for prop_formula in self.all_property_formulas
            ],
        }


@dataclass
class TimedRelaxedConstraintSystem:
    traces: Sequence[TimedRelaxedTraceConstraints]

    @property
    def width(self) -> int:
        return len(self.traces)

    def get_delta_variables_for(self, width: int) -> Sequence[Variable]:
        return self.traces[width].delta_variables

    def get_trace_inequalities_for(self, width: int) -> Set[Inequality]:
        return self.traces[width].all_inequalities

    def get_property_formulas_for(self, width: int) -> Set[Formula]:
        return self.traces[width].all_property_formulas
