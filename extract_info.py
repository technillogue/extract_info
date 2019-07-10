from __future__ import division
import sys
import csv
import argparse
from enum import Enum
from itertools import zip_longest, tee
from typing import List, Mapping, Tuple, Sequence, Iterator, Any
from strategies import Stages, STAGES
from cache import cache
from helpers import extract_contacts, space_dashes

Names = List[str]
NameAttempts = Iterator[Names]
Entry = Mapping[str, Names]


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
    refinements, fallback = tee(
        refine(consensus) for consensus in consensuses for refine in refiners
    )
    try:
        return next(
            refinement
            for refinement in refinements
            if min_names <= len(refinement) <= max_names
        )
    except StopIteration:
        every_refinement = list(
            fallback
        )  # note: this may have a bunch of [] at the end
        if max(map(len, every_refinement)) < min_names:
            return max(every_refinement, key=len)
        return min(
            filter(None, every_refinement), key=len, default=list()
        )  # smallest non-empty but [] if they're all empty


def min_max_names(emails: List[str], phones: List[str]) -> Tuple[int, int]:
    contact_counts: Tuple[int, int] = (len(emails), len(phones))
    # if there's 1 email and 3 phones, min_names should be 1
    # but if there's 0 email and 1 phone, it should be 1, not 0
    min_names: int = max(1, min(contact_counts))
    max_names: int = max(contact_counts)
    # maybe add min, likely_max, absolute_max to distingish max vs sum?
    return (min_names, max_names)


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


def save_entries(entries: Sequence[Entry], fname: str) -> None:
    header = ["line", "emails", "phones", "names"]
    with open(fname, "w", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for entry in entries:
            contact_infos = [entry[heading] for heading in header]
            contacts = zip_longest(*contact_infos, fillvalue="")
            for contact in contacts:
                writer.writerow(list(contact))


class EntryType(str, Enum):
    correct = "correct"
    too_many = "too many"
    not_enough = "not enough"
    multiple_contacts = "multiple contacts"
    one_contact = "one_contact"
    all = "all"
    skipped = "skipped"

    def __str__(self) -> str:
        return self.value


def decide_entry_type(entry: Entry) -> Sequence[EntryType]:
    min_names, max_names = min_max_names(entry["emails"], entry["phones"])
    if not max_names:
        return (EntryType.skipped,)
    entry_types = (
        EntryType.all,
        (EntryType.one_contact if max_names == 1 else EntryType.multiple_contacts),
    )
    names_count = len(entry["names"])
    if names_count <= max_names:
        if names_count < min_names:
            return entry_types + (EntryType.not_enough,)
        return entry_types + (EntryType.correct,)
    return entry_types + (EntryType.too_many,)


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
    for entry_type in list(EntryType)[:4]:
        print(
            "{}: {:.2%}. ".format(
                entry_type, counts[entry_type] / counts[EntryType.all]
            ),
            end="",
        )
    print()
    return (entries_by_type, counts)


def main() -> Tuple[Mapping, Mapping]:
    parser = argparse.ArgumentParser("extract names and contact info from csv")
    parser.add_argument("-i", "--input", default="data/trello.csv")
    parser.add_argument("-o", "--output", default="data/info.csv")
    args = parser.parse_args()
    lines = list(csv.reader(open(args.input, encoding="utf-8")))[1:]
    with cache:
        entries = [extract_info(line[0]) for line in lines]
    save_entries(entries, args.output)
    return analyze_metrics(entries)


if __name__ == "__main__":
    metrics = main()
