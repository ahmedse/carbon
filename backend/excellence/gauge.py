"""Excellence gauge — collect, evaluate, snapshot, ratchet (ADR-0051 §9).

    python -m excellence.gauge                       # levels for every tier, from the ledger
    python -m excellence.gauge --tier pulse          # one tier
    python -m excellence.gauge --collect             # run collectors (repo, antipatterns, pulse_gauge) and write events
    python -m excellence.gauge --collect --only repo # a subset of collectors
    python -m excellence.gauge --collect --run pytest:accounts   # one app's tests, explicitly
    python -m excellence.gauge --write               # freeze today's levels as Snapshot rows
    python -m excellence.gauge --gate                # exit 1 if any subject regressed vs its last snapshot
    python -m excellence.gauge --no-db               # evaluate collected events in memory (CI without the ledger DB)
    python -m excellence.gauge --json                # machine output

Runs inside Django so the ledger alias is available. ``--no-db`` never touches
the database and is the P0 fallback when ``carbon_excellence`` is absent.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from typing import Any

import yaml

from .catalogue import LEVEL_NAMES, REPO_ROOT, Catalogue, load_catalogue
from .collectors import EventDraft, run_collectors
from .evaluator import SubjectReport, evaluate, regressions


def head_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


def persist(drafts: list[EventDraft], head: str, runner: str = "local") -> int:
    from .models import Event

    rows = [
        Event(
            check_id=d.check_id, subject_id=d.subject_id, tier=d.tier, track=d.track, commit=head,
            result=d.result, evidence_class=d.evidence_class, source=d.source, runner=d.runner or runner,
            duration_ms=d.duration_ms, detail=d.detail,
        )
        for d in drafts
    ]
    Event.objects.bulk_create(rows)
    return len(rows)


def load_events(tier: str | None) -> list[Any]:
    from .models import Event

    qs = Event.objects.all()
    if tier:
        qs = qs.filter(tier=tier)
    return list(qs.values("check_id", "subject_id", "commit", "result", "evidence_class", "at", "source"))


def load_exemptions() -> list[Any]:
    from .models import Exemption

    return list(Exemption.objects.values("check_id", "subject_id", "until"))


def _baseline_date() -> date:
    """Snapshots before this date used the old formula. They are not regressions."""
    from .standard import STANDARD_PATH
    path = STANDARD_PATH.parent / "baseline.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return date.fromisoformat(str(raw["date"]))


def previous_levels(tier: str | None) -> dict[str, int]:
    """Latest snapshot level per subject (before today)."""
    from .models import Snapshot

    qs = Snapshot.objects.filter(date__lt=date.today(), date__gte=_baseline_date())
    if tier:
        qs = qs.filter(tier=tier)
    out: dict[str, int] = {}
    for row in qs.order_by("subject_id", "-date").values("subject_id", "level"):
        out.setdefault(row["subject_id"], row["level"])
    return out


def write_snapshots(reports: dict[str, SubjectReport], head: str) -> int:
    from .models import Snapshot

    today = date.today()
    n = 0
    for rep in reports.values():
        Snapshot.objects.update_or_create(
            date=today, subject_id=rep.subject.id,
            defaults={
                "tier": rep.subject.tier, "track": rep.subject.track, "commit": head,
                "level": rep.level, "dimensions": rep.dimensions,
            },
        )
        n += 1
    return n


def render_text(cat: Catalogue, reports: dict[str, SubjectReport], head: str) -> str:
    lines = [f"Excellence ladder · HEAD {head[:7] or '?'} · {len(reports)} subjects"]
    if cat.problems:
        lines.append(f"  catalogue problems: {len(cat.problems)} (run with --json to list)")
    by_tier: dict[str, list[SubjectReport]] = {}
    for rep in reports.values():
        by_tier.setdefault(rep.subject.tier, []).append(rep)
    for tier_id in sorted(by_tier):
        tier = cat.tiers.get(tier_id)
        names = tier.level_names if tier else LEVEL_NAMES
        lines.append(f"\n[{tier_id}] {tier.title if tier else ''}")
        for rep in sorted(by_tier[tier_id], key=lambda r: (r.subject.track, -r.level, r.subject.id)):
            nxt = ", ".join(c.check.id for c in rep.next_steps[:3])
            dims = " ".join(f"{d[:4]}:{lv}" for d, lv in rep.dimensions.items())
            track = f"{rep.subject.track:<8}" if rep.subject.track else " " * 8
            lines.append(
                f"  {track} L{rep.level} {names[rep.level]:<10} {rep.subject.id:<44} {dims}"
                + (f"  next: {nxt}" if nxt else "")
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Excellence gauge (ADR-0051)")
    p.add_argument("--tier")
    p.add_argument("--track")
    p.add_argument("--collect", action="store_true", help="run collectors and (unless --no-db) persist events")
    p.add_argument("--only", help="comma list of collectors, e.g. repo,pulse_gauge,observe")
    p.add_argument("--run", action="append", default=[], help="explicit heavy runs, e.g. pytest:accounts or vitest:src/...")
    p.add_argument("--write", action="store_true", help="freeze today's levels as snapshots")
    p.add_argument("--gate", action="store_true", help="exit 1 when a subject regressed vs its last snapshot")
    p.add_argument(
        "--changed", nargs="?", const="origin/main", default=None,
        help="only evaluate/collect subjects whose paths changed vs BASE (default origin/main)",
    )
    p.add_argument("--no-db", action="store_true", help="never touch the ledger database")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    cat = load_catalogue()
    head = head_commit()
    subjects = cat.subjects_in(args.tier, args.track)
    changed_list: list[str] = []
    if args.changed is not None:
        from .changed import changed_paths, subjects_touched

        paths = changed_paths(args.changed)
        subjects = subjects_touched(cat, paths, tier=args.tier, track=args.track)
        changed_list = sorted(paths)
        if not subjects and args.gate:
            # nothing moved in the ladder → ratchet is vacuously clean
            if args.json:
                print(json.dumps({"head": head, "changed": changed_list, "subjects": [], "regressions": []}, indent=2))
            else:
                print(f"Excellence ladder · HEAD {head[:7] or '?'} · no subjects touched vs {args.changed}")
                print("\nratchet: clean (no changed subjects)")
            return 0

    run_apps = {r.split(":", 1)[1] for r in args.run if r.startswith("pytest:")}
    run_vitest = {r.split(":", 1)[1] for r in args.run if r.startswith("vitest:")}
    run_playwright = {r.split(":", 1)[1] for r in args.run if r.startswith("playwright:")}
    run_runtime = next((r.split(":", 1)[1] for r in args.run if r.startswith("runtime:")), "")
    ctx = {
        "run_apps": run_apps, "run_vitest": run_vitest, "run_playwright": run_playwright,
        "run_runtime": run_runtime,
    }
    only = {s.strip() for s in args.only.split(",")} if args.only else None
    if not args.collect and (run_apps or run_vitest or run_playwright or run_runtime):
        args.collect = True

    drafts: list[EventDraft] = []
    if args.collect:
        drafts = run_collectors(cat, subjects, only=only, ctx=ctx)
        if run_apps and (only is None or "pytest" not in only):
            drafts.extend(run_collectors(cat, subjects, only={"pytest"}, ctx=ctx))
        if run_vitest and (only is None or "vitest" not in only):
            drafts.extend(run_collectors(cat, subjects, only={"vitest"}, ctx=ctx))
        if run_playwright and (only is None or "playwright" not in only):
            drafts.extend(run_collectors(cat, subjects, only={"playwright"}, ctx=ctx))
        if run_runtime and (only is None or "runtime" not in only):
            drafts.extend(run_collectors(cat, subjects, only={"runtime"}, ctx=ctx))

    if args.no_db:
        events: list[Any] = [{**d.as_dict(), "commit": head, "at": None} for d in drafts]
        exemptions: list[Any] = []
        previous: dict[str, int] = {}
    else:
        _setup_django()
        if drafts:
            persist(drafts, head)
        events = load_events(args.tier)
        exemptions = load_exemptions()
        previous = previous_levels(args.tier)

    reports = evaluate(cat, events, exemptions, head=head, tier=args.tier, track=args.track)
    if args.changed is not None:
        keep = {s.id for s in subjects}
        reports = {k: v for k, v in reports.items() if k in keep}

    if args.write and not args.no_db:
        write_snapshots(reports, head)

    regressed = regressions(reports, previous) if args.gate else []

    if args.json:
        print(json.dumps({
            "head": head,
            "changed": changed_list or None,
            "problems": cat.problems,
            "collected": len(drafts),
            "subjects": [r.as_dict() for r in reports.values()],
            "regressions": regressed,
        }, indent=2, default=str))
    else:
        print(render_text(cat, reports, head))
        if drafts:
            print(f"\ncollected {len(drafts)} events" + (" (not persisted: --no-db)" if args.no_db else ""))
        if cat.problems and not args.json:
            for prob in cat.problems[:20]:
                print(f"  ! {prob}")
        if args.gate:
            print("\nratchet: " + ("clean" if not regressed else "REGRESSED\n  " + "\n  ".join(regressed)))

    if args.gate and regressed:
        return 1
    if args.gate and cat.problems and args.changed is None:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
