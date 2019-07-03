from typing import Any
import utils

number_of_limbs_owed_to_google: int


def test_cache() -> None:
    # pylint: disable=global-statement
    global number_of_limbs_owed_to_google
    number_of_limbs_owed_to_google = 0
    utils.cache.clear_cache("machine_learning_powered_echo")

    @utils.cache.with_cache
    def machine_learning_powered_echo(x: Any) -> Any:
        global number_of_limbs_owed_to_google
        number_of_limbs_owed_to_google += 1
        return x

    machine_learning_powered_echo("foo")
    machine_learning_powered_echo("foo")
    assert number_of_limbs_owed_to_google == 1
    utils.cache.clear_cache("machine_learning_powered_echo")
    machine_learning_powered_echo("foo")
    assert number_of_limbs_owed_to_google == 2
    assert machine_learning_powered_echo([]) == []
    assert machine_learning_powered_echo(["foo"]) == ["foo"]
    utils.cache.clear_cache("machine_learning_powered_echo")
