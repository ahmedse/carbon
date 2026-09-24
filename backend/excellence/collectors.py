"""Collectors turn checks into events (ADR-0051 §8).

A collector receives the catalogue and the checks it owns, runs or reads
something, and returns event drafts. Collectors shell out to the systems
under test or read their outputs; they never import ``people``, ``emissions``,
``gradevance`` or ``ai.engine``. Anything that cannot run reports
``unknown`` — never a guessed pass.

Built-in collectors and the probes they understand:

repo (default)
    field_nonempty {field}        subject attribute is non-empty
    paths_exist {field}           every declared path in that field exists
    tests_present                 ≥1 test_*.py / *.test.* under subject paths/tests
    process_yaml                  subject.process file exists and parses
antipatterns
    verify_antipatterns           .ai-toolkit/scripts/verify.sh antipatterns (exit 0)
pulse_gauge
    budget_gate                   ai.eval.harness_budget gate has no violations
    ladder_level {level}          intelligence ladder level id reached
    packs_gate                    ai.eval.pack_contract has no violations
    soak_complete                 PV2-6B soak complete
pytest
    pytest_app {app}              runs one app's tests (only when explicitly requested)
vitest
    vitest_file {file}            one frontend test file (only when --run vitest:<path>)
observe
    ci_files                      subject.ci paths exist
    runbook_files                 subject.runbook paths exist
    migrations_present            backend/<app>/migrations exists
    gauge_series_fresh {days}     evidence series file modified within N days
    evaluator_self_check          in-process Soundcheck/fault rules still hold (fault-demonstrated)
"""
from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .catalogue import REPO_ROOT, Catalogue, Check, Subject

TEST_GLOBS = ("test_*.py", "*_test.py", "*.test.js", "*.test.jsx", "*.test.ts", "*.test.tsx", "*.spec.ts")


@dataclass
class EventDraft:
    check_id: str
    subject_id: str
    tier: str
    track: str
    result: str
    evidence_class: str
    source: str = ""
    runner: str = "local"
    duration_ms: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


Collector = Callable[[Catalogue, list[tuple[Check, Subject]], dict[str, Any]], list[EventDraft]]


def _draft(check: Check, subject: Subject, result: str, evidence_class: str = "executed", **kw) -> EventDraft:
    return EventDraft(
        check_id=check.id, subject_id=subject.id, tier=subject.tier, track=subject.track,
        result=result, evidence_class=evidence_class, **kw,
    )


def _unknown(check: Check, subject: Subject, why: str) -> EventDraft:
    return _draft(check, subject, "unknown", "unknown", detail={"why": why})


# ── repo ───────────────────────────────────────────────────────────────────


def _has_tests(subject: Subject) -> bool:
    roots = [REPO_ROOT / p for p in (*subject.tests, *subject.paths)]
    for root in roots:
        if root.is_file():
            if any(root.match(g) for g in TEST_GLOBS):
                return True
            continue
        if not root.is_dir():
            continue
        for g in TEST_GLOBS:
            if next(root.rglob(g), None) is not None:
                return True
    return False


def collect_repo(cat: Catalogue, pairs: list[tuple[Check, Subject]], ctx: dict[str, Any]) -> list[EventDraft]:
    out: list[EventDraft] = []
    for check, subject in pairs:
        kind = str(check.probe.get("type") or "")
        if kind == "field_nonempty":
            fld = str(check.probe.get("field") or "")
            val = getattr(subject, fld, None) if fld else None
            if val is None:
                val = subject.extra.get(fld)
            out.append(_draft(check, subject, "passed" if val else "failed", source=f"manifest:{fld}"))
        elif kind == "paths_exist":
            fld = str(check.probe.get("field") or "paths")
            paths = getattr(subject, fld, ()) or ()
            missing = [p for p in paths if not (REPO_ROOT / p).exists()]
            ok = bool(paths) and not missing
            out.append(_draft(check, subject, "passed" if ok else "failed", source=f"manifest:{fld}",
                              detail={"declared": list(paths), "missing": missing}))
        elif kind == "tests_present":
            out.append(_draft(check, subject, "passed" if _has_tests(subject) else "failed", source="repo:tests"))
        elif kind == "process_yaml":
            path = REPO_ROOT / subject.process if subject.process else None
            if path is None or not path.is_file():
                out.append(_draft(check, subject, "failed", source="manifest:process"))
                continue
            try:
                import yaml

                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                ok = isinstance(data, dict) and bool(data)
            except Exception as exc:  # noqa: BLE001
                out.append(_draft(check, subject, "failed", source=str(subject.process), detail={"error": str(exc)}))
                continue
            out.append(_draft(check, subject, "passed" if ok else "failed", source=str(subject.process)))
        else:
            out.append(_unknown(check, subject, f"repo collector has no probe {kind!r}"))
    return out


