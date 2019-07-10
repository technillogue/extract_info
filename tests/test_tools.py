# mypy: disallow_untyped_decorators=False
import json
import io
from typing import Any, Callable
import pytest
import tools
import test_integration


class Entry(dict):
    def __init__(self, contents: str) -> None:
        self.contents = contents
        super().__init__(names=[contents], line=[contents])

    def __repr__(self) -> str:
        return f"<Entry {self.contents}>"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Entry):
            return self.contents == other.contents
        return super().__eq__(other)  # elephants all the way down


@pytest.fixture(name="send")
def sender(monkeypatch: Any) -> Callable[[str], None]:
    def send(text: str) -> None:
        monkeypatch.setattr(tools, "fd_input", lambda _: text)

    return send


def test_ask(send: Callable, capfd: Any) -> None:
    send("yes")
    assert tools.ask(Entry("foo"))
    send("no")
    assert tools.ask(Entry("bar")) is False
    capfd.readouterr()


def test_reclassify(monkeypatch: Any, capfd: Any, send: Callable) -> None:
    monkeypatch.setattr(json, "dump", lambda *dummy, **kwdummy: None)
    monkeypatch.setattr(
        tools, "open", lambda *dummy, **kwdummy: io.StringIO, raising=False
    )
    example, counterexample = Entry("corrent"), Entry("incorrect")
    monkeypatch.setattr(tools, "EXAMPLES", [example])
    monkeypatch.setattr(tools, "COUNTEREXAMPLES", [counterexample])
    cases = [
        (  # we have the wrong output for a correct example
            "no",
            (Entry("wrong"), tools.EXAMPLES[0]),
            ("example: \n", "marking as incorrect", "reclassifying"),
        ),
        (  # counterexample is incorrect but has new output
            "no",
            (Entry("different wrong"), tools.COUNTEREXAMPLES[0]),
            ("counterexample: \n", "marking as incorrect", "updating example"),
        ),
        (  # an incorrect example has no generated correct output
            "yes",
            (Entry("newly correct"), tools.COUNTEREXAMPLES[0]),
            ("counterexample: \n", "marking as correct", "reclassifying"),
        ),
    ]
    for response, (actual_entry, expected_entry), correct_response in cases:
        monkeypatch.setattr(tools, "EXAMPLES", [example])
        monkeypatch.setattr(tools, "COUNTEREXAMPLES", [counterexample])
        send(response)
        tools.reclassify(actual_entry, expected_entry)
        out = capfd.readouterr().out
        for part in correct_response:
            assert part in out


def test_generate_graph() -> None:
    strategies = [["", "a", "A"], ["", "b", "B"]]
    graph_iterator = test_integration.generate_graph(strategies)
    actual = {state: transition for state, transition in graph_iterator}
    expected = {
        (0, 0): {"a": (1, 0)},
        (1, 0): {"b": (1, 1), "A": (2, 0)},
        (1, 1): {"B": (1, 2)},
        (1, 2): {"A": (2, 0)},
        (2, 0): {"b": (2, 1)},
        (2, 1): {"B": (2, 2)},
    }
    assert actual == expected

