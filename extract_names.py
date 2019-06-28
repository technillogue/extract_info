import re
import string
from itertools import (
    permutations, combinations, product, filterfalse, chain#, starmap
)
from functools import reduce, partial
from typing import List, Callable, Iterator, Tuple, Sequence
import nltk
from nltk.corpus import wordnet
import google_analyze
from utils import cache, compose, identity_function, soft_filter

Names = List[str]

# general functions

def space_dashes(text: str) -> str:
    "put spaces around dashes without spaces"
    return re.sub(r"-([^ -])", r"- \1", re.sub(r"([^ -])-", r"\1 -", text))

def contains_nonlatin(text: str) -> bool:
    return not any(string.printable.__contains__(c) for c in text)

# combinatorial functions

## extractors

### "crude" extractors

@cache.with_cache
def nltk_extract_names(text: str) -> Names:
    "returns names using NLTK Named Entity Recognition, filters out repetition"
    names = []
    for sentance in nltk.sent_tokenize(text):
        for chunk in nltk.ne_chunk(nltk.pos_tag(nltk.word_tokenize(sentance))):
            if isinstance(chunk, nltk.tree.Tree):
                if chunk.label() == 'PERSON':
                    names.append(' '.join([c[0] for c in chunk]))
    # remove any names that contain each other
    for name1, name2 in permutations(names, 2):
        if name1 in name2:
            names.remove(name1)
    return names

def all_capitalized_extract_names(text: str) -> List[str]:
    return [
        "".join(filter(str.isalpha, word))
        for word in text.split() if word[0].isupper()
    ]

CRUDE_EXTRACTORS: List[Callable[[str], Names]] = [
    nltk_extract_names, all_capitalized_extract_names
]

### google extractor and preprocessors

@cache.with_cache
def google_extract_names(text: str) -> Names:
    """
    returns names using Google Cloud Knowledge Graph Named Entity Recognition
    skips non-ASCII charecters
    """
    text = "".join(c for c in text if not contains_nonlatin(c))
    return google_analyze.extract_entities(text)

# check if simplifying this logic reduces accuracy
def only_alpha(text: str) -> str:
    "remove words that don't have any alphabetical chareceters or -"
    return " ".join([
        word for word in text.split()
        if all(c.isalpha() or c in r"-\!$%(,.:;?" for c in word)
    ])

def every_name(line: str) -> str:
    potential_names = "".join(filter(str.isalpha, line)).split()
    return "".join(map(
        "My name is {}. ".format,
        potential_names
    ))


GOOGLE_EXTRACTORS = list(map(
    partial(compose, google_extract_names),
    [only_alpha, identity_function, every_name]
))

## refiners

def fuzzy_union(set_pair: Tuple[Names, Names]) -> Names:
    google_names, crude_names = set_pair
    if google_names == []:
        return crude_names
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

@cache.with_cache
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

REFINERS: Sequence[Callable[[Names], Names]]
REFINERS = [identity_function] + list(map(
    partial(reduce, compose),
    chain(*(map(
        partial(combinations, UNIQUE_REFINERS),
        range(1, len(UNIQUE_REFINERS))
    )))
))

def extract_names(line: str, min_names: int, max_names: int) -> Names:
    text: str = space_dashes(line)
    def min_criteria(names: Names) -> bool:
        return len(names) >= min_names
    google_extractions: Iterator[Names] = soft_filter(
        min_criteria,
        (extractor(text) for extractor in GOOGLE_EXTRACTORS)
    )
    crude_extractions: Iterator[Names] = soft_filter(
        min_criteria,
        (extractor(text) for extractor in CRUDE_EXTRACTORS)
    )
    consensuses: Iterator[Names] = filter(
        min_criteria,
        map(fuzzy_union, product(google_extractions, crude_extractions))
    )
    refined_consensuses: Iterator[Names] = soft_filter(
        lambda consensus: min_names <= len(consensus) <= max_names,
        (
            refine(consensus)
            for consensus, refine in product(consensuses, REFINERS)
        )
    )
    return next(refined_consensuses)