# ── antipatterns (verify.sh) ───────────────────────────────────────────────


def collect_antipatterns(cat: Catalogue, pairs: list[tuple[Check, Subject]], ctx: dict[str, Any]) -> list[EventDraft]:
    script = REPO_ROOT / ".ai-toolkit" / "scripts" / "verify.sh"
    if not script.is_file():
        return [_unknown(c, s, "verify.sh missing") for c, s in pairs]
    started = time.monotonic()
    try:
        proc = subprocess.run(
            ["bash", str(script), "antipatterns"], cwd=REPO_ROOT, capture_output=True, text=True,
            timeout=int(ctx.get("timeout", 600)), check=False,
        )
    except subprocess.TimeoutExpired:
        return [_unknown(c, s, "verify.sh antipatterns timed out") for c, s in pairs]
    ms = int((time.monotonic() - started) * 1000)
    result = "passed" if proc.returncode == 0 else "failed"
    tail = (proc.stdout + proc.stderr)[-2000:]
    return [
        _draft(c, s, result, source="verify.sh antipatterns", duration_ms=ms,
               detail={"exit": proc.returncode, "tail": tail})
        for c, s in pairs
    ]


# ── pulse_gauge (ai.eval.*) ────────────────────────────────────────────────


def collect_pulse_gauge(cat: Catalogue, pairs: list[tuple[Check, Subject]], ctx: dict[str, Any]) -> list[EventDraft]:
    out: list[EventDraft] = []
    cache: dict[str, Any] = {}

    def budget() -> tuple[bool, dict[str, Any]]:
        if "budget" not in cache:
            from ai.eval.harness_budget import gate_violations, measure
            from ai.eval.pulse_gauge import CEILING_PATH, _load

            measured = measure()
            violations = gate_violations(measured, _load(CEILING_PATH))
            cache["budget"] = (not violations, {"violations": violations, "measured": measured})
        return cache["budget"]

    def ladder() -> dict[str, Any]:
        if "ladder" not in cache:
            from ai.eval.pulse_gauge import collect_ladder

            cache["ladder"] = collect_ladder()
        return cache["ladder"]

    def packs() -> tuple[bool, dict[str, Any]]:
        if "packs" not in cache:
            from ai.eval.pack_contract import check_all

            rows, violations = check_all()
            cache["packs"] = (not violations, {"violations": violations, "packs": [r.get("id") for r in rows]})
        return cache["packs"]

    def soak() -> dict[str, Any]:
        if "soak" not in cache:
            from ai.eval.pulse_gauge import collect_soak

            cache["soak"] = collect_soak()
        return cache["soak"]

    for check, subject in pairs:
        kind = str(check.probe.get("type") or "")
        try:
            if kind == "budget_gate":
                ok, detail = budget()
                out.append(_draft(check, subject, "passed" if ok else "failed", source="ai.eval.harness_budget", detail=detail))
            elif kind == "ladder_level":
                want = str(check.probe.get("level") or "")
                status = (ladder().get("levels") or {}).get(want)
                if status is None:
                    out.append(_unknown(check, subject, f"ladder level {want!r} not scored"))
                else:
                    out.append(_draft(check, subject, "passed" if status == "reached" else "failed",
                                      source="ai.eval.intelligence_ladder", detail={"level": want, "status": status}))
            elif kind == "packs_gate":
                ok, detail = packs()
                out.append(_draft(check, subject, "passed" if ok else "failed", source="ai.eval.pack_contract", detail=detail))
            elif kind == "soak_complete":
                row = soak()
                ok = bool(row.get("soak_complete"))
                out.append(_draft(check, subject, "passed" if ok else "failed", source="PV2-6B-nights.json", detail=row))
            else:
                out.append(_unknown(check, subject, f"pulse_gauge collector has no probe {kind!r}"))
        except Exception as exc:  # noqa: BLE001
            out.append(_unknown(check, subject, f"{type(exc).__name__}: {exc}"))
    return out


# ── pytest (one app, explicit) ─────────────────────────────────────────────


