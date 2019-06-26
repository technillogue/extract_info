import csv
import itertools
import argparse
from typing import List, Dict, Tuple
from collections import Counter
from cache import cache
from extract_names import extract_names, extract_emails, extract_phones
# requires python3.6+

@cache.with_cache
def extract_info(raw_line: str, **flags: bool) -> Dict[str, List[str]]:
    line: str = raw_line.replace("'", "").replace("\n", "")
    emails: List[str] = extract_emails(line)
    phones: List[str] = extract_phones(line)
    contact_counts: Tuple[int, int] = (len(emails), len(phones))
    max_contacts: int = max(contact_counts)
    # if there's 1 email and 3 phones, min_contacts should be 1
    # but if there's 0 email and 1 phone, it should be 1, not 0
    min_contacts: int = max(1, min(contact_counts))
    names: List[str]
    if max_contacts == 0:
        names = ["skipped"]
    else:
        names = extract_names(line, min_contacts, max_contacts, **flags)
    return {
        "line": [line],
        "emails": emails,
        "phones": phones,
        "names": names
    }

def classify(entry: Dict[str, List[str]]) -> Tuple[str, str]:
    contact_counts: Tuple[int, int] = (
        len(entry["emails"]), len(entry["phones"])
    )
    max_contacts: int = max(contact_counts)
    min_contacts: int = max(1, min(contact_counts))
    names: int = len(entry["names"])
    contacts_type: str
    correctness: str
    if max_contacts == 0:
        return ("skipped", "skipped")
    if max_contacts == 1:
        contacts_type = "one contact"
    else:
        contacts_type = "multiple contacts"
    if names < min_contacts:
        correctness = "not enough"
    elif min_contacts <= names <= max_contacts:
        correctness = "correct"
    else:
        correctness = "too many"
    return (correctness, contacts_type)


if __name__ == "__main__":
    cache.open_cache()
    parser = argparse.ArgumentParser("extract names and contact info from csv")
    parser.add_argument("-k", "--keep", action="store_false", dest="refine")
    #parser.add_argument("-p", "--preprocess", action="store_true")
    parser.add_argument("-c", "--clear", action="store_true")
    parser.add_argument("-d", "--debug", action="store_true")
    args = parser.parse_args()
    if args.clear:
        cache.clear_cache("extract_info")
    try:
        lines = list(csv.reader(open("data/info_edited.csv", encoding="utf-8")))[1:]
        entries = [
            extract_info(line[0], refine=args.refine)
            for line in lines
        ]
        ## counting
        entries.sort(key=classify)
        entry_types = {k: list(g) for k, g in itertools.groupby(entries, classify)}
        counts = Counter(map(classify, entries))
        total = sum(counts.values()) - counts[("skipped", "skipped")]
        categories = ("correct", "not enough", "too many")
        print(", ".join(
            "{}: {:.2%}".format(
                category,
                sum(
                    counts[k] for k in counts.keys() if k[0] == category
                ) / total
            )
            for category in ("correct", "not enough", "too many")
        ))
        # padding
        header = ["line", "emails", "phones", "names"]
        rows = [
            list(triple)
            for entry in entries
            for triple in itertools.zip_longest(
                *map(entry.get, header),
                ""
            )
        ]
        with open("data/info.csv", "w", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
    finally:
        cache.save_cache()

# preprocess, keep
# true positive: 0.6172839506172839, false negative: 0.19547325102880658, false positive: 0.18724279835390947

# don't preprocess, keep
#true positive: 0.565843621399177, false negative: 0.24279835390946503, false positive: 0.19135802469135801

#preprocess, keep [unknown change]
#true positive: 0.588477366255144, false negative: 0.2345679012345679, false positive: 0.17695473251028807


#preprocess, keep [unknown change]
#true positive: 0.588477366255144, false negative: 0.2345679012345679, false positive: 0.17695473251028807


# cleaned up, fixed preprocessing bug, one preprocessing method
#$ python -i extract_info.py --clear
#true positive: 0.533, false negative: 0.416, false positive: 0.0514

# only compare google if it gives an answer
#$ python -i extract_info.py --clear
#true positive: 0.533, false negative: 0.329, false positive: 0.138

# not sure what the change here is
# $ python -i extract_info.py --clear
#true positive: 0.591, false negative: 0.276, false positive: 0.134

# check max(clean, not clean) and every capitalized word
#true positive: 0.733, false negative: 0.105, false positive: 0.163

# don't check clean
#true positive: 0.726, false negative: 0.113, false positive: 0.16
# however, somewhat better performance for getting the correct name imo

# don't check clean but put spaces around -
#true positive: 0.728, false negative: 0.105, false positive: 0.167

# also remember to keep the dashses lol
# true positive: 0.77, false negative: 0.109, false positive: 0.121

# what if dashes but parsed correctly without fucking phone numbers
#true positive: 0.782, false negative: 0.0885, false positive: 0.13

# remove duplicate phone numbers
# true positive: 78.19%, false negative: 8.85%, false positive: 12.96%

# do things by hand? maybe some other change
# true positive: 82.51%, false negative: 4.53%, false positive: 12.96%

# add min and max contacts, give google more punctuation
# true positive: 83.54%, false negative: 4.53%, false positive: 11.93%

# send google only alpha words instead of words with alpha chars
# true positive: 83.54%, false negative: 4.53%, false positive: 11.93%


# a lot of errors are based on incorrectly identifying locations
# spacy might help a lot, actually, for forming consensus
# approches: examine every extra word to see if it's in google
# try different preprocessing to see where google gives max results

# cleaner data
# true positive: 84.57%, false negative: 4.53%, false positive: 10.91%

# refactored, maybe refine in all cases
# true positive: 86.63%, false negative: 4.53%, false positive: 8.85%

# use google to check every name seperately
# true positive: 87.04%, false negative: 4.53%, false positive: 8.44%

# actually always refine and trust google to say 'nothing'
# true positive: 85.39%, false negative: 6.79%, false positive: 7.82%
# welp

# don't trust google to say nothing
# true positive: 87.04%, false negative: 4.53%, false positive: 8.44%

# after some early refactoring that wasn't checked correctly
# correct: 86.83%, not enough: 4.53%, too many: 8.64%

# after tweaking refine,
# correct: 86.42%, not enough: 5.35%, too many: 8.23%
