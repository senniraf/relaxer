from typing import Any, Dict, Protocol


class MethodUser(Protocol):
    @property
    def used_method(self) -> str:
        ...


class StatsRecorder(Protocol):
    @property
    def stats(self) -> Dict[str, Any]:
        ...