def collect_pytest(cat: Catalogue, pairs: list[tuple[Check, Subject]], ctx: dict[str, Any]) -> list[EventDraft]:
    wanted = set(ctx.get("run_apps") or ())
    out: list[EventDraft] = []
    for check, subject in pairs:
        app = str(check.probe.get("app") or subject.extra.get("app") or "")
        if not app:
            out.append(_unknown(check, subject, "pytest probe has no app"))
            continue
        if app not in wanted:
            out.append(EventDraft(
                check_id=check.id, subject_id=subject.id, tier=subject.tier, track=subject.track,
                result="unknown", evidence_class="configured", source=f"pytest {app}",
                detail={"why": "not requested; pass --run pytest:<app>"},
            ))
            continue
        started = time.monotonic()
        cmd = [sys.executable, "-m", "pytest", app, "-q", "--maxfail=5", "--disable-warnings", "-p", "no:cacheprovider"]
        try:
            proc = subprocess.run(cmd, cwd=REPO_ROOT / "backend", capture_output=True, text=True,
                                  timeout=int(ctx.get("timeout", 1800)), check=False)
        except subprocess.TimeoutExpired:
            out.append(_unknown(check, subject, f"pytest {app} timed out"))
            continue
        ms = int((time.monotonic() - started) * 1000)
        result = "passed" if proc.returncode == 0 else ("unknown" if proc.returncode == 5 else "failed")
        out.append(_draft(check, subject, result, source=" ".join(cmd[2:]), duration_ms=ms,
                          detail={"exit": proc.returncode, "tail": (proc.stdout + proc.stderr)[-2000:]}))
    return out


# ── vitest (one file, explicit) ────────────────────────────────────────────


def collect_vitest(cat: Catalogue, pairs: list[tuple[Check, Subject]], ctx: dict[str, Any]) -> list[EventDraft]:
    wanted = set(ctx.get("run_vitest") or ())
    out: list[EventDraft] = []
    for check, subject in pairs:
        rel = str(check.probe.get("file") or subject.extra.get("vitest") or "")
        if not rel:
            # default: first tests path that looks like a file, else skip
            for t in subject.tests:
                if t.endswith((".js", ".jsx", ".ts", ".tsx")):
                    rel = t
                    break
        if not rel:
            out.append(_unknown(check, subject, "vitest probe has no file"))
            continue
        if rel not in wanted and not any(rel.endswith(w) or w.endswith(rel) for w in wanted):
            out.append(EventDraft(
                check_id=check.id, subject_id=subject.id, tier=subject.tier, track=subject.track,
                result="unknown", evidence_class="configured", source=f"vitest {rel}",
                detail={"why": "not requested; pass --run vitest:<path>"},
            ))
            continue
        started = time.monotonic()
        cmd = ["npx", "vitest", "run", rel]
        try:
            proc = subprocess.run(
                cmd, cwd=REPO_ROOT / "carbon-frontend", capture_output=True, text=True,
                timeout=int(ctx.get("timeout", 600)), check=False,
            )
        except subprocess.TimeoutExpired:
            out.append(_unknown(check, subject, f"vitest {rel} timed out"))
            continue
        ms = int((time.monotonic() - started) * 1000)
        result = "passed" if proc.returncode == 0 else "failed"
        out.append(_draft(check, subject, result, source=" ".join(cmd), duration_ms=ms,
                          detail={"exit": proc.returncode, "tail": (proc.stdout + proc.stderr)[-2000:]}))
    return out


# ── observe (P3) ───────────────────────────────────────────────────────────


def _evaluator_self_check() -> tuple[bool, dict[str, Any]]:
    """Fault-demonstration: prove stale/conflict/fail pin a subject at L0."""
    from datetime import date as date_cls

    from .catalogue import Check, Subject, Tier, Catalogue
    from .evaluator import evaluate

    cat = Catalogue()
    cat.tiers["platform"] = Tier(id="platform", title="p")
    cat.subjects["m"] = Subject(id="m", kind="module", title="m", tier="platform", owner="o", paths=("x",))
    cat.checks["G1"] = Check(id="G1", title="G1", dimension="governed", rank=1, collector="repo")
    cat.checks["G2"] = Check(id="G2", title="G2", dimension="governed", rank=1, collector="repo")
    head = "abc"
    cases = []
    # failing rank-1 must pin L0
    rep = evaluate(cat, [
        {"check_id": "G1", "subject_id": "m", "commit": head, "result": "passed", "evidence_class": "executed", "at": 1},
        {"check_id": "G2", "subject_id": "m", "commit": head, "result": "failed", "evidence_class": "executed", "at": 1},
    ], head=head)["m"]
    cases.append(("fail_pins_l0", rep.level == 0))
    # stale does not count
    rep = evaluate(cat, [
        {"check_id": "G1", "subject_id": "m", "commit": "old", "result": "passed", "evidence_class": "executed", "at": 1},
        {"check_id": "G2", "subject_id": "m", "commit": head, "result": "passed", "evidence_class": "executed", "at": 1},
    ], head=head)["m"]
    cases.append(("stale_not_pass", rep.level == 0))
    # conflict never passable
    rep = evaluate(cat, [
        {"check_id": "G1", "subject_id": "m", "commit": head, "result": "passed", "evidence_class": "conflict", "at": 1},
        {"check_id": "G2", "subject_id": "m", "commit": head, "result": "passed", "evidence_class": "executed", "at": 1},
    ], head=head)["m"]
    cases.append(("conflict_blocks", rep.level == 0))
    # expired exemption does not satisfy
    today = date_cls(2026, 9, 24)
    rep = evaluate(cat, [
        {"check_id": "G1", "subject_id": "m", "commit": head, "result": "passed", "evidence_class": "executed", "at": 1},
        {"check_id": "G2", "subject_id": "m", "commit": head, "result": "failed", "evidence_class": "executed", "at": 1},
    ], [{"check_id": "G2", "subject_id": "m", "until": date_cls(2026, 9, 1)}], head=head, today=today)["m"]
    cases.append(("expired_exemption", rep.level == 0))
    ok = all(v for _, v in cases)
    return ok, {"cases": dict(cases)}


