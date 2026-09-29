"""Rank-5 probes for platform.module.inbound.

A missing workflow, series file, GitHub run, password, or live batch is
``unknown``. Reading YAML or a file's mtime is not a pass. Evidence class
``enforcement-verified`` is used only after git, ``gh``, HTTP, or the named
pytest nodes were actually checked. This module does not start or stop the
stack. Playwright runs only for the Arabic People-door spec when the gauge
``--run`` names that file. The nightly journey is never launched from here.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from .catalogue import REPO_ROOT, Catalogue, Check, Subject
from .collectors import EventDraft, _draft, _unknown

_EVIDENCE = "enforcement-verified"
_COUNTS = ("insert", "update", "skip", "reject")


def collect_inbound_operated(
    cat: Catalogue, pairs: list[tuple[Check, Subject]], ctx: dict[str, Any],
) -> list[EventDraft]:
    out: list[EventDraft] = []
    for check, subject in pairs:
        kind = str(check.probe.get("type") or "")
        handler = _HANDLERS.get(kind)
        if handler is None:
            out.append(_unknown(check, subject, f"inbound_operated has no probe {kind!r}"))
            continue
        out.append(handler(check, subject, ctx))
    return out


def _spec_same_merge(check: Check, subject: Subject, ctx: dict[str, Any]) -> EventDraft:
    probe = check.probe
    base = _base(ctx)
    code, names = _git_names(ctx, base)
    if code != 0 or names is None:
        return _unknown(check, subject, "git diff failed")
    code_roots = [str(p) for p in (probe.get("code") or [])]
    docs = [str(p) for p in (probe.get("paths") or [])]
    touched = [p for p in names if _under(p, code_roots)]
    if not touched:
        return _draft(
            check, subject, "passed", _EVIDENCE, source=f"git diff {base}...HEAD",
            detail={"base": base, "no_code_diff": True},
        )
    docs_hit = [p for p in names if p in docs]
    if docs_hit:
        return _draft(
            check, subject, "passed", _EVIDENCE, source=f"git diff {base}...HEAD",
            detail={"base": base, "code": touched, "docs": docs_hit},
        )
    return _draft(
        check, subject, "failed", _EVIDENCE, source=f"git diff {base}...HEAD",
        detail={"base": base, "code": touched, "why": "inbound code changed without the studio contract"},
    )


def _journey(check: Check, subject: Subject, ctx: dict[str, Any]) -> EventDraft:
    """Scheduled nightly only. The local Playwright command is never run."""
    probe = check.probe
    workflow = str(probe.get("workflow") or "")
    path = _abs(workflow)
    if not path.is_file():
        return _unknown(check, subject, f"missing {workflow}")
    text = path.read_text(encoding="utf-8")
    if str(probe.get("hosted_github") or "") == "reject" and "ubuntu-latest" in text:
        return _draft(
            check, subject, "failed", _EVIDENCE, source=workflow,
            detail={"why": "ubuntu-latest cannot host this nightly"},
        )
    cron = str(probe.get("cron") or "")
    if cron and cron not in text:
        return _draft(check, subject, "failed", _EVIDENCE, source=workflow, detail={"why": "cron mismatch"})
    command = str(probe.get("command") or "")
    if command and command not in text:
        return _draft(check, subject, "failed", _EVIDENCE, source=workflow, detail={"why": "command mismatch"})
    for banned in probe.get("forbid_in_workflow") or []:
        if str(banned) and str(banned) in text:
            return _draft(
                check, subject, "failed", _EVIDENCE, source=workflow,
                detail={"why": f"workflow contains {banned}"},
            )
    runs = _gh_runs(ctx, workflow)
    if runs is None:
        return _unknown(check, subject, "gh run list failed")
    head = _head(ctx)
    matched = [
        row for row in runs
        if row.get("event") == "schedule" and row.get("conclusion") == "success" and row.get("headSha") == head
    ]
    failed = [
        row for row in runs
        if row.get("event") == "schedule" and row.get("headSha") == head and row.get("conclusion") not in ("success", None, "")
    ]
    if matched:
        return _draft(
            check, subject, "passed", _EVIDENCE, source="gh run list",
            detail={"workflow": workflow, "head": head},
        )
    if failed:
        return _draft(
            check, subject, "failed", _EVIDENCE, source="gh run list",
            detail={"workflow": workflow, "head": head, "conclusion": failed[0].get("conclusion")},
        )
    return _unknown(check, subject, "no scheduled success for this commit")


def _ci_node(check: Check, subject: Subject, ctx: dict[str, Any]) -> EventDraft:
    probe = check.probe
    workflow = str(probe.get("workflow") or "")
    if not _abs(workflow).is_file():
        return _unknown(check, subject, f"missing {workflow}")
    script = _step_run(_abs(workflow), str(probe.get("step") or ""))
    want = str(probe.get("pytest") or "python -m pytest")
    if script is None or want not in script:
        return _draft(
            check, subject, "failed", _EVIDENCE, source=workflow,
            detail={"why": f"step does not run {want}"},
        )
    banned = str(probe.get("forbid_ignore") or "")
    if banned and _ignores(script, banned):
        return _draft(
            check, subject, "failed", _EVIDENCE, source=workflow,
            detail={"why": f"pytest ignores {banned}"},
        )
    missing_nodes = [node for node in (probe.get("nodes") or []) if not _node_present(str(node))]
    if missing_nodes:
        return _draft(
            check, subject, "failed", _EVIDENCE, source=workflow,
            detail={"why": "named node is not in the suite", "missing": missing_nodes},
        )
    runs = _gh_runs(ctx, workflow, sha=_head(ctx))
    if runs is None:
        return _unknown(check, subject, "gh run list failed")
    if not runs:
        return _unknown(check, subject, "no ci run for this commit")
    conclusion = str(runs[0].get("conclusion") or "")
    if conclusion != str(probe.get("conclusion") or "success"):
        return _draft(
            check, subject, "failed", _EVIDENCE, source="gh run list",
            detail={"conclusion": conclusion},
        )
    return _draft(
        check, subject, "passed", _EVIDENCE, source="gh run list",
        detail={"conclusion": conclusion, "pytest": want},
    )


def _scheduled(check: Check, subject: Subject, ctx: dict[str, Any]) -> EventDraft:
    probe = check.probe
    workflow = str(probe.get("workflow") or "")
    if not _abs(workflow).is_file():
        return _unknown(check, subject, f"missing {workflow}")
    runs = _gh_runs(ctx, workflow)
    if runs is None:
        return _unknown(check, subject, "gh run list failed")
    want = str(probe.get("conclusion") or "success")
    event = str(probe.get("event") or "schedule")
    good = [row for row in runs if row.get("event") == event and row.get("conclusion") == want]
    need = int(probe.get("runs") or 1)
    if len(good) >= need:
        return _draft(
            check, subject, "passed", _EVIDENCE, source="gh run list",
            detail={"runs": len(good)},
        )
    bad = [row for row in runs if row.get("event") == event and row.get("conclusion") not in (want, None, "")]
    if bad and not good:
        return _draft(
            check, subject, "failed", _EVIDENCE, source="gh run list",
            detail={"conclusion": bad[0].get("conclusion")},
        )
    return _unknown(check, subject, "no scheduled success")


def _sample_cap(check: Check, subject: Subject, ctx: dict[str, Any]) -> EventDraft:
    probe = check.probe
    path = str(probe.get("path") or "")
    if "health" in path.lower():
        return _draft(
            check, subject, "failed", _EVIDENCE, source=path,
            detail={"why": "health latency is not the inbound benchmark"},
        )
    password = _password(ctx, probe.get("password_env") or [])
    if not password:
        return _unknown(check, subject, "password env is unset")
    origin = _origin(ctx, probe)
    token, why = _login(ctx, origin, str(probe.get("username") or ""), password)
    if token is None:
        return _unknown(check, subject, why or "login unavailable")
    listed, why = _get_json(ctx, origin + str(probe.get("list_path") or ""), token)
    if listed is None:
        return _unknown(check, subject, why or "batch list unavailable")
    rows = listed.get("results") if isinstance(listed, dict) else listed
    if not isinstance(rows, list):
        return _unknown(check, subject, "batch list has no results")
    allowed = {str(s) for s in (probe.get("status") or [])}
    chosen = [
        row for row in rows
        if isinstance(row, dict) and str(row.get("status") or "") in allowed and row.get("id") is not None
    ]
    if not chosen:
        return _unknown(check, subject, "no smoked or committed batch")
    batch_id = max(int(row["id"]) for row in chosen)
    detail_path = path.replace("{id}", str(batch_id))
    body, why = _get_json(ctx, origin + detail_path, token)
    if body is None or not isinstance(body, dict):
        return _unknown(check, subject, why or "batch read unavailable")
    sample = body.get("sample")
    row_count = body.get("row_count")
    target = str(body.get("target_key") or "")
    limit = int(probe.get("max_sample") or 20)
    ok = (
        isinstance(sample, list)
        and len(sample) <= limit
        and type(row_count) is int
        and bool(target)
    )
    return _draft(
        check, subject, "passed" if ok else "failed", _EVIDENCE, source=detail_path,
        detail={"batch_id": batch_id, "sample_len": len(sample) if isinstance(sample, list) else None, "max_sample": limit},
    )


def _rtl(check: Check, subject: Subject, ctx: dict[str, Any]) -> EventDraft:
    probe = check.probe
    spec = str(probe.get("spec") or "")
    requested = bool(spec) and spec in set(ctx.get("run_playwright") or ())
    runner = ctx.get("inbound_cmd")
    observed = ctx.get("inbound_rtl")
    if not requested and not isinstance(observed, dict):
        if runner is not None and int(runner(str(probe.get("script") or ""))) != 0:
            return _draft(
                check, subject, "failed", _EVIDENCE, source=str(probe.get("script") or ""),
                detail={"exit": "i18n"},
            )
        return _unknown(check, subject, "i18n:check alone does not pass; RTL was not observed")
    if runner is not None:
        code = int(runner(str(probe.get("script") or "")))
    elif requested:
        code = _command_exit(ctx, str(probe.get("script") or ""), cwd=REPO_ROOT / "carbon-frontend")
    else:
        code = 0
    if code != 0:
        return _draft(check, subject, "failed", _EVIDENCE, source=str(probe.get("script") or ""), detail={"exit": code})
    if requested:
        if not (REPO_ROOT / spec).is_file():
            return _unknown(check, subject, f"missing {spec}")
        spec_code = _spec_exit(ctx, spec)
        if spec_code != 0:
            return _draft(check, subject, "failed", _EVIDENCE, source=spec, detail={"exit": spec_code})
        return _draft(check, subject, "passed", _EVIDENCE, source=spec, detail={"dir": probe.get("dir")})
    if not isinstance(observed, dict):
        return _unknown(check, subject, "i18n:check alone does not pass")
    expect = {
        "dir": probe.get("dir"),
        "eye_name": probe.get("eye_name"),
        "primary_name": probe.get("primary_name"),
        "search_placeholder": probe.get("search_placeholder"),
    }
    missing = [key for key, value in expect.items() if observed.get(key) != value]
    if missing:
        return _draft(
            check, subject, "failed", _EVIDENCE, source=str(probe.get("path") or ""),
            detail={"missing": missing},
        )
    return _draft(
        check, subject, "passed", _EVIDENCE, source=str(probe.get("path") or ""),
        detail={"dir": observed.get("dir")},
    )


def _spec_exit(ctx: dict[str, Any], spec: str) -> int:
    if "inbound_spec_exit" in ctx:
        return int(ctx["inbound_spec_exit"])
    rel = spec[len("carbon-frontend/"):] if spec.startswith("carbon-frontend/") else spec
    return _argv_exit(
        ctx,
        ["npx", "playwright", "test", rel, "--config", "e2e/playwright.config.ts"],
        REPO_ROOT / "carbon-frontend",
        ci=True,
    )


def _command_exit(ctx: dict[str, Any], command: str, cwd: Path) -> int:
    return _argv_exit(ctx, command.split(), cwd, ci=False)


def _argv_exit(ctx: dict[str, Any], argv: list[str], cwd: Path, *, ci: bool) -> int:
    env = os.environ.copy()
    if ci:
        env["CI"] = "1"
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=180, check=False, env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 1
    return int(proc.returncode)


def _ratchet(check: Check, subject: Subject, ctx: dict[str, Any]) -> EventDraft:
    probe = check.probe
    workflow = str(probe.get("workflow") or "")
    if not _abs(workflow).is_file():
        return _unknown(check, subject, f"missing {workflow}")
    script = _step_run(_abs(workflow), str(probe.get("step") or ""))
    if script is None:
        return _draft(
            check, subject, "failed", _EVIDENCE, source=workflow,
            detail={"why": "ratchet step is not in the workflow"},
        )
    needles = [str(item) for item in (probe.get("substrings") or []) if str(item)]
    if not needles:
        return _unknown(check, subject, "match rule not declared")
    missing = [item for item in needles if item not in script]
    if missing:
        return _draft(
            check, subject, "failed", _EVIDENCE, source=workflow,
            detail={"why": "ratchet substrings missing", "missing": missing},
        )
    runs = _gh_runs(ctx, workflow, sha=_head(ctx))
    if runs is None:
        return _unknown(check, subject, "gh run list failed")
    if not runs:
        return _unknown(check, subject, "no ci run for this commit")
    conclusion = str(runs[0].get("conclusion") or "")
    if conclusion != "success":
        return _draft(
            check, subject, "failed", _EVIDENCE, source="gh run list",
            detail={"conclusion": conclusion},
        )
    return _draft(check, subject, "passed", _EVIDENCE, source="gh run list", detail={"conclusion": conclusion})


def _series(check: Check, subject: Subject, ctx: dict[str, Any]) -> EventDraft:
    probe = check.probe
    rel = str(probe.get("file") or "")
    path = _abs(rel)
    if not path.is_file():
        return _unknown(check, subject, f"missing {rel}")
    if str(probe.get("commit_file") or "") == "reject" and _series_tracked(ctx, path):
        return _draft(
            check, subject, "failed", _EVIDENCE, source=rel,
            detail={"why": "series file is tracked by git"},
        )
    if ctx.get("no_db") and "inbound_batches" not in ctx:
        return _unknown(check, subject, "no-db cannot match InboundBatch.smoke")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _draft(check, subject, "failed", _EVIDENCE, source=rel, detail={"why": "series is not json"})
    if not isinstance(payload, dict) or payload.get("schema") != probe.get("schema"):
        return _draft(check, subject, "failed", _EVIDENCE, source=rel, detail={"why": "schema mismatch"})
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        return _draft(check, subject, "failed", _EVIDENCE, source=rel, detail={"why": "series has no rows"})
    batches = ctx.get("inbound_batches")
    if batches is None:
        batches = _load_smoke()
    if not isinstance(batches, dict):
        return _unknown(check, subject, "cannot match InboundBatch.smoke")
    days = int(probe.get("days") or 14)
    cutoff = date.today() - timedelta(days=days)
    for row in rows:
        if not isinstance(row, dict):
            return _draft(check, subject, "failed", _EVIDENCE, source=rel, detail={"why": "row is not an object"})
        env = batches.get(row.get("batch_id"))
        smoke = (env or {}).get("smoke") if isinstance(env, dict) else None
        if not isinstance(smoke, dict):
            return _draft(
                check, subject, "failed", _EVIDENCE, source=rel,
                detail={"why": "row does not match a stored envelope", "batch_id": row.get("batch_id")},
            )
        for key in _COUNTS:
            if int(row.get(key) or 0) != int(smoke.get(key) or 0):
                return _draft(
                    check, subject, "failed", _EVIDENCE, source=rel,
                    detail={"why": f"{key} does not match InboundBatch.smoke", "batch_id": row.get("batch_id")},
                )
        try:
            when = date.fromisoformat(str(row.get("date") or ""))
        except ValueError:
            return _draft(check, subject, "failed", _EVIDENCE, source=rel, detail={"why": "row date is invalid"})
        if when < cutoff:
            return _draft(check, subject, "failed", _EVIDENCE, source=rel, detail={"why": f"older than {days} days"})
    return _draft(check, subject, "passed", _EVIDENCE, source=rel, detail={"rows": len(rows)})


def _base(ctx: dict[str, Any]) -> str:
    env = _environ(ctx)
    return str(env.get("GITHUB_BASE_SHA") or "HEAD~1")


def _head(ctx: dict[str, Any]) -> str:
    pinned = ctx.get("head")
    if pinned:
        return str(pinned)
    code, out = _git(["rev-parse", "HEAD"], ctx)
    return out.strip() if code == 0 else ""


def _environ(ctx: dict[str, Any]) -> Any:
    return ctx.get("inbound_environ", os.environ)


def _password(ctx: dict[str, Any], names: Any) -> str:
    env = _environ(ctx)
    for name in names:
        value = env.get(str(name)) if hasattr(env, "get") else ""
        if value:
            return str(value)
    return ""


def _origin(ctx: dict[str, Any], probe: dict[str, Any]) -> str:
    env = _environ(ctx)
    key = str(probe.get("origin_env") or "")
    value = env.get(key) if key and hasattr(env, "get") else ""
    return str(value or probe.get("origin_default") or "").rstrip("/")


def _git(args: list[str], ctx: dict[str, Any]) -> tuple[int, str]:
    fn = ctx.get("inbound_git")
    if fn is not None:
        code, out = fn(args)
        return int(code), str(out)
    try:
        proc = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
    except OSError as exc:
        return 127, str(exc)
    return proc.returncode, proc.stdout


def _git_names(ctx: dict[str, Any], base: str) -> tuple[int, list[str] | None]:
    code, out = _git(["diff", "--name-only", f"{base}...HEAD"], ctx)
    if code != 0:
        return code, None
    return 0, [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]


def _gh(args: list[str], ctx: dict[str, Any]) -> tuple[int, str]:
    fn = ctx.get("inbound_gh")
    if fn is not None:
        code, out = fn(args)
        return int(code), str(out)
    try:
        proc = subprocess.run(
            ["gh", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
    except OSError as exc:
        return 127, str(exc)
    return proc.returncode, proc.stdout


def _gh_runs(ctx: dict[str, Any], workflow: str, sha: str | None = None) -> list[dict[str, Any]] | None:
    args = [
        "run", "list", "--workflow", Path(workflow).name,
        "--json", "conclusion,headSha,event,databaseId", "--limit", "20",
    ]
    if sha:
        args.extend(["--commit", sha])
    code, out = _gh(args, ctx)
    if code != 0:
        return None
    try:
        rows = json.loads(out or "[]")
    except json.JSONDecodeError:
        return None
    return rows if isinstance(rows, list) else None


def _step_run(path: Path, step_name: str) -> str | None:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    jobs = raw.get("jobs") if isinstance(raw, dict) else None
    if not isinstance(jobs, dict):
        return None
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if isinstance(step, dict) and step.get("name") == step_name:
                run = step.get("run")
                return str(run) if run else ""
    return None


def _ignores(script: str, token: str) -> bool:
    return "--ignore" in script and token in script


def _node_present(node: str) -> bool:
    path, _, name = node.partition("::")
    file = REPO_ROOT / "backend" / path
    if not name or not file.is_file():
        return False
    return f"def {name}" in file.read_text(encoding="utf-8")


def _abs(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / path


def _under(path: str, roots: list[str]) -> bool:
    for root in roots:
        root = root.strip("/")
        if path == root or path.startswith(root + "/"):
            return True
    return False


def _login(ctx: dict[str, Any], origin: str, username: str, password: str) -> tuple[str | None, str]:
    status, body = _http(ctx, "POST", origin + "/carbon-api/token/", None, {"username": username, "password": password})
    if status == 0:
        return None, "origin unreachable"
    if status != 200 or not isinstance(body, dict) or not body.get("access"):
        return None, f"login status {status}"
    return str(body["access"]), ""


def _get_json(ctx: dict[str, Any], url: str, token: str) -> tuple[Any, str]:
    status, body = _http(ctx, "GET", url, token, None)
    if status == 0:
        return None, "origin unreachable"
    if status != 200:
        return None, f"status {status}"
    return body, ""


def _http(
    ctx: dict[str, Any], method: str, url: str, token: str | None, payload: dict | None,
) -> tuple[int, Any]:
    fn = ctx.get("inbound_http")
    if fn is not None:
        return fn(method, url, token, payload)
    return _urllib_json(method, url, token, payload)


def _urllib_json(method: str, url: str, token: str | None, payload: dict | None) -> tuple[int, Any]:
    import urllib.error
    import urllib.request

    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return int(resp.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return int(exc.code), {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return 0, {}


def _load_smoke() -> dict[int, dict[str, Any]] | None:
    try:
        import django

        if not django.apps.apps.ready:
            return None
        from inbound.models import InboundBatch

        rows = list(InboundBatch.objects.all())
    except Exception:
        return None
    return {row.id: {"smoke": row.smoke or {}} for row in rows}


def _series_tracked(ctx: dict[str, Any], path: Path) -> bool:
    if "inbound_tracked" in ctx:
        return bool(ctx["inbound_tracked"])
    try:
        rel = str(path.relative_to(REPO_ROOT))
    except ValueError:
        return False
    code, _out = _git(["ls-files", "--error-unmatch", "--", rel], ctx)
    return code == 0


_HANDLERS = {
    "spec_same_merge": _spec_same_merge,
    "workflow_journey_green": _journey,
    "ci_node_red": _ci_node,
    "scheduled_run_green": _scheduled,
    "live_sample_cap": _sample_cap,
    "rtl_i18n_a11y": _rtl,
    "ratchet_gate": _ratchet,
    "smoke_series_fresh": _series,
}
