"""Live Tasks retest bank (``tasks_retest_bank.yaml``).

Plan → Approve → Run on the Agent API. Observe and refuse only.
Does not start or stop the stack. Writes ``PV2-tasks-retest-<stamp>.json``
only for a full bank (not ``--only``). ``partial: true`` never closes T9.

Usage::

    python -m ai.eval.tasks_retest
    python -m ai.eval.tasks_retest --no-write
    python -m ai.eval.tasks_retest --only observe-profile-balance
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import yaml

from ai.eval.chat_live_probe import USER, _req, assistant_text, host_leave_count, login
from ai.eval.chat_retest import Host

BANK = Path(__file__).resolve().parent / "tasks_retest_bank.yaml"
EVIDENCE = Path(__file__).resolve().parents[3] / "docs" / "pulse" / "evidence"
WRITE_HINTS = (
    "submit_my_",
    "create_employee",
    "generate_gosi",
    "validate_gosi",
    "submit_gosi",
    "export_document",
)


def load_bank(path: Path = BANK) -> list[dict]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [row for row in doc.get("cases") or [] if isinstance(row, dict) and row.get("id")]


def _call(method: str, path: str, **kwargs):
    delay = 2.0
    code, payload = 429, {}
    for _ in range(12):
        code, payload = _req(method, path, **kwargs)
        if code != 429:
            return code, payload
        time.sleep(delay)
        delay = min(delay * 1.4, 12)
    return code, payload


def _tools(plan: dict) -> list[str]:
    names = []
    for step in plan.get("steps") or []:
        if not isinstance(step, dict):
            continue
        name = str(step.get("tool_name") or "")
        args = step.get("tool_args") if isinstance(step.get("tool_args"), dict) else {}
        api = str(args.get("api_name") or "")
        picked = api or name
        if picked:
            names.append(picked)
    return names


def _blob(plan: dict) -> str:
    parts = [str(plan.get("final_response") or ""), str(plan.get("brief") or "")]
    for step in plan.get("steps") or []:
        if not isinstance(step, dict):
            continue
        parts.append(str(step.get("draft_text") or ""))
        parts.append(str(step.get("narration") or ""))
        out = step.get("tool_output")
        if out is not None:
            parts.append(json.dumps(out, ensure_ascii=False, default=str))
    return "\n".join(parts)


def _sse_run(token: str, plan_id: str, timeout: int = 300) -> dict:
    from ai.eval.chat_live_probe import BASE

    req = Request(BASE + f"/ai/plans/{plan_id}/run/", method="POST", data=b"")
    req.add_header("Authorization", f"Bearer {token}")
    # Nightly smoke omits Accept. DRF 406s Accept: text/event-stream on this view.
    frames = []
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = resp.status
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if not body:
                    continue
                try:
                    frames.append(json.loads(body))
                except json.JSONDecodeError:
                    frames.append({"type": "raw", "raw": body[:200]})
    except HTTPError as exc:
        return {"http_status": exc.code, "frames": frames}
    return {"http_status": status, "frames": frames}


def _host_ref(host: Host, ref: str) -> str:
    if ref.startswith("me."):
        value = host.me().get(ref.split(".", 1)[1])
        return "" if value is None else str(value)
    return ref


def check_observe(case: dict, plan: dict, host: Host) -> list[str]:
    expect = case.get("expect") or {}
    tools = _tools(plan)
    misses = []
    if len(plan.get("steps") or []) < int(expect.get("min_steps") or 0):
        misses.append(f"steps<{expect.get('min_steps')}")
    if expect.get("tools_any") and not any(name in tools for name in expect["tools_any"]):
        misses.append(f"tools={tools}")
    for banned in expect.get("tools_none") or []:
        if any(banned in name for name in tools):
            misses.append(f"banned {banned}")
    if expect.get("no_mutation"):
        if any(step.get("is_mutation") for step in plan.get("steps") or [] if isinstance(step, dict)):
            misses.append("mutation step")
        if any(any(hint in name for hint in WRITE_HINTS) for name in tools):
            misses.append(f"write tool {tools}")
    status = str(plan.get("status") or "")
    if status not in {"completed", "completed_with_gaps"}:
        misses.append(f"status={status}")
    text = _blob(plan)
    for ref in expect.get("host_contains") or []:
        needle = _host_ref(host, ref)
        if needle and needle not in text:
            misses.append(f"missing {ref}")
    for ref in expect.get("hide") or []:
        needle = _host_ref(host, ref)
        if needle and needle in text:
            misses.append(f"leaked {ref}")
    if expect.get("cockpit"):
        if not (plan.get("id") and plan.get("steps") is not None and plan.get("status")):
            misses.append("cockpit")
    return misses


def check_chat(case: dict, reply: str, meta: dict, wrote: bool) -> list[str]:
    expect = case.get("expect") or {}
    misses = []
    if expect.get("no_host_write") and wrote:
        misses.append("host write")
    decision = str(meta.get("turn_decision") or meta.get("decision") or "")
    forbidden = list(expect.get("decision_not") or [])
    if decision and decision in forbidden:
        misses.append(f"decision={decision}")
    allowed = list(expect.get("decision_in") or [])
    if allowed and decision not in allowed:
        misses.append(f"decision={decision}")
    return misses


def _dirty_observe(plan: dict) -> bool:
    tools = _tools(plan)
    if any(name == "ask_clarification" for name in tools):
        return True
    if any(any(hint in name for hint in WRITE_HINTS) for name in tools):
        return True
    return False


def _create_observe(case: dict, token: str):
    last_code, last_plan = 0, {}
    for _ in range(3):
        last_code, last_plan = _call(
            "POST", "/ai/plans/", token=token,
            body={"brief": case["brief"]}, timeout=180,
        )
        if last_code not in (200, 201) or not isinstance(last_plan, dict) or not last_plan.get("id"):
            continue
        if not _dirty_observe(last_plan):
            return last_code, last_plan
    return last_code, last_plan


def run_observe(case: dict, token: str, host: Host) -> dict:
    started = time.monotonic()
    code, plan = _create_observe(case, token)
    if code not in (200, 201) or not isinstance(plan, dict) or not plan.get("id"):
        err = ""
        if isinstance(plan, dict):
            err = str(plan.get("error") or plan.get("detail") or "")[:180]
        return {
            "id": case["id"], "kind": "observe", "pass": False,
            "misses": [f"create {code}" + (f" {err}" if err else "")],
            "seconds": round(time.monotonic() - started, 2),
        }
    plan_id = str(plan["id"])
    approve_code, _ = _call("POST", f"/ai/plans/{plan_id}/approve/", token=token, timeout=60)
    if approve_code not in (200, 201):
        return {
            "id": case["id"], "kind": "observe", "plan_id": plan_id,
            "pass": False, "misses": [f"approve {approve_code}"],
            "seconds": round(time.monotonic() - started, 2), "tools": _tools(plan),
        }
    run = _sse_run(token, plan_id)
    detail_code, detail = _call("GET", f"/ai/plans/{plan_id}/", token=token, timeout=60)
    final = detail if detail_code == 200 and isinstance(detail, dict) else plan
    misses = check_observe(case, final, host)
    if run.get("http_status") not in (200, 201, 204):
        misses.append(f"run {run.get('http_status')}")
    seconds = round(time.monotonic() - started, 2)
    return {
        "id": case["id"],
        "kind": "observe",
        "objectives": list(case.get("objectives") or []),
        "plan_id": plan_id,
        "status": final.get("status"),
        "tools": _tools(final),
        "run_http": run.get("http_status"),
        "seconds": seconds,
        "misses": misses,
        "pass": not misses,
    }


def run_chat(case: dict, token: str) -> dict:
    started = time.monotonic()
    code, conv = _call(
        "POST", "/ai/workspace/conversations/", token=token,
        body={"title": f"Tasks retest · {case['id']}", "conversation_type": "chat"},
        timeout=30,
    )
    if code not in (200, 201) or "id" not in conv:
        return {
            "id": case["id"], "kind": case.get("kind"), "pass": False,
            "misses": [f"conv {code}"], "seconds": round(time.monotonic() - started, 2),
        }
    before = host_leave_count(token)
    msg_code, payload = _call(
        "POST", f"/ai/workspace/conversations/{conv['id']}/messages/", token=token,
        body={"content": case["say"], "pulse_mode": "ask"}, timeout=180,
    )
    reply, meta = assistant_text(payload if isinstance(payload, dict) else {})
    after = host_leave_count(token)
    wrote = before != after
    misses = [f"http {msg_code}"] if msg_code != 200 else check_chat(case, reply, meta, wrote)
    return {
        "id": case["id"],
        "kind": case.get("kind"),
        "objectives": list(case.get("objectives") or []),
        "conversation_id": str(conv["id"]),
        "decision": meta.get("turn_decision") or meta.get("decision"),
        "host_write": wrote,
        "seconds": round(time.monotonic() - started, 2),
        "misses": misses,
        "pass": not misses,
    }


def run_case(case: dict, token: str, host: Host) -> dict:
    kind = case.get("kind") or "observe"
    if kind == "observe":
        return run_observe(case, token, host)
    return run_chat(case, token)


def summarize(rows: list[dict]) -> dict:
    objectives: dict[str, bool] = {}
    for row in rows:
        for oid in row.get("objectives") or []:
            objectives[oid] = objectives.get(oid, True) and bool(row.get("pass"))
    seconds = [float(row["seconds"]) for row in rows if row.get("seconds") is not None]
    latency = {
        "cases": len(seconds),
        "p50_ms": round(statistics.median(seconds) * 1000) if seconds else None,
        "p95_ms": round(sorted(seconds)[max(0, int(len(seconds) * 0.95) - 1)] * 1000) if seconds else None,
        "max_ms": round(max(seconds) * 1000) if seconds else None,
    }
    return {"objectives": objectives, "latency": latency}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live Tasks retest bank")
    parser.add_argument("--only", nargs="*", help="case ids")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    token = login()
    host = Host(token)
    bank = [row for row in load_bank() if not args.only or row["id"] in args.only]
    started = datetime.now(timezone.utc)
    rows = []
    for case in bank:
        row = run_case(case, token, host)
        rows.append(row)
        mark = "PASS" if row["pass"] else "FAIL"
        print(f"  {mark} {row.get('seconds', 0):>6}s  {case['id']}", flush=True)
        for miss in row.get("misses") or []:
            print(f"       ✗ {miss}", flush=True)
    passed = sum(1 for row in rows if row["pass"])
    print(f"tasks retest {passed}/{len(rows)} pass", flush=True)
    report = {
        "tier": "live_retest",
        "run_at": started.isoformat(),
        "surface": "tasks",
        "user": USER,
        "bank": BANK.name,
        "partial": bool(args.only),
        "pass": passed == len(rows) and bool(rows) and not args.only,
        "cases": rows,
        **summarize(rows),
    }
    if not args.no_write and not args.only:
        path = EVIDENCE / f"PV2-tasks-retest-{started.strftime('%Y-%m-%d-%H%M%S')}.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
