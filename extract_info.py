import csv
import json
import re
import itertools
import functools
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
    return itertools.chain(iterable, itertools.repeat(padding))

def pad(iterable, size, padding=""):
    return list(itertools.islice(pad_infinite(iterable, padding), size))

def take_until(stop_condition, iterable):
    for x in iterable:
        yield x
        if stop_condition(x):
            break

class Cache:
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
    phone_numbers = [
        re.sub(r'\D', '', number)
        for number in PHONE_RE.findall(text)
    ]
    return phone_numbers

@cache.with_cache
def extract_emails(text):
    return EMAIL_RE.findall(text)

@cache.with_cache
def extract_names(text):
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

@cache.with_cache
def extract_info(text, refine=True):
    # if there's no contact info, skip it
    # if there's one contact and one normal name, great
    # if less normal names than contacts:
    # try google
    # if google doesn't know, try stripping punctuation
    # if that's too much try stripping synonyms

    # if text in cache:
    #    return cache[text]
    result = {
        "line":   [text.replace("'", "").replace("\n", "")],
        "emails": extract_emails(text),
        "phones": extract_phones(text)
    }
    contacts = max(len(result["emails"]), len(result["phones"]))
    if contacts == 0:
        names = ["skipped"]
    else:
        # preprocess
        clean_text = " ".join([
            word for word in text.split()
            if (word not in extract_emails(text)
                and any(c.isalpha() for c in word))
        ])
        names = extract_names(clean_text)
        # if not correct, compare and filter with g_names
        if len(names) > contacts:
            g_names = g_extract_names(clean_text)
            if g_names:
                names_intersect = [
                    name
                    for name in names
                    if [
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
            writer.writerow(rows)
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
