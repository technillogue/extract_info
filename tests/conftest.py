# mypy: disallow_untyped_decorators=False
from typing import Iterator
import pytest
from utils import cache

@pytest.fixture
def save_cache() -> Iterator[None]:
    yield
    cache.save_cache()
