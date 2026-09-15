#!/usr/bin/env python3
"""Pulse V2 golden scenarios (Phase 10.4) — G1..G5 live integration validation.

Drives the five manual golden scenarios from PULSE-V2-IMPLEMENTATION-PLAN.md
through the live chat API and grades each against its expected signal.

Usage:
    cd backend && ../.venv/bin/python qa_pulse_golden_v2.py [--verbose]

Notes:
  * G1/G3/G5 are brand-agnostic engine behaviours (Phase 2 routing, Phase 3
    work objectives, spelling regression).
  * G2/G4 are Carbon-domain (emissions DQ rules / emission factors). Under a
    non-carbon brand (e.g. nibras) the correct behaviour is graceful
    decline — graded as "isolated" rather than "failed".
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime

from dotenv import load_dotenv

BASE_URL = "http://localhost:8009/carbon-api"
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", ".env"))
ADMIN_USER = os.environ.get("PULSE_QA_USER", "ahmed")
ADMIN_PASS = os.environ.get("PULSE_QA_PASS") or os.environ.get("CARBON_ADMIN_PASSWORD")

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "qa_pulse_golden_v2.json")


# ── HTTP helpers ────────────────────────────────────────────────────────────
def _post(url, body, token=None, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


def _get(url, token=None, timeout=30):
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


def get_token():
    status, data = _post(f"{BASE_URL}/token/", {"username": ADMIN_USER, "password": ADMIN_PASS})
    if status not in (200, 201) or "access" not in data:
        raise RuntimeError(f"Auth failed: {status}")
    return data["access"]


def create_conversation(token):
    status, data = _post(
        f"{BASE_URL}/ai/workspace/conversations/",
        {"title": f"V2 Golden {datetime.now().strftime('%H:%M:%S')}", "conversation_type": "chat"},
        token=token,
    )
    if status not in (200, 201) or "id" not in data:
        raise RuntimeError(f"Create conversation failed: {status}")
    return data["id"]


def send_message(token, conv_id, text, timeout=120):
    status, data = _post(
        f"{BASE_URL}/ai/workspace/conversations/{conv_id}/messages/",
        {"content": text},
        token=token,
        timeout=timeout,
    )
    if status not in (200, 201):
        return None, {}, [], [], []
    msg = data.get("assistant_message") or data
    content = msg.get("content", "")
    raw_meta = msg.get("metadata_json") or msg.get("metadata") or {}
    if isinstance(raw_meta, str):
        try:
            raw_meta = json.loads(raw_meta)
        except Exception:
            raw_meta = {}
    actions = raw_meta.get("actions") or ([raw_meta["action"]] if raw_meta.get("action") else [])
    pending = raw_meta.get("pending_actions") or []
    trace = msg.get("tool_trace") or raw_meta.get("tool_trace") or []
    return content, raw_meta, actions, pending, trace


def _tools(trace):
    """Flatten tool trace into a set of tool names (best effort)."""
    names = set()
    if isinstance(trace, list):
        for item in trace:
            if isinstance(item, dict):
                n = item.get("tool") or item.get("name") or item.get("tool_name")
                if n:
                    names.add(n)
            elif isinstance(item, str):
                names.add(item)
    return names


def _decline(content):
    return bool(re.search(
        r"don't have access|do not have access|can'?t (help|access|retrieve)|unable to|"
        r"not (available|part of|in scope|something i)|outside (my|the)? ?scope|"
        r"out of scope|not in my scope|i (only|primarily|exclusively) (handle|work|support)",
        content, re.IGNORECASE))


# ── Scenario graders ────────────────────────────────────────────────────────
def g1(token, conv_id):
    content, meta, actions, pending, trace = send_message(
        token, conv_id,
        "hi what is the weather in north coast egypt today, is it suitable for beach swimming?",
    )
    tools = _tools(trace)
    used_web = "web_research" in tools
    located = bool(re.search(r"north coast|mediterranean|egypt|alexandria|marsa", content, re.IGNORECASE))
    if not content:
        return ("FAIL", "empty response")
    if used_web and located:
        return ("PASS", f"web_research called + location stated (tools={sorted(tools)})")
    if used_web:
        return ("PARTIAL", f"web_research called but no location in prose (tools={sorted(tools)})")
    return ("FAIL", f"web_research NOT called (tools={sorted(tools)}); content[:80]={content[:80]!r}")


def g2(token, conv_id):
    content, meta, actions, pending, trace = send_message(
        token, conv_id, "What are the active DQ rules for the emissions module?",
    )
    tools = _tools(trace)
    grounded = bool(tools & {"get_entity_details", "call_host_api", "list_host_entities", "dq"}) or \
        bool(re.search(r"rule|condition|threshold|critical|error", content, re.IGNORECASE))
    if _decline(content):
        return ("ISOLATED", f"correctly declined under non-carbon brand (tools={sorted(tools)})")
    if grounded and tools:
        return ("PASS", f"grounded via {sorted(tools)}")
    return ("FAIL", f"no tool grounding and no decline (tools={sorted(tools)}); content[:80]={content[:80]!r}")


def g3(token, conv_id):
    content1, *_ = send_message(
        token, conv_id,
        "Investigate why emissions increased in August. Save this so I can continue later.",
    )
    # create a fresh conversation to simulate "new conversation" resume
    conv2 = create_conversation(token)
    content2, meta2, actions2, pending2, trace2 = send_message(
        token, conv2, "Where did we get to on my emissions investigation?",
    )
    tools2 = _tools(trace2)
    resumed = "get_work_objectives" in tools2 or bool(re.search(
        r"emissions|august|investigat|objective|saved", content2, re.IGNORECASE))
    if resumed:
        return ("PASS", f"resume reported saved objective (tools={sorted(tools2)})")
    return ("FAIL", f"no saved objective surfaced (tools={sorted(tools2)}); content[:80]={content2[:80]!r}")


def g4(token, conv_id):
    content, *_ = send_message(
        token, conv_id, "What is the current emission factor for our electricity consumption?",
    )
    if _decline(content):
        return ("ISOLATED", "correctly declined under non-carbon brand")
    numeric = bool(re.search(r"\d+\.?\d*", content))
    generic = bool(re.search(r"global average|typically|grid average|depends on", content, re.IGNORECASE))
    if numeric and not generic:
        return ("PASS", "returned a configured numeric value")
    if numeric:
        return ("PARTIAL", "returned a number but framed generically")
    return ("FAIL", f"no value and no decline; content[:80]={content[:80]!r}")


def g5(token, conv_id):
    content, meta, actions, pending, trace = send_message(
        token, conv_id,
        "Correct the spelling in this sentence: 'what is the weather in north cost egypt toay?'",
    )
    tools = _tools(trace)
    used_web = "web_research" in tools
    corrected = bool(re.search(r"north coast|north coast egypt|today", content, re.IGNORECASE))
    if used_web:
        return ("FAIL", f"web_research was called for a spelling task (tools={sorted(tools)})")
    if corrected:
        return ("PASS", "rewrote sentence without calling web_research")
    return ("PARTIAL", f"no web_research but no clear correction; content[:80]={content[:80]!r}")


SCENARIOS = [
    ("G1", "Weather ambiguity → web_research", g1),
    ("G2", "Single-tool grounded answer (DQ rules)", g2),
    ("G3", "Save and resume (WorkObjective)", g3),
    ("G4", "Factual grounding (emission factor)", g4),
    ("G5", "Spelling transformation (no web_research)", g5),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    token = get_token()
    print(f"✅ Authenticated as {ADMIN_USER} @ {BASE_URL}")

    results = []
    for sid, name, fn in SCENARIOS:
        conv_id = create_conversation(token)
        try:
            status, detail = fn(token, conv_id)
        except Exception as exc:  # noqa: BLE001
            status, detail = "ERROR", str(exc)
        results.append({"id": sid, "name": name, "status": status, "detail": detail})
        print(f"  {sid}  [{status:8s}] {name} — {detail}")
        if args.verbose and status in ("FAIL", "ERROR"):
            print(f"         (conversation {conv_id})")

    with open(RESULTS_FILE, "w") as f:
        json.dump({"ran_at": datetime.now().isoformat(), "results": results}, f, indent=2)

    passed = sum(1 for r in results if r["status"] == "PASS")
    isolated = sum(1 for r in results if r["status"] == "ISOLATED")
    print(f"\nResult: {passed} pass, {isolated} isolated (brand-scoped), "
          f"{len(results) - passed - isolated} fail/partial — wrote {RESULTS_FILE}")
    return 0 if (passed + isolated) == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
