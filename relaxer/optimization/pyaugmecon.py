from collections import defaultdict
from fractions import Fraction
from io import StringIO
from math import inf
from numbers import Real
from pathlib import Path
from typing import Any, Collection, Dict, Optional, Sequence, Set, Tuple

import pyomo.environ as pyo
from pyaugmecon import PyAugmecon

from relaxer.logical.lra import (
    DNFFormula,
    Inequality,
    InequalitySymbol,
    RelaxationVariable,
    Variable,
)
from relaxer.io import DumpLocationHandler, EmptyDumpLocationHandler
from relaxer.optimization.pareto import ParetoSet
from relaxer.optimization import pycddlib


class Optimizer:
    def __init__(
        self,
        grid_points: int,
        dump_handler: DumpLocationHandler,
        pyaugmecon_logging_folder: Optional[Path],
    ) -> None:
        self._grid_points = grid_points
        self._model_dump = dump_handler.create_dump_location("pyaugmecon_input")
        self._logs_dir = Path("/dev/null")
        if pyaugmecon_logging_folder is not None:
            pyaugmecon_logging_folder.mkdir(parents=True, exist_ok=True)
            self._logs_dir = pyaugmecon_logging_folder

        self._runtimes: Dict[str, float] = defaultdict(lambda: 0.0)

    def maximize_relaxation(
        self,
        objectives: Sequence[RelaxationVariable],
        constraints: DNFFormula,
        strict_epsilon: Fraction,
    ) -> Tuple[Set[Tuple[Real]], bool]:

        output = ParetoSet()
        for i, conj_constraints in enumerate(constraints.terms):
            trivial_solutions = self._get_trivial_solutions(
                conj_constraints, objectives, strict_epsilon, i
            )

            is_upper_bounded = [True for _ in objectives]

            for solution in trivial_solutions:
                output.add(solution)
                for i, value in enumerate(solution):
                    if value == inf:
                        is_upper_bounded[i] = False

            if len(trivial_solutions) <= 1:
                continue

            model = pyo.ConcreteModel()

            model.rho = pyo.Var(
                [i + 1 for i, _ in enumerate(objectives)], domain=pyo.NonNegativeReals
            )

            var_to_pyo_var: Dict[Variable, Any] = {
                objective: model.rho[i + 1] for i, objective in enumerate(objectives)
            }

            model.constraints = pyo.ConstraintList()

            for ineq in conj_constraints:
                factor = 1.0
                if (
                    ineq.symbol == InequalitySymbol.GreaterEqual
                    or ineq.symbol == InequalitySymbol.GreaterThan
                ):
                    factor = -1.0

                s = sum(
                    (
                        float(summand.coefficient) * var_to_pyo_var[summand.var]
                        for summand in ineq.left.summands
                    )
                )

                offset = Fraction(0)

                if ineq.is_strict:
                    offset = strict_epsilon

                model.constraints.add(s * factor <= ineq.right - float(offset))

            model.obj_list = pyo.ObjectiveList()
            for i, objective in enumerate(objectives):
                if not is_upper_bounded[i]:
                    continue

                model.obj_list.add(expr=var_to_pyo_var[objective], sense=pyo.maximize)

            for _, entry in enumerate(model.obj_list):
                model.obj_list[entry].deactivate()  # type: ignore

            dump_str = ""
            string_io = StringIO(dump_str)
            model.pprint(string_io)
            self._model_dump.write_dump(f"{i}.txt", string_io.getvalue())

            nadir_points = [0 for _ in range(len(model.obj_list) - 1)]

            opts = {
                "grid_points": self._grid_points,
                "nadir_points": nadir_points,
                "logging_folder": self._logs_dir,
            }
            solver_opts = {}

            A = PyAugmecon(model, opts, solver_opts)
            A.solve()
            sols = A.unique_pareto_sols
            for sol in sols:
                solution = []
                idx = 0
                for i, var in enumerate(objectives):
                    if not is_upper_bounded[i]:
                        solution.append(inf)
                        continue
                    solution.append(sol[idx])
                    idx += 1
                output.add(tuple(solution))

        return output.to_set(), False

    def _get_trivial_solutions(
        self,
        conj_constraints: Collection[Inequality],
        objectives: Sequence[RelaxationVariable],
        strict_epsilon: Fraction,
        i: int,
    ) -> Collection[Tuple[Real]]:
        opt = pycddlib.Optimizer(self._grid_points, EmptyDumpLocationHandler())
        solutions, _ = opt.maximize_con_relaxation(
            objectives, conj_constraints, strict_epsilon, i
        )

        return solutions

    @property
    def stats(self) -> Dict[str, Any]:
        return self._runtimes

    @property
    def used_method(self) -> str:
        return "AUGMECON"
