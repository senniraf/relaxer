from dataclasses import dataclass
import json
import math
from numbers import Real
from pathlib import Path
from typing import (
    Any,
    Collection,
    Dict,
    Iterable,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Union,
)

from relaxer.tracing.uppyyl.relaxation import GuardRelaxation, InvariantRelaxation


@dataclass
class RelaxationInput:
    model: str
    type_: str
    depth: int
    invariant_relaxations: Sequence[InvariantRelaxation]
    guard_relaxations: Sequence[GuardRelaxation]
    relax_all: bool = False


@dataclass
class OutputConfig:
    type_: str = "stdout"
    path: str = ""


@dataclass
class StatsConfig:
    type_: str
    path: str


@dataclass
class DumpConfig:
    type_: str
    path: str


@dataclass
class Config:
    inputs: Sequence[RelaxationInput]
    output: OutputConfig = OutputConfig()
    stats_config: Optional[StatsConfig] = None
    debug: bool = False
    dump_config: Optional[DumpConfig] = None

    @staticmethod
    def from_json(json_dict: Dict[str, Any]) -> "Config":

        config = Config(
            inputs=[
                RelaxationInput(
                    model=input_["model"]["path"],
                    type_=input_["type"],
                    depth=input_["depth"],
                    invariant_relaxations=[
                        InvariantRelaxation.from_json(relaxation)
                        for relaxation in input_.get("invariant_relaxations", [])
                    ],
                    guard_relaxations=[
                        GuardRelaxation.from_json(relaxation)
                        for relaxation in input_.get("guard_relaxations", [])
                    ],
                    relax_all=input_.get("relax_all", False),
                )
                for input_ in json_dict["inputs"]
            ]
        )
        if "output" in json_dict:
            if "type" in json_dict["output"]:
                config.output.type_ = json_dict["output"]["type"]
                if config.output.type_ == "file":
                    config.output.path = json_dict["output"]["path"]

        if "stats" in json_dict:
            config.stats_config = StatsConfig(
                type_=json_dict["stats"]["type"], path=json_dict["stats"]["path"]
            )

        if "debug" in json_dict:
            config.debug = json_dict["debug"]

        if "dump" in json_dict:
            config.dump_config = DumpConfig(
                type_=json_dict["dump"]["type"], path=json_dict["dump"]["path"]
            )

        return config


class SolutionWriter(Protocol):
    def write_solutions(
        self,
        solutions: Collection[Tuple[Real]],
        supported: bool,
        model: str,
        inv_relaxations: Sequence[InvariantRelaxation],
        guard_relaxations: Sequence[GuardRelaxation],
        depth: int,
        timestamp: str,
    ):
        ...


class StatsWriter(Protocol):
    def write_stats(self, stats: Dict[str, Any], model: str, timestamp: str):
        ...


class DumpLocationHandler(Protocol):
    """A dump location handler is responsible for creating dump locations and managing them."""

    def create_dump_location(self, name: str) -> "DumpLocation":
        """Creates a new dump location. If a dump location with the given name already exists, a ValueError is raised.

        Args:
            name (str): The name of the dump location.

        Raises:
            ValueError: If a dump location with the given name already exists.

        Returns:
            DumpLocation: The newly created dump location.
        """
        ...

    def get_location(self, name: str) -> "DumpLocation":
        """Returns the dump location with the given name. If no such dump location exists, a ValueError is raised.

        Args:
            name (str): The name of the dump location.

        Raises:
            ValueError: If no dump location with the given name exists.

        Returns:
            DumpLocation: The dump location with the given name.
        """
        ...


class DumpLocation(Protocol):
    """A dump location is responsible for writing dumps to a specific location."""

    def write_dump(self, name: str, content: str) -> None:
        """Writes a dump with the given name and content to the dump location.

        Args:
            name (str): The name of the dump.
            content (str): The content of the dump.
        """
        ...


