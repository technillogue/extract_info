from functools import wraps
from itertools import tee
from typing import MutableMapping, Iterable, Callable, Any


class IterableSnooper:
    def __init__(self) -> None:
        self.iterables: MutableMapping[str, MutableMapping] = {}

    def snoop_iterable(self, it: Iterable, name: str) -> Iterable:
        self.iterables[name] = {"collected": []}

        def advance() -> Iterable[Any]:
            for item in it:
                self.iterables[name]["collected"].append(item)
                yield item

        main, sneaky = tee(advance())
        self.iterables[name]["advance"] = sneaky
        return main

    def with_snooping(self, func: Callable) -> Callable:
        @wraps(func)
        def snooped(it: Iterable, *args: Any, **kwargs: Any) -> Any:
            snooped_it = self.snoop_iterable(it, f"iterable #{len(self.iterables)}")
            result = func(snooped_it, *args, **kwargs)
            if isinstance(result, Iterable):
                yield from result
            else:
                yield result

        return snooped
