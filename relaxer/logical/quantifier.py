from typing import Protocol
from relaxer.logical.iterator import TraceIterator

from relaxer.logical.lra import DNFFormula
from relaxer.statistics import StatsRecorder, MethodUser


class QuantifierEliminator(MethodUser, StatsRecorder, Protocol):
    def process(self, trace_iterator: TraceIterator) -> DNFFormula:
        ...
