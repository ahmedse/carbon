"""Live Chat retest bank runner (``chat_retest_bank.yaml``).

One dated run: each thread in a fresh Chat conversation (pulse_mode=ask),
checked against host values read at run time. Writes
``docs/pulse/evidence/PV2-chat-retest-<stamp>.json``. ``chat_deep_bench``
closes an operator finding only after three runs pass every thread naming it.

Does not start or stop the stack. Chat never writes the host; the bank
checks that too.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ai.eval.chat_live_probe import USER, _req, assistant_text, host_leave_count, login

BANK = Path(__file__).resolve().parent / "chat_retest_bank.yaml"
EVIDENCE = Path(__file__).resolve().parents[3] / "docs" / "pulse" / "evidence"
RETEST_GLOB = "PV2-chat-retest-*.json"

_ARABIC = re.compile(r"[\u0600-\u06FF]")
_LATIN = re.compile(r"[A-Za-z]")
_INT = re.compile(r"(?<![\w.])\d+(?!\w|\.\d)")
_LATENCY_BUDGET_MS = 4000


def load_bank(path: Path = BANK) -> list[dict]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [t for t in doc.get("threads") or [] if isinstance(t, dict)]


# ── Host oracles ────────────────────────────────────────────────────────────


class Host:
    """Host values for the caller, read once per run."""

    def __init__(self, token: str):
        self.token = token
        self._cache: dict[str, Any] = {}

    def _get(self, path: str) -> Any:
        status, data = _req("GET", path, token=self.token, timeout=60)
        if status != 200:
            raise RuntimeError(f"host oracle {path} → {status}")
        return data

    def me(self) -> dict:
        if "me" not in self._cache:
            self._cache["me"] = self._get("/people/me/")
        return self._cache["me"]

    def employee(self, employee_no: str) -> dict:
        key = f"emp:{employee_no}"
        if key not in self._cache:
            page = self._get(f"/people/employees/?q={employee_no}&page_size=50")
            rows = [r for r in page.get("results") or [] if str(r.get("employee_no")) == employee_no]
            if len(rows) != 1:
                raise RuntimeError(f"host oracle: employee_no {employee_no} matched {len(rows)} rows")
            self._cache[key] = self._get(f"/people/employees/{rows[0]['id']}/")
        return self._cache[key]

    def count(self, spec: str) -> int:
        key = f"count:{spec}"
        if key in self._cache:
            return self._cache[key]
        if spec == "active":
            value = int(self._get("/people/employees/?is_active=true&page_size=1")["count"])
        elif spec.startswith("active_prefix:"):
            prefix = spec.split(":", 1)[1]
            value, page = 0, 1
            while True:
                data = self._get(f"/people/employees/?is_active=true&q={prefix}&page_size=200&page={page}")
                rows = data.get("results") or []
                value += sum(1 for r in rows if str(r.get("full_name") or "").startswith(prefix))
                if page * 200 >= int(data.get("count") or 0) or not rows:
                    break
                page += 1
        else:
            raise ValueError(f"unknown count ref {spec!r}")
        self._cache[key] = value
        return value

    def resolve(self, ref: str) -> Any:
        """A ref's value: ``me.x``, ``emp:<no>.x``, ``count:...``, or a quoted literal."""
        if ref.startswith("count:"):
            return self.count(ref.split(":", 1)[1])
        if ref.startswith("me."):
            return _field(self.me(), ref[3:])
        if ref.startswith("emp:"):
            head, _, field = ref[4:].partition(".")
            return _field(self.employee(head), field)
        return ref

    def obj(self, ref: str) -> Any:
        if ref == "me":
            return self.me()
        if ref.startswith("emp:"):
            return self.employee(ref[4:])
        raise ValueError(f"unknown object ref {ref!r}")


def _field(row: dict, name: str) -> Any:
    value = row.get(name)
    if isinstance(value, dict):
        return value.get("name") or value.get("label") or value.get("code")
    return value


# ── Checks ──────────────────────────────────────────────────────────────────


def _degradation_sentences() -> list[str]:
    from ai.engine.cognition.turn.degradation import Degradation, sentence

    out = []
    for stage, cause in (("write", "invalid_output"), ("understand", "x"), ("act", "record_mismatch")):
        for lang in ("en", "ar"):
            out.append(sentence(Degradation(stage, cause), lang))
    return out


