# mypy: disallow_untyped_decorators=False
import re
from typing import Dict, List, Any, Tuple, Callable, Sequence
import pytest
import extract_info
import extract_names
import utils
from tools import reclassify, LABELED_EXAMPLES

# NOTE: for reclassification to work, use pytest with --capture=sys

STAGES: Sequence[Sequence[Callable]] = extract_names.STAGES
# the original annotation is more specific, but we just care that
# they're callables here


def regex_gen(
    stages_strategy_names: List[List[str]], continuation_rule: str, terminal_rule: str
) -> str:
    """
    Generate a regex that should match a call trace following given rules.

    Our code has three stages and various strategies for each stage, and tries
    different combinations of strategies in a specific order.
    This corresponds to a finate state automata where the symbols are the names
    of each of each strategy and the states are the possibile combinations of
    strategies for each stage (including "not doing this stage right now" as the
    0th straegy.
    We can inject logging to trace which strategies are tried.
    Because each FSA corresponds to a regex, we can generate a regex that
    matches correct sequences of calls.
    """
    metatest_logger = utils.Logger(log_name="metatest")

    @metatest_logger.logged
    def strategy_recurser(strategies: List[str], next_stages: str) -> str:
        if len(strategies) == 1:
            return terminal_rule.format(
                last_strategy=strategies[0], next_stages=next_stages
            )
        # how can our metaprogramming be real if our scopes aren't real
        # in other terms, variables not found in locals() will be first looked up in the
        # context of *this call* of strategy_recurser-- that's why this trick works in the first place
        next_strategies = strategy_recurser(strategies[1:], next_stages)
        return continuation_rule.format(
            strategy=strategies[0],
            next_stages=next_stages,
            next_strategies=next_strategies,
        )

    # consider the last stage. what pattern describes the sequence of strategies for that stage?
    # we're calling that pattern next_stages (there's only one for now, but that's okay)
    # take the penultimate stage. given that next_stages are a fixed string,
    # what pattern describes the sequence of trying strategies and trying the next stages?
    @metatest_logger.logged
    def stages_recurser(stages: List[List[str]]) -> str:
        if len(stages) == 1:
            return strategy_recurser(stages[0], "")
        return strategy_recurser(stages[0], stages_recurser(stages[1:]))

    return stages_recurser(stages_strategy_names)


# the code tries each strategy until one of them works, then goes to the next stage,
# until it gets a final result that works.
# if a given stratgy for this stage doesn't work it should jump to the next

# if none of the strategies for a given stage work, it should go back to the
# previous stage and try the next strategy there.
# does in order until one works.

# as soon as a given strategy for this stage doesn't work, it should jump
# to the next strategy for this stage without trying the next stages
PATTERN_DEFINITIONS = {
    extract_info.Flags.correct: {
        # try current strategy; if it works, next stage, otherwise, next strategy
        "continuation_rule": "{strategy}\n({next_stages}|{next_strategies})",
        # in the correct case, we get to every stage
        "terminal_rule": "{last_strategy}\n{next_stages}",
    },
    extract_info.Flags.not_enough: {
        # we might not get to the next stage but we have to try every strategy
        "continuation_rule": "{strategy}\n({next_stages})?{next_strategies}",
        # don't need to go to the next if there isn't a working strategy
        "terminal_rule": "{last_strategy}\n({next_stages})?",
    },
    extract_info.Flags.too_many: {
        # we just have to try every combination, because "works" is definied as
        # "has enough items"-- we only check if there are too many at the very end
        # however, sometimes a strategy might return nothing, and then skipping
        # to the next strategy makes sense
        "continuation_rule": "{strategy}\n({next_stages})?{next_strategies}",
        "terminal_rule": "{last_strategy}\n{next_stages}",
    },
}

Entry = Dict[str, List[str]]


def generate_trace_tester() -> Callable[[Entry, str], None]:
    stages_strategy_names: List[List[str]] = [
        [strategy.__name__ for strategy in step] for step in STAGES
    ]

    metatest_logger = utils.Logger(log_name="metatest")

    patterns = {
        exit_type: regex_gen(stages_strategy_names, **definition)
        for exit_type, definition in PATTERN_DEFINITIONS.items()
    }

    # no rest for the test-driven wicked
    regex_gen_pattern = (
        "stages_recurser\n" * len(STAGES)
        + "strategy_recurser\n" * sum(map(len, STAGES))
    ) * len(PATTERN_DEFINITIONS)
    assert re.match(regex_gen_pattern, metatest_logger.get_log()) is not None

    def trace_tester(result: Entry, trace: str) -> None:
        name_limits: Tuple[int, int] = extract_info.min_max_names(
            result["emails"], result["phones"]
        )
        exit_type = extract_info.decide_exit_type(result["names"], *name_limits)
        assert re.fullmatch(patterns[exit_type], trace)

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
    # could try reclassifying everything in case something is falsely
    # marked as wrong
