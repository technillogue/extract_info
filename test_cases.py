import pdb
from typing import Dict, List
import pytest
import extract_info
# test accuracy

CASES: List[Dict[str, List[str]]] = [
    {'line':
     ['1/11/19 -- 8 - 9 am -- Blythe Spiegel -- 781-864-9432 -- ViralGains 10 Psot Office Square Boston. -- cr card charged 1/9/19'],
     'emails': [],
     'phones': ['7818649432'],
     'names': ['Blythe Spiegel']},
    {'line': ['8/2/18, rain date 8/9/18 -- done by 4 pm -- Klee -- 617-957-1189 -- kleehmiller@gmail.com -- 85 Northern Ave. it’s located right next to district 12.'],
     'emails': ['kleehmiller@gmail.com'],
     'phones': ['6179571189'],
     'names': ['Klee']}
]


@pytest.fixture(params=CASES)
def case(request) -> Dict[str, List[str]]:
    return request.param


def test_cases(case):
    line = case["line"][0]
    actual = extract_info.extract_info(line)
    if actual != case:
        pdb.set_trace()
        actual = extract_info.extract_info(line)
    assert actual == case
