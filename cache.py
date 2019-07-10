from __future__ import division
import json
import functools
from collections import defaultdict
from typing import List, Dict, Callable, Any, Union

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

