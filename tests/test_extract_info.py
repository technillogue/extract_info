import re
import json
from typing import Dict, List, Any, Tuple, Callable, Sequence, cast
import pytest
import extract_info
import extract_names
import utils
from tools import ask, fd_print

# NOTE: for reclassification, use --capture=sys

# our code has three stages and various strategies for  each stage,
# which it does in order until one works
# as soon as a given strategy for this stage doesn't work, it should jump
# to the next strategy for this stage without trying the next stages

# this corresponds to a finate state automata
# where the symbols are the names of each strategy for each stage
# and the states are the combinations of strategies for each stage,
# including "not doing this stage right now" as the 0th state

# because every FSA corresponds to a regex, we know that there exists a
# regex that match correct paths. we can log which strategies are called
# and see if they match the regex to test correct program flow
#
# reminder:
# a stage is made up out of strategies for that stage
STAGES = cast(Sequence[Sequence[Callable]], extract_names.STAGES)
STAGES_STRATEGY_NAMES: List[List[str]] = [
    [strategy.__name__ for strategy in step] for step in STAGES
]

metatest_logger = utils.Logger()


def regex_gen(
    continuation_pattern: str,
    terminal_pattern: str = "{last_strategy}\n{next_stages}",
    stages_strategy_names: List[List[str]] = STAGES_STRATEGY_NAMES,
) -> str:
    @metatest_logger.logged
    def strategy_recurser(strategies: List[str], next_stages: str) -> str:
        if len(strategies) == 1:
            return terminal_pattern.format(
                last_strategy=strategies[0], next_stages=next_stages
            )
        # how can our metaprogramming be real if our scopes aren't real
        # in other terms, variables not found in locals() will be first looked up in the
        # context of *this call* of pattern_gen_gen-- that's why this trick works in the first place
        next_strategies = strategy_recurser(strategies[1:], next_stages)
        return continuation_pattern.format(
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


REGEX_GEN_PATTERN = "stages_recurser\n" * len(
    STAGES_STRATEGY_NAMES
) + "strategy_recurser\n" * sum(
    len(stage_strategies) for stage_strategies in STAGES_STRATEGY_NAMES
)

NOT_ENOUGH_PATTERN = regex_gen(
    continuation_pattern="{strategy}\n({next_stages})?{next_strategies}",
    terminal_pattern="{last_strategy}\n({next_stages})?",
)
# hide your functions, hide your tests, because they're testing everyone out there there
assert re.fullmatch(REGEX_GEN_PATTERN, metatest_logger.get_log()) is not None

CORRECT_PATTERN = regex_gen(
    continuation_pattern="{strategy}\n({next_stages}|{next_strategies})"
)
TOO_MUCH_PATTERN = regex_gen(
    continuation_pattern="{strategy}\n{next_stages}\n{next_strategies}"
)

# no rest for the test-driven wicked
assert re.match(REGEX_GEN_PATTERN * 3, metatest_logger.get_log()) is not None

Entry = Dict[str, List[str]]
EXAMPLES_FNAME = "data/examples.json"
EXAMPLES: List[Entry] = json.load(open(EXAMPLES_FNAME, encoding="utf-8"))
COUNTEREXAMPLES_FNAME = "data/counterexamples.json"
COUNTEREXAMPLES: List[Entry] = json.load(open(COUNTEREXAMPLES_FNAME, encoding="utf-8"))
LABELED_EXAMPLES: List[Tuple[Entry, bool]] = [
    (example, True) for example in EXAMPLES
] + [(example, False) for example in COUNTEREXAMPLES]


@pytest.fixture(params=LABELED_EXAMPLES, name="labeled_example")
def labeled_example_fixture(request: Any) -> Tuple[Entry, bool]:
    return request.param


def trace_extract_info_nonfixture() -> Tuple[utils.Logger, Callable]:
    logger = utils.Logger()
    stages = tuple(
        [logger.logged(strategy) for strategy in stage]
        for stage in STAGES
    )

    def traced_extract_info(*args: Any, **kwargs: Any) -> Any:
        result = extract_info.extract_info(*args, stages=stages, **kwargs)  # type: ignore
        return result

    return (logger, traced_extract_info)


trace_extract_info_fixture = pytest.fixture(
    trace_extract_info_nonfixture, name="trace_extract_info"
)


def test_examples(
    labeled_example: Tuple[Entry, bool],
    trace_extract_info: Tuple[utils.Logger, Callable],
) -> None:
    logger, traced_extract_info = trace_extract_info
    logger.new_stream()
    example, correct = labeled_example
    line = example["line"][0]
    actual = traced_extract_info(line)
    min_names, max_names = extract_info.min_max_names(
        example["emails"], example["phones"]
    )
    # check trace
    log_trace = logger.get_log()
    actual_names = len(actual["names"])
    if actual_names <= max_names:
        if actual_names >= min_names:
            assert re.fullmatch(CORRECT_PATTERN, log_trace) is not None
        else:
            assert re.fullmatch(NOT_ENOUGH_PATTERN, log_trace) is not None
    else:
        assert re.fullmatch(TOO_MUCH_PATTERN, log_trace) is not None
    # check corectness
    if actual != example:
        really_correct = ask(example)
        # reclassify
        if really_correct is True:
            fd_print("marking as correct")
            remove_from_list, remove_from_fname = (
                COUNTEREXAMPLES,
                COUNTEREXAMPLES_FNAME,
            )
            add_to_list, add_to_fname = (EXAMPLES, EXAMPLES_FNAME)
        elif really_correct is False:
            remove_from_list, remove_from_fname = (EXAMPLES, EXAMPLES_FNAME)
            add_to_list, add_to_fname = (COUNTEREXAMPLES, COUNTEREXAMPLES_FNAME)
            fd_print("marking as incorrect")
        if isinstance(really_correct, bool):
            if correct != really_correct:
                fd_print("reclassifying")
                remove_from_list.remove(example)
                json.dump(
                    remove_from_list,
                    open(remove_from_fname, "w", encoding="utf-8"),
                    indent=4,
                )
            else:
                add_to_list.remove(example)
                fd_print("updating example")
            json.dump(
                add_to_list + [actual], open(add_to_fname, "w", encoding="utf-8"), indent=4
            )
        if correct and not really_correct:
            assert actual == example


def test_last() -> None:
    # fake test
    utils.cache.save_cache()
