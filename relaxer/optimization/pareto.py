from numbers import Real
from typing import Set, Tuple


class ParetoSet:
    def __init__(self) -> None:
        self._points: Set[Tuple[Real]] = set()

    def add(self, p: Tuple[Real]):
        for q in self._points.copy():
            if dominates(p, q):
                self._points.remove(q)
                continue

            if dominates(q, p):
                return

        self._points.add(p)

    def to_set(self) -> Set[Tuple[Real]]:
        return self._points


def dominates(p: Tuple[Real], q: Tuple[Real]) -> bool:
    """Returns whether Solution p dominates Solution q.

    Args:
        p (Tuple[Constant]): Point p
        q (Tuple[Constant]): Point q

    Returns:
        bool: True if p dominates q
    """
    return all(p_c >= q_c for p_c, q_c in zip(p, q)) and any(
        p_c > q_c for p_c, q_c in zip(p, q)
    )
