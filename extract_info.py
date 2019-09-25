from __future__ import division
import sys
import csv
import re
from enum import Enum
from itertools import zip_longest
from typing import List, Mapping, Tuple, Sequence, Iterator, IO, Any
from phonenumbers import PhoneNumberMatcher, format_number, PhoneNumberFormat
from strategies import Stages, STAGES
from cache import cache

Names = List[str]
NameAttempts = Iterator[Names]
Entry = Mapping[str, Names]


EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+")


def extract_contacts(line: str) -> Tuple[List[str], List[str]]:
    emails = EMAIL_RE.findall(line)
    # "how hard can it be to write a regex to match phone numbers?"
    # way too hard for international formats, as it turns out
    phones = [
        format_number(match.number, PhoneNumberFormat.INTERNATIONAL)
        for match in PhoneNumberMatcher(line, "US")
    ] 
    return emails, phones


def min_max_names(emails: List[str], phones: List[str]) -> Tuple[int, int]:
    """ 
    Returns lower and upper bound on the number of names a text could have
    based on the contact info, e.g., if there's 1 email and 3 phones, 
    there could be between 1 and 3 names. If there's 0 emails and 1 phone,
    there can only be exactly one name.
    """
    contact_counts: Tuple[int, int] = (len(emails), len(phones))
    min_names: int = max(1, min(contact_counts))
    max_names: int = max(contact_counts)
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
    return fuzzy_intersect(remaining_left, right, recursion=True)


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
        refine(consensus) for consensus in consensuses for refine in refiners
    )
    try:
        return next(
            refinement
            for refinement in refinements
            if min_names <= len(refinement) <= max_names
        )
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
    incorrect = "incorrect"
    all = "all"

    def __str__(self) -> str:
        return self.value


def decide_entry_type(entry: Entry) -> Sequence[EntryType]:
    min_names, max_names = min_max_names(entry["emails"], entry["phones"])
    if not max_names:
        return tuple()
    if min_names <= len(entry["names"]) <= max_names:
        return (EntryType.all, EntryType.correct)
    return (EntryType.all, EntryType.incorrect)


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
        print("{}: {:.2%}. ".format(entry_type, fraction), end="")
    print()
    return (entries_by_type, counts)


def main() -> Tuple[Mapping, Mapping]:
    with open("data/trello.csv", encoding="utf-8") as in_file:
        lines = list(csv.reader(in_file))[1:]
    with cache:
        entries = [extract_info(line[0]) for line in lines]
    with open("data/info.csv", "w", encoding="utf-8") as out_file:
        save_entries(entries, out_file)
    return analyze_metrics(entries)


if __name__ == "__main__":
    metrics = main()
