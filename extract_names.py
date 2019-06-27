from itertools import permutations, combinations, product, filterfalse, chain
from functools import reduce, partial
import re
import string
from typing import List, Callable, Iterator
import nltk
from nltk.corpus import wordnet
from googleapiclient.errors import HttpError
from google_analyze import analyze_entities
from utils import cache, compose, identity_function

Names = List[str]

def space_dashes(text: str) -> str:
    "put spaces around dashes without spaces"
    return re.sub(r"-([^ -])", r"- \1", re.sub(r"([^ -])-", r"\1 -", text))

@cache.with_cache
def nltk_extract_names(text: str) -> Names:
    "returns names using NLTK Named Entity Recognition, filters out repetition"
    names = []
    for sentance in nltk.sent_tokenize(text):
        for chunk in nltk.ne_chunk(nltk.pos_tag(nltk.word_tokenize(sentance))):
            if isinstance(chunk, nltk.tree.Tree):
                if chunk.label() == 'PERSON':
                    names.append(' '.join([c[0] for c in chunk]))
    for name1, name2 in permutations(names, 2):
        if name1 in name2:
            names.remove(name1)
    return names


def contains_nonlatin(text: str) -> bool:
    return not any(string.printable.__contains__(c) for c in text)

@cache.with_cache
def google_extract_names(text: str) -> Names:
    """
    returns names using Google Cloud Knowledge Graph Named Entity Recognition
    skips non-ASCII charecters
    """
    text = "".join(c for c in text if not contains_nonlatin(c))
    try:
        results = analyze_entities(text)
    except HttpError:
        return []
    return [
        entity['name']
        for entity in results['entities']
        if entity['type'] == "PERSON"
    ]

## preprocessing functions to use with google
def only_alpha(text: str) -> str:
    "remove words that don't have any alphabetical chareceters or -"
    return " ".join([
        word for word in text.split()
        if all(c.isalpha() or c in r"-\!$%(,.:;?" for c in word)
    ])

def every_name(names: Names) -> str:
    return "".join(map(
        "My name is {}. ".format,
        names
    ))

def fuzzy_union(crude_names: Names, google_names: Names) -> Names:
    union = []
    for crude_name in crude_names:
        if contains_nonlatin(crude_name):
            union.append(crude_name)
            # google doesn't work with non-latin characters
            # so we ignore it in those cases
        else:
            for google_name in google_names:
                if [part for part in crude_name.split() if part in google_name]:
                    union.append(crude_name)
    return union

#@cache.with_cache
def remove_synonyms(names: Names) -> Names:
    "removes words that have wordnet synonyms"
    return [
        name
        for name in names
        if not any(len(wordnet.synsets(word)) > 1 for word in name.split())
    ]

def remove_nonlatin(names: Names) -> Names:
    return list(filterfalse(contains_nonlatin, names))

UNIQUE_REFINERS = [remove_synonyms, remove_nonlatin]

REFINERS: List[Callable[[Names], Names]]
REFINERS = [identity_function] + list(map(
    partial(reduce, compose),
    chain(*(map(
        partial(combinations, UNIQUE_REFINERS),
        range(1, len(UNIQUE_REFINERS)))
    ))
))
 
def extract_names(line: str, min_names: int, max_names: int) -> Names:
    text = space_dashes(line)
    # get a crude attempt
    nltk_names: Names = nltk_extract_names(text)
    if len(nltk_names) >= min_names:
        crude_names = nltk_names
    else:
        crude_names = [word for word in text.split() if word[0].isupper()]
    # if we have too many names, get google's attempt
    names_filtered: Names
    if len(crude_names) <= max_names:
        names_filtered = crude_names
    else:
        # try to do it with google
        approaches = (
            lambda: only_alpha(text),
            lambda: text,
            lambda: every_name(crude_names)
        ) # unfortunately the only way to make this lazy in python
        google_names: Names = next(filter(
            None,
            (google_extract_names(approach()) for approach in approaches)
        ), [])
        if google_names:
            names_filtered = fuzzy_union(crude_names, google_names)
        else:
            names_filtered = crude_names
    consensuses = [names_filtered]

    refined_consensuses: Iterator[Names] = (
        refine(consensus)
        for consensus, refine in product(consensuses, REFINERS)
    )
    while True:
        try:
            last_consensus = next(refined_consensuses)
            if min_names <= len(last_consensus) <= max_names:
                return last_consensus
        except StopIteration:
            return last_consensus
