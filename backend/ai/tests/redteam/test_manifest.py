"""P1-17 accounting gate — proves the catalogue is a real 10 x 6 matrix.

Guards against drift: if a path loses or gains an entry (or two paths collide
on an id), this test fails before any guard assertion runs.
"""

from __future__ import annotations

from ai.tests.redteam import mutations


def test_catalogue_has_sixty_attempts():
    assert len(mutations.ALL) == 60


def test_each_path_has_ten_attempts():
    for path, entries in mutations.PATHS.items():
        assert len(entries) == 10, f"path {path!r} has {len(entries)} attempts"


def test_attempt_ids_are_unique():
    ids = [e["id"] for e in mutations.ALL]
    assert len(ids) == len(set(ids)), "duplicate attempt id detected"


def test_attempt_ids_are_prefixed_by_path():
    for path, entries in mutations.PATHS.items():
        for entry in entries:
            assert entry["id"].startswith(
                f"{path}-"
            ), f"id {entry['id']!r} does not match path {path!r}"
