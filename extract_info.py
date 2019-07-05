from __future__ import division
import sys
import csv
import re
import itertools
import argparse
from enum import Enum
from typing import List, Dict, Tuple, Any
from extract_names import extract_names
from utils import cache
# requires python3.6+

Names = List[str]
Entry = Dict[str, Names]

class Flags(str, Enum):
    correct = "correct"
    too_many = "too many"
    not_enough = "not enough"
    multiple_contacts = "multiple contacts"
    one_contact = "one_contact"
    all = "all"
    skipped = "skipped"

    def __str__(self) -> str:
        return self.value


PHONE_RE = re.compile(
    r"(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{3}[-\.\s]??\d{4})"
)
EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+")


def space_dashes(text: str) -> str:
    "Put spaces around dashes without spaces."
    return re.sub(r"-([^ -])", r"- \1", re.sub(r"([^ -])-", r"\1 -", text))


def extract_phones(text: str) -> List[str]:
    phone_numbers = [re.sub(r"\D", "", number) for number in PHONE_RE.findall(text)]
    # removes duplicates while preserving order, only works correctly in python3.6+
    return list(dict.fromkeys(phone_numbers))


def extract_emails(text: str) -> List[str]:
    return EMAIL_RE.findall(text)


def min_max_names(emails: List[str], phones: List[str]) -> Tuple[int, int]:
    contact_counts: Tuple[int, int] = (len(emails), len(phones))
    # if there's 1 email and 3 phones, min_names should be 1
    # but if there's 0 email and 1 phone, it should be 1, not 0
    min_names: int = max(1, min(contact_counts))
    max_names: int = sum(contact_counts)
    # maybe add min, likely_max, absolute_max to distingish max vs sum?
    return (min_names, max_names)


def decide_exit_type(names: List[str], min_names: int, max_names: int) -> Flags:
    names_count = len(names)
    if names_count <= max_names:
        if names_count < min_names:
            return Flags.not_enough
        return Flags.correct
    return Flags.too_many


def extract_info(
    raw_line: str, flags: bool = False, **extract_names_kwargs: Any
) -> Dict[str, List[str]]:
    line: str = raw_line.replace("'", "").replace("\n", "")
    emails: List[str] = extract_emails(line)
    phones: List[str] = extract_phones(line)
    min_names, max_names = min_max_names(emails, phones)
    names: List[str]
    if max_names == 0:
        names = ["skipped"]
    else:
        clean_line = space_dashes(line)
        names = extract_names(clean_line, min_names, max_names, **extract_names_kwargs)
    print(".", end="")
    sys.stdout.flush()
    result = {"line": [line], "emails": emails, "phones": phones, "names": names}
    if flags:
        if not max_names:
            result["flags"] = [Flags.skipped]
            return result
        result["flags"] = [
            (Flags.one_contact if min_names == 1 else Flags.multiple_contacts),
            decide_exit_type(names, min_names, max_names),
            Flags.all,
        ]
    return result


def main() -> Dict:
    parser = argparse.ArgumentParser("extract names and contact info from csv")
    parser.add_argument("-i", "--input", default="data/trello.csv")
    parser.add_argument("-o", "--output", default="data/info.csv")
    lines = list(csv.reader(open("data/trello.csv", encoding="utf-8")))[1:]
    with cache:
        lines = list(csv.reader(open("data/trello.csv", encoding="utf-8")))[1:]
        entries = [extract_info(line[0], flags=True) for line in lines]
        entry_types = {
            flag: [entry for entry in entries if flag in entry["flags"]]
            for flag in Flags
        }
        counts = dict(zip(entry_types.keys(), map(len, entry_types.values())))
        for flag in list(Flags)[:4]:
            print("{}: {:.2%}. ".format(flag, counts[flag] / counts[Flags.all]), end="")
        # padding
        header = ["line", "emails", "phones", "names"]
        rows = [
            list(triple)
            for entry in entries
            for triple in itertools.zip_longest(
                *[entry[heading] for heading in header], fillvalue=""
            )
        ]
        with open("data/info.csv", "w", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
        return locals()


if __name__ == "__main__":
    debugging = main() 
