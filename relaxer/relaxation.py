from fractions import Fraction
from numbers import Real
from time import process_time
from typing import Any, Dict, Set, Tuple
from relaxer.logical.iterator import TraceIterator
from relaxer.logical.quantifier import QuantifierEliminator
from relaxer.optimization.optimization import DisjunctiveOptimizer


def relax(
    cs_iterator: TraceIterator,
    qe: QuantifierEliminator,
    opt: DisjunctiveOptimizer,
    strict_epsilon: Fraction,
) -> Tuple[Set[Tuple[Real]], bool, Dict[str, float]]:
    stats: Dict[str, Any] = {}

    start = process_time()
    qf = qe.process(cs_iterator)
    stop = process_time()
    stats["total_tg_and_qe_runtime_s"] = stop - start
    stats["trace_generation_method"] = cs_iterator.used_method
    stats["quantifier_elimination_method"] = qe.used_method
    stats.update(qe.stats)

    objectives = cs_iterator.relaxation_variables
    stats["num_relaxations"] = len(objectives)
    stats["num_terms"] = len(qf.terms)

    start = process_time()
    optima, supported = opt.maximize_relaxation(objectives, qf, strict_epsilon)
    stop = process_time()
    stats["optimization_runtime_s"] = stop - start
    stats["supported_optima"] = supported
    stats["optimization_method"] = opt.used_method
    stats.update(opt.stats)

    return optima, supported, stats
