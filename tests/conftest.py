# mypy: disallow_untyped_decorators=False
from typing import Iterator
import pytest
from cache import cache

@pytest.fixture
def save_cache() -> Iterator[None]:
    with cache:
        yield
