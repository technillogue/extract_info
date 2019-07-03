# mypy: disallow_untyped_decorators=False
import json
import io
from collections import defaultdict
from typing import Any, Callable, Dict
import pytest
import tools

# elephants all the way down


@pytest.fixture(name="send")
def sender(monkeypatch: Any) -> Callable[[str], None]:
    def send(text: str) -> None:
        monkeypatch.setattr(tools, "fd_input", lambda _: text)

    return send


@pytest.mark.usefixtures("capfd")
def test_ask(send: Callable) -> None:
    send("yes")
    assert tools.ask(defaultdict(str))
    send("no")
    assert tools.ask(defaultdict(str)) is False


def entry(arg: str) -> Dict:
    return defaultdict(lambda: [arg])


def test_reclassify(monkeypatch: Any, capfd: Any, send: Callable) -> None:
    monkeypatch.setattr(json, "dump", lambda *dummy, **kwdummy: None)
    monkeypatch.setattr(
        tools, "open", lambda *dummy, **kwdummy: io.StringIO, raising=False
    )
    monkeypatch.setattr(tools, "EXAMPLES", [entry("correct")])
    monkeypatch.setattr(tools, "COUNTEREXAMPLES", [entry("incorrect")])
    cases = [
        (    # we have the wrong output for a correct example
            "no",
            (entry("wrong"), tools.EXAMPLES[0]),
            ("example: \n", "marking as incorrect", "reclassifying"),
        ),
        ( # counterexample is incorrect but has new output
            "no",
            (entry("different wrong"), tools.COUNTEREXAMPLES[0]),
            ("counterexample: \n", "marking as incorrect", "updating example")
        ),
        (# an incorrect example has no generated correct output
            "yes",
            (entry("newly correct"), tools.COUNTEREXAMPLES[0]), 
            ("counterexample: \n", "marking as correct", "reclassifying")
        )
    ]
    for response, (actual_entry, expected_entry), correct_response  in cases:
        monkeypatch.setattr(tools, "EXAMPLES", [entry("correct")])
        monkeypatch.setattr(tools, "COUNTEREXAMPLES", [entry("incorrect")])
        send(response)
        tools.reclassify(actual_entry, expected_entry)
        out = capfd.readouterr().out
        for part in correct_response:
            assert part in out
