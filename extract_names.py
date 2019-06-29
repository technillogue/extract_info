import re
import string
from itertools import (
    permutations, combinations, filterfalse, chain, tee#starmap
)
from functools import reduce, partial
from typing import List, Callable, Iterator, Sequence, Tuple
import nltk
from nltk.corpus import wordnet
import google_analyze
from utils import cache, compose, identity_function

Names = List[str]

# general functions

def space_dashes(text: str) -> str:
    "put spaces around dashes without spaces"
    return re.sub(r"-([^ -])", r"- \1", re.sub(r"([^ -])-", r"\1 -", text))

def contains_nonlatin(text: str) -> bool:
    return not any(map(string.printable.__contains__, text))
    # .84usec faster than using a comprehension

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
    latin_text = "".join(filter(string.printable.__contains__, text))
    return google_analyze.extract_entities(latin_text)
    # TO DO: merge adjacent names

@cache.with_cache
def only_alpha(text: str) -> str:
    "remove words that don't have any alphabetical chareceters or -"
    return " ".join([
        word for word in text.split()
        if all(c.isalpha() or c in r"-/\$%(),.:;?!" for c in word)
    ])

@cache.with_cache
def every_name(line: str) -> str:
    open("every_name_ex", "a").write(line + "\n")
    return "".join(map(
        "My name is {}. ".format,
        only_alpha(line).split()
    ))
    # explore some option for merging adjacent names?

GOOGLE_EXTRACTORS = list(map(
    partial(compose, google_extract_names),
    [only_alpha, identity_function, every_name]
))

## refiners

def fuzzy_intersect(left_names: Names, right_names: Names) -> Names:
    if left_names == []:
        return right_names
    if right_names == []:
        return left_names
    intersect = [
        min(left_name, right_name, key=len)
        for left_name in left_names
        for right_name in right_names
        if any(part in left_name for part in right_name.split())
    ]
    return intersect

@cache.with_cache
def remove_synonyms(names: Names) -> Names:
    "removes words that have wordnet synonyms"
    return [
        name
        for name in names
        if not any(len(wordnet.synsets(word)) > 1 for word in name.split())
    ]

def remove_short(names: Names) -> Names:
    return [name for name in names if len(name) > 2]

UNIQUE_REFINERS = [remove_short, remove_synonyms]

REFINERS: Sequence[Callable[[Names], Names]]
REFINERS = [identity_function] + list(map(
    partial(reduce, compose),
    chain(*(map(
        partial(combinations, UNIQUE_REFINERS),
        range(1, len(UNIQUE_REFINERS))
    )))
))


def refine_consensuses(consensuses: Iterator[Tuple[Names, Names]],
                       min_names: int, max_names: int,
                       refiners: Sequence[Callable] = REFINERS
                      ) -> Iterator[Names]:
    refined_consensuses, fallback_probe, fallback = tee((
        refine(consensus)
        for nonlatin, latin in consensuses
        for refine in refiners
        for consensus in ([nonlatin + latin, latin] if nonlatin else [latin])
    ), 3)
    for refined_consensus in refined_consensuses:
        if min_names <= len(refined_consensus) <= max_names:
            yield refined_consensus
    # after checking if all of them satisfy the conditions
    # give the one that came the closest
    best = max if max(map(len, fallback_probe), default=0) < min_names else min
    yield best(
        fallback, key=len, default=[]
    )


def extract_names(line: str, min_names: int, max_names: int) -> Names:
    text: str = space_dashes(line)
    def min_criteria(partioned: Tuple[Names, Names]) -> bool:
        return sum(map(len, partioned)) > min_names
    google_extractions: Iterator[Names] = chain(filter(
        None, # i.e. lambda item: bool(item)
        (extractor(text) for extractor in GOOGLE_EXTRACTORS)
    ), [[]])
    crude_extractions: Iterator[Tuple[Names, Names]] = (
        (list(filter(contains_nonlatin, names)), # e.g. cyrillic  names
         list(filterfalse(contains_nonlatin, names))) # then latin names
        for names in chain(filter(
            min_criteria,
            (extractor(text) for extractor in CRUDE_EXTRACTORS)
        ), [[]])
    )
    consensuses: Iterator[Tuple[Names, Names]] = filter(min_criteria, (
        (nonlatin_names, fuzzy_intersect(google_extraction, crude_extraction))
        for google_extraction in google_extractions
        for nonlatin_names, crude_extraction in crude_extractions
    ))
    refined_consensuses = refine_consensuses(
        (consensus for consensus in consensuses if min_criteria(consensus)),
        min_names, max_names
    )
    return next(refined_consensuses)
