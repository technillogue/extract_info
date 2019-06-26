import pdb
import json
from typing import Dict, List
import pytest
import extract_info
# test accuracy

CASES: List[Dict[str, List[str]]]
CASES = json.load(open("data/correct_cases.json"))

@pytest.fixture(params=CASES)
def correct_case(request) -> Dict[str, List[str]]:
    return request.param

def test_cases(correct_case):
    line = correct_case["line"][0]
    actual = extract_info.extract_info(line, no_cache=True)
    if actual != correct_case:
        pdb.set_trace()
        actual = extract_info.extract_info(line, no_cache=True)
    assert actual == correct_case


DIFFICULT_CASES: List[Dict[str, List[str]]]
DIFFICULT_CASES = json.load(open("data/incorrect_cases.json"))

@pytest.fixture(params=DIFFICULT_CASES)
def difficult_case(request) -> Dict[str, List[str]]:
    return request.param

@pytest.mark.xfail
def test_difficult_cases(difficult_case):
    """these are examples that were marked as incorrect, if we have
    different anaswers for them that means there might be improvement"""
    line = difficult_case["line"][0]
    actual_names = extract_info.extract_info(line, no_cache=True)
    assert actual_names != difficult_names["names"]
