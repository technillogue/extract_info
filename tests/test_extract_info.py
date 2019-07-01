import re
import random
import os
import pdb
import json
from typing import Dict, List, Iterable, Any, Tuple, Callable
import pytest
import extract_info
import extract_names
import utils


# R_good = "R1( R2( R3)?)??"
# R_fail = "R1R2R3"
# C_good = f"C1 {R_good} (C2 {R_good})"
# G_good = f"G1({C_good})?G2
# there's a few versions that are acceptable
# g1, c1, r1, r2, c2, r1, r2, g2, c1, r1, r2, etc would make sense
# but if g1 is wrong we need to immediately skip to g2
# if c1 is wrong we need to immediately skip to c2 without trying to refine

# start -> g1 -> g2 -> g3 -> fail
# g{n} -> c1 -> c2 -> g{n+1}
# c{n} -> r1 -> r2 -> r3 -> c{n+1}
# r{n} -> success

# simpler complete version
# g1 -> (c1, g2)
# g2 -> (c1, fail)
# c1 -> (r1, c2)
# c2 -> (r1, g2)
# r1 -> (success, r2)
# r2 -> (success, c2)

# if this is an FSM there should be a regex for it
# using a shorthand where [gcr][12] is one char


def correct_pattern_gen(items: List[str], suffix: str) -> str:
    if len(items) == 1:
        return items[0] + "\n" + suffix
    return f"{items[0]}\n{suffix}({correct_pattern_gen(items[1:], suffix)})?".replace(
        "\n\n", "\n"
    )
    # awful hack please debug


def trace_extract_info_nonfixture() -> Tuple[utils.Logger, Callable]:
    logger = utils.Logger()

    def wrap_logging(funcs: List[Callable]) -> List[Callable]:
        return [logger.logged(func) for func in funcs]

    methods = {
        "refiners": wrap_logging(extract_names.REFINERS),
        "crude_extractors": wrap_logging(extract_names.CRUDE_EXTRACTORS),
        "google_extractors": wrap_logging(extract_names.GOOGLE_EXTRACTORS),
    }
    methods_names: List[str] = [
        [f.__name__ for f in category] for category in methods.values()
    ]
    correct_pattern = ""
    for method_names in methods_names:
        correct_pattern = correct_pattern_gen(method_names, correct_pattern)

    def traced_extract_info(*args: Any, **kwargs: Any) -> Any:
        result = extract_info.extract_info(*args, **methods, **kwargs)
        #        assert re.fullmatch(correct_pattern, logger.stream.getvalue()) is not None
        return result

    return (logger, traced_extract_info)


trace_extract_info_fixture = pytest.fixture(
    trace_extract_info_nonfixture, name="trace_extract_info"
)


Entry = Dict[str, List[str]]

CASES: List[Entry]
CASES = json.load(open("data/correct_cases.json", encoding="utf-8"))


@pytest.fixture(params=CASES, name="correct_case")
def correct_case_fixture(request: Any) -> Entry:
    return request.param


def test_cases(
    correct_case: Entry, trace_extract_info: Tuple[utils.Logger, Callable]
) -> None:
    logger, traced_extract_info = trace_extract_info
    stream = logger.new_stream()
    line = correct_case["line"][0]
    actual = traced_extract_info(line)
    if actual != correct_case:
        pdb.set_trace()
        actual = extract_info.extract_info(line)
    assert actual == correct_case


DIFFICULT_CASES: List[Entry]
DIFFICULT_CASES = json.load(open("data/incorrect_cases.json", encoding="utf-8"))


@pytest.fixture(params=DIFFICULT_CASES, name="difficult_case")
def difficult_case_fixture(request: Any) -> Entry:
    return request.param


def fd_print(text: str, end: str = "\n") -> None:
    with os.fdopen(os.dup(1), "w") as stdout:
        stdout.write(text + end)


def fd_input(prompt: str) -> str:
    fd_print("\n{}".format(prompt))
    with os.fdopen(os.dup(2), "r") as stdin:
        return stdin.readline()


def ask(case: Dict, show_contact_info: bool = False) -> bool:
    fd_print(f"\nLINE: {case['line']}")
    fd_print(f"NAMES: {case['names']}")
    if show_contact_info:
        fd_print(f"PHONES: {case['phones']}")
        fd_print(f"EMAILS: {case['emails']}")
    correctness = fd_input("correct? ([y]es/no, default yes) ").lower() in [
        "",
        "y",
        "yes",
    ]
    return correctness


@pytest.mark.skip
@pytest.mark.xfail
def test_difficult_cases(difficult_case: Entry) -> None:
    """these are examples that were marked as incorrect, if we have
    different anaswers for them that means there might be improvement"""
    line = difficult_case["line"][0]
    actual_case: Entry = extract_info.extract_info(line)
    if actual_case["names"] != difficult_case["names"]:
        correct = ask(actual_case)
        if correct:
            json.dump(
                [case for case in DIFFICULT_CASES if case != difficult_case],
                open("data/incorrect_cases.json", "w", encoding="utf-8"),
                indent=4,
            )
            json.dump(
                CASES + [actual_case],
                open("data/correct_cases.json", "w", encoding="utf-8"),
                indent=4,
            )
            fd_print("marked as a correct example")
            # just move this into the other one
    assert actual_case["names"] != difficult_case["names"]


def test_last() -> None:
    # fake test
    utils.cache.save_cache()