def _mostly_arabic(text: str) -> bool:
    ar = len(_ARABIC.findall(text or ""))
    latin = len(_LATIN.findall(text or ""))
    return ar > 0 and ar >= latin


def _first_int(text: str) -> int | None:
    found = _INT.findall((text or "").replace(",", ""))
    return int(found[0]) if found else None


def check_turn(spec: dict, reply: str, meta: dict, host: Host) -> list[str]:
    """Failed check descriptions for one turn. Empty when the turn passed."""
    from ai.engine.cognition.turn.grounding import ungrounded_numbers

    misses: list[str] = []
    text = reply or ""
    for ref in spec.get("contains") or []:
        value = host.resolve(ref)
        if value in (None, "") or str(value) not in text:
            misses.append(f"contains {ref}={value!r}")
    for ref in spec.get("excludes") or []:
        value = host.resolve(ref)
        if value not in (None, "") and str(value) in text:
            misses.append(f"excludes {ref}={value!r}")
    if spec.get("says_any"):
        folded = text.casefold()
        if not any(str(s).casefold() in folded for s in spec["says_any"]):
            misses.append(f"says_any {spec['says_any']}")
    if spec.get("decision_not"):
        decided = str((meta.get("turn_meter") or {}).get("turn_decision") or "")
        if decided in spec["decision_not"]:
            misses.append(f"decision_not {spec['decision_not']} got={decided}")
    if spec.get("int_equals"):
        want = host.resolve(spec["int_equals"])
        got = _first_int(text)
        if got != want:
            misses.append(f"int_equals {spec['int_equals']}={want} got={got}")
    if spec.get("int_in_or_none"):
        allowed = {host.resolve(ref) for ref in spec["int_in_or_none"]}
        got = _first_int(text)
        if got is not None and got not in allowed:
            misses.append(f"int_in_or_none {sorted(allowed)} got={got}")
    if spec.get("arabic"):
        prose = text
        for ref in spec.get("contains") or []:
            value = host.resolve(ref)
            if value not in (None, ""):
                prose = prose.replace(str(value), "")
        if not _mostly_arabic(prose):
            misses.append("arabic")
    if spec.get("numbers_from"):
        payloads = [host.obj(ref) for ref in spec["numbers_from"]]
        bad = ungrounded_numbers(text, payloads)
        if bad:
            misses.append(f"numbers_from {bad}")
    meter = meta.get("turn_meter") if isinstance(meta.get("turn_meter"), dict) else {}
    if spec.get("truthful") and (meter.get("truthfulness_flags") or []):
        misses.append(f"truthful {meter.get('truthfulness_flags')}")
    if "llm_calls_max" in spec:
        calls = meter.get("llm_calls")
        if calls is None or int(calls) > int(spec["llm_calls_max"]):
            misses.append(f"llm_calls_max {spec['llm_calls_max']} got={calls}")
    if "writer_calls_max" in spec:
        stages = meter.get("llm_calls_by_stage")
        writer = (
            sum(int(n) for stage, n in stages.items() if stage != "understand")
            if isinstance(stages, dict) else None
        )
        if writer is None or writer > int(spec["writer_calls_max"]):
            misses.append(f"writer_calls_max {spec['writer_calls_max']} got={writer}")
    if spec.get("not_degraded") and any(s and s in text for s in _degradation_sentences()):
        misses.append("not_degraded")
    if spec.get("table_nonempty"):
        envelope = meta.get("envelope") if isinstance(meta.get("envelope"), dict) else {}
        for table in envelope.get("tables") or []:
            if isinstance(table, dict) and not (table.get("rows") or []):
                misses.append("table_nonempty")
                break
    return misses


# ── Run ─────────────────────────────────────────────────────────────────────


