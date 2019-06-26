import csv
import json
import re
import itertools
import argparse
from string import printable
from typing import Callable, List, Dict
from collections import defaultdict, Counter
import nltk
from nltk.corpus import wordnet
from googleapiclient.errors import HttpError
from google_analyze import analyze_entities
from cache import cache
# requires python3.6+

PHONE_RE = re.compile(r'(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{3}[-\.\s]??\d{4})')
EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+')


# extracting info

@cache.with_cache
def extract_phones(text: str) -> List[str]:
    "returns phone numbers in text"
    phone_numbers = [
        re.sub(r'\D', '', number)
        for number in PHONE_RE.findall(text)
    ]
    # removes duplicates while preserving order, only works correctly in
    # python3.6+
    return list(dict.fromkeys(phone_numbers))

@cache.with_cache
def extract_emails(text: str) -> List[str]:
    "returns emails in text"
    return EMAIL_RE.findall(text)

@cache.with_cache
def extract_names(text: str) -> List[str]:
    "returns names using NLTK Named Entity Recognition, filters out repetition"
    names = []
    for sentance in nltk.sent_tokenize(text):
        for chunk in nltk.ne_chunk(nltk.pos_tag(nltk.word_tokenize(sentance))):
            if isinstance(chunk, nltk.tree.Tree):
                if chunk.label() == 'PERSON':
                    names.append(' '.join([c[0] for c in chunk]))
    for name1, name2 in itertools.permutations(names, 2):
        if name1 in name2:
            names.remove(name1)
    return names

@cache.with_cache
def g_extract_names(text: str) -> List[str]:
    """
    returns names using Google Cloud Knowledge Graph Named Entity Recognition
    skips non-ASCII charecters
    """
    text = "".join(filter(printable.__contains__, text))
    try:
        results = analyze_entities(text)
    except HttpError:
        return []
    return [
        entity['name']
        for entity in results['entities']
        if entity['type'] == "PERSON"
    ]


def refine_names(names: List[str], min_goal: int, max_goal: int) -> List[str]:
    "removes words that have wordnet synonyms, then maybe removes nonlatin"
    refined_names = [
        name
        for name in names
        if not any(len(wordnet.synsets(word)) > 1 for word in name.split())
    ]
    if len(refined_names) > max_goal:
        pass # ADD: remove latin names
    keep = min_goal <= len(refined_names) <= max_goal
    if args.debug:
        if keep:
            print("refined {} to {}. goal: {}-{}, keeping: {}".format(
                names,
                refined_names,
                min_goal,
                max_goal,
                keep
            ))
    if keep:
        return refined_names
    return names

def space_dashes(text: str) -> str:
    "put spaces around dashes without spaces"
    return re.sub(r"-([^ -])", r"- \1", re.sub(r"([^ -])-", r"\1 -", text))

def only_alpha(text: str) -> str:
    "remove words that don't have any alphabetical chareceters or -"
    return " ".join([
        word for word in text.split()
        if (word not in extract_emails(text)
            and all((c.isalpha() or c in r"-\!$%(,.:;?") for c in word))
    ])

def every_name(names: str) -> str:
    return "".join(map(
        "My name is {}. ".format,
        names
    ))

cases: defaultdict = defaultdict(
    lambda: defaultdict(lambda: defaultdict(lambda: 0))
)

@cache.with_cache
def extract_info(line, refine=True):
    result = {
        "line":   [line.replace("'", "").replace("\n", "")],
        "emails": extract_emails(line),
        "phones": extract_phones(line)
    }
    text = space_dashes(line)
    max_contacts = max(len(result["emails"]), len(result["phones"]))
    if max_contacts == 0:
        result["names"] = ["skipped"]
        return result
    # e.g. if there's 0 email and 1 phone, it's 1,
    # but if there's 1 email and 3 phone it's 1.
    min_contacts = max(1, min(len(result["emails"]), len(result["phones"])))
    # preprocess

    # get more names
    name_attempt = extract_names(text)
    if len(name_attempt) < min_contacts:
        n_status = "n_every_cap"
        names = [word for word in text.split() if word[0].isupper()]
    else:
        n_status = "n_good"
        names = name_attempt
    # maybe filter out names
    if len(names) <= max_contacts:
        names_filtered = names
        g_approach = "no_g"
    else:
        # only_alpha(text), text, map(names)
        # try to do it with google
        approaches = (
            lambda: only_alpha(text),
            lambda: text,
            lambda: every_name(names)
        ) # unfortunately the only way to make this lazy in python
        g_approach, g_names = next(
            filter(
                lambda e: bool(e[1]),
                enumerate(
                    g_extract_names(approach()) for approach in approaches
                )
            ),
            ("g_failed", None)
        )
        if g_names:
            names_filtered = [
                name
                for name in names
                if name[0] not in printable or [
                    part
                    for g_name in g_names
                    for part in name.split()
                    if part in g_name
                ]
            ]
        else:
            names_filtered = names
    # maybe refine with synset and discarding nonlatin names
    if refine and len(names_filtered) > max_contacts:
        result["names"] = refine_names(
            names_filtered,
            min_contacts,
            max_contacts
        )
    else:
        result["names"] = names_filtered
    if not min_contacts <= len(result["names"]) <= max_contacts:
        cases[n_status][g_approach][
            "too much" if len(result["names"]) > max_contacts else "too little"
        ] += 1
    return result


def classify(entry):
    max_contacts = max(len(entry["emails"]), len(entry["phones"]))
    min_contacts = max(1, min(len(entry["emails"]), len(entry["phones"])))
    names = len(entry["names"])
    if max_contacts == 0:
        return (-1, -1)
    else:
        if max_contacts == 1:
            contacts_type = 1
        else:
            contacts_type = 2
        if names < min_contacts:
            names_type = 2 # type 2 error, not enough names, false negative
        elif min_contacts <= names <= max_contacts:
            names_type = 0 # correct
        else:
            names_type = 1 # type 1 error, too many names, false positive
        return (names_type, contacts_type)


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
        total = sum(counts.values()) - counts[(-1, -1)]
        print(
            "true positive: {:.2%}, false negative: {:.2%}"
            ", false positive: {:.2%}".format(*[
                sum(
                    counts[k] for k in counts.keys() if k[0] == names_type
                ) / total
                for names_type in (0, 2, 1)
            ])
        )
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
