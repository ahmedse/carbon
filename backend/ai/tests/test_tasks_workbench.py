"""The Tasks workbench holds, and the core file stays pack-free."""
from pathlib import Path

from ai.eval.tasks_workbench import CORE_BANK, load_cases, score


def _core_cases():
    return [case for case in load_cases() if str(case["id"]).startswith("core.")]


def test_core_cases_hold():
    """The domain-free core (this surface) must be 100% green."""
    report = score(_core_cases())
    assert report["misses"] == [], report["misses"]
    assert report["gate_pass"] is True
    assert report["tier"] == "structural"
    assert report["n"] >= 200
    ids = [case["id"] for case in load_cases()]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 250
    assert sum(1 for case_id in ids if case_id.startswith("nibras.")) >= 160


def test_pack_cases_are_present_and_structural():
    """Packs are loaded from disk; their data is owned by the pack, not the core."""
    ids = [case["id"] for case in load_cases()]
    assert any(case_id.startswith("core.") for case_id in ids)
    assert any(case_id.startswith("nibras.") for case_id in ids)
    assert any(case_id.startswith("eduos.") for case_id in ids)
    assert any(case_id.startswith("carbon.") for case_id in ids)


def test_core_bank_does_not_name_a_pack():
    text = CORE_BANK.read_text(encoding="utf-8").lower()
    packs = Path(__file__).resolve().parents[3] / "domain_packs"
    ids = [p.name.lower() for p in packs.iterdir() if p.is_dir() and not p.name.startswith(".")]
    leaked = [name for name in ids if name in text]
    assert leaked == []


def test_workbench_is_structural_and_never_scores_live():
    report = score()
    assert report["tier"] == "structural"
    assert "not a Tasks retest" in report["live"]


def test_generated_guard_consent_and_citation_families_hold():
    """The broadened families must exist and pass."""
    report = score(_core_cases())
    assert report["misses"] == [], report["misses"]
    ids = {case["id"] for case in load_cases()}
    # Consent ordering across wait / observe / subflow.
    for kind in ("wait", "observe", "subflow"):
        assert f"core.gen.consent.{kind}.before" in ids
        assert f"core.gen.consent.{kind}.write-before-human" in ids
        assert f"core.gen.consent.{kind}.two-humans-differ" in ids
        assert f"core.gen.consent.{kind}.two-humans-same" in ids
    # Citation strictness.
    for cid in (
        "core.gen.cite.empty-tokens",
        "core.gen.cite.duplicate-hits",
        "core.gen.cite.missing-one-of-three",
        "core.gen.cite.arabic-token",
    ):
        assert cid in ids
    # Tool-set traps for every readonly role.
    for role in ("domain_specialist", "researcher", "planner", "critic"):
        assert f"core.gen.toolset.{role}.write-trap" in ids
        assert f"core.gen.toolset.{role}.readonly" in ids
    # Edits must keep consent on the write.
    assert "core.gen.edit.reroute-past-consent" in ids
    assert "core.gen.edit.drop-consent-edge" in ids
    # Compensation and hidden-field families.
    assert "core.gen.compensate.ungated-trap" in ids
    assert "core.gen.hidden2.salary" in ids


def test_no_case_mentions_a_brand_in_the_generated_core():
    """Generated core stays domain-free (ADR-0050) even though it lives in code."""
    core = [case for case in load_cases() if str(case["id"]).startswith("core.")]
    blob = " ".join(str(case.get("brief") or "") for case in core).lower()
    packs = Path(__file__).resolve().parents[3] / "domain_packs"
    names = [p.name.lower() for p in packs.iterdir() if p.is_dir() and not p.name.startswith(".")]
    leaked = [name for name in names if name in blob]
    assert leaked == []


def _case(case_id):
    for case in load_cases():
        if case["id"] == case_id:
            return case
    raise AssertionError(f"missing case {case_id}")


def test_carbon_citation_decoys_are_near_misses():
    """A carbon decoy must tempt without holding every token.

    The token-strict citer may only cite a passage that holds the whole token
    set. The wrong statement stays a tempting wrong citation but omits a token,
    so ``cite`` cites only the hit and ``cite-miss`` refuses the lone decoy.
    """
    for name in ("coverage-complete", "period-open"):
        hit_case = _case(f"carbon.gen.cite.{name}")
        miss_case = _case(f"carbon.gen.cite-miss.{name}")
        report = score([hit_case, miss_case])
        assert report["misses"] == [], report["misses"]
        assert report["gate_pass"] is True

        tokens = [str(token).lower() for token in hit_case["tokens"]]
        decoy = next(p["text"] for p in hit_case["passages"] if p["id"] == "decoy").lower()
        other = miss_case["passages"][0]["text"].lower()
        for text in (decoy, other):
            assert [token for token in tokens if token in text] != tokens, (name, text)
