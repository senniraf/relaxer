from datetime import datetime
from fractions import Fraction
from pathlib import Path

from relaxer.logical import pysmt
from relaxer.logical.iterator import DFSTraceIterator
from relaxer.optimization import pyaugmecon, pycddlib
from relaxer.optimization.optimization import HybridOptimizer
from relaxer.io import (
    DirectoryLocationHandler,
    EmptyDumpLocationHandler,
    EmptyOutput,
    JSONFileOutput,
    StdOutOutput,
)
from relaxer.relaxation import relax
from relaxer.tracing.uppyyl import UppyylTASystem
from relaxer import cli
from relaxer.tracing.uppyyl.system import (
    get_relaxation_for_bounds_of_system,
)


def main():
    config = cli.parse_command_line()
    grid_points = 2

    output = StdOutOutput()
    if config.output.type_ == "file":
        output = JSONFileOutput(Path(config.output.path))

    stats_output = EmptyOutput()
    if config.stats_config is not None:
        if config.stats_config.type_ == "json":
            stats_output = JSONFileOutput(Path(config.stats_config.path))

    debug = config.debug
    dump = EmptyDumpLocationHandler()

    for input in config.inputs:
        timestamp = datetime.now().astimezone()
        iso_timestamp = timestamp.isoformat()

        if config.dump_config is not None:
            if config.dump_config.type_ == "directory":
                dump = DirectoryLocationHandler(
                    Path(config.dump_config.path)
                    / timestamp.strftime("%Y-%m-%d_%H-%M-%S-%f")
                )

        logs_path = None
        if isinstance(dump, DirectoryLocationHandler):
            logs_path = dump.create_dump_location("pyaugmecon_logs").path

        irs = input.invariant_relaxations
        grs = input.guard_relaxations
        if input.relax_all:
            irs_unsorted, grs_unsorted = get_relaxation_for_bounds_of_system(
                input.model
            )

            irs = sorted(irs_unsorted, key=lambda ir: str(ir))
            grs = sorted(grs_unsorted, key=lambda gr: str(gr))

        system = UppyylTASystem(input.model, irs, grs)
        cs_iterator = DFSTraceIterator(system, input.depth)

        qe = pysmt.QuantifierEliminator(dump, debug)

        # dnf_optimizer = pyaugmecon.Optimizer(grid_points, dump, logs_path)
        conj_optimizer = pycddlib.Optimizer(grid_points, dump)

        # opt = HybridOptimizer(dnf_optimizer, conj_optimizer)
        opt = conj_optimizer

        optima, supported, stats = relax(cs_iterator, qe, opt, Fraction(1, 10))
        stats["depth"] = input.depth
        stats["grid_points"] = grid_points
        stats["num_solutions"] = len(optima)

        sorted_optima = sorted(optima, reverse=True)

        output.write_solutions(
            sorted_optima,
            supported,
            input.model,
            irs,
            grs,
            input.depth,
            iso_timestamp,
        )

        stats_output.write_stats(stats, input.model, iso_timestamp)


if __name__ == "__main__":
    main()
