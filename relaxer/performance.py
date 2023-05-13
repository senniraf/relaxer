from collections import defaultdict
import re
import time
from typing import Any, Callable, Iterator, Tuple, TypeVar


_runtimes = defaultdict(float)


def time_method(method: Callable):
    """Decorator to time a method call. The runtime can be accessed via `get_method_runtime`.

    Args:
        method (Callable): Method to time.
    """

    def timed(self, *args, **kwargs):
        start = time.process_time()
        result = method(self, *args, **kwargs)
        end = time.process_time()
        _runtimes[(self, method.__name__)] = end - start
        return result

    return timed


def time_function(func: Callable):
    """Decorator to time a function call. The runtime can be accessed via `get_function_runtime`.

    Args:
        func (Callable): Function to time.
    """

    def timed(*args, **kwargs):
        start = time.process_time()
        result = func(*args, **kwargs)
        end = time.process_time()
        _runtimes[func.__name__] = end - start
        return result

    return timed


def get_method_runtime(self: object, method_name: str) -> float:
    """Get the runtime of a method call.

    Args:
        self (object): Instance of the class the method belongs to.
        method_name (str): Name of the method.

    Returns:
        float: Runtime of the method call. If the method was not called before, 0 is returned.
    """
    return _runtimes[(self, method_name)]


def get_function_runtime(func_name: str) -> float:
    """Get the runtime of a function call.

    Args:
        func_name (str): Name of the function.

    Returns:
        float: Runtime of the function call. If the function was not called before, 0 is returned.
    """
    return _runtimes[func_name]


R = TypeVar("R")  # the return type of the function


def process_timeit(
    func: Callable[..., R], *args: Any, **kwargs: Any
) -> Tuple[R, float]:
    """Measure the runtime of a function call.

    Args:
        func (Callable[..., R]): Function to call.
        args (Any): Positional arguments to pass to the function.
        kwargs (Any): Keyword arguments to pass to the function.

    Returns:
        Tuple[R, float]: Tuple of the function result and the runtime.
    """
    start = time.process_time()
    result = func(*args, **kwargs)
    end = time.process_time()
    return result, end - start


T = TypeVar("T")


class TimedIterator(Iterator[T]):
    """Wrapper for an iterator to measure the iteration process runtime."""

    def __init__(self, wrapped: Iterator[T]) -> None:
        self._wrapped = wrapped
        self._iter_wrapped = wrapped
        self._iter_runtime = 0.0
        self._next_runtime = 0.0

    @property
    def iter_runtime(self) -> float:
        """Runtime of the iteration initialisation."""
        return self._iter_runtime

    @property
    def next_runtime(self) -> float:
        """Runtime of the iteration."""
        return self._next_runtime

    def __iter__(self) -> Iterator[T]:
        start = time.process_time()
        self._iter_wrapped = iter(self._wrapped)
        self._iter_runtime = time.process_time() - start
        return self

    def __next__(self) -> T:
        start = time.process_time()
        result = next(self._iter_wrapped)
        self._next_runtime = time.process_time() - start
        return result
