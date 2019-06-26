import pdb
from typing import Dict, List
import pytest
import extract_info
# test accuracy

CASES: List[Dict[str, List[str]]]
CASES = [
    # phone and email
    {'line': ['8/2/18, rain date 8/9/18 -- done by 4 pm -- Klee -- 617-957-1189 -- kleehmiller@gmail.com -- 85 Northern Ave. it’s located right next to district 12.'],
     'emails': ['kleehmiller@gmail.com'],
     'phones': ['6179571189'],
     'names': ['Klee']},
     # multiple names
    {'line': ['10/22 Alison 774-487-1300 allyson.kane@sagerx.com Judy jbowe@epilepsynewengland.org - check u deda!!!!'],
     'emails': ['allyson.kane@sagerx.com', 'jbowe@epilepsynewengland.org'],
     'phones': ['7744871300'],
     'names': ['Alison', 'Judy']},
     # multiple names
    {'line': ['10/22 Kristina 781-241-2479 Tommy 781-844-3155 - cash on delivery'],
     'emails': [],
     'phones': ['7812412479', '7818443155'],
     'names': ['Kristina', 'Tommy']}
]


@pytest.fixture(params=CASES)
def case(request) -> Dict[str, List[str]]:
    return request.param


def test_cases(case):
    line = case["line"][0]
    actual = extract_info.extract_info(line)
    #if actual != case:
    #    pdb.set_trace()
    #    actual = extract_info.extract_info(line)
    assert actual == case
