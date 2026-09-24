"""The committed manifests must load clean — a manifest that points at nothing is a claim."""
from __future__ import annotations

from pathlib import Path

import pytest

from excellence.catalogue import PLATFORM_TIER, Catalogue, load_catalogue


@pytest.fixture(scope="module")
def cat() -> Catalogue:
    return load_catalogue()


def test_committed_manifests_have_no_problems(cat: Catalogue) -> None:
    assert cat.problems == [], "\n".join(cat.problems)


def test_platform_and_pulse_tiers_load(cat: Catalogue) -> None:
    assert PLATFORM_TIER in cat.tiers
    assert "pulse" in cat.tiers
    assert "nibras" in cat.tiers
    assert "datatrust" in cat.tiers
    assert "carbon" in cat.tiers
    assert {"chat", "agent", "memory", "packs", "ops"} <= {t for (tier, t) in cat.tracks if tier == "pulse"}
    assert {"people", "my", "team", "payroll", "correspondence"} <= {t for (tier, t) in cat.tracks if tier == "nibras"}


def test_platform_checks_are_inherited_by_pulse_subjects(cat: Catalogue) -> None:
    planner = cat.subjects["pulse.agent.planner"]
    ids = {c.id for c in cat.checks_for(planner)}
    assert {"PLAT-GOV-01", "PLAT-GOV-02", "PLAT-COR-01"} <= ids
    # the antipatterns check is scoped to the platform.repo artifact only
    assert "PLAT-MNT-01" not in ids
    # a chat-track check never reaches an agent-track subject
    assert not any(c.id.startswith("PULSE-CHAT") for c in cat.checks_for(planner))


def test_checks_are_sorted_by_rank(cat: Catalogue) -> None:
    ranks = [c.rank for c in cat.checks_for(cat.subjects["pulse.chat.turn"])]
    assert ranks == sorted(ranks)


def test_bad_manifest_is_reported_not_raised(tmp_path: Path) -> None:
    (tmp_path / "platform").mkdir()
    (tmp_path / "platform" / "ladder.yaml").write_text(
        "tier: platform\nsubjects:\n  - id: x\n    kind: widget\n"
        "checks:\n  - id: C1\n    dimension: bogus\n    rank: 1\n"
        "  - id: C2\n    dimension: correct\n    rank: 9\n",
        encoding="utf-8",
    )
    cat = load_catalogue(assurance_root=tmp_path, domain_packs_root=tmp_path / "nope")
    assert cat.subjects == {} and cat.checks == {}
    joined = "\n".join(cat.problems)
    assert "kind 'widget'" in joined and "dimension 'bogus'" in joined and "rank 9" in joined
