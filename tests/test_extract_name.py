import extract_names


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


def test_no_google() -> None:
    actual = extract_names.extract_names(
        "12/31 -- Lisa balloon drop -- off 123.123.1234 - paid, check deposited", 1, 1
    )
    expected = ["Lisa"]
    if actual != expected:
        breakpoint()
        extract_names.extract_names(
            "12/31 -- Lisa balloon drop -- off 123.123.1234 - paid, check deposited",
            1,
            1,
        )
    else:
        extract_names.cache.save_cache()
    assert actual == expected
