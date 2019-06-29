import json
import functools
from typing import (
    List, Dict, Callable, Any, Union, Iterator, TypeVar
)
from collections import defaultdict

Names = List[str]
TextOrNames = Union[str, Names]

def identity_function(x: Any) -> Any:
    return x

def compose(f: Callable[[TextOrNames], Names],
            g: Callable[[TextOrNames], TextOrNames]) -> Callable:
    def composed_function(arg: TextOrNames) -> Names:
        return f(g(arg))
    return composed_function

X = TypeVar("X")


class Cache:
    """
    non-functional cache for storing expensive computation in between
    program runs, as a function decorator.
    only stores the first argument and repeats it exactly once when saving
    to disk, i.e. {text: {func1: result1, func2: result2}, text2: {...}, ...}
    use finally: to make sure the cache gets saved
    """

    def __init__(self, cache_name: str = "data/cache.json",
                 log_name: str = "data/cache.log"):
        self.cache_name = cache_name
        self.log_name = log_name
        self.func_names: Names = []
        self.cache: Dict[str, Dict[str, str]]
        self.log_level: str = "none" # for REPL debugging

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
        lines = set(
            line[0] for line in csv.reader(open("data/info_edited.csv"))
        )
        keep = lines.intersection(self.cache)
        keep_funcs = set(("google_extract_names",))
        self.cache = {
            key: {
                func: self.cache[key][func]
                for func in keep_funcs.intersection(set(self.cache[key].keys()))
            }
            for key in keep
        }
        self.save_cache()

    def log(self, status: str, func_name: str, value: Any, arg: str) -> None:
        if self.log_level != "none":
            if self.log_level == "verbose":
                log_entry = (f"{status:<4}: {func_name:<20}\nresult '{value}'"
                             f"\nfor input '{arg}'\n\n\n")
            else:
                log_entry = f"{func_name}\n"
            with open("data/cache.log", "a", encoding="utf-8") as log_file:
                log_file.write(log_entry)

    def with_cache(self, decorated: Callable) -> Callable:
        func_name = decorated.__name__
        self.func_names.append(func_name)
        # optimize this a bit
        @functools.wraps(decorated)
        def wrapper(arg1: Union[str, List[str]], *args: Any,
                    no_cache: bool = False, **kwargs: Any) -> Any:
            if isinstance(arg1, list):
                key = json.dumps(arg1)
            else:
                key = arg1
            try:
                if (not no_cache and self.cache[key][func_name] is not None):
                    # sometimes we've saved google saying nothing
                    # in some cases this is because of e.g. network error
                    # so we don't trust that
                    self.log("hit", func_name, self.cache[key][func_name], key)
                    return self.cache[key][func_name]
            except KeyError:
                pass
            value = decorated(arg1, *args, **kwargs)
            self.cache[key][func_name] = value
            self.log("miss", func_name, value, key)
            return value
        return wrapper


cache = Cache()
cache.open_cache()
