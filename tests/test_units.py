# mypy: disallow_untyped_decorators=False
from typing import Any, List, Sequence
import pytest
import strategies
import extract_info
from cache import cache
from test_integration import generate_graph, save_cache

number_of_limbs_owed_to_google: int

@pytest.mark.usefixtures("save_cache")
def test_cache() -> None:
    # pylint: disable=global-statement
    global number_of_limbs_owed_to_google
    number_of_limbs_owed_to_google = 0

    cache.clear_cache("machine_learning_powered_echo")

    @cache.with_cache
    def machine_learning_powered_echo(x: Any) -> Any:
        global number_of_limbs_owed_to_google
        number_of_limbs_owed_to_google += 1
        return x

    machine_learning_powered_echo("foo")
    machine_learning_powered_echo("foo")
    assert number_of_limbs_owed_to_google == 1
    cache.clear_cache("machine_learning_powered_echo")
    machine_learning_powered_echo("foo")
    assert number_of_limbs_owed_to_google == 2
    assert machine_learning_powered_echo([]) == []
    assert machine_learning_powered_echo(["foo"]) == ["foo"]
    cache.clear_cache("machine_learning_powered_echo")


# strategies


def test_contains_nonlatin() -> None:
    assert not strategies.contains_nonlatin("Stephanie")
    assert strategies.contains_nonlatin(u"Лена")
    assert strategies.contains_nonlatin(u"Лена Stephanie")


def test_every_name() -> None:
    assert strategies.every_name(
        "3/14 Planet Fitness McCall 603-750-0001 X 119 Paid cr card"
    ) == (
        "My name is Planet. My name is Fitness. My name is McCall. "
        "My name is X. My name is Paid. My name is cr. My name is card. "
    )


# extract_info


def test_fuzzy_intersect() -> None:
    cases: Sequence[Sequence[List]] = [
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
        assert extract_info.fuzzy_intersect(left, right) == expected


LINE = "12/31 -- Lisa balloon drop -- off 617.555.5555 - paid, check deposited"

@pytest.mark.usefixtures("save_cache")
def test_no_google() -> None:
    # LINE happens to never have any results from Google
    actual = extract_info.extract_names(LINE, 1, 1)
    expected = ["Lisa"]
    assert actual == expected


def test_generate_graph() -> None:
    graph = generate_graph([["", "a", "A"], ["", "b", "B"]])
    actual = {state: transition for state, transition in graph}
    expected = {
        (0, 0): {"a": (1, 0)},
        (1, 0): {"b": (1, 1), "A": (2, 0)},
        (1, 1): {"B": (1, 2)},
        (1, 2): {"A": (2, 0)},
        (2, 0): {"b": (2, 1)},
        (2, 1): {"B": (2, 2)},
    }
    assert actual == expected
