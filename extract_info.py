# information-extraction.py
import csv
import json
import re
import itertools
import functools
from collections import defaultdict
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

def count_dict(d):
    return {k:len(d[k]) for k in d.keys()}

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
            lambda : {func: None for func in self.funcs},
            data
        )

    def save_cache(self):
        with open(self.cachename, "w", encoding="utf-8") as f:
            json.dump(dict(self.cache), f)
        print("saved cache")

    def with_cache(self, decorated):
        func = decorated.__name__
        self.funcs.append(func)
        @functools.wraps(decorated)
        def wrapper(text):
            if self.cache[text][func] is not None:
                return self.cache[text][func]
            value = decorated(text)
            self.cache[text][func] = value
            return value
        return wrapper

cache = Cache()

# extracting info

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

def filter_alpha(text):
    return " ".join([
        word for word in text.split()
        if word not in extract_emails(text)
        and any(c.isalpha for c in word)
    ])


def get_more_names(text, goal):
    methods = (
        extract_names,
        g_extract_names
    )
    preprocesses = (
        lambda text: text,
        lambda text: text.replace("-", ""),
        filter_alpha
    )
    # ideally this should be an inclusive takeUntil, but oh well
    return list(take_until(
        lambda attempt: len(attempt) > goal,
        [
            method(preprocess(text))
            for preprocess in preprocesses
            for method in methods
        ]
    ))

def refine_names(name_attempts, goal):
    # add more comparisons to previous attempts later
    if len(name_attempts[-1]) > goal:
        return [
            name
            for name in name_attempts[-1]
            if not any(wordnet.synsets(word) for word in name)
        ]
    else:
        return name_attempts[-1]


def extract_info(text):
    # if there's no contact info, skip it
    # if there's one contact and one normal name, great
    # if less normal names than contacts:
    # try google
    # if google doesn't know, try stripping punctuation
    # if that's too much try stripping synonyms

    # if text in cache:
    #    return cache[text]
    result = {
        "line":   text.replace("'", "").replace("\n", ""),
        "emails": extract_emails(text),
        "phones": extract_phones(text)
    }
    contacts = max(len(result["emails"]), len(result["phones"]))
    if contacts == 0:
        result["names"] = result["g_names"] = ["skipped"]
    else:
        result["name_attempts"] = get_more_names(text, contacts)
        result["names"] = refine_names(result["name_attempts"], contacts)
    return result


def classify(entry):
    contacts = max(len(entry["emails"]), len(entry["phones"]))
    names = len(entry["names"])
    if contacts == 0:
        return "n/a"
    else:
        if contacts == 1:
            contacts_type = "1 contact"
        else:
            contacts_type = "many contacts"
        if names < contacts:
            names_type = "not enough names"
        elif names == contacts:
            names_type = "success"
        else:
            names_type = "too many names"
        return (contacts_type, names_type)


if __name__ == "__main__":
    cache.open_cache()
    try:
        cols = ["emails", "phones", "names", "g_names"]
        lines = open("trello.csv", encoding="utf-8").readlines()[1:]
        entries = [extract_info(line) for line in lines]

        ## counting
        entries.sort(key=classify)
        entry_types = {k: g for k, g in itertools.groupby(entries, classify)}
        entry_types_counts = count_dict(entry_types)

        # padding
        max_len = {
            key: max(map(len, [entry[key] for entry in entries]))
            for key in cols + ["line"]
        }
        header = ["line"] + [pad([k], max_len[k]) for k in cols]
        rows = [
            [
                item
                for key in entry.keys()
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
