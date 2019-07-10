from __future__ import division
import sys
import csv
import argparse
import re
from enum import Enum
from itertools import zip_longest, tee
from typing import List, Mapping, Tuple, Sequence, Iterator, IO, Any
from phonenumbers import PhoneNumberMatcher, format_number, PhoneNumberFormat
from strategies import Stages, STAGES
from cache import cache
from helpers import extract_contacts, space_dashes

Names = List[str]
NameAttempts = Iterator[Names]
Entry = Mapping[str, Names]


EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+")


def extract_contacts(line: str) -> Tuple[List[str], List[str]]:
    emails = EMAIL_RE.findall(line)
    phones = [
        format_number(match.number, PhoneNumberFormat.INTERNATIONAL)
        for match in PhoneNumberMatcher(line, "US")
    ]
    return emails, phones


def min_max_names(emails: List[str], phones: List[str]) -> Tuple[int, int]:
    contact_counts: Tuple[int, int] = (len(emails), len(phones))
    # if there's 1 email and 3 phones, min_names should be 1
    # but if there's 0 email and 1 phone, it should be 1, not 0
    min_names: int = max(1, min(contact_counts))
    max_names: int = max(contact_counts)
    # maybe add min, likely_max, absolute_max to distingish max vs sum?
    return (min_names, max_names)


def fuzzy_intersect(left: Names, right: Names, recursive: bool = False) -> Names:
    """
    Take the first name on the left, if it contains or is contained by a name
    on the right, set aside all of the names on the left or right that the first
    name contains or is contained by, and return [the longest of these]
    + [the result of repeating this process on everything that was not set aside]

    If either left or right are empty, return the other one.
    """
    if recursive:
        if not left:
            return []
    else:
        if not (left and right):
            return left or right
    first_left, *remaining_left = left
    similar_right = set(
        right_name
        for right_name in right
        if right_name in first_left or first_left in right_name
    )
    if similar_right:
        # catch duplicate similar names
        also_similar_left = set(
            left_name
            for left_name in remaining_left
            if left_name in first_left or first_left in left_name
        )
        intersection = max(first_left, *similar_right, *also_similar_left, key=len)
        dissimilar_right = list(set(right) - similar_right)
        dissimilar_left = list(set(remaining_left) - also_similar_left)
        return [intersection] + fuzzy_intersect(dissimilar_left, dissimilar_right, True)
    return fuzzy_intersect(remaining_left, right, True)


def extract_names(
    text: str, min_names: int, max_names: int, stages: Stages = STAGES
) -> Names:
    def filter_min_criteria(attempts: NameAttempts) -> NameAttempts:
        yielded_anything = False
        for attempt in attempts:
            if len(attempt) >= min_names:
                yielded_anything = True
                yield attempt
        if not yielded_anything:
            yield []

    google_extractors, crude_extractors, refiners = stages
    google_extractions: Iterator[Names] = filter_min_criteria(
        extractor(text) for extractor in google_extractors
    )
    consensuses = (
        fuzzy_intersect(google_extraction, crude_extraction)
        for google_extraction in google_extractions
        for crude_extraction in filter_min_criteria(
            extractor(text) for extractor in crude_extractors
        )
    )
    refinements = (
        refine(consensus)
        for consensus in consensuses
        for refine in refiners
        if min_names <= len(refinement) <= max_names
    )
    try:
        return next(refinements)
    except StopIteration:
        return []


def space_dashes(text: str) -> str:
    """Put spaces around dashes without spaces."""
    return re.sub(r"-([^ -])", r"- \1", re.sub(r"([^ -])-", r"\1 -", text))


def extract_info(raw_line: str, **extract_names_kwargs: Any) -> Mapping[str, List[str]]:
    line = raw_line.replace("'", "").replace("\n", "")
    emails, phones = extract_contacts(line)
    min_names, max_names = min_max_names(emails, phones)
    if max_names == 0:
        names = ["skipped"]
    else:
        clean_line = space_dashes(line)
        names = extract_names(clean_line, min_names, max_names, **extract_names_kwargs)
        print(".", end="")
        sys.stdout.flush()
    return {"line": [line], "emails": emails, "phones": phones, "names": names}


def save_entries(entries: Sequence[Entry], out_file: IO) -> None:
    writer = csv.writer(out_file)
    writer.writerow(entries[0].keys())
    for entry in entries:
        contacts = zip_longest(*entry.values(), fillvalue="")
        for contact in contacts:
            writer.writerow(list(contact))


class EntryType(str, Enum):
    correct = "correct"
    too_many = "too many"
    not_enough = "not enough"
    all = "all"

    def __str__(self) -> str:
        return self.value


def decide_entry_type(entry: Entry) -> Sequence[EntryType]:
    min_names, max_names = min_max_names(entry["emails"], entry["phones"])
    if not max_names:
        return tuple()
    names_count = len(entry["names"])
    if names_count <= max_names:
        if names_count < min_names:
            return (EntryType.all, EntryType.not_enough)
        return (EntryType.all, EntryType.correct)
    return (EntryType.all, EntryType.too_many)


def analyze_metrics(entries: List[Entry]) -> Tuple[Mapping, Mapping]:
    typed_entries = [(decide_entry_type(entry), entry) for entry in entries]
    entries_by_type = {
        entry_type_being_found: [
            entry
            for entry_types, entry in typed_entries
            if entry_type_being_found in entry_types
        ]
        for entry_type_being_found in EntryType
    }
    counts = dict(zip(entries_by_type.keys(), map(len, entries_by_type.values())))
    for entry_type in list(EntryType):
        fraction = counts[entry_type] / counts[EntryType.all]
        print(  "{}: {:.2%}. ".format(entry_type, fraction)
        print(metric, end="")
    print()
    return (entries_by_type, counts)


def main() -> Tuple[Mapping, Mapping]:
    with open("data/trello.csv", encoding="utf-8") as in_file:
        lines = list(csv.reader(in_file))[1:]
    with cache:
        entries = [extract_info(line[0]) for line in lines]
    with open("data/info.csv", "w", encoding="utf-8") as out_file:
        save_entries(entries, args.output)
    return analyze_metrics(entries)


if __name__ == "__main__":
    metrics = main()
