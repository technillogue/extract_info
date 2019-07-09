import json
import random
import os
from functools import wraps
from itertools import tee
from typing import Mapping, List, Iterable, Tuple, Callable, Any, Dict
import extract_names

Entry = Mapping[str, List[str]]
EXAMPLES_FNAME = "data/examples.json"
EXAMPLES: List[Entry] = json.load(open(EXAMPLES_FNAME, encoding="utf-8"))
COUNTEREXAMPLES_FNAME = "data/counterexamples.json"
COUNTEREXAMPLES: List[Entry] = json.load(open(COUNTEREXAMPLES_FNAME, encoding="utf-8"))
LABELED_EXAMPLES: List[Tuple[Entry, bool]] = [
    (example, True) for example in EXAMPLES
] + [(example, False) for example in COUNTEREXAMPLES]

assert EXAMPLES and COUNTEREXAMPLES


def fd_print(text: str, end: str = "\n") -> None:
    with os.fdopen(os.dup(1), "w") as stdout:
        stdout.write(text + end)


def fd_input(prompt: str) -> str:
    fd_print("\n{}".format(prompt))
    with os.fdopen(os.dup(2), "r") as stdin:
        return stdin.readline()


def ask(actual: Mapping, show_contact_info: bool = False) -> bool:
    fd_print("\nLINE: {line}\nNAMES: {names}\n".format(**actual))
    if show_contact_info:
        fd_print("\nPHONES: {phones}\nEMAILS: {emails}".format(**actual))
    response = fd_input("is that correct? ([y]es/no, default yes) ").lower().strip()
    correct = response in ("", "y", "yes")
    return correct


def reclassify(actual: Entry, example: Entry) -> bool:
    fd_print("example: " if example in EXAMPLES else "counterexample: ")
    fd_print(f"EXPECTED NAMES: {example['names']}", end="")
    try:
        really_correct = ask(actual)
    except KeyboardInterrupt:
        return False
    # reclassify
    if really_correct:
        fd_print("marking as correct")
        remove_from_list, remove_from_fname = (COUNTEREXAMPLES, COUNTEREXAMPLES_FNAME)
        add_to_list, add_to_fname = (EXAMPLES, EXAMPLES_FNAME)
    else:
        fd_print("marking as incorrect")
        remove_from_list, remove_from_fname = (EXAMPLES, EXAMPLES_FNAME)
        add_to_list, add_to_fname = (COUNTEREXAMPLES, COUNTEREXAMPLES_FNAME)
    if example in remove_from_list:
        fd_print("reclassifying")
        remove_from_list.remove(example)
        json.dump(remove_from_list, open(remove_from_fname, "w"), indent=4)
    else:
        fd_print("updating example")
        add_to_list.remove(example)
    json.dump(add_to_list + [actual], open(add_to_fname, "w"), indent=4)
    return really_correct


def show_all_extractions(text: str) -> List[List[List[str]]]:
    return [
        [extractor(text) for extractor in extractors]
        for extractors in extract_names.STAGES[:2]
    ]


def classify_examples(
    entries: List[Entry], n: int, show_contact_info: bool = False
) -> Iterable[Tuple[bool, Entry]]:
    random.shuffle(entries)
    classified = 0
    while classified < n and entries:
        entry = entries.pop()
        if entry not in EXAMPLES and entry not in COUNTEREXAMPLES:
            correctness = ask(entry, show_contact_info)
            classified += 1
            yield (correctness, entry)


def save_examples(entries: List[Entry], n: int) -> None:
    examples: List[Tuple[bool, Entry]] = list(classify_examples(entries, n))
    correct: List[Entry] = [
        example for (correctness, example) in examples if correctness
    ]
    incorrect: List[Entry] = [
        example for (correctness, example) in examples if not correctness
    ]
    assert len(correct) + len(incorrect) == len(examples)
    json.dump(EXAMPLES + correct, open(EXAMPLES_FNAME, "w"), indent=4)
    json.dump(COUNTEREXAMPLES + incorrect, open(COUNTEREXAMPLES_FNAME, "w"), indent=4)
    print(f"saved {len(correct)} correct, {len(incorrect)} incorrect examples")


class IterableSnooper:
    def __init__(self) -> None:
        self.iterables: Dict[str, Dict] = {}

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
