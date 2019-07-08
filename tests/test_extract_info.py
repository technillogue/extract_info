# mypy: disallow_untyped_decorators=False
from typing import Mapping, List, Any, Tuple, Callable, Sequence, Iterable
from itertools import product
import pytest
import extract_info
import extract_names
import utils
from tools import reclassify, LABELED_EXAMPLES

# NOTE: for reclassification to work, use pytest with --capture=sys

STAGES: Sequence[Sequence[Callable]] = extract_names.STAGES
# the original annotation is more specific, but we just care that
# they're callables here

State = Tuple[int, ...]
Graph = Mapping[State, Mapping[str, State]]


def generate_graph(
    strategies: List[List[str]]
) -> Iterable[Tuple[State, Mapping[str, State]]]:
    "Yield a graph describing valid transitions between combinations of strategies"
    # state[i] is an index of strategies[i]
    states = product(*(range(len(stage)) for stage in strategies))
    # zeros cannot be followed by zeros, we can't have started stage n+1 but not n
    valid_states = [
        state for state in states if not (0 in state and any(state[state.index(0) :]))
    ]
    for state, step_state in zip(valid_states[:-1], valid_states[1:]):
        first_change = [
            index
            for index, strategy in enumerate(state)
            if step_state[index] is not strategy
        ][0]
        step_symbol = strategies[first_change][step_state[first_change]]
        if 0 in state:
            incremented_stage = state.index(0) - 1
            # can't skip if there isn't a previous stage to increment
            # not if that stage has run out
            if (
                incremented_stage >= 0
                and len(strategies[incremented_stage]) > state[incremented_stage] + 1
            ):
                skip_symbol = strategies[incremented_stage][
                    state[incremented_stage] + 1
                ]
                skip_state = tuple(
                    {incremented_stage: strategy + 1, incremented_stage + 1: 0}.get(
                        stage, strategy
                    )
                    for stage, strategy in enumerate(state)
                )
                yield (state, {step_symbol: step_state, skip_symbol: skip_state})
                continue
        yield (state, {step_symbol: step_state})


def test_generate_graph():
    strategies = [["a", "A"], ["b", "B"]]
    actual = {state: transition for state, transition in generate_graph(strategies)}
    expected = {
        (0, 0): {"a": (1, 0)},
        (1, 0): {"b": (1, 1), "A": (2, 0)},
        (1, 1): {"B": (1, 2)},
        (1, 2): {"A": (2, 0)},
        (2, 0): {"b": (2, 1)},
        (2, 1): {"B": (2, 2)},
    }
    assert actual == expected


def walk_graph(symbols: List[str], state: State, graph: Graph, trace: str) -> State:
    if not symbols:
        return state
    current_symbol, *next_symbols = symbols
    try:
        next_state = graph[state][current_symbol]
    except KeyError:
        raise Exception(
            f"Can only go to {tuple(graph[state].keys())} from {state},"
            f"not {current_symbol}"
        )
    return walk_graph(next_symbols, next_state, graph, trace)
    # turn this into something reducable so it doesn't clog the call stack in pdb


Entry = Mapping[str, List[str]]


def generate_trace_tester() -> Callable[[Entry, str], None]:
    strategies: List[List[str]] = [
        [""] + [strategy.__name__ for strategy in stage] for stage in STAGES
    ]
    graph: Graph = {
        state: transitions for state, transitions in generate_graph(strategies)
    }
    initial_state = (0,) * len(STAGES)
    final_state = tuple(map(len, STAGES))

    def trace_tester(result: Entry, trace: str) -> None:
        name_limits: Tuple[int, int] = extract_info.min_max_names(
            result["emails"], result["phones"]
        )
        exit_type = extract_info.decide_exit_type(result["names"], *name_limits)
        exit_state = walk_graph(trace.split(), initial_state, graph, trace)
        if 0 in exit_state:
            # we must have skipped the refiners
            assert exit_type == extract_info.Flags.not_enough
        elif exit_state is final_state:
            assert exit_type == extract_info.Flags.too_many

    return trace_tester


@pytest.fixture(name="traced_extract_info")
def trace_extract_info() -> Callable:
    logger = utils.Logger()
    stages = tuple([logger.logged(strategy) for strategy in stage] for stage in STAGES)
    test_trace = generate_trace_tester()

    def traced_extract_info(*args: Any, **kwargs: Any) -> Any:
        logger.new_stream()
        result = extract_info.extract_info(*args, stages=stages, **kwargs)
        test_trace(result, logger.get_log())
        return result

    return traced_extract_info


@pytest.fixture(name="labeled_example", params=LABELED_EXAMPLES)
def labeled_example_fixture(request: Any) -> Entry:
    return request.param


@pytest.mark.usefixtures("save_cache")
def test_examples(
    labeled_example: Tuple[Entry, bool], traced_extract_info: Callable
) -> None:
    example, correct = labeled_example
    line = example["line"][0]
    try:
        actual = traced_extract_info(line)
    except AssertionError as e:
        raise e
    if actual != example:
        really_correct = reclassify(actual, example)
        if not really_correct:
            if correct:
                assert actual == example
            else:
                raise pytest.xfail("output still the same as known wrong output")
