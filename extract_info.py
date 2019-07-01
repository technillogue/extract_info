from __future__ import division
import sys
import csv
import re
import itertools
import argparse
from typing import List, Dict, Tuple, Any
from extract_names import extract_names
from utils import cache


# requires python3.6+

PHONE_RE = re.compile(
    r"(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{3}[-\.\s]??\d{4})"
)
EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+")


def space_dashes(text: str) -> str:
    "put spaces around dashes without spaces"
    return re.sub(r"-([^ -])", r"- \1", re.sub(r"([^ -])-", r"\1 -", text))


def extract_phones(text: str) -> List[str]:
    "returns phone numbers in text"
    phone_numbers = [re.sub(r"\D", "", number) for number in PHONE_RE.findall(text)]
    # removes duplicates while preserving order, only works correctly in
    # python3.6+
    return list(dict.fromkeys(phone_numbers))


def extract_emails(text: str) -> List[str]:
    "returns emails in text"
    return EMAIL_RE.findall(text)


def min_max_names(emails: List[str], phones: List[str]) -> Tuple[int, int]:
    contact_counts: Tuple[int, int] = (len(emails), len(phones))
    # if there's 1 email and 3 phones, min_names should be 1
    # but if there's 0 email and 1 phone, it should be 1, not 0
    min_names: int = max(1, min(contact_counts))
    max_names: int = sum(contact_counts)
    return (min_names, max_names)


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
        names = extract_names(
            space_dashes(line), min_names, max_names, **extract_names_kwargs
        )
    print(".", end="")
    sys.stdout.flush()
    result = {"line": [line], "emails": emails, "phones": phones, "names": names}
    if flags:
        return {
            **result,
            "flags": ["skipped"]
            if not max_names
            else [
                "one contact" if max_names == 1 else "multiple names",
                "not enough"
                if len(names) < min_names
                else ("correct" if len(names) <= max_names else "too many"),
                "all",
            ],
        }
    return result


if __name__ == "__main__":
    cache.open_cache()
    parser = argparse.ArgumentParser("extract names and contact info from csv")
    # parser.add_argument("-p", "--preprocess", action="store_true")
    parser.add_argument("-c", "--clear", action="store_true")
    parser.add_argument("-d", "--debug", action="store_true")
    args = parser.parse_args()
    if args.clear:
        cache.clear_cache("extract_info")
    try:
        lines = list(csv.reader(open("data/info_edited.csv", encoding="utf-8")))[1:]
        entries = [extract_info(line[0], flags=True) for line in lines]
        entry_types = {
            flag: [entry for entry in entries if flag in entry["flags"]]
            for flag in [
                "too many",
                "correct",
                "not enough",
                "multiple contacts",
                "one contact",
                "all",
            ]
        }
        counts = dict(zip(entry_types.keys(), map(len, entry_types.values())))
        print(
            ", ".join(
                "{}: {:.2%}".format(category, counts[category] / counts["all"])
                for category in ("correct", "not enough", "too many")
            )
        )
        # padding
        header = ["line", "emails", "phones", "names"]
        rows = [
            list(triple)
            for entry in entries
            for triple in itertools.zip_longest(  # type: ignore
                *map(entry.get, header), ""
            )
            # this has incompatible type "*Iterator[Optional[List[str]]]"; expected "Iterable[Any]"
            # but I don't remember the logic for this, so I'm leaving it alone until
            # I decide to replace this with long instead of wide format
        ]
        with open("data/info.csv", "w", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
    finally:
        cache.save_cache()
