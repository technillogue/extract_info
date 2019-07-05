import string
from itertools import permutations, combinations, filterfalse, tee
from functools import reduce
from typing import List, Callable, Iterator, Sequence, Tuple
import google_analyze
from utils import cache, compose

Names = List[str]
NameAttempts = Iterator[Names]
# general functions


def contains_nonlatin(text: str) -> bool:
    return not any(map(string.printable.__contains__, text))
    # .84usec faster pcall than using a comprehension


# combinatorial functions
## extractors
### "crude" extractors

@cache.with_cache
def nltk_extract_names(text: str) -> Names:
    "returns names using NLTK Named Entity Recognition, filters out repetition"
    import nltk

    names = []
    for sentance in nltk.sent_tokenize(text):
        for chunk in nltk.ne_chunk(nltk.pos_tag(nltk.word_tokenize(sentance))):
            if isinstance(chunk, nltk.tree.Tree):
                if chunk.label() == "PERSON":
                    names.append(" ".join([c[0] for c in chunk]))
    # remove any names that contain each other
    for name1, name2 in permutations(names, 2):
        if name1 in name2:
            names.remove(name1)
    return names


def all_capitalized_extract_names(text: str) -> List[str]:
    return [
        "".join(filter(str.isalpha, word))
        for word in text.split()
        if word[0].isupper() and not all(map(str.isupper, word[1:]))
        # McCall is a name, but ELISEVER isn't
    ]


Extractors = Sequence[Callable[[str], Names]]

CRUDE_EXTRACTORS: Extractors = [nltk_extract_names, all_capitalized_extract_names]

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


# use lru here? currently compose strips this cache
@cache.with_cache
def only_alpha(text: str) -> str:
    "remove words that don't have any alphabetical chareceters or -"
    return " ".join(
        [
            word
            for word in text.split()
            if all(c.isalpha() or c in r"-/\$%(),.:;?!" for c in word)
            # relatively bad, 0.8s tottime
        ]
    )


def no_preprocess(text: str) -> str:
    return text


@cache.with_cache
def every_name(text: str) -> str:
    return "".join(map("My name is {}. ".format, only_alpha(text).split()))
    # explore some option for merging adjacent names?


GOOGLE_PREPROCESSES: List[Callable[[str], str]] = [
    only_alpha,
    no_preprocess,
    every_name,
]

GOOGLE_EXTRACTORS: Extractors = [
    compose(google_extract_names, preprocess) for preprocess in GOOGLE_PREPROCESSES
]


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


def remove_none(names: Names) -> Names:
    return names


@cache.with_cache
def remove_synonyms(names: Names) -> Names:
    "removes words that have wordnet synonyms"
    from nltk.corpus import wordnet

    return [
        name
        for name in names
        if not any(len(wordnet.synsets(word)) > 1 for word in name.split())
    ]


@cache.with_cache
def remove_nonlatin(names: Names) -> Names:
    """ keep names that contain no nonlatin chars"""
    return list(filterfalse(contains_nonlatin, names))
    # this is .5 usec faster than using a comprehension


def remove_short(names: Names) -> Names:
    return [name for name in names if len(name) > 2]


Refiners = Sequence[Callable[[Names], Names]]

UNIQUE_REFINERS: Refiners = [remove_short, remove_synonyms, remove_nonlatin]


REFINERS: Refiners = [remove_none] + [
    reduce(compose, combination)  # type: ignore # overly specific inferred signature
    for i in range(1, len(UNIQUE_REFINERS))
    for combination in combinations(UNIQUE_REFINERS, i)
]

STAGES: Tuple[Extractors, Extractors, Refiners] = (
    GOOGLE_EXTRACTORS,
    CRUDE_EXTRACTORS,
    REFINERS,
)


def extract_names(
    text: str,
    min_names: int,
    max_names: int,
    stages: Tuple[Extractors, Extractors, Refiners] = STAGES,
) -> Names:
    google_extractors, crude_extractors, refiners = stages
    # maybe in the future wrap everyone so that they could be reduced?
    # i.e. so that google_extractors return (text, names) and crude_extractors
    # take (text, names) and does fuzzy_intersect by itself to return consensus names
    # then you could do something like
    # big_enough_consensuses = (
    #   reduce(
    #       lambda arg, strategy: filter_min_criteria(strategy(arg)),
    #       strategy_combination,
    #       initial=text
    #   )
    #   for strategy_combination in product(*stages)
    # )
    # however, the overhead of wrapping everything into stages kind of sucks
    # you could try making it homogenous
    # Strategy = Callable[[str, Names, Names], Tuple[str, Names, Names]]
    def filter_min_criteria(attempts: NameAttempts) -> NameAttempts:
        yield from (attempt for attempt in attempts if len(attempt) >= min_names)
        yield []

    google_extractions: Iterator[Names] = filter_min_criteria(
        extractor(text) for extractor in google_extractors
    )
    crude_extractions: Iterator[Names] = filter_min_criteria(
        extractor(text) for extractor in crude_extractors
    )
    consensuses: Iterator[Names] = filter_min_criteria(
        fuzzy_intersect(google_extraction, crude_extraction)
        for google_extraction in google_extractions
        for crude_extraction in crude_extractions
    )
    refinements, fallback = tee(
        refine(consensus) for consensus in consensuses for refine in refiners
    )
    try:
        return next(
            refinement
            for refinement in refinements
            if min_names <= len(refinement) <= max_names
        )
    except StopIteration:
        every_refinement = list(fallback)  # note: this has a bunch of [] at the end
        if max(map(len, every_refinement)) < min_names:
            return max(every_refinement, key=len)
        return min(
            filter(None, every_refinement), key=len, default=list()
        )  # smallest non-empty but [] if they're all empty
