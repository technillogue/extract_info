# mypy: disallow_untyped_decorators=False
from typing import Any, List, Sequence
import pytest
import extract_names
import extract_info


def test_contains_nonlatin() -> None:
    assert not extract_names.contains_nonlatin("Stephanie")
    assert extract_names.contains_nonlatin(u"Лена")


def test_every_name() -> None:
    assert extract_names.every_name(
        "3/14 Planet Fitness McCall 603-750-0001 X 119 Paid cr card"
    ) == (
        "My name is Planet. My name is Fitness. My name is McCall. "
        "My name is X. My name is Paid. My name is cr. My name is card. "
    )


def test_fuzzy_intersect() -> None:
    cases: Sequence[Sequence[List[str]]] = [
        (["Bob", "Miller"], ["Miller"], ["Miller"]),
        (["Deadham", "Bob"], ["Bob Miller"], ["Bob Miller"]),
        ([], ["Bob"], ["Bob"]),
        (["Bob"], [], ["Bob"]),
        (
            ["Ariel Kochi", "Pierre Kochi"],
            ["Ariel", "Kochi", "TO", "Pierre", "Kochi", "Marion"],
            ["Ariel Kochi", "Pierre Kochi"],
        ),
    ]
    for left, right, expected in cases:
        assert extract_names.fuzzy_intersect(left, right) == expected


LINE = "12/31 -- Lisa balloon drop -- off 617.555.5555 - paid, check deposited"


@pytest.mark.usefixtures("save_cache")
def test_no_google() -> None:
    actual = extract_names.extract_names(LINE, 1, 1)
    expected = ["Lisa"]
    if actual != expected:
        breakpoint()
        extract_names.extract_names(LINE, 1, 1)
    assert actual == expected


@pytest.mark.usefixtures("save_cache")
def test_too_many(monkeypatch: Any) -> None:
    def mock_fuzzy_intersect(*_dummy: Any) -> List[str]:
        return ["Stephanie", "red", "Собака", "Ariel", "Lisa"]

    monkeypatch.setattr(extract_names, "fuzzy_intersect", mock_fuzzy_intersect)
    try:
        actual = extract_names.extract_names(LINE, 1, 1)
        assert actual  # return the best attempt, not nothing
        assert actual == ["Stephanie", "Ariel", "Lisa"]
        assert (
            extract_info.Flags.too_many
            in extract_info.extract_info(LINE, flags=True)["flags"]
        )
    except AssertionError:
        breakpoint()
        actual = extract_names.extract_names(LINE, 1, 1)
        assert 0
