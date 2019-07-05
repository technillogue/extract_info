# mypy: disallow_untyped_decorators=False
from utils import cache
import pytest

@pytest.fixture
def save_cache() -> None:
    yield
    cache.save_cache()
