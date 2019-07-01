import json
import logging
import io
import functools
from typing import List, Dict, Callable, Any, Union, Iterator, TypeVar, Optional, IO
from collections import defaultdict


Names = List[str]
TextOrNames = Union[str, Names]


def identity_function(x: Any) -> Any:
    return x


def compose(
    f: Callable[[TextOrNames], Names], g: Callable[[TextOrNames], TextOrNames]
) -> Callable:
    use_cache = False
    try:
        f = f.__wrapped__
        use_cache = True
    except AttributeError:
        pass
    try:
        g = g.__wrapped_
        use_cache = True
    except AttributeError:
        pass

    def composed_function(arg: TextOrNames) -> Names:
        return f(g(arg))

    composed_function.__name__ = "_".join((f.__name__, g.__name__))
    if use_cache:
        return cache.with_cache(composed_function)
    return composed_function


X = TypeVar("X")


def soft_filter(
    predicate: Callable[[X], bool],
    seq: Iterator[X],
    default_if_empty: Union[X, None, List] = None,
) -> Iterator[X]:
    """filter, but always returning at least one item.
    if iter is empty, return default_if_empty
    otherwise, if none of the items in iter satisfy predicate, return the last
    item in iter"""
    if default_if_empty is None:
        default_if_empty: X = []
    last = default_if_empty
    empty = True
    while True:
        try:
            last = next(seq)
            if predicate(last):
                empty = False
                yield last
        except StopIteration:
            if empty:
                yield last
            break


class Cache:
    """
    non-functional cache for storing expensive computation in between
    program runs, as a function decorator.
    only stores the first argument and repeats it exactly once when saving
    to disk, i.e. {text: {func1: result1, func2: result2}, text2: {...}, ...}
    use finally: to make sure the cache gets saved
    """

    # maybe add cache hit/miss statistics in the future
    def __init__(self, cache_name: str = "data/cache.json"):
        self.cache_name = cache_name
        self.func_names: Names = []
        self.cache: Dict[str, Dict[str, str]]

    def open_cache(self) -> None:
        try:
            data = json.load(open(self.cache_name, encoding="utf-8"))
        except IOError:
            data = {}
        self.cache = defaultdict(dict, data)

    def save_cache(self) -> None:
        with open(self.cache_name, "w", encoding="utf-8") as f:
            json.dump(dict(self.cache), f)
        print("saved cache")

    def clear_cache(self, func_name: str) -> None:
        for item in self.cache.values():
            if func_name in item:
                del item[func_name]

    def clever_clear_cache(self) -> None:
        import csv

        lines = {line[0] for line in csv.reader(open("data/info_edited.csv"))}
        keep = lines.intersection(self.cache)
        keep_funcs = {"google_extract_names", "nltk_extract_names"}
        self.cache = {
            key: {
                func: self.cache[key][func]
                for func in keep_funcs.intersection(set(self.cache[key].keys()))
            }
            for key in keep
        }
        self.save_cache()

    def with_cache(self, func: Callable) -> Callable:
        func_name = func.__name__
        self.func_names.append(func_name)

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


class Logger:
    def __init__(self, stream: Optional[IO] = None, log_name: str = "trace"):
        self.log = logging.getLogger(log_name)
        self.log.setLevel("INFO")
        self.handler: Optional[logging.Handler] = None
        self.new_stream(stream)

    def logged(self, fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self.log.info(fn.__name__)
            return fn(*args, **kwargs)

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


cache = Cache()
cache.open_cache()
