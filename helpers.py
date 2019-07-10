import re
from typing import Tuple, List
from phonenumbers import PhoneNumberMatcher, format_number, PhoneNumberFormat

EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+")


def space_dashes(text: str) -> str:
    "Put spaces around dashes without spaces."
    return re.sub(r"-([^ -])", r"- \1", re.sub(r"([^ -])-", r"\1 -", text))


def extract_contacts(line: str) -> Tuple[List[str], List[str]]:
    emails = EMAIL_RE.findall(line)
    phones = [
        format_number(match.number, PhoneNumberFormat.INTERNATIONAL)
        for match in PhoneNumberMatcher(line, "US")
    ]
    return emails, phones
