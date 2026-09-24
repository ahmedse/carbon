"""Cell map: open cells cap the dimension; Pulse is one app."""
from excellence.catalogue import Check, Subject
from excellence.cells import build_grid, subjects_for_app
from excellence.evaluator import CheckState
from excellence.evaluator import SubjectReport
from excellence.standard import load_standard


def _subject(sid="platform.module.accounts", kind="module"):
    return Subject(id=sid, kind=kind, title=sid, tier="platform", owner="owner")


def _check(cid, dimension, rank):
    return Check(id=cid, title=cid, dimension=dimension, rank=rank, collector="repo")


def _report(subject, checks):
    states = [CheckState(c, "passed", "executed", "abc", "t") for c in checks]
    return SubjectReport(subject=subject, level=0, checks=states)


def test_open_dimension_caps_the_app_at_zero():
    subject = _subject()
    checks = [_check("G1", "governed", 1)]
    grid = build_grid([subject], {subject.id: _report(subject, checks)})
    governed = next(c for c in grid["cells"] if c["dimension"] == "governed" and c["level"] == 1)
    secure = next(c for c in grid["cells"] if c["dimension"] == "secure" and c["level"] == 1)
    assert governed["state"] == "passed"
    assert secure["state"] == "open"
    assert grid["dimensions"]["secure"] == 0
    assert grid["level"] == 0
    assert grid["dimensions"][grid["weakest"]] == 0


def test_na_dimension_does_not_cap_an_artifact():
    subject = _subject("platform.repo", "artifact")
    checks = [
        _check(f"D{dim}{rank}", dim, rank)
        for dim in ("specified", "correct", "reliable", "maintainable", "observed", "governed")
        for rank in range(1, 7)
    ]
    grid = build_grid([subject], {subject.id: _report(subject, checks)})
    assert next(c for c in grid["cells"] if c["dimension"] == "secure")["state"] == "n/a"
    assert grid["level"] == 6


def test_standard_declares_every_cell():
    standard = load_standard()
    assert len(standard.rungs) == 54
    assert standard.applies("dataset", "usable") is False
    assert standard.applies("module", "secure") is True


def test_pulse_is_one_app():
    from excellence.catalogue import load_catalogue
    cat = load_catalogue()
    rows = subjects_for_app(cat, "pulse")
    assert rows
    assert all(s.tier == "pulse" for s in rows)
    chat = subjects_for_app(cat, "pulse", "chat")
    assert chat and all(s.track == "chat" for s in chat)