def collect_observe(cat: Catalogue, pairs: list[tuple[Check, Subject]], ctx: dict[str, Any]) -> list[EventDraft]:
    out: list[EventDraft] = []
    self_cache: tuple[bool, dict[str, Any]] | None = None
    for check, subject in pairs:
        kind = str(check.probe.get("type") or "")
        if kind == "ci_files":
            paths = subject.ci or _tuple_probe(check)
            missing = [p for p in paths if not (REPO_ROOT / p).exists()]
            ok = bool(paths) and not missing
            out.append(_draft(check, subject, "passed" if ok else "failed", source="observe:ci",
                              detail={"declared": list(paths), "missing": missing}))
        elif kind == "runbook_files":
            paths = subject.runbook or _tuple_probe(check)
            missing = [p for p in paths if not (REPO_ROOT / p).exists()]
            ok = bool(paths) and not missing
            out.append(_draft(check, subject, "passed" if ok else "failed", source="observe:runbook",
                              detail={"declared": list(paths), "missing": missing}))
        elif kind == "migrations_present":
            app = str(check.probe.get("app") or subject.extra.get("app") or "")
            if not app:
                out.append(_unknown(check, subject, "no app for migrations_present"))
                continue
            mig = REPO_ROOT / "backend" / app / "migrations"
            out.append(_draft(check, subject, "passed" if mig.is_dir() else "failed",
                              source=str(mig.relative_to(REPO_ROOT))))
        elif kind == "gauge_series_fresh":
            rel = str(check.probe.get("file") or "docs/pulse/evidence/PV2-gauge-series.json")
            days = int(check.probe.get("days") or 14)
            path = REPO_ROOT / rel
            if not path.is_file():
                out.append(_draft(check, subject, "failed", source=rel, detail={"why": "missing"}))
                continue
            age = (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 86400
            ok = age <= days
            out.append(_draft(check, subject, "passed" if ok else "failed", source=rel,
                              detail={"age_days": round(age, 2), "limit_days": days}))
        elif kind == "evaluator_self_check":
            if self_cache is None:
                self_cache = _evaluator_self_check()
            ok, detail = self_cache
            # this is the fault-demonstration campaign: evidence class is fault-demonstrated
            out.append(_draft(check, subject, "passed" if ok else "failed",
                              evidence_class="fault-demonstrated", source="excellence.evaluator", detail=detail))
        else:
            out.append(_unknown(check, subject, f"observe collector has no probe {kind!r}"))
    return out


def _tuple_probe(check: Check) -> tuple[str, ...]:
    raw = check.probe.get("paths") or check.probe.get("files") or ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list):
        return tuple(str(x) for x in raw)
    return ()


REGISTRY: dict[str, Collector] = {
    "repo": collect_repo,
    "antipatterns": collect_antipatterns,
    "pulse_gauge": collect_pulse_gauge,
    "pytest": collect_pytest,
    "vitest": collect_vitest,
    "observe": collect_observe,
}


def run_collectors(
    cat: Catalogue,
    subjects: Iterable[Subject],
    *,
    only: set[str] | None = None,
    ctx: dict[str, Any] | None = None,
    registry: dict[str, Collector] | None = None,
) -> list[EventDraft]:
    """Group applicable checks by collector and run each once."""
    registry = registry or REGISTRY
    ctx = ctx or {}
    grouped: dict[str, list[tuple[Check, Subject]]] = {}
    for subject in subjects:
        for check in cat.checks_for(subject):
            if only and check.collector not in only:
                continue
            grouped.setdefault(check.collector, []).append((check, subject))
    drafts: list[EventDraft] = []
    for name, pairs in grouped.items():
        fn = registry.get(name)
        if fn is None:
            drafts.extend(_unknown(c, s, f"no collector named {name!r}") for c, s in pairs)
            continue
        try:
            drafts.extend(fn(cat, pairs, ctx))
        except Exception as exc:  # noqa: BLE001
            drafts.extend(_unknown(c, s, f"collector {name} crashed: {exc}") for c, s in pairs)
    return drafts
