import json
import random
import os
from typing import Dict, List, Iterable, Tuple, Optional
import extract_names

Entry = Dict[str, List[str]]


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


def show_all_extractions(text: str) -> Dict[str, List[List[str]]]:
    return {
        "google_extractions": [
            extractor(text) for extractor in extract_names.GOOGLE_EXTRACTORS
        ],
        "crude_extractions": [
            extractor(text) for extractor in extract_names.CRUDE_EXTRACTORS
        ],
    }

    # consensuses: Iterator[Names] = filter(
    #     min_criteria,
    #     map(fuzzy_intersect, product(google_extractions, crude_extractions))
    # )
    # refined_consensuses: Iterator[Names] = soft_filter(
    #     lambda consensus: min_names <= len(consensus) <= max_names,
    #     (
    #         refine(consensus)
    #         for consensus, refine in product(consensuses, REFINERS)
    #     )
    # )


def classify_examples(
    entries: List[Entry],
    n: int,
    show_contact_info: bool,
    known_correct: List[Entry],
    known_incorrect: List[Entry],
) -> Iterable[Tuple[bool, Entry]]:
    random.shuffle(entries)
    classified = 0
    while classified < n and entries:
        entry = entries.pop()
        if entry not in known_correct and entry not in known_incorrect:
            correctness = ask(entry, show_contact_info)
            classified += 1
            yield (correctness, entry)


def save_examples(
    entries: List[Entry],
    n: int,
    show_contact_info: bool = False,
    known_correct: Optional[List[Entry]] = None,
    known_incorrect: Optional[List[Entry]] = None,
) -> None:
    if known_correct is None:
        known_correct = json.load(open("data/correct_cases.json", encoding="utf-8"))
    if known_incorrect is None:
        known_incorrect = json.load(open("data/incorrect_cases.json", encoding="utf-8"))
    examples: List[Tuple[bool, Entry]] = list(
        classify_examples(entries, n, show_contact_info, known_correct, known_incorrect)
    )
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
        indent=4,
    )
    json.dump(
        known_incorrect + incorrect,
        open("data/incorrect_cases.json", "w", encoding="utf-8"),
        indent=4,
    )
    print(f"saved {len(correct)} correct, {len(incorrect)} incorrect examples")
