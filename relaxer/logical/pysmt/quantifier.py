import json
import time
from collections import defaultdict
from typing import Any, Dict, Iterable
import warnings

import pysmt.fnode
import pysmt.oracles
import pysmt.shortcuts

from relaxer import performance
from relaxer.logical.constraint_system import TimedRelaxedTraceConstraints
from relaxer.logical.iterator import TraceIterator
from relaxer.logical.lra import DNFFormula
from relaxer.logical.pysmt.conversion import (
    dnf_from_pysmt,
    trace_constraints_to_pysmt,
)
from relaxer.logical.pysmt.normalform import CNFTransformer, DNFTransformer
from relaxer.logical.pysmt.rip import propagate_real_intervals_cnf
from relaxer.io import DumpLocation, DumpLocationHandler


class QuantifierEliminator:
    """Class to build a DNF formula from a trace iterator by eliminating the quantifiers from the trace constraints."""

    def __init__(
        self,
        dump_handler: DumpLocationHandler,
        debug: bool = False,
    ) -> None:
        """Initialize the quantifier eliminator.

        Args:
            dump_handler (DumpLocationHandler): Dump location handler.
            debug (bool, optional): If true, intermediate results are checked for equivalence using the smt solver. Defaults to False.
        """
        self._debug = debug
        self._runtimes: Dict[str, float] = defaultdict(lambda: 0.0)

        self._trace_dump_loc = dump_handler.create_dump_location("trace")
        self._trace_formula_dump_loc = dump_handler.create_dump_location(
            "trace_formula"
        )
        self._qe_input_dump_loc = dump_handler.create_dump_location("qe_input")
        self._qe_output_dump_loc = dump_handler.create_dump_location("qe_output")
        self._rip_input_dump_loc = dump_handler.create_dump_location("rip_input")
        self._rip_output_dump_loc = dump_handler.create_dump_location("rip_output")
        self._result_cnf_formula_dump_loc = dump_handler.create_dump_location(
            "qf_cnf_formula"
        )
        self._result_dnf_formula_dump_loc = dump_handler.create_dump_location(
            "qf_dnf_formula"
        )

    @property
    def used_method(self) -> str:
        """Return the name of the used quantifier elimination method.

        Returns:
            str: 'MATHSAT Fourier-Motzkin'
        """
        return "MATHSAT Fourier-Motzkin"

    def process(self, trace_iterator: TraceIterator) -> DNFFormula:
        """Iterate over the trace constraints generated by the trace iterator, convert them to a smt formula, eliminate the quantifiers and returns the result as a DNF formula.

        Args:
            trace_iterator (TraceIterator): Trace iterator that generates the trace constraints.

        Returns:
            DNFFormula: DNF formula representing the relaxed traces.
        """
        timed_iterator = performance.TimedIterator(trace_iterator)

        formulas = set()

        for w, trace_constraints in enumerate(timed_iterator):
            self._width = w + 1
            self._runtimes["trace_generation"] += timed_iterator.next_runtime

            start = QuantifierEliminator._timer()
            self._trace_dump_loc.write_dump(
                f"{w}.json", json.dumps(trace_constraints.to_json())
            )
            qe_input = self._convert_to_pysmt(w, trace_constraints)
            self._runtimes["processing"] += QuantifierEliminator._timer() - start

            qf, runtime = performance.process_timeit(
                self._eliminate_quantifiers, w, qe_input
            )
            self._runtimes["quantifier_elimination"] += runtime

            start = QuantifierEliminator._timer()
            formula = self._post_process(w, qf)
            formulas.add(formula)
            self._runtimes["processing"] += QuantifierEliminator._timer() - start

        self._runtimes["trace_generation"] += timed_iterator.iter_runtime

        dnf_formula, runtime = performance.process_timeit(
            self._convert_to_dnf, formulas
        )
        self._runtimes["processing"] += runtime

        self._result_dnf_formula_dump_loc.write_dump(
            "qf_free_dnf_formula.txt", f"{dnf_formula}\n"
        )

        return dnf_formula

    @property
    def stats(self) -> Dict[str, Any]:
        """Returns a dictionary containing the statistics of the quantifier elimination process.

        Returns:
            Dict[str, Any]: Dictionary containing the statistics of the quantifier elimination process.
        """
        d = {f"{s}_runtime_s": runtime for s, runtime in self._runtimes.items()}
        d["number_of_traces"] = self._width
        return d

    @staticmethod
    def _timer() -> float:
        return time.process_time()

    def _convert_to_dnf(self, formulas: Iterable[pysmt.fnode.FNode]) -> DNFFormula:
        conjunction = CNFTransformer().transform(pysmt.shortcuts.And(*formulas))

        rip_output = propagate_real_intervals_cnf(conjunction)
        formula = CNFTransformer().transform(rip_output)  # In order to absorpt clauses

        QuantifierEliminator._smt2_dump(
            self._result_cnf_formula_dump_loc, "result_cnf", formula
        )

        dnf_formula = DNFTransformer().transform(formula)

        if self._debug:
            assert pysmt.shortcuts.is_valid(
                pysmt.shortcuts.Iff(conjunction, dnf_formula)
            )

        return dnf_from_pysmt(dnf_formula)

    def _post_process(self, w: int, qf: pysmt.fnode.FNode) -> pysmt.fnode.FNode:
        rip_input = CNFTransformer().transform(qf)
        if self._debug:
            assert pysmt.shortcuts.is_valid(pysmt.shortcuts.Iff(qf, rip_input))

        QuantifierEliminator._smt2_dump(self._rip_input_dump_loc, f"{w}", rip_input)

        rip_output = propagate_real_intervals_cnf(rip_input)
        if self._debug:
            assert pysmt.shortcuts.is_valid(pysmt.shortcuts.Iff(rip_input, rip_output))

        QuantifierEliminator._smt2_dump(self._rip_output_dump_loc, f"{w}", rip_output)

        return rip_output

    def _eliminate_quantifiers(
        self, w: int, qe_input: pysmt.fnode.FNode
    ) -> pysmt.fnode.FNode:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            qfree = pysmt.shortcuts.qelim(qe_input, solver_name="msat_fm")

        if not pysmt.oracles.QuantifierOracle().is_qf(qfree):
            raise RuntimeError(
                "Quantifier elimination failed. Returned formula is not quantifier free!"
            )

        QuantifierEliminator._smt2_dump(self._qe_output_dump_loc, f"{w}", qfree)

        return qfree

    def _convert_to_pysmt(
        self, w: int, trace_constraints: TimedRelaxedTraceConstraints
    ) -> pysmt.fnode.FNode:
        trace_formula = trace_constraints_to_pysmt(trace_constraints)
        QuantifierEliminator._smt2_dump(
            self._trace_formula_dump_loc, f"{w}", trace_formula
        )

        QuantifierEliminator._smt2_dump(self._qe_input_dump_loc, f"{w}", trace_formula)

        return trace_formula

    @staticmethod
    def _smt2_dump(loc: DumpLocation, name: str, formula: pysmt.fnode.FNode):
        loc.write_dump(
            f"{name}.smt2", pysmt.shortcuts.to_smtlib(formula, daggify=False)
        )