def run_thread(thread: dict, token: str, host: Host) -> dict:
    status, conv = _req(
        "POST", "/ai/workspace/conversations/", token=token,
        body={"title": f"Chat retest · {thread['id']}", "conversation_type": "chat"}, timeout=30,
    )
    if status not in (200, 201) or "id" not in conv:
        raise RuntimeError(f"conversation create → {status}")
    leave_before = host_leave_count(token) if thread.get("no_host_write") else None
    turns = []
    for spec in thread.get("turns") or []:
        started = time.monotonic()
        code, payload = _req(
            "POST", f"/ai/workspace/conversations/{conv['id']}/messages/", token=token,
            body={"content": spec["say"], "pulse_mode": "ask"}, timeout=180,
        )
        seconds = round(time.monotonic() - started, 2)
        reply, meta = assistant_text(payload if isinstance(payload, dict) else {})
        misses = [f"http {code}"] if code != 200 else check_turn(spec, reply, meta, host)
        meter = meta.get("turn_meter") if isinstance(meta.get("turn_meter"), dict) else {}
        turns.append({
            "say": spec["say"],
            "reply": reply,
            "seconds": seconds,
            "llm_calls": meter.get("llm_calls"),
            "turn_decision": meter.get("turn_decision"),
            "tools": [t.get("input") for t in meta.get("tool_trace") or [] if isinstance(t, dict)],
            "misses": misses,
            "pass": not misses,
        })
        print(f"  {'PASS' if not misses else 'FAIL'} {seconds:>5}s llm={meter.get('llm_calls')} · {spec['say'][:60]}", flush=True)
        for miss in misses:
            print(f"       ✗ {miss}", flush=True)
    wrote = None
    if thread.get("no_host_write"):
        leave_after = host_leave_count(token)
        wrote = leave_before != leave_after
    passed = all(t["pass"] for t in turns) and not wrote
    return {
        "id": thread["id"],
        "closes": list(thread.get("closes") or []),
        "objectives": list(thread.get("objectives") or []),
        "conversation_id": str(conv["id"]),
        "host_write": wrote,
        "turns": turns,
        "pass": passed,
    }


def summarize(threads: list[dict]) -> dict:
    """Finding and objective verdicts for one run."""
    findings: dict[str, bool] = {}
    for thread in threads:
        for fid in thread["closes"]:
            findings[fid] = findings.get(fid, True) and thread["pass"]
    degraded = any("not_degraded" in m for t in threads for turn in t["turns"] for m in turn["misses"])
    if "no-writer-retry" in findings:
        findings["no-writer-retry"] = findings["no-writer-retry"] and not degraded
    objectives: dict[str, bool] = {}
    for thread in threads:
        for oid in thread["objectives"]:
            objectives[oid] = objectives.get(oid, True) and thread["pass"]
    turns = [turn for t in threads for turn in t["turns"]]
    if turns:
        objectives["C4"] = all(turn.get("turn_decision") for turn in turns)
    seconds = [turn["seconds"] for t in threads for turn in t["turns"]]
    over = sum(1 for s in seconds if s * 1000 > _LATENCY_BUDGET_MS)
    calls = [int(turn["llm_calls"]) for t in threads for turn in t["turns"] if turn["llm_calls"] is not None]
    latency = {
        "turns": len(seconds),
        "p50_ms": round(statistics.median(seconds) * 1000) if seconds else None,
        "over_4s": over,
        "llm_calls_p50": statistics.median(calls) if calls else None,
        "llm_calls_max": max(calls) if calls else None,
    }
    return {"findings": findings, "objectives": objectives, "latency": latency}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live Chat retest bank")
    parser.add_argument("--only", nargs="*", help="thread ids")
    parser.add_argument("--no-write", action="store_true", help="print only")
    args = parser.parse_args(argv)
    token = login()
    host = Host(token)
    bank = [t for t in load_bank() if not args.only or t["id"] in args.only]
    started = datetime.now(timezone.utc)
    threads = []
    for thread in bank:
        print(f"▶ {thread['id']}", flush=True)
        threads.append(run_thread(thread, token, host))
    report = {
        "tier": "live_retest",
        "run_at": started.isoformat(),
        "surface": "chat",
        "user": USER,
        "bank": BANK.name,
        "partial": bool(args.only),
        "threads": threads,
        **summarize(threads),
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if not args.no_write and not args.only:
        path = EVIDENCE / f"PV2-chat-retest-{started.strftime('%Y-%m-%d-%H%M')}.json"
        path.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {path}")
    print(json.dumps({k: report[k] for k in ("findings", "objectives", "latency")}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
