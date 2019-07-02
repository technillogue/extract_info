import re
import json
from typing import Dict, List, Any, Tuple, Callable, Sequence
from functools import reduce
import pytest
import extract_info
import extract_names
import utils
from tools import ask, fd_print

# our code has three step and various strategies for  each step,
# which it does in order until one works
# as soon as a given strategy for this step doesn't work, it should jump
# to the next strategy for this step without trying the next steps

# this corresponds to a finate state automata
# where the symbols are the names of each strategy for each step
# and the states are the combinations of strategies for each step,
# including "not doing this step right now" as the 0th state

# because every FSA corresponds to a regex, we know that there exists a
# regex that match correct paths. we can log which strategies are called
# and see if they match the regex to test correct program flow


def correct_pattern_gen(suffix: str, items: List[str]) -> str:
    if len(items) == 1:
        return items[0] + "\n" + suffix
    return f"{items[0]}\n({suffix}|{correct_pattern_gen(suffix, items[1:])})"


STEPS_STRATEGY_NAMES: List[List[str]] = [
    [strategy.__name__ for strategy in step] for step in extract_names.STEPS
]

CORRECT_PATTERN = reduce(correct_pattern_gen, reversed(STEPS_STRATEGY_NAMES), "")


def trace_extract_info_nonfixture() -> Tuple[utils.Logger, Callable]:
    logger = utils.Logger()

    def wrap_logging(funcs: Sequence[Callable]) -> Sequence[Callable]:
        return [logger.logged(func) for func in funcs]

    steps = {
        "refiners": wrap_logging(extract_names.REFINERS),
        "crude_extractors": wrap_logging(extract_names.CRUDE_EXTRACTORS),
        "google_extractors": wrap_logging(extract_names.GOOGLE_EXTRACTORS),
    }

    def traced_extract_info(*args: Any, **kwargs: Any) -> Any:
        result = extract_info.extract_info(*args, **steps, **kwargs)  # type: ignore
        return result

    return (logger, traced_extract_info)


trace_extract_info_fixture = pytest.fixture(
    trace_extract_info_nonfixture, name="trace_extract_info"
)


Entry = Dict[str, List[str]]
EXAMPLES_FNAME = "data/examples.json"
EXAMPLES: List[Entry] = json.load(open(EXAMPLES_FNAME, encoding="utf-8"))
COUNTEREXAMPLES_FNAME = "data/counterexamples.json"
COUNTEREXAMPLES: List[Entry] = json.load(open(COUNTEREXAMPLES_FNAME, encoding="utf-8"))
LABELED_EXAMPLES: List[Tuple[Entry, bool]] = [
    (example, True) for example in EXAMPLES
] + [(example, False) for example in COUNTEREXAMPLES]


@pytest.fixture(params=LABELED_EXAMPLES, name="labeled_example")
def labeled_example_fixture(request: Any) -> Tuple[Entry, bool]:
    return request.param


def test_examples(
    labeled_example: Tuple[Entry, bool],
    trace_extract_info: Tuple[utils.Logger, Callable],
) -> None:
    logger, traced_extract_info = trace_extract_info
    logger.new_stream()
    example, correct = labeled_example
    line = example["line"][0]
    actual = traced_extract_info(line)
    min_names, max_names = extract_info.min_max_names(
        example["emails"], example["phones"]
    )
    # check trace
    log_trace = logger.get_log()
    actual_names = len(actual["names"])
    if actual_names <= max_names:
        if actual_names >= min_names:
            assert re.fullmatch(CORRECT_PATTERN, log_trace) is not None
        else:
            # check that it matches not enough
            pass
    else:
        # check that it matches too many
        pass
    # check corectness
    if actual != example:
        # really_correct = ask(example)
        # reclassify
        # correct = ask(actual_case)
        # if correct:
        #     json.dump(
        #         [case for case in DIFFICULT_CASES if case != difficult_case],
        #         open("data/incorrect_cases.json", "w", encoding="utf-8"),
        #         indent=4,
        #     )
        #     json.dump(
        #         CASES + [actual_case],
        #         open("data/correct_cases.json", "w", encoding="utf-8"),
        #         indent=4,
        #     )
        #     fd_print("marked as a correct example")
        if correct:
            assert actual == example


def test_last() -> None:
    # fake test
    utils.cache.save_cache()
