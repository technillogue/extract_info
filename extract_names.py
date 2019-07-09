import string
from itertools import combinations, filterfalse, tee
from functools import reduce
from typing import List, Callable, Iterator, Sequence, Tuple
import google_analyze
from utils import cache, compose

Names = List[str]
NameAttempts = Iterator[Names]


def contains_nonlatin(text: str) -> bool:
    return not all(map(string.printable.__contains__, text))
    # .84usec faster pcall than using a comprehension
    # read as "not all of the characters are in the ASCII set"


@cache.with_cache
def nltk_extract_names(text: str) -> Names:
    "Returns names using NLTK Named Entity Recognition filtering repetition"
    import nltk

    names = [
        " ".join(labeled[0] for labeled in chunk)
        for sentance in nltk.sent_tokenize(text)
        for chunk in nltk.ne_chunk(nltk.pos_tag(nltk.word_tokenize(sentance)))
        if isinstance(chunk, nltk.tree.Tree) and chunk.label() == "PERSON"
    ]
    # remove any names that contain each other
    duplicate_names = [
        max(name1, name2, key=len)
        for name1, name2 in combinations(names, 2)
        if name1 in name2 or name2 in name1
    ]
    return list(set(names) - set(duplicate_names))


def all_capitalized_extract_names(text: str) -> List[str]:
    words = ("".join(filter(str.isalpha, word)) for word in text.split())
    # McCall is a name, but ELISEVER isn't
    return [word for word in words if word and word[0].isupper() and not word.isupper()]


Extractors = Sequence[Callable[[str], Names]]

CRUDE_EXTRACTORS: Extractors = [nltk_extract_names, all_capitalized_extract_names]
# try adding nltk_extract_names_only_alpha


@cache.with_cache
def google_extract_names(text: str) -> Names:
    "Return names using Google Cloud Knowledge Graph Named Entity Recognition."
    latin_text = "".join(filter(string.printable.__contains__, text))
    return google_analyze.extract_entities(latin_text)


@cache.with_cache
def only_alpha(text: str) -> str:
    "Remove words without any alphabetical chareceters or dashes."
    words = [
        word
        for word in text.split()
        if all(c.isalpha() or c in r"-/\$%(),.:;?!" for c in word)
    ]
    return " ".join(words)


def no_preprocess(text: str) -> str:
    return text


@cache.with_cache
def every_name(text: str) -> str:
    return "".join(map("My name is {}. ".format, only_alpha(text).split()))


GOOGLE_PREPROCESSES: List[Callable[[str], str]] = [
    only_alpha,
    no_preprocess,
    every_name,
]

GOOGLE_EXTRACTORS: Extractors = [
    compose(google_extract_names, preprocess) for preprocess in GOOGLE_PREPROCESSES
]


def partition_similar(name: str, other_names: Names) -> Tuple[Names, Names]:
    def similar_to(other_name: str) -> bool:
        return name in other_name or other_name in name

    return (
        list(filter(similar_to, other_names)),
        list(filterfalse(similar_to, other_names)),
    )


def fuzzy_intersect(left: Names, right: Names, recursive: bool = False) -> Names:
    if not recursive:
        if not (left and right):
            return left or right
    else:
        if not left:
            return []
    first_left, *remaining_left = left
    similar_right, dissimilar_right = partition_similar(first_left, right)
    if similar_right:
        similar_left, dissimilar_left = partition_similar(first_left, remaining_left)
        intersection = max(first_left, *similar_left, *similar_right, key=len)
        return [intersection] + fuzzy_intersect(dissimilar_left, dissimilar_right, True)
    return fuzzy_intersect(remaining_left, right, True)


def remove_none(names: Names) -> Names:
    return names


@cache.with_cache
def remove_synonyms(names: Names) -> Names:
    from nltk.corpus import wordnet  # if this is cached we don't need to import nltk

    return [
        name
        for name in names
        if not any(len(wordnet.synsets(word)) > 1 for word in name.split())
        # note: will have synonyms for e.g. David (various dictionary-worthy Davids)
    ]


@cache.with_cache
def remove_nonlatin(names: Names) -> Names:
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

    def filter_min_criteria(attempts: NameAttempts) -> NameAttempts:
        yielded_anything = False
        for attempt in attempts:
            if len(attempt) >= min_names:
                yielded_anything = True
                yield attempt
        if not yielded_anything:
            yield []

    google_extractions: Iterator[Names] = filter_min_criteria(
        extractor(text) for extractor in google_extractors
    )
    consensuses = (
        fuzzy_intersect(google_extraction, crude_extraction)
        for google_extraction in google_extractions
        for crude_extraction in filter_min_criteria(
            extractor(text) for extractor in crude_extractors
        )
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
        every_refinement = list(
            fallback
        )  # note: this may have a bunch of [] at the end
        if max(map(len, every_refinement)) < min_names:
            return max(every_refinement, key=len)
        return min(
            filter(None, every_refinement), key=len, default=list()
        )  # smallest non-empty but [] if they're all empty