class JSONFileOutput:
    def __init__(self, path: Path):
        self.path = path

    def write_solutions(
        self,
        solutions: Collection[Tuple[Real]],
        supported: bool,
        model: str,
        inv_relaxations: Sequence[InvariantRelaxation],
        guard_relaxations: Sequence[GuardRelaxation],
        depth: int,
        timestamp: str,
    ):
        self._append_to_json_file(
            {
                "model": model,
                "timestamp": timestamp,
                "invariant_relaxations": [
                    relaxation.to_json() for relaxation in inv_relaxations
                ],
                "guard_relaxations": [
                    relaxation.to_json() for relaxation in guard_relaxations
                ],
                "depth": depth,
                "supported_solution": supported,
                "solution": JSONFileOutput._solutions_to_json(solutions),
            }
        )

    def write_stats(self, stats: Dict[str, Any], model: str, timestamp: str):
        self._append_to_json_file({"model": model, "timestamp": timestamp, **stats})

    def _append_to_json_file(self, json_object: Dict[str, Any]):
        if not self.path.exists():
            with self.path.open("x"):
                pass

        with self.path.open() as f:
            try:
                l = json.load(f)
            except json.JSONDecodeError:
                l = []

        if not isinstance(l, list):
            l = [l]

        l.append(json_object)

        with self.path.open("w") as f:
            json.dump(l, f, indent=4)

    @staticmethod
    def _solutions_to_json(
        solutions: Iterable[Tuple[Real]],
    ) -> List[Tuple[Union[float, str]]]:
        """Replaces all numbers with floats and Infinity with 'inf'"""
        return [
            tuple("inf" if math.isinf(x) else float(x) for x in solution)
            for solution in solutions
        ]


class StdOutOutput:
    def write_solutions(
        self,
        solutions: Collection[Tuple[Real]],
        supported: bool,
        model: str,
        inv_relaxations: Sequence[InvariantRelaxation],
        guard_relaxations: Sequence[GuardRelaxation],
        timestamp: str,
    ):
        print(f"Model: {model}")
        print(f"Timestamp: {timestamp}")
        relaxation_string = "\n".join(
            f"#{i}: {relaxation}"
            for i, relaxation in enumerate([*inv_relaxations] + [*guard_relaxations])
        )
        print(f"==================== Relaxations ====================")
        print(relaxation_string)
        print(f"===================== Solutions =====================")
        print(f"Supported: {supported}")

        header = ", ".join(
            f"#{i}" for i in range(len(inv_relaxations) + len(guard_relaxations))
        )
        print(f"({header})")
        for solution in solutions:
            print(f"{solution}")


class EmptyOutput:
    def write_solutions(
        self,
        solutions: Collection[Tuple[Real]],
        supported: bool,
        model: str,
        inv_relaxations: Sequence[InvariantRelaxation],
        guard_relaxations: Sequence[GuardRelaxation],
        timestamp: str,
    ):
        pass

    def write_stats(self, stats: Dict[str, Any], model: str, timestamp: str):
        pass


class EmptyDumpLocationHandler:
    """A dump location handler that does not create any dump locations."""

    def create_dump_location(self, name: str) -> DumpLocation:
        return EmptyDumpLocation()

    def get_location(self, name: str) -> DumpLocation:
        return EmptyDumpLocation()


class DirectoryLocationHandler:
    """A dump location handler that writes dumps to a directory and creates subdirectories for each dump location."""

    def __init__(self, dump_path: Path) -> None:
        self._dump_path = dump_path
        self._dump_locations: Dict[str, DumpLocation] = {}

    def create_dump_location(self, name: str) -> "DirectoryDumpLocation":
        if name in self._dump_locations:
            raise ValueError(f"Dump location {name} already exists")

        dump_location = DirectoryDumpLocation(self._dump_path / name)
        self._dump_locations[name] = dump_location
        return dump_location

    def get_location(self, name: str) -> DumpLocation:
        if name not in self._dump_locations:
            raise ValueError(f"Dump location {name} does not exist")
        return self._dump_locations[name]


class EmptyDumpLocation:
    """A dump location that does not write any dumps."""

    def write_dump(self, name: str, content: str) -> None:
        pass


class DirectoryDumpLocation:
    """A dump location that writes dumps to files in a directory."""

    def __init__(self, path: Path):
        self._path = path
        self._path.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def write_dump(self, name: str, content: str) -> None:
        with open(self._path / name, "w") as file:
            file.write(content)
