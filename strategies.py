import string
from itertools import combinations, filterfalse
from functools import reduce
from typing import List, Callable, Sequence, Tuple, TypeVar
from typing_extensions import Protocol, runtime_checkable
import googleapiclient.discovery
from googleapiclient.errors import HttpError
from cache import cache

X = TypeVar("X")
Y = TypeVar("Y")
Z = TypeVar("Z")


@runtime_checkable
class Wrapper(Protocol):
    __wrapped__: Callable


def compose(f: Callable[[Y], Z], g: Callable[[X], Y]) -> Callable[[X], Z]:
    use_cache = False
    if isinstance(f, Wrapper):
        f = f.__wrapped__
        use_cache = True
    if isinstance(g, Wrapper):
        g = g.__wrapped__
        use_cache = True

    def composed_function(arg: X) -> Z:
        return f(g(arg))

    composed_function.__name__ = composed_function.__qualname__ = "_".join(
        (f.__name__, g.__name__)
    )
    if use_cache:
        return cache.with_cache(composed_function)
    return composed_function


Names = List[str]


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
def google_extract_names(raw_text: str) -> Names:
    "Return names using Google Cloud Knowledge Graph Named Entity Recognition."
    text = "".join(filter(string.printable.__contains__, raw_text))
    try:
        body = {
            "document": {"type": "PLAIN_TEXT", "content": text},
            "encoding_type": "UTF32",
        }
        service = googleapiclient.discovery.build("language", "v1")
        request = service.documents().analyzeEntities(  # pylint: disable=no-member
            body=body
        )
        response = request.execute()
    except HttpError:
        return []
    return [
        entity["name"] for entity in response["entities"] if entity["type"] == "PERSON"
    ]


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

Stages = Tuple[Extractors, Extractors, Refiners]
STAGES: Stages = (GOOGLE_EXTRACTORS, CRUDE_EXTRACTORS, REFINERS)
