import argparse
import json
from pathlib import Path
from relaxer.io import Config


parser = argparse.ArgumentParser(
    prog="relaxer",
    description="relaxer - A tool for relaxing clock constraints in UPPAAL models.",
    epilog="For more information, see README.md.",
)
parser.add_argument("-m", "--model", type=Path, help="Path to the UPPAAL model.")
parser.add_argument(
    "-d",
    "--depth",
    type=int,
    help="Depth of the search tree to explore. (length of the traces)",
    default=10,
)
parser.add_argument(
    "-c",
    "--config",
    type=Path,
    help="Path to a json configuration file. CLI arguments override the configuration file.",
)


def parse_command_line() -> Config:

    args = parser.parse_args()

    config = Config([])
    if args.config is not None:
        with args.config.open() as f:
            config = Config.from_json(json.load(f))

    return config
