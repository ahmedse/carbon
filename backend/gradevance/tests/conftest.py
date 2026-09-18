"""Shared fixtures for GradeVance tests."""
import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    """Avoid cross-test LTI state + DRF throttle 429 flakes."""
    cache.clear()
    yield
    cache.clear()
