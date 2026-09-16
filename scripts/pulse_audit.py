#!/usr/bin/env python3
"""
pulse_audit.py — ensemble audit orchestrator with a reconciling judge.

Turns "one model's opinion" into "a ranked, deduplicated, TESTABLE worklist".

Pipeline per lane:
    1. Fan out the same review task to N strong models (different families).
    2. Collect each model's findings.
    3. A JUDGE model (a different family, to avoid shared bias) reconciles them:
       dedupes, resolves conflicts, ranks by (severity × cross-model agreement),
       and — critically — tags each finding with whether it can become a failing
       test and which file that test targets.

Only findings the judge marks `testable: true` are worth acting on immediately;
they convert to a failing test, you fix, then re-run pulse_scorecard.py to prove
the number moved. Everything else becomes a tracked issue.

Model roster is grounded in what the Poe API actually exposes (verified via
/v1/models). Override per lane with --models.

Usage:
    # Prompt audit across an ensemble, judged by a different family:
    python3 scripts/pulse_audit.py --lane prompt_audit \
        --files backend/ai/engine/llm/prompts.py \
        --models claude-opus-4.8 gpt-5.4-pro o3-pro \
        --judge gemini-3.1-pro \
        --out raw/reviews/audit-prompts.json

    # Architecture ensemble:
    python3 scripts/pulse_audit.py --lane architecture \
        --files backend/ai/engine/cognition/turn/runner.py \
                backend/ai/engine/agent/reasoning.py \
                backend/ai/engine/cognition/turn/intent.py \
        --models o3-pro claude-opus-4.8 gpt-5.3-codex \
        --judge gpt-5.4-pro \
        --out raw/reviews/audit-architecture.json

    # Domain/regulatory gaps (deep-research model shines here):
    python3 scripts/pulse_audit.py --lane domain_gaps \
        --files domain_packs/nibras/api_catalog.yaml \
                domain_packs/nibras/processes/payroll.run.lifecycle.yaml \
        --models perplexity-adv-deep-research gpt-5.4-pro claude-opus-4.8 \
        --judge claude-opus-4.8 \
        --out raw/reviews/audit-domain.json
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

_REPO = Path(__file__).resolve().parent.parent
load_dotenv(_REPO / "backend" / ".env")

API_KEY = os.environ.get("LLM_API_KEY", "")
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.poe.com/v1")
if not API_KEY:
    sys.exit("LLM_API_KEY not set in backend/.env")

# Reuse the reviewer's task prompts so lanes stay in one place.
sys.path.insert(0, str(_REPO / "scripts"))
from poe_review import TASK_PROMPTS  # noqa: E402

# Default ensembles per lane — strongest available families, verified present
# on the Poe /models endpoint. Mix families so the judge sees diverse priors.
DEFAULT_ENSEMBLES = {
    "prompt_audit": ["claude-opus-4.8", "gpt-5.4-pro", "o3-pro"],
    "architecture": ["o3-pro", "claude-opus-4.8", "gpt-5.3-codex"],
    "redteam_generate": ["grok-4.20-multi-agent", "gpt-5.4-pro"],
    "domain_gaps": ["perplexity-adv-deep-research", "gpt-5.4-pro", "claude-opus-4.8"],
    "skill_audit": ["claude-opus-4.8", "gpt-5.4-pro"],
    "instance_review": ["gpt-5.4-pro", "claude-opus-4.8"],
}
DEFAULT_JUDGE = "gemini-3.1-pro"  # different family from most panelists

JUDGE_PROMPT = textwrap.dedent("""
    You are the RECONCILING JUDGE over several independent expert reviews of the
    same code/config for an enterprise AI coworker (Pulse — HR/payroll, Kuwait).

    You are given an array of reviews, each `{model, findings}`. Your job:
      1. DEDUPE findings that describe the same underlying issue (across models).
      2. Note AGREEMENT: how many distinct models raised each issue (higher =
         more trustworthy, less likely a single-model hallucination).
      3. RESOLVE conflicts: if models disagree, state the most defensible call.
      4. RANK by priority = severity × agreement × blast-radius.
      5. For EACH surviving finding decide whether it can become a FAILING
         AUTOMATED TEST. If yes, name the concrete target file and sketch the
         test. If it cannot be tested, say why and mark it a tracked issue.

    A finding that cannot be verified by a test or a re-measured score is NOT
    actionable — flag it `actionable: false`.

    Output ONLY this JSON:
    {
      "worklist": [
        {
          "rank": 1,
          "title": "...",
          "severity": "CRITICAL|HIGH|MED|LOW",
          "agreement": <int models that raised it>,
          "summary": "...",
          "target_file": "path or null",
          "testable": true|false,
          "proposed_test": "one-line description or null",
          "actionable": true|false,
          "raised_by": ["model", ...]
        }
      ],
      "consensus_note": "1-2 sentences on where the panel agreed/disagreed most"
    }
