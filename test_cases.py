import os
import pdb
import json
from typing import Dict, List, Iterable, Any
import pytest
import extract_info

Entry = Dict[str, List[str]]

CASES: List[Entry]
CASES = json.load(open("data/correct_cases.json"))


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
DIFFICULT_CASES = json.load(open("data/incorrect_cases.json"))


@pytest.fixture(params=DIFFICULT_CASES)
def difficult_case(request: Any) -> Entry:
    return request.param

def fd_print(text: str) -> None:
    with os.fdopen(os.dup(1), "w") as stdout:
        stdout.write(text)

def fd_input(prompt: str) -> str:
    fd_print("\n{}".format(prompt))

    with os.fdopen(os.dup(2), "r") as stdin:
        return stdin.readline()

@pytest.mark.xfail
def test_difficult_cases(difficult_case: Entry) -> None:
    """these are examples that were marked as incorrect, if we have
    different anaswers for them that means there might be improvement"""
    line = difficult_case["line"][0]
    actual_case: Entry = extract_info.extract_info(line, no_cache=True)
    if actual_case["names"] != difficult_case["names"]:
        fd_print(repr(actual_case))
        correct: str = fd_input(
            "is that right? (<ret> for no, anything else for yes)"
        )
        if correct:
            json.dump(
                [case for case in DIFFICULT_CASES if case != difficult_case],
                open("data/incorrect_cases.json", "w")
            )
            json.dump(
                CASES + [actual_case],
                open("data/correct_case.json", "w")
            )
            fd_print("marked as a correct example")
    assert actual_case["names"] != difficult_case["names"]



def classify_examples(entries: List[Entry],
                      n: int, show_contact_info: bool,
                      known_correct,
                      known_incorrect) -> Iterable[Tuple[bool, Entry]]:
    random.shuffle(entries)
    classified = 0
    while classified < n and entries:
        entry = entries.pop()
        if entry not in known_correct and entry not in known_incorrect:
            print(f"LINE: {entry['line']}")
            print(f"NAMES: {entry['names']}")
            if show_contact_info:
                print(f"PHONES: {entry['phones']}")
                print(f"EMAILS: {entry['emails']}")
            incorrect = bool(input(
                "correct? (any input for no, return for yes) "
            ))
            yield (incorrect, entry)


def save_examples(entries: List[Entry], n: int, show_contact_info=False,
                  known_correct: List[Entry] = CASES,
                  known_incorrect: List[Entry] = DIFFICULT_CASES) -> None:
    examples: Iterable[Tuple[bool, Entry]] = classify_examples(
        entries, n, show_contact_info,
        known_correct, known_incorrect
    )
    correct: List[Entry]
    incorrect: List[Entry]
    correct, incorrect = (
        [example for (type_, example) in examples if type_ == selected_type]
        for selected_type in (True, False)
    )
    json.dump(known_correct + correct, open("data/correct_cases.json"))
    json.dump(known_incorrect + incorrect, open("data/incorrect_cases.json"))

