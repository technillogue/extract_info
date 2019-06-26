import itertools
import re
from string import printable
from typing import List
import nltk
from nltk.corpus import wordnet
from googleapiclient.errors import HttpError
from google_analyze import analyze_entities
from cache import cache

def space_dashes(text: str) -> str:
    "put spaces around dashes without spaces"
    return re.sub(r"-([^ -])", r"- \1", re.sub(r"([^ -])-", r"\1 -", text))

PHONE_RE = re.compile(r'(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{3}[-\.\s]??\d{4})')
EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+')

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
def nltk_extract_names(text: str) -> List[str]:
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
def google_extract_names(text: str) -> List[str]:
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

## preprocessing functions to use with google
def only_alpha(text: str) -> str:
    "remove words that don't have any alphabetical chareceters or -"
    return " ".join([
        word for word in text.split()
        if (word not in extract_emails(text)
            and all((c.isalpha() or c in r"-\!$%(,.:;?") for c in word))
    ])

def every_name(names: List[str]) -> str:
    return "".join(map(
        "My name is {}. ".format,
        names
    ))

def fuzzy_union(crude_names: List[str], google_names: List[str]) -> List[str]:
    union = []
    for crude_name in crude_names:
        if crude_name[0] not in printable:
    #if not min_names <= len(result["names"]) <= max_names:
    #    cases[nltk_status][google_approach][
    #        "too much" if len(result["names"]) > max_names else "too little"
    #    ] += 1
            union.append(crude_name)
            # google doesn't work with non-latin characters
            # so we ignore it in those cases
        else:
            for google_name in google_names:
                if [part for part in crude_name.split() if part in google_name]:
                    union.append(crude_name)
    return union

def remove_synonyms(names: List[str]) -> List[str]:
    "removes words that have wordnet synonyms"
    return [
        name
        for name in names
        if not any(len(wordnet.synsets(word)) > 1 for word in name.split())
    ]

def remove_nonlatin(names: List[str]) -> List[str]:
    return names
    # to be implemented later



def extract_names(line: str, min_names: int, max_names: int,
                  refine: bool = True) -> List[str]:
    text = space_dashes(line)
    # get a crude attempt
    nltk_names: List[str] = nltk_extract_names(text)
    if len(nltk_names) >= min_names:
        crude_names = nltk_names
    else:
        crude_names = [word for word in text.split() if word[0].isupper()]
    # if we have too many names, get google's attempt
    names_filtered: List[str]
    if len(crude_names) <= max_names:
        names_filtered = crude_names
    else:
        # try to do it with google
        approaches = (
            lambda: only_alpha(text),
            lambda: text,
            lambda: every_name(crude_names)
        ) # unfortunately the only way to make this lazy in python
        google_names: List[str] = next(filter(
            None,
            (google_extract_names(approach()) for approach in approaches)
        ), [])
        if google_names:
            names_filtered = fuzzy_union(crude_names, google_names)
        else:
            names_filtered = crude_names
    # if needed, refine with synset and discarding nonlatin names
    if refine and len(names_filtered) > max_names:
        refined_names = remove_synonyms(names_filtered)
        if len(refined_names) <= min_names:
            return refined_names
    return names_filtered