""").strip()


def call_poe(model: str, system: str, user: str, max_tokens: int = 8000) -> str:
    resp = requests.post(
        BASE_URL.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
        },
        timeout=600,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def parse_json(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"(\[.*\]|\{.*\})", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    return {"raw": raw}


def build_content(files: list[str]) -> str:
    parts = []
    for f in files:
        p = _REPO / f
        if not p.exists():
            print(f"  ⚠ missing: {f}", file=sys.stderr)
            continue
        parts.append(f"\n\n{'='*60}\n# FILE: {f}\n{'='*60}\n{p.read_text(encoding='utf-8')}")
    return "\n".join(parts)


def review_one(model: str, system: str, content: str) -> dict:
    print(f"    → {model} reviewing…", flush=True)
    try:
        raw = call_poe(model, system, content)
        return {"model": model, "findings": parse_json(raw)}
    except Exception as e:  # noqa: BLE001
        print(f"    ✗ {model} failed: {e}", file=sys.stderr)
        return {"model": model, "findings": {"error": str(e)}}


def main() -> int:
    ap = argparse.ArgumentParser(description="Pulse ensemble audit + judge")
    ap.add_argument("--lane", required=True, choices=list(TASK_PROMPTS))
    ap.add_argument("--files", nargs="+", required=True)
    ap.add_argument("--models", nargs="*", help="Ensemble panel (defaults per lane)")
    ap.add_argument("--judge", default=DEFAULT_JUDGE)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-tokens", type=int, default=8000)
    args = ap.parse_args()

    panel = args.models or DEFAULT_ENSEMBLES.get(args.lane, ["claude-opus-4.8", "gpt-5.4-pro"])
    system = TASK_PROMPTS[args.lane]
    content = build_content(args.files)
    if not content.strip():
        sys.exit("No file content to review.")

    print(f"  lane={args.lane}  panel={panel}  judge={args.judge}  chars={len(content):,}")

    # 1-2. Fan out the panel in parallel.
    with cf.ThreadPoolExecutor(max_workers=min(4, len(panel))) as ex:
        reviews = list(ex.map(lambda m: review_one(m, system, content), panel))

    ok = [r for r in reviews if "error" not in (r["findings"] if isinstance(r["findings"], dict) else {})]
    print(f"  → {len(ok)}/{len(panel)} panelists returned findings")

    # 3-5. Judge reconciles into a ranked, testable worklist.
    print(f"  → judge {args.judge} reconciling…", flush=True)
    judged = None
    try:
        judge_input = json.dumps(
            [{"model": r["model"], "findings": r["findings"]} for r in ok], ensure_ascii=False
        )
        judged = parse_json(call_poe(args.judge, JUDGE_PROMPT, judge_input, args.max_tokens))
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ judge failed: {e}", file=sys.stderr)

    out = {
        "lane": args.lane,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "files": args.files,
        "panel": panel,
        "judge": args.judge,
        "raw_reviews": reviews,
        "verdict": judged,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"  ✓ saved → {out_path}")

    # Print the actionable, testable head of the worklist.
    wl = (judged or {}).get("worklist", []) if isinstance(judged, dict) else []
    testable = [w for w in wl if w.get("testable") and w.get("actionable")]
    print(f"\n  Worklist: {len(wl)} findings · {len(testable)} testable+actionable")
    for w in wl[:10]:
        flag = "✎test" if w.get("testable") else ("•issue" if w.get("actionable") else "∅noise")
        print(f"    #{w.get('rank','?'):<2} [{w.get('severity','?'):<8}] "
              f"agree={w.get('agreement','?')} {flag}  {w.get('title','')[:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
