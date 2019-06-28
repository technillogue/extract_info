import random
import os
import pdb
import json
from typing import Dict, List, Iterable, Any, Tuple
import pytest
import extract_info
import extract_names
import utils

def test_soft_filter() -> None:
    assert list(utils.soft_filter(lambda i: True, iter([]))) == [[]]
    assert list(utils.soft_filter(lambda i: i < 0, iter(range(10)))) == [9]
    assert list(utils.soft_filter(lambda i: i % 2 == 0, iter(range(10)))) == [
        0, 2, 4, 6, 8
    ]

def test_contains_nonlatin() -> None:
    assert not extract_names.contains_nonlatin("Stephanie")
    assert extract_names.contains_nonlatin(u"Лена")

Entry = Dict[str, List[str]]

CASES: List[Entry]
CASES = json.load(open("data/correct_cases.json", encoding="utf-8"))


def test_no_google() -> None:
    actual = extract_names.extract_names(
        "12/31 -- Lisa balloon drop -- off 123.123.1234 - paid, check deposited",
        1, 1)
    expected = ["Lisa"]
    if actual != expected:
        pdb.set_trace()
        extract_names.extract_names(
            "12/31 -- Lisa balloon drop -- off 123.123.1234 - paid, check deposited",
            1, 1
        )
    assert actual == expected

@pytest.fixture(params=CASES)
def correct_case(request: Any) -> Entry:
    return request.param

def test_cases(correct_case: Entry) -> None:
    line = correct_case["line"][0]
    actual = extract_info.extract_info(line, no_cache=True)
    if actual != correct_case:
        pdb.set_trace()
        actual = extract_info.extract_info(line, no_cache=True)
    assert actual == correct_case


DIFFICULT_CASES: List[Entry]
DIFFICULT_CASES = json.load(
    open(
        "data/incorrect_cases.json",
        encoding="utf-8"))

@pytest.fixture(params=DIFFICULT_CASES)
def difficult_case(request: Any) -> Entry:
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
    correctness = fd_input(
        "correct? ([y]es/no, default yes) "
    ).lower() in ["", "y", "yes"]
    return correctness

@pytest.mark.xfail
def test_difficult_cases(difficult_case: Entry) -> None:
    """these are examples that were marked as incorrect, if we have
    different anaswers for them that means there might be improvement"""
    line = difficult_case["line"][0]
    actual_case: Entry = extract_info.extract_info(line, no_cache=True)
    if actual_case["names"] != difficult_case["names"]:
        correct = ask(actual_case)
        if correct:
            json.dump(
                [case for case in DIFFICULT_CASES if case != difficult_case],
                open("data/incorrect_cases.json", "w", encoding="utf-8"),
                indent=4
            )
            json.dump(
                CASES + [actual_case],
                open("data/correct_cases.json", "w", encoding="utf-8"),
                indent=4
            )
            fd_print("marked as a correct example")
    assert actual_case["names"] != difficult_case["names"]


def classify_examples(entries: List[Entry],
                      n: int, show_contact_info: bool,
                      known_correct: List[Entry],
                      known_incorrect: List[Entry]
                      ) -> Iterable[Tuple[bool, Entry]]:
    random.shuffle(entries)
    classified = 0
    while classified < n and entries:
        entry = entries.pop()
        if entry not in known_correct and entry not in known_incorrect:
            correctness = ask(entry, show_contact_info)
            classified += 1
            yield (correctness, entry)

def save_examples(entries: List[Entry], n: int,
                  show_contact_info: bool = False,
                  known_correct: List[Entry] = CASES,
                  known_incorrect: List[Entry] = DIFFICULT_CASES) -> None:
    examples: List[Tuple[bool, Entry]] = list(classify_examples(
        entries, n, show_contact_info,
        known_correct, known_incorrect
    ))
    correct: List[Entry]
    incorrect: List[Entry]
    correct, incorrect = (
        [example for (type_, example) in examples if type_ == selected_type]
        for selected_type in (True, False)
    )
    assert len(correct) + len(incorrect) == len(examples)
    json.dump(
        known_correct + correct,
        open("data/correct_cases.json", "w", encoding="utf-8"),
        indent=4)
    json.dump(
        known_incorrect + incorrect,
        open("data/incorrect_cases.json", "w", encoding="utf-8"),
        indent=4)
    print(f"saved {len(correct)} correct, {len(incorrect)} incorrect examples")
