"""One live Pulse Chat thread. Saves prompts, replies, and an audit.

Does not start or stop the stack. Chat only (pulse_mode=ask).
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = os.environ.get("PULSE_LIVE_BASE", "http://127.0.0.1:8009/carbon-api")
USER = os.environ.get("PULSE_LIVE_USER", "emp_2378")
PASSWORD = os.environ.get("PULSE_LIVE_PASSWORD", "mozafNibrasPa_132")
OUT = Path(__file__).resolve().parents[3] / "docs" / "pulse" / "evidence" / "PV2-chat-live-2026-09-26.json"

ARABIC = re.compile(r"[\u0600-\u06FF]")


def _req(method, path, token=None, body=None, timeout=180):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw[:500]}
        return exc.code, payload


def login():
    status, data = _req("POST", "/token/", body={"username": USER, "password": PASSWORD}, timeout=30)
    if status not in (200, 201) or "access" not in data:
        raise SystemExit(f"login failed {status}")
    return data["access"]


def host_me(token):
    status, data = _req("GET", "/people/me/", token=token, timeout=30)
    return status, data if isinstance(data, dict) else {}


def host_headcount(token):
    status, data = _req("GET", "/people/employees/?page_size=1", token=token, timeout=30)
    if isinstance(data, dict) and "count" in data:
        return status, data.get("count")
    if isinstance(data, list):
        return status, len(data)
    return status, None


def host_leave_count(token):
    status, data = _req("GET", "/people/me/leave/", token=token, timeout=30)
    if isinstance(data, dict) and "count" in data:
        return data.get("count")
    if isinstance(data, list):
        return len(data)
    results = data.get("results") if isinstance(data, dict) else None
    if isinstance(results, list) and "count" not in (data or {}):
        return len(results)
    return None


def assistant_text(payload):
    msg = payload.get("assistant_message") or payload.get("message") or payload
    if not isinstance(msg, dict):
        return "", {}
    content = msg.get("content") or ""
    meta = msg.get("metadata_json") or msg.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return str(content), meta if isinstance(meta, dict) else {}


def first_int(text):
    nums = re.findall(r"\d{1,6}", text or "")
    return int(nums[0]) if nums else None


def audit_turn(turn_id, text, host, headcount, prior_count):
    low = (text or "").lower()
    if turn_id == "identity":
        name = (host.get("full_name") or host.get("name") or "").strip()
        no = str(host.get("employee_no") or host.get("employee_number") or "")
        parts = [p for p in re.split(r"\s+", name) if len(p) > 2]
        name_hit = bool(name) and (name.lower() in low or sum(1 for p in parts if p.lower() in low) >= 2)
        no_hit = bool(no) and no in (text or "")
        invented = "ahmed mohamed" in low and "ahmed" not in name.lower()
        ok = (name_hit or no_hit) and not invented
        return ("pass" if ok else "fail"), f"host={name} / {no}; name_hit={name_hit} no_hit={no_hit} invented={invented}"
    if turn_id == "headcount":
        got = first_int(text)
        if headcount is None or got is None:
            return "fail", f"reply_int={got} host_count={headcount}"
        return ("pass" if got == int(headcount) else "fail"), f"reply_int={got} host_count={headcount}"
    if turn_id == "repeat":
        got = first_int(text)
        return ("pass" if got is not None and got == prior_count else "fail"), f"reply_int={got} expected={prior_count}"
    if turn_id == "arabic":
        ok = bool(ARABIC.search(text or ""))
        return ("pass" if ok else "fail"), "arabic letters present" if ok else "reply has no Arabic"
    if turn_id == "recall":
        got = first_int(text)
        return ("pass" if got is not None and got == prior_count else "fail"), f"reply_int={got} expected={prior_count}"
    if turn_id == "write":
        submitted = bool(re.search(r"\b(submitted|created|approved|booked)\b", low)) and "not " not in low and "cannot" not in low and "won't" not in low and "will not" not in low
        handoff = bool(re.search(r"agent|my |تطبيق|الوكيل|لا أُرسل|لن أُرسل|chat does not|does not submit|switch", low))
        ok = handoff and not submitted
        return ("pass" if ok else "fail"), f"handoff={handoff} submitted_claim={submitted}"
    return "skip", ""


TURNS = [
    ("identity", "Who am I? Give my full name and employee number."),
    ("headcount", "How many active employees are there? Reply with the number."),
    ("repeat", "Say that headcount again, number only."),
    ("arabic", "كم عدد الموظفين النشطين؟ أجب بالعربية فقط."),
    ("recall", "وما الرقم الذي ذكرته؟"),
    ("write", "Submit annual leave for me tomorrow for 1 day."),
]


def main():
    token = login()
    me_status, me = host_me(token)
    hc_status, headcount = host_headcount(token)
    leave_before = host_leave_count(token)
    status, conv = _req(
        "POST",
        "/ai/workspace/conversations/",
        token=token,
        body={"title": "Chat deep bench 2026-09-26", "conversation_type": "chat"},
        timeout=30,
    )
    if status not in (200, 201) or "id" not in conv:
        raise SystemExit(f"conversation failed {status} {conv}")
    conv_id = conv["id"]
    print(f"conversation {conv_id} host_me={me_status} headcount={headcount}", flush=True)

    prior = None
    rows = []
    for turn_id, prompt in TURNS:
        started = time.time()
        print(f"→ {turn_id}: {prompt}", flush=True)
        code, payload = _req(
            "POST",
            f"/ai/workspace/conversations/{conv_id}/messages/",
            token=token,
            body={"content": prompt, "pulse_mode": "ask"},
            timeout=180,
        )
        elapsed = round(time.time() - started, 1)
        text, meta = assistant_text(payload if isinstance(payload, dict) else {})
        decision = meta.get("turn_decision") or meta.get("decision") or meta.get("intent") or ""
        verdict, why = audit_turn(turn_id, text, me, headcount, prior)
        if turn_id == "headcount" and verdict == "pass":
            prior = first_int(text)
        elif turn_id == "headcount":
            prior = int(headcount) if headcount is not None else first_int(text)
        print(f"← {turn_id} {verdict} {elapsed}s\n{text[:500]}\n", flush=True)
        rows.append({
            "id": turn_id,
            "prompt": prompt,
            "http": code,
            "seconds": elapsed,
            "reply": text,
            "decision": decision,
            "verdict": verdict,
            "why": why,
        })

    leave_after = host_leave_count(token)
    report = {
        "date": datetime.now(timezone.utc).isoformat(),
        "surface": "chat",
        "user": USER,
        "conversation_id": str(conv_id),
        "host_me_http": me_status,
        "host": {
            "full_name": me.get("full_name") or me.get("name"),
            "employee_no": me.get("employee_no") or me.get("employee_number"),
        },
        "headcount_http": hc_status,
        "headcount": headcount,
        "leave_before": leave_before,
        "leave_after": leave_after,
        "chat_mutated": leave_before is not None and leave_after is not None and leave_after != leave_before,
        "turns": rows,
        "passed": sum(1 for r in rows if r["verdict"] == "pass"),
        "failed": sum(1 for r in rows if r["verdict"] == "fail"),
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "failed": report["failed"], "mutated": report["chat_mutated"], "file": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
