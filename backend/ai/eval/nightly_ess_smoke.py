"""PV2-6B — Nightly live ESS smoke (Chat → Agent → Approve as emp_1067).

Three journeys on Nibras dev: leave, loan, attendance permission.
Chat must not create host rows (ADR-0046). Agent Approve + Run must.
IC: handoff_ready / handoff_agent, slot_carry on inherited_context,
host-row fingerprint after Run.

SOAKING until five consecutive live PASS nights. Dry-run and skipped
nights do not count. Never invent elapsed nights.

Safety (all required for a mutating run):
  --live
  --i-have-stack-hold
  --host-user emp_1067
  env PULSE_NIGHTLY_LIVE=1

Default is --dry-run (catalog + assertion helpers only; no HTTP, no ORM).

Usage:
  python -m ai.eval.nightly_ess_smoke --dry-run
  PULSE_NIGHTLY_LIVE=1 python -m ai.eval.nightly_ess_smoke \\
      --live --i-have-stack-hold --host-user emp_1067
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = REPO_ROOT / "docs" / "pulse" / "evidence"
NIGHTS_JSON = EVIDENCE_DIR / "PV2-6B-nights.json"
SOAK_MD = EVIDENCE_DIR / "PV2-6B-soak.md"

HOST_USER = "emp_1067"
REQUIRED_CONSECUTIVE = 5
DEFAULT_BASE = "http://127.0.0.1:8009/carbon-api"
LIVE_ENV = "PULSE_NIGHTLY_LIVE"

# Tokens the Chat lexical binder + process_dial must see. Kept here so
# --dry-run can validate journeys without importing the engine.
_LEAVE_TOKEN = "I want annual leave"
_LOAN_TOKEN = "personal loan"
_ATTENDANCE_TOKEN = "attendance permission"


@dataclass(frozen=True)
class Journey:
    id: str
    process: str
    api_name: str
    host_list_path: str
    required_slots: tuple[str, ...]
    fingerprint_fields: tuple[str, ...]


JOURNEYS: tuple[Journey, ...] = (
    Journey(
        id="leave",
        process="leave.request.lifecycle",
        api_name="submit_my_leave",
        host_list_path="/people/me/leave/",
        required_slots=("leave_type", "start_date"),
        fingerprint_fields=("start_date",),
    ),
    Journey(
        id="loan",
        process="loan.request.lifecycle",
        api_name="submit_my_loan",
        host_list_path="/people/me/loan/",
        required_slots=("loan_type", "amount"),
        fingerprint_fields=("principal", "term_months"),
    ),
    Journey(
        id="attendance",
        process="attendance.permission.lifecycle",
        api_name="submit_my_attendance_permission",
        host_list_path="/people/me/attendance-permissions/",
        required_slots=("permission_type", "date", "hours"),
        fingerprint_fields=("date", "hours"),
    ),
)


@dataclass
class NightRecord:
    night_id: str
    status: str
    host_user: str
    journeys: list[dict] = field(default_factory=list)
    consecutive_green: int = 0
    notes: str = ""
    recorded_at: str = ""


class ConsentError(ValueError):
    """Live mutation refused — missing hold, env, or persona."""


def require_live_consent(
    *,
    live: bool,
    stack_hold: bool,
    host_user: str,
    env: dict[str, str] | None = None,
) -> None:
    """Refuse a mutating run unless every live-consent flag is present."""
    if not live:
        return
    environ = env if env is not None else os.environ
    if not stack_hold:
        raise ConsentError(
            "refused: --live requires --i-have-stack-hold (STACK-HOLD + COMMS)"
        )
    if (environ.get(LIVE_ENV) or "").strip() != "1":
        raise ConsentError(
            f"refused: --live requires {LIVE_ENV}=1 (do not run on shared CI)"
        )
    if (host_user or "").strip() != HOST_USER:
        raise ConsentError(
            f"refused: nightly ESS smoke is {HOST_USER} only, got {host_user!r}"
        )


def _weekday_on_or_after(day: date) -> date:
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def journey_bindings(night_id: str) -> dict[str, dict[str, Any]]:
    """Deterministic far-future slots so the same calendar night is replay-safe."""
    digest = hashlib.sha256(night_id.encode("utf-8")).hexdigest()
    offset = int(digest[:6], 16) % 180
    base = _weekday_on_or_after(date(2027, 4, 5) + timedelta(days=offset))
    leave_start = _weekday_on_or_after(base)
    loan_start = _weekday_on_or_after(leave_start + timedelta(days=14))
    att_day = _weekday_on_or_after(loan_start + timedelta(days=7))
    principal = 517 + (int(digest[6:8], 16) % 80)
    return {
        "leave": {
            "leave_type": "annual",
            "start_date": leave_start.isoformat(),
            "days": 1,
        },
        "loan": {
            "loan_type": "personal",
            "amount": principal,
            "principal": principal,
            "term_months": 12,
            "start_date": loan_start.isoformat(),
        },
        "attendance": {
            "permission_type": "official",
            "date": att_day.isoformat(),
            "hours": 2,
        },
    }


def chat_utterance(journey: Journey, slots: dict[str, Any]) -> str:
    if journey.id == "leave":
        return (
            f"{_LEAVE_TOKEN} from {slots['start_date']} for {slots['days']} day"
        )
    if journey.id == "loan":
        return (
            f"I need a {_LOAN_TOKEN} of {slots['principal']} KWD for "
            f"{slots['term_months']} months starting {slots['start_date']}"
        )
    if journey.id == "attendance":
        return (
            f"Request {_ATTENDANCE_TOKEN} {slots['permission_type']} "
            f"{slots['hours']} hours on {slots['date']}"
        )
    raise ValueError(f"unknown journey {journey.id}")


def catalog_issues(journeys: tuple[Journey, ...] = JOURNEYS) -> list[str]:
    issues: list[str] = []
    ids = [j.id for j in journeys]
    if ids != ["leave", "loan", "attendance"]:
        issues.append(f"expected leave/loan/attendance, got {ids}")
    bindings = journey_bindings("catalog-check")
    for journey in journeys:
        slots = bindings[journey.id]
        text = chat_utterance(journey, slots)
        if journey.id == "leave" and _LEAVE_TOKEN not in text:
            issues.append("leave utterance missing personal-leave token")
        if journey.id == "loan" and _LOAN_TOKEN not in text:
            issues.append("loan utterance missing personal-loan token")
        if journey.id == "attendance" and _ATTENDANCE_TOKEN not in text:
            issues.append("attendance utterance missing permission token")
        for key in journey.required_slots:
            src = "principal" if key == "amount" else key
            if src not in slots and key not in slots:
                issues.append(f"{journey.id} missing slot {key}")
        if not journey.host_list_path.startswith("/people/me/"):
            issues.append(f"{journey.id} host list is not ESS /people/me/")
    return issues


def _as_list(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "items", "data"):
            if isinstance(payload.get(key), list):
                return [row for row in payload[key] if isinstance(row, dict)]
    return []


def _field(row: dict, key: str) -> str:
    value = row.get(key)
    if isinstance(value, dict):
        value = value.get("code") or value.get("value") or value.get("name")
    if value is None:
        return ""
    return str(value)


def row_ids(rows: list[dict]) -> set[str]:
    out: set[str] = set()
    for row in rows:
        ident = row.get("id") or row.get("pk")
        if ident is not None:
            out.add(str(ident))
    return out


def chat_did_not_mutate(before: list[dict], after: list[dict]) -> bool:
    return row_ids(before) == row_ids(after)


def matching_rows(rows: list[dict], fingerprint: dict[str, Any]) -> list[dict]:
    hits = []
    for row in rows:
        if all(_field(row, key) == str(value) for key, value in fingerprint.items()):
            hits.append(row)
    return hits


def slot_carry_ok(inherited: list[dict], required: tuple[str, ...]) -> bool:
    keys = {str(item.get("key") or "") for item in inherited if isinstance(item, dict)}
    return all(slot in keys for slot in required)


def ic_failures(journey: dict) -> list[str]:
    """Return IC / host assertion misses for one journey result dict."""
    misses: list[str] = []
    decision = str(journey.get("chat_decision") or "")
    if not (
        journey.get("handoff_ready")
        or decision in {"handoff_agent", "handoff"}
        or journey.get("active_plans")
    ):
        misses.append("chat_handoff")
    if journey.get("chat_mutated"):
        misses.append("chat_host_mutation")
    if not journey.get("slot_carry"):
        misses.append("slot_carry")
    if not journey.get("host_row_after_agent"):
        misses.append("host_row")
    approve_http = journey.get("approve_http")
    if approve_http is not None and approve_http not in (200, 201):
        misses.append("approve_http")
    return misses


def load_nights(path: Path = NIGHTS_JSON) -> dict[str, Any]:
    if not path.exists():
        return {
            "phase": "PV2-6B",
            "required_consecutive": REQUIRED_CONSECUTIVE,
            "nights": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def consecutive_green_nights(nights: list[dict]) -> int:
    """Trailing live PASS nights only. DRY_RUN / SKIP / FAIL break the streak."""
    streak = 0
    for row in reversed(nights):
        if row.get("status") != "PASS":
            break
        streak += 1
    return streak


def soak_complete(nights: list[dict], required: int = REQUIRED_CONSECUTIVE) -> bool:
    return consecutive_green_nights(nights) >= required


def record_night(record: NightRecord, path: Path = NIGHTS_JSON) -> dict[str, Any]:
    payload = load_nights(path)
    nights = list(payload.get("nights") or [])
    nights = [row for row in nights if row.get("night_id") != record.night_id]
    nights.append(asdict(record))
    nights.sort(key=lambda row: str(row.get("night_id") or ""))
    record.consecutive_green = consecutive_green_nights(nights)
    nights[-1]["consecutive_green"] = record.consecutive_green
    payload["nights"] = nights
    payload["required_consecutive"] = REQUIRED_CONSECUTIVE
    payload["soak_complete"] = soak_complete(nights)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def render_soak_md(payload: dict[str, Any]) -> str:
    nights = payload.get("nights") or []
    streak = consecutive_green_nights(nights)
    lines = [
        "# PV2-6B — Nightly live ESS smoke soak",
        "",
        "Chat → Agent → Approve as `emp_1067` (leave, loan, attendance).",
        f"Required: **{REQUIRED_CONSECUTIVE}** consecutive live PASS nights.",
        "Dry-run / SKIP / FAIL do not count. Do not back-date rows.",
        "",
        f"Streak: **{streak}/{REQUIRED_CONSECUTIVE}**. "
        f"Soak complete: **{soak_complete(nights)}**.",
        "",
        "| Night | Status | Leave | Loan | Attendance | Notes |",
        "|---|---|---|---|---|---|",
    ]
    if not nights:
        lines.append("| — | no live nights yet | — | — | — | SOAKING |")
    for row in nights:
        by_id = {j.get("id"): j for j in (row.get("journeys") or [])}
        def cell(jid: str) -> str:
            item = by_id.get(jid) or {}
            return "PASS" if item.get("passed") else (item.get("status") or "—")
        lines.append(
            f"| {row.get('night_id')} | {row.get('status')} | "
            f"{cell('leave')} | {cell('loan')} | {cell('attendance')} | "
            f"{row.get('notes') or ''} |"
        )
    lines.append("")
    return "\n".join(lines)


class LiveClient:
    """Thin HTTP client for the running Nibras stack (:8009)."""

    def __init__(self, token: str, base: str = DEFAULT_BASE):
        self.token = token
        self.base = base.rstrip("/") + "/"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def post(self, path: str, body: dict | None = None, timeout: int = 180):
        import requests

        return requests.post(
            urljoin(self.base, path.lstrip("/")),
            json=body or {},
            headers=self._headers(),
            timeout=timeout,
        )

    def get(self, path: str, timeout: int = 60):
        import requests

        return requests.get(
            urljoin(self.base, path.lstrip("/")),
            headers=self._headers(),
            timeout=timeout,
        )

    def sse(self, path: str, timeout: int = 300) -> dict:
        import requests

        frames: list[dict] = []
        with requests.post(
            urljoin(self.base, path.lstrip("/")),
            headers=self._headers(),
            stream=True,
            timeout=timeout,
        ) as resp:
            status = resp.status_code
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data:"):
                    continue
                try:
                    frames.append(json.loads(raw[5:].strip()))
                except json.JSONDecodeError:
                    frames.append({"type": "raw", "raw": raw})
        return {"http_status": status, "frames": frames}


def _mint_token(username: str) -> str:
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.tokens import RefreshToken

    user = get_user_model().objects.get(username=username)
    return str(RefreshToken.for_user(user).access_token)


def _list_host(client: LiveClient, path: str) -> list[dict]:
    resp = client.get(path)
    if resp.status_code != 200:
        return []
    return _as_list(resp.json())


def _chat_decision(assistant: dict, state_plans: list) -> tuple[str, bool]:
    meta = assistant.get("metadata") or {}
    plans = meta.get("active_plans") or state_plans or []
    handoff = bool(plans) or bool(meta.get("handoff_ready"))
    decision = str(meta.get("turn_decision") or meta.get("decision") or "")
    if not decision and handoff:
        decision = "handoff_agent"
    return decision, handoff or decision in {"handoff_agent", "handoff"}


def run_journey(
    client: LiveClient,
    journey: Journey,
    slots: dict[str, Any],
) -> dict[str, Any]:
    utterance = chat_utterance(journey, slots)
    before = _list_host(client, journey.host_list_path)
    conv = client.post(
        "/ai/workspace/conversations/",
        {"conversation_type": "chat", "title": f"pv2-6b-{journey.id}"},
    )
    if conv.status_code not in (200, 201):
        return {
            "id": journey.id,
            "passed": False,
            "status": "FAIL",
            "notes": f"conv {conv.status_code}",
        }
    cid = conv.json()["id"]
    msg = client.post(
        f"/ai/workspace/conversations/{cid}/messages/",
        {"content": utterance},
        timeout=180,
    )
    if msg.status_code not in (200, 201):
        return {
            "id": journey.id,
            "passed": False,
            "status": "FAIL",
            "notes": f"chat {msg.status_code}",
            "conversation_id": cid,
        }
    body = msg.json()
    assistant = body.get("assistant_message") or {}
    after_chat = _list_host(client, journey.host_list_path)
    mutated = not chat_did_not_mutate(before, after_chat)
    detail = client.get(f"/ai/workspace/conversations/{cid}/")
    active_plans = []
    if detail.status_code == 200:
        active_plans = list((detail.json() or {}).get("active_plans") or [])
    decision, handoff = _chat_decision(assistant, active_plans)

    plan = client.post(
        "/ai/plans/",
        {"brief": utterance, "conversation_id": cid},
        timeout=180,
    )
    if plan.status_code not in (200, 201):
        return {
            "id": journey.id,
            "passed": False,
            "status": "FAIL",
            "conversation_id": cid,
            "chat_decision": decision,
            "handoff_ready": handoff,
            "chat_mutated": mutated,
            "notes": f"plan {plan.status_code}",
        }
    plan_data = plan.json()
    inherited = list(plan_data.get("inherited_context") or [])
    carry = slot_carry_ok(inherited, journey.required_slots)
    plan_id = plan_data.get("id")
    approve = client.post(f"/ai/plans/{plan_id}/approve/")
    approve_http = approve.status_code
    if approve_http in (200, 201):
        client.sse(f"/ai/plans/{plan_id}/run/", timeout=300)
    after_agent = _list_host(client, journey.host_list_path)
    fingerprint = {key: slots[key] for key in journey.fingerprint_fields if key in slots}
    host_hit = bool(matching_rows(after_agent, fingerprint)) or (
        len(row_ids(after_agent) - row_ids(before)) >= 1 and not mutated
    )
    result = {
        "id": journey.id,
        "process": journey.process,
        "api_name": journey.api_name,
        "conversation_id": cid,
        "plan_id": plan_id,
        "chat_decision": decision,
        "handoff_ready": handoff,
        "active_plans": bool(active_plans or inherited),
        "chat_mutated": mutated,
        "inherited_context": inherited,
        "slot_carry": carry,
        "approve_http": approve_http,
        "host_row_after_agent": host_hit,
        "fingerprint": fingerprint,
        "utterance": utterance,
    }
    misses = ic_failures(result)
    result["passed"] = not misses
    result["status"] = "PASS" if result["passed"] else "FAIL"
    result["notes"] = ",".join(misses)
    return result


def run_live_night(
    *,
    night_id: str,
    host_user: str = HOST_USER,
    base: str = DEFAULT_BASE,
) -> NightRecord:
    token = _mint_token(host_user)
    client = LiveClient(token, base=base)
    bindings = journey_bindings(night_id)
    journeys = [run_journey(client, journey, bindings[journey.id]) for journey in JOURNEYS]
    passed = all(row.get("passed") for row in journeys)
    return NightRecord(
        night_id=night_id,
        status="PASS" if passed else "FAIL",
        host_user=host_user,
        journeys=journeys,
        notes="live Chat→Agent→Approve",
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )


def run_dry_night(night_id: str) -> NightRecord:
    issues = catalog_issues()
    bindings = journey_bindings(night_id)
    journeys = []
    for journey in JOURNEYS:
        slots = bindings[journey.id]
        journeys.append(
            {
                "id": journey.id,
                "status": "DRY_RUN",
                "passed": False,
                "utterance": chat_utterance(journey, slots),
                "required_slots": list(journey.required_slots),
                "fingerprint": {
                    key: slots[key]
                    for key in journey.fingerprint_fields
                    if key in slots
                },
            }
        )
    return NightRecord(
        night_id=night_id,
        status="DRY_RUN",
        host_user=HOST_USER,
        journeys=journeys,
        notes="; ".join(issues) if issues else "catalog valid; no host writes",
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PV2-6B nightly ESS smoke")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--i-have-stack-hold", action="store_true")
    parser.add_argument("--host-user", default=HOST_USER)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--night", default="", help="Calendar night YYYY-MM-DD (UTC)")
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument(
        "--record",
        action="store_true",
        help="Write the official soak ledger (live PASS/FAIL only)",
    )
    args = parser.parse_args(argv)

    dry = args.dry_run or not args.live
    night_id = (args.night or datetime.now(timezone.utc).date().isoformat()).strip()

    if args.live:
        try:
            require_live_consent(
                live=True,
                stack_hold=args.i_have_stack_hold,
                host_user=args.host_user,
            )
        except ConsentError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django

        django.setup()
        record = run_live_night(
            night_id=night_id,
            host_user=args.host_user,
            base=args.base,
        )
        if args.record:
            payload = record_night(record)
            SOAK_MD.write_text(render_soak_md(payload), encoding="utf-8")
        print(json.dumps(asdict(record), ensure_ascii=False, indent=2, default=str))
        return 0 if record.status == "PASS" else 1

    issues = catalog_issues()
    record = run_dry_night(night_id)
    print(json.dumps(asdict(record), ensure_ascii=False, indent=2, default=str))
    if issues:
        print("catalog issues: " + "; ".join(issues), file=sys.stderr)
        return 2
    if dry:
        print(
            "SOAKING — dry-run only. Live night needs STACK-HOLD, "
            f"{LIVE_ENV}=1, --live --i-have-stack-hold --host-user {HOST_USER}.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
