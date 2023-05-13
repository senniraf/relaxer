from fractions import Fraction
from math import inf
from numbers import Real
from typing import Collection, Dict, FrozenSet, Sequence, Set, Tuple

import cdd
import numpy as np

from relaxer.logical.lra import DNFFormula, Inequality, RelaxationVariable
from relaxer.optimization.pareto import ParetoSet, dominates
from relaxer.optimization.scipy import ScalarizationOptimizer
from relaxer.io import DumpLocationHandler

_V_FORMAT_TYPE_IDX = 0
_V_FORMAT_RAY_TYPE = 0
_V_FORMAT_VERTEX_TYPE = 1


class Optimizer:
    def __init__(self, grid_points: int, dump_handler: DumpLocationHandler) -> None:
        self.grid_points = grid_points
        self._input_dump_location = dump_handler.create_dump_location("pycddlib_input")
        self._output_dump_location = dump_handler.create_dump_location(
            "pycddlib_output"
        )

    def maximize_con_relaxation(
        self,
        objectives: Sequence[RelaxationVariable],
        conj_constraints: Collection[Inequality],
        strict_epsilon: Fraction,
        i: int,
    ) -> Tuple[Set[Tuple[Real]], bool]:
        output = ParetoSet()

        self._maximize_conj_constraints(
            objectives, strict_epsilon, 0, conj_constraints, output
        )

        return output.to_set(), True

    def maximize_relaxation(
        self,
        objectives: Sequence[RelaxationVariable],
        constraints: DNFFormula,
        strict_epsilon: Fraction,
    ) -> Tuple[Set[Tuple[Real]], bool]:
        n_objectives = len(objectives)

        if len(constraints.terms) == 1:
            return self.maximize_con_relaxation(
                objectives, constraints.terms[0], strict_epsilon, 0
            )

        output = ParetoSet()
        for term_idx, conj_constraints in enumerate(constraints.terms):
            self._maximize_conj_constraints(
                objectives,
                strict_epsilon,
                term_idx,
                conj_constraints,
                output,
            )

        return output.to_set(), False

    def _maximize_conj_constraints(
        self,
        objectives: Sequence[RelaxationVariable],
        strict_epsilon: Fraction,
        term_idx: int,
        conj_constraints: Collection[Inequality],
        output: ParetoSet,
    ):
        n_objectives = len(objectives)
        vertices, rays, adjacency = self._get_polygon_surfaces(
            objectives, conj_constraints, strict_epsilon, term_idx
        )

        if len(vertices) == 0 and len(rays) == 0:
            # No solution
            return

        unbounded_mask = self._get_unbounded_mask(objectives, rays)

        if len(vertices) == 0:
            output.add(tuple(np.zeros(n_objectives) + unbounded_mask))
            return

        dominated = [False for _ in vertices]

        for i, v1 in enumerate(vertices):
            for j, v2 in enumerate(vertices):
                if i == j:
                    continue
                v1_array = np.array(v1) + unbounded_mask
                v2_array = np.array(v2) + unbounded_mask
                if dominates(tuple(v2_array), tuple(v1_array)):
                    dominated[i] = True
                    break

        thetas = np.linspace(1, 0, self.grid_points).reshape((1, self.grid_points))

        for i, v in enumerate(vertices):
            if dominated[i]:
                continue

            output.add(tuple(np.array(v) + unbounded_mask))
            for j in adjacency[i]:
                if j >= len(vertices) or j <= i or dominated[j]:
                    continue

                np_adj_v = np.reshape(np.array(vertices[j]), (n_objectives, 1))
                np_v = np.reshape(np.array(v), (n_objectives, 1))

                line_segment = np_v * thetas + np_adj_v * (1 - thetas)
                for point in line_segment.T:
                    to_add = point + unbounded_mask
                    output.add(tuple(to_add))

    def _get_polygon_surfaces(
        self,
        objectives: Sequence[RelaxationVariable],
        conj_constraints: Collection[Inequality],
        strict_epsilon: Fraction,
        i: int,
    ) -> Tuple[Sequence[Tuple[Real]], Sequence[Tuple[Real]], Sequence[FrozenSet[int]]]:
        A, b = ScalarizationOptimizer._to_A_b(
            objectives, conj_constraints, strict_epsilon
        )

        mat = cdd.Matrix(np.insert(-A, 0, b, axis=1), number_type="fraction")
        mat.rep_type = cdd.RepType.INEQUALITY
        poly = cdd.Polyhedron(mat)
        self._input_dump_location.write_dump(f"{i}.txt", str(poly))
        ext = poly.get_generators()
        self._output_dump_location.write_dump(f"{i}.txt", str(ext))
        vertices = []
        rays = []
        for row in ext:
            if row[_V_FORMAT_TYPE_IDX] == _V_FORMAT_VERTEX_TYPE:
                vertices.append(row[_V_FORMAT_TYPE_IDX + 1 :])
            else:
                rays.append(row[_V_FORMAT_TYPE_IDX + 1 :])

        adjacency = poly.get_adjacency()
        return vertices, rays, adjacency

    def _get_unbounded_mask(self, objectives, rays):
        unbounded_mask = np.zeros(len(objectives))
        for ray in rays:
            for i, coord in enumerate(ray):
                if coord != 0:
                    unbounded_mask[i] = inf
        return unbounded_mask

    @property
    def stats(self) -> Dict[str, float]:
        return {}

    @property
    def used_method(self) -> str:
        return "CDD"
