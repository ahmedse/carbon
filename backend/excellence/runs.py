"""Staff-triggered collector runs (ADR-0051 P2–P4).

Safe collectors (``repo``, ``pulse_gauge``, ``antipatterns``, ``observe``) may run
from the UI without an app list. ``pytest`` / ``vitest`` require exactly one
target (app label or file path) — never the full suite.
"""
from __future__ import annotations

from typing import Any

from django.utils import timezone

from .catalogue import load_catalogue
from .collectors import REGISTRY, run_collectors
from .gauge import head_commit, persist, write_snapshots
from .models import Run, RunStatus

UI_SAFE = frozenset({"repo", "pulse_gauge", "antipatterns", "observe", "rbac", "budget", "design_lint"})


def execute_run(
    *,
    collectors: list[str],
    requested_by: str,
    tier: str = "",
    track: str = "",
    run_apps: list[str] | None = None,
    run_vitest: list[str] | None = None,
    run_playwright: list[str] | None = None,
    write_snapshot: bool = False,
) -> Run:
    names = [c.strip() for c in collectors if c and str(c).strip()]
    apps = [a.strip() for a in (run_apps or []) if a and str(a).strip()]
    vitest_files = [a.strip() for a in (run_vitest or []) if a and str(a).strip()]
    playwright_files = [a.strip() for a in (run_playwright or []) if a and str(a).strip()]
    unknown = [c for c in names if c not in REGISTRY]
    if unknown:
        raise ValueError(f"Unknown collectors: {', '.join(unknown)}")
    if not names:
        raise ValueError("At least one collector is required.")
    if "pytest" in names and len(apps) != 1:
        raise ValueError("pytest requires run_apps with exactly one app label.")
    if "vitest" in names and len(vitest_files) != 1:
        raise ValueError("vitest requires run_vitest with exactly one test file path.")
    if "playwright" in names and len(playwright_files) != 1:
        raise ValueError("playwright requires run_playwright with exactly one journey path.")
    unsafe = [c for c in names if c not in UI_SAFE and c not in ("pytest", "vitest", "playwright")]
    if unsafe:
        raise ValueError(f"Collectors not allowed from the UI: {', '.join(unsafe)}")

    head = head_commit()
    run = Run.objects.create(
        collectors=names,
        tier=tier or "",
        track=track or "",
        run_apps=apps or vitest_files,
        status=RunStatus.RUNNING,
        requested_by=requested_by,
        commit=head,
    )
    try:
        cat = load_catalogue()
        subjects = cat.subjects_in(tier or None, track or None)
        only = set(names)
        ctx: dict[str, Any] = {
            "run_apps": set(apps),
            "run_vitest": set(vitest_files),
            "run_playwright": set(playwright_files),
        }
        drafts = run_collectors(cat, subjects, only=only, ctx=ctx)
        n = persist(drafts, head, runner=f"ui:{requested_by}")
        if write_snapshot:
            from .evaluator import evaluate
            from .gauge import load_events, load_exemptions

            reports = evaluate(
                cat, load_events(tier or None), load_exemptions(),
                head=head, tier=tier or None, track=track or None,
            )
            write_snapshots(reports, head)
        run.event_count = n
        run.status = RunStatus.SUCCEEDED
        run.detail = {"collected": n, "write_snapshot": write_snapshot}
        run.finished_at = timezone.now()
        run.save(update_fields=["event_count", "status", "detail", "finished_at"])
    except Exception as exc:  # noqa: BLE001
        run.status = RunStatus.FAILED
        run.detail = {"error": f"{type(exc).__name__}: {exc}"}
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "detail", "finished_at"])
    return run


def run_as_dict(run: Run, *, include_ladder: bool = False) -> dict[str, Any]:
    body = {
        "id": run.pk,
        "collectors": list(run.collectors or []),
        "tier": run.tier,
        "track": run.track,
        "run_apps": list(run.run_apps or []),
        "status": run.status,
        "requested_by": run.requested_by,
        "commit": run.commit,
        "event_count": run.event_count,
        "detail": run.detail,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }
    if include_ladder and run.status == RunStatus.SUCCEEDED:
        from .api import build_ladder

        body["ladder"] = build_ladder(run.tier or None, run.track or None)
    return body
