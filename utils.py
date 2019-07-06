from __future__ import division
import json
import logging
import io
import functools
from collections import defaultdict
from typing import List, Dict, Callable, Any, Union, Optional, IO, TypeVar
from typing_extensions import Protocol, runtime_checkable

X = TypeVar("X")
Y = TypeVar("Y")
Z = TypeVar("Z")


@runtime_checkable
class Wrapper(Protocol):
    __wrapped__: Callable


def compose(f: Callable[[Y], Z], g: Callable[[X], Y]) -> Callable[[X], Z]:
    use_cache = False
    if isinstance(f, Wrapper):
        f = f.__wrapped__
        use_cache = True
    if isinstance(g, Wrapper):
        g = g.__wrapped__
        use_cache = True

    def composed_function(arg: X) -> Z:
        return f(g(arg))

    composed_function.__name__ = composed_function.__qualname__ = "_".join(
        (f.__name__, g.__name__)
    )
    if use_cache:
        return cache.with_cache(composed_function)
    return composed_function


class Cache:
    """
    Non-functional persistent cache for storing expensive computation between runs.

    Only stores the first argument and repeats it exactly once when saving
    to disk, i.e. {text: {func1: result1, func2: result2}, text2: {...}, ...}
    """

    # maybe add cache hit/miss statistics in the future
    def __init__(self, cache_name: str = "data/cache.json"):
        # this needs to be called before cached funcs are defined
        self.cache_name = cache_name
        self.cache: Dict[str, Dict[str, str]]

    def __enter__(self) -> None:
        # this only needs to be called before cached funcs are called
        try:
            data = json.load(open(self.cache_name, encoding="utf-8"))
        except IOError:
            data = {}
        self.cache = defaultdict(dict, data)

    def __exit__(self, *exception_info: Any) -> None:
        with open(self.cache_name, "w", encoding="utf-8") as f:
            json.dump(dict(self.cache), f)
        print("saved cache")

    def clear_cache(self, func_name: str) -> None:
        for item in self.cache.values():
            if func_name in item:
                del item[func_name]

    def with_cache(self, func: Callable) -> Callable:
        func_name = func.__name__

        @functools.wraps(func)
        def wrapper(arg1: Union[str, List[str]], *args: Any, **kwargs: Any) -> Any:
            if isinstance(arg1, list):
                key = json.dumps(arg1)
            else:
                key = arg1
            try:
                return self.cache[key][func_name]
            except KeyError:
                pass
            value = func(arg1, *args, **kwargs)
            # nice-to-have: allow a default value to be returned in case
            # of errors, and don't store that (instead of current impl
            # where the function has to catch its error and that defaut is
            # cached)
            self.cache[key][func_name] = value
            return value

        return wrapper


cache = Cache()

class Logger:
    def __init__(self, log_name: str = "trace", stream: Optional[IO] = None):
        self.log = logging.getLogger(log_name)
        self.log.setLevel("DEBUG")
        self.handler: Optional[logging.Handler] = None
        self.new_stream(stream)

    def logged(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(
            *args: Any,
            _func: Callable = func,
            _log: logging.Logger = self.log,
            _name: str = func.__name__,
            **kwargs: Any
        ) -> Any:
            _log.debug(_name)
            return _func(*args, **kwargs)

        return wrapper

    def new_stream(self, stream: Optional[IO] = None) -> IO:
        if self.handler:
            self.log.removeHandler(self.handler)
        if stream is None:
            stream = io.StringIO()
        self.stream = stream
        self.handler = logging.StreamHandler(self.stream)
        self.log.addHandler(self.handler)
        return stream

    def get_log(self) -> str:
        if isinstance(self.stream, io.StringIO):
            return self.stream.getvalue()
        raise NotImplementedError
