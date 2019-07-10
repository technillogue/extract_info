# mypy: disallow_untyped_decorators=False
import logging
import io
import pdb
from itertools import product
from functools import wraps
from typing import Mapping, List, Any, Tuple, Callable, Sequence, Iterable
import pytest
import strategies
from extract_info import extract_info, decide_entry_type, EntryType
from tools import reclassify, LABELED_EXAMPLES

# NOTE: for reclassification to work, use pytest with --capture=sys

State = Tuple[int, ...]
Graph = Mapping[State, Mapping[str, State]]
Entry = Mapping[str, List[str]]
STAGES: Sequence[Sequence[Callable]] = strategies.STAGES
# the original annotation is more specific, but we just care that
# they're callables here


def generate_graph(
    stages: List[List[str]]
) -> Iterable[Tuple[State, Mapping[str, State]]]:
    """
    Yield a graph describing valid transitions between combinations of strategies.

    extract_info.extract_names tries strategies in a way that corresponds to a
    Finate State Automata. At a given combination of strategies for each stage,
    it can either try the first strategy of the next stage, the next strategy of this
    stage, or, if this is the last strategy, can go to the next strategy of the
    previous stage.
    """
    # state[i] is an index of strategies[i]
    states = product(*(range(len(stage)) for stage in stages))
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
        step_symbol = stages[first_change][step_state[first_change]]
        if 0 in state:
            incremented_stage = state.index(0) - 1
            # can't skip if there isn't a previous stage to increment
            # nor if the previous stage has run out
            if (
                incremented_stage >= 0
                and len(stages[incremented_stage]) > state[incremented_stage] + 1
            ):
                skip_symbol = stages[incremented_stage][state[incremented_stage] + 1]
                skip_state = tuple(
                    {incremented_stage: strategy + 1, incremented_stage + 1: 0}.get(
                        stage, strategy
                    )
                    for stage, strategy in enumerate(state)
                )
                yield (state, {step_symbol: step_state, skip_symbol: skip_state})
                continue
        yield (state, {step_symbol: step_state})


# it's usually inconvenient to `up` all the way through the path; pdb++ hides this
@pdb.hideframe  # type: ignore # mypy doesn't see pdb++
def walk_graph(symbols: List[str], state: State, graph: Graph) -> State:
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
    return walk_graph(next_symbols, next_state, graph)


class Logger:
    def __init__(self, log_name: str = "trace"):
        self.log = logging.getLogger(log_name)
        self.log.setLevel("DEBUG")
        self.new_stream()

    def logged(self, func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self.log.debug(func.__name__)
            return func(*args, **kwargs)

        return wrapper

    def new_stream(self) -> None:
        for handler in self.log.handlers:
            self.log.removeHandler(handler)
        self.stream = io.StringIO()
        self.log.addHandler(logging.StreamHandler(self.stream))


@pytest.fixture(name="traced_extract_info")
def trace_extract_info() -> Callable:
    strategy_names: List[List[str]] = [
        [""] + [strategy.__name__ for strategy in stage] for stage in STAGES
    ]
    graph: Graph = {
        state: transitions for state, transitions in generate_graph(strategy_names)
    }
    initial_state = (0,) * len(STAGES)
    final_state = tuple(map(len, STAGES))
    logger = Logger()
    stages = tuple([logger.logged(strategy) for strategy in stage] for stage in STAGES)

    def traced_extract_info(*args: Any, **kwargs: Any) -> Any:
        logger.new_stream()
        result = extract_info(*args, stages=stages, **kwargs)
        entry_types = decide_entry_type(result)
        trace = logger.stream.getvalue()
        exit_state = walk_graph(trace.split(), initial_state, graph)
        if 0 in exit_state:
            # we must have skipped the refiners
            assert EntryType.not_enough in entry_types
        elif exit_state is final_state:
            assert EntryType.too_many in entry_types

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
                pytest.xfail("output still the same as known wrong output")
