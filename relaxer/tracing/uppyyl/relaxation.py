from abc import ABC
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class Relaxation(ABC):
    uppaal_clock_constraint: str

    def to_json(self) -> Dict[str, Any]:
        return {
            "clock_constraint": self.uppaal_clock_constraint,
        }

    @staticmethod
    def clean_clock_constraint(clock_constraint: str) -> str:
        return clock_constraint.replace(" ", "")


@dataclass(frozen=True)
class InvariantRelaxation(Relaxation):
    location_id: str

    def to_json(self) -> Dict[str, Any]:
        return {
            "location_id": self.location_id,
            **super().to_json(),
        }

    def __str__(self) -> str:
        return (
            f"InvariantRelaxation(<{self.location_id}>, {self.uppaal_clock_constraint})"
        )

    @staticmethod
    def from_json(json: Dict[str, Any]) -> "InvariantRelaxation":
        return InvariantRelaxation.create(
            uppaal_clock_constraint=json["clock_constraint"],
            location_id=json["location_id"],
        )

    @staticmethod
    def create(uppaal_clock_constraint: str, location_id: str) -> "InvariantRelaxation":
        return InvariantRelaxation(
            uppaal_clock_constraint=Relaxation.clean_clock_constraint(
                uppaal_clock_constraint
            ),
            location_id=location_id,
        )


@dataclass(frozen=True)
class GuardRelaxation(Relaxation):
    source_id: str
    target_id: str

    def to_json(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            **super().to_json(),
        }

    def __str__(self) -> str:
        return f"GuardRelaxation(<{self.source_id}, {self.target_id}>, {self.uppaal_clock_constraint})"

    @staticmethod
    def from_json(json: Dict[str, Any]) -> "GuardRelaxation":
        return GuardRelaxation.create(
            uppaal_clock_constraint=json["clock_constraint"],
            source_id=json["source_id"],
            target_id=json["target_id"],
        )

    @staticmethod
    def create(
        uppaal_clock_constraint: str, source_id: str, target_id: str
    ) -> "GuardRelaxation":
        return GuardRelaxation(
            uppaal_clock_constraint=Relaxation.clean_clock_constraint(
                uppaal_clock_constraint
            ),
            source_id=source_id,
            target_id=target_id,
        )
