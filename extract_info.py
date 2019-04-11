import csv
import json
import re
import itertools
import functools
import string
import argparse
from collections import defaultdict, Counter
from pprint import pprint as pp
from pdb import pm
import nltk
from nltk.corpus import wordnet
from google_analyze import analyze_entities
from googleapiclient.errors import HttpError

PHONE_RE = re.compile(r'(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{3}[-\.\s]??\d{4})')
EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+')

## generic functions

def pad_infinite(iterable, padding=None):
    "infinitely pad an iterable"
    return itertools.chain(iterable, itertools.repeat(padding))

def pad(iterable, size, padding=""):
    "pad an iterable to length size"
    return list(itertools.islice(pad_infinite(iterable, padding), size))


class Cache:
    """
    non-functional cache for storing expensive computation in between
    program runs, as a function decorator.
    only stores the first argument and repeats it exactly once when saving
    to disk, i.e. {arg: {func1: result1, func2: result2}, arg2: {...}, ...}
    use finally: to make sure the cache gets saved
    """
    def __init__(self, cachename="cache.json"):
        self.cachename = cachename
        self.funcs = []
        self.cache = None

    def open_cache(self):
        try:
            data = json.load(open(self.cachename, encoding="utf-8"))
        except IOError:
            data = {}
        self.cache = defaultdict(
            lambda : {},
            data
        )

    def save_cache(self):
        with open(self.cachename, "w", encoding="utf-8") as f:
            json.dump(dict(self.cache), f)
        print("saved cache")

    def clear_cache(self, func):
        for item in self.cache.values():
            if func in item:
                del item[func]

    def with_cache(self, decorated):
        func = decorated.__name__
        self.funcs.append(func)
        @functools.wraps(decorated)
        def wrapper(text, *args, **kwargs):
            try:
                if self.cache[text][func] is not None:
                    return self.cache[text][func]
            except KeyError:
                pass
            value = decorated(text, *args, **kwargs)
            self.cache[text][func] = value
            return value
        return wrapper

cache = Cache()

# extracting info

@cache.with_cache
def extract_phones(text):
    "returns phone numbers in text"
    phone_numbers = [
        re.sub(r'\D', '', number)
        for number in PHONE_RE.findall(text)
    ]
    return phone_numbers

@cache.with_cache
def extract_emails(text):
    "returns emails in text"
    return EMAIL_RE.findall(text)

@cache.with_cache
def extract_names(text):
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
def g_extract_names(text):
    "returns names using Google Cloud Knowledge Graph Named Entity Recognition"
    try:
        results = analyze_entities(text)
    except HttpError:
        return []
    return [
        entity['name']
        for entity in results['entities']
        if entity['type'] == "PERSON"
    ]


def refine_names(names, goal):
    "removes words that have wordnet synonyms"
    refined_names = [
        name
        for name in names
        if not any(len(wordnet.synsets(word)) > 1 for word in name.split())
    ]
    keep = len(refined_names) == goal
    if args.debug:
        if keep:
            print ("refined {} to {}. goal: {}, keeping: {}".format(
                names,
                refined_names,
                goal,
                keep
            ))
    if keep:
        return refined_names
    return names

def space_dashes(text):
    "put spaces around dashes without spaces"
    return re.sub(r"-([^ -])", r"- \1", re.sub(r"([^ -])-", r"\1 -", text))

def remove_non_alpha(text):
    "remove words that don't have any alphabetical chareceters or -"
    return " ".join([
            word for word in text.split()
            if (word not in extract_emails(text)
                and any((c.isalpha() or c == "-") for c in word))
        ])

@cache.with_cache
def extract_info(line, refine=True):
    result = {
        "line":   [line.replace("'", "").replace("\n", "")],
        "emails": extract_emails(line),
        "phones": extract_phones(line)
    }
    text = space_dashes(line)
    contacts = max(len(result["emails"]), len(result["phones"]))
    if contacts == 0:
        names = ["skipped"]
    else:
        # preprocess
        clean_text = remove_non_alpha(text)
        # find names
        name_attempt =  extract_names(text)
        """max(
            extract_names(clean_text),
            extract_names(text),
            key=len
        )"""
        if len(name_attempt) < contacts:
            names = [word for word in text.split() if word[0].isupper()]
        else:
            names = name_attempt
        # if not correct, compare and filter with g_names
        if len(names) > contacts:
            g_names = g_extract_names(
                "".join([c for c in clean_text if c in string.printable])
            )
            if g_names:
                names_intersect = [
                    name
                    for name in names
                    if name[0] not in string.printable or [
                        part
                        for g_name in g_names
                        for part in name.split()
                        if part in g_name
                    ]
                ]
            # maybe refine with synset
                if refine and len(names_intersect) > contacts:
                    result["names"] = refine_names(names_intersect, contacts)
                    return result
                result["names"] = names_intersect
                return result
    result["names"] = names
    return result


def classify(entry):
    contacts = max(len(entry["emails"]), len(entry["phones"]))
    names = len(entry["names"])
    if contacts == 0:
        return (0, 0)
    else:
        if contacts == 1:
            contacts_type = 1
        else:
            contacts_type = 2
        if names < contacts:
            names_type = -1
        elif names == contacts:
            names_type = 1
        else:
            names_type = 2
        return (contacts_type, names_type)


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
        cols = ["line", "emails", "phones", "names"]
        lines = open("trello.csv", encoding="utf-8").readlines()[1:]
        entries = [
            extract_info(line, refine=args.refine)
            for line in lines
        ]
        ## counting
        entries.sort(key=classify)
        entry_types = {k: list(g) for k, g in itertools.groupby(entries, classify)}
        counts = Counter(map(classify, entries))
        total = sum(counts.values()) - counts[(0, 0)]
        print(
            "true positive: {:.3}, false negative: {:.3}"
            ", false positive: {:.3}".format(
            (counts[(1, 1)] + counts[(2, 1)]) / total,
            (counts[(1, -1)] + counts[(2, -1)]) / total,
            (counts[(1, 2)] + counts[(2, 2)]) / total
        ))

        # padding
        max_len = {
            key: max(map(len, [entry[key] for entry in entries]))
            for key in cols
        }
        header = [heading for k in cols for heading in pad([k], max_len[k])]
        rows = [
            [
                item
                for key in cols
                for item in pad(entry[key], max_len[key])
            ]
            for entry in entries
        ]
        with open("info.csv", "w", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
    finally:
        cache.save_cache()

"""
[technillogue@spock:~/misc/dad]$ python -i extract_info.py --clear --preprocess --keep
true positive: 0.6172839506172839, false negative: 0.19547325102880658, false positive: 0.18724279835390947
saved cache
>>>

[technillogue@spock:~/misc/dad]$ python -i extract_info.py --clear --keep
true positive: 0.565843621399177, false negative: 0.24279835390946503, false positive: 0.19135802469135801
saved cache
>>>

[technillogue@spock:~/misc/dad]$ python -i extract_info.py --clear --preprocess --keep
true positive: 0.588477366255144, false negative: 0.2345679012345679, false positive: 0.17695473251028807
saved cache
"""

#$ python -i extract_info.py --clear --preprocess --keep
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
