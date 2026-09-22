"""Operator-lane evidence for all Nibras governed processes (Chat·Plan·Run·consent).

JWT-driven (same cast as deep sim). Writes:
  docs/ops/SIM-QA-CHAT-AGENT/logs/SESSION-<stamp>-NIBRAS-OPERATOR.{md,json}

Usage:
  cd backend && ../.venv/bin/python manage.py simulate_nibras_operator_processes
  cd backend && ../.venv/bin/python manage.py simulate_nibras_operator_processes --skip-llm
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from ai.management.commands.simulate_nibras_pulse_processes import (
    CARBON_REFUSE,
    PROCESSES,
    Live,
    _chat,
    _load_pack,
    _plan,
    _staged_body_incomplete,
)
from people.models import Employee

EVIDENCE_DIR = Path(__file__).resolve().parents[4] / "docs" / "ops" / "SIM-QA-CHAT-AGENT" / "logs"


class Command(BaseCommand):
    help = "Operator Chat·Plan·Run·consent evidence for all Nibras processes"

    def add_arguments(self, parser):
        parser.add_argument("--skip-llm", action="store_true")
        parser.add_argument("--only", default="")

    def handle(self, *args, **options):
        skip_llm = options["skip_llm"]
        only = (options["only"] or "").strip().lower()
        stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        rows = []
        for pid in PROCESSES:
            if only and only not in pid:
                continue
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n══ operator {pid} ══"))
            pack = _load_pack(pid)
            if skip_llm:
                row = {"process_id": pid, "binary": "SKIPPED", "lanes": {}}
            else:
                row = self._operator_process(pid, pack)
            rows.append(row)
            self.stdout.write(f"  → {row['binary']}")

        payload = {
            "stamp": stamp,
            "wave": "nibras-processes-proper-operator",
            "canvas_pack": "nibras-processes-e2e-sim",
            "processes": rows,
            "summary": {
                "executed": len([r for r in rows if r["binary"] != "SKIPPED"]),
                "pass": sum(1 for r in rows if r["binary"] == "PASS"),
                "partial": sum(1 for r in rows if r["binary"] == "PARTIAL"),
                "fail": sum(1 for r in rows if r["binary"] == "FAIL"),
            },
        }
        jpath = EVIDENCE_DIR / f"SESSION-{stamp}-NIBRAS-OPERATOR.json"
        mpath = EVIDENCE_DIR / f"SESSION-{stamp}-NIBRAS-OPERATOR.md"
        jpath.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        mpath.write_text(self._md(payload), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {mpath}"))
        self.stdout.write(json.dumps(payload["summary"], indent=2))

    def _operator_process(self, pid: str, pack: dict) -> dict:
        live = Live("ahmed")
        if pid.startswith("leave"):
            live = Live("emp_1067")
        elif pid.startswith("loan"):
            live = Live("emp_1001")

        lanes = {}
        # Chat briefing ≠ nav
        q = (
            f"Explain the Nibras process `{pid}` end-to-end for an operator. "
            f"Do not invent emissions topics."
        )
        chat = _chat(live, q)
        reply = chat.get("reply") or ""
        nav = bool(re.search(r"would you like to open|which would you like to open", reply, re.I))
        refuse = bool(CARBON_REFUSE.search(reply))
        lanes["chat_brief"] = {
            "binary": "FAIL" if refuse or chat.get("error") else ("PARTIAL" if nav else "PASS"),
            "nav_shortcircuit": nav,
            "preview": reply[:280],
        }

        # Plan bind
        if pid.startswith("leave"):
            brief = f"Execute {pid} for myself using submit_my_leave. Consent before writes."
        elif pid.startswith("loan"):
            brief = f"Plan {pid} for myself using submit_my_loan. Never submit_my_leave."
        elif pid.startswith("payroll"):
            brief = (
                f"Plan {pid}: list payroll runs then compute/validate/commit via call_host_api."
            )
        elif pid.startswith("gosi"):
            brief = (
                f"Plan {pid} on a committed payroll run using generate_gosi_wps_sif, "
                f"validate_gosi_wps_sif, submit_gosi_wps_sif. Never submit_my_leave."
            )
        elif pid.startswith("attendance"):
            brief = (
                f"Plan {pid}: submit_my_attendance_permission (self-service). "
                f"Never submit_my_leave."
            )
        else:
            brief = (
                f"Plan {pid}: create_employee then update_employee to activate. "
                f"Never submit_my_leave."
            )
        plan = _plan(live, brief)
        apis = {
            (s.get("tool_args") or {}).get("api_name")
            for s in (plan.get("steps") or [])
            if (s.get("tool_args") or {}).get("api_name")
        }
        bind_ok = True
        if pid.startswith("loan") and "submit_my_leave" in apis:
            bind_ok = False
        if pid.startswith("employee") and "submit_my_leave" in apis:
            bind_ok = False
        if pid.startswith("gosi") and "submit_my_leave" in apis:
            bind_ok = False
        if pid.startswith("attendance") and "submit_my_leave" in apis:
            bind_ok = False
        if plan.get("http") not in (200, 201):
            bind_ok = False
        lanes["agent_plan"] = {
            "binary": "PASS" if bind_ok else "PARTIAL",
            "plan_id": plan.get("id"),
            "apis": sorted(a for a in apis if a),
            "http": plan.get("http"),
        }

        # Run + consent
        consent = {"binary": "PARTIAL", "notes": "no plan"}
        if plan.get("id") and plan.get("http") in (200, 201):
            pid_plan = plan["id"]
            live.post(f"/ai/plans/{pid_plan}/approve/")
            sse = live.sse(f"/ai/plans/{pid_plan}/run/", timeout=300)
            detail = live.get(f"/ai/plans/{pid_plan}/")
            plan2 = detail.json() if detail.ok else {}
            steps = plan2.get("steps") or []
            awaiting = next((s for s in steps if s.get("status") == "awaiting_approval"), None)
            evidence = {
                "sse_http": sse.get("http_status"),
                "plan_status": plan2.get("status"),
                "consent_api": ((awaiting or {}).get("tool_args") or {}).get("api_name"),
            }
            if awaiting is None:
                done = next((f for f in (sse.get("frames") or []) if f.get("type") == "done"), {})
                if done.get("status") in ("completed", "completed_with_gaps"):
                    consent = {
                        "binary": "PASS",
                        "notes": "completed without pending consent",
                        "evidence": evidence,
                    }
                else:
                    consent = {
                        "binary": "PARTIAL",
                        "notes": "no awaiting_approval",
                        "evidence": evidence,
                    }
            else:
                body = None
                if _staged_body_incomplete(awaiting):
                    api = ((awaiting.get("tool_args") or {}).get("api_name") or "")
                    if api == "create_employee":
                        org = Employee.objects.filter(org_unit__isnull=False).first()
                        from datetime import date

                        body = {
                            "employee_no": f"OP{timezone.now().strftime('%H%M%S')}",
                            "full_name": "Operator Hire",
                            "org_unit": org.org_unit_id if org else 1,
                            "join_date": date.today().isoformat(),
                            "basic_salary": "450.000",
                            "is_active": False,
                        }
                    elif api in ("submit_my_leave", "create_leave_record"):
                        from datetime import date, timedelta

                        start = date.today() + timedelta(days=100)
                        body = {
                            "leave_type": "annual",
                            "start_date": start.isoformat(),
                            "end_date": start.isoformat(),
                            "days": 1,
                            "note": "operator lane",
                        }
                    elif api == "create_attendance_permission":
                        from datetime import date, timedelta

                        emp = Employee.objects.filter(user__username="emp_1067").first()
                        if emp is None:
                            emp = Employee.objects.filter(is_active=True).first()
                        body = {
                            "employee": emp.pk if emp else 1,
                            "date": (date.today() + timedelta(days=25)).isoformat(),
                            "permission_type": "personal",
                            "hours": "2.00",
                            "notes": "operator lane",
                            "approved": False,
                        }
                    elif api == "submit_my_attendance_permission":
                        from datetime import date, timedelta

                        body = {
                            "date": (date.today() + timedelta(days=25)).isoformat(),
                            "permission_type": "personal",
                            "hours": "2.00",
                            "notes": "operator lane ESS",
                        }
                    elif api == "approve_attendance_permission":
                        body = {"approved": True}
                    elif api == "submit_my_loan":
                        from datetime import date, timedelta

                        start = (date.today().replace(day=1) + timedelta(days=32)).replace(day=1)
                        body = {
                            "loan_type": "emergency",
                            "principal": "80.000",
                            "interest_rate": "0",
                            "term_months": 3,
                            "start_date": start.isoformat(),
                        }
                payload = {"step_id": awaiting["step_id"]}
                if body:
                    payload["body"] = body
                conf = live.post(f"/ai/plans/{pid_plan}/steps/confirm/", payload)
                evidence["confirm_http"] = conf.status_code
                if conf.status_code == 404:
                    consent = {"binary": "FAIL", "notes": "confirm 404", "evidence": evidence}
                elif conf.status_code in (200, 201):
                    consent = {
                        "binary": "PASS",
                        "notes": "timeline consent confirmed",
                        "evidence": evidence,
                    }
                else:
                    consent = {
                        "binary": "PARTIAL",
                        "notes": f"confirm {conf.status_code}",
                        "evidence": evidence,
                    }
        lanes["operator_run"] = consent

        bins = [v.get("binary") for v in lanes.values()]
        if bins and all(b == "PASS" for b in bins):
            binary = "PASS"
        elif any(b == "FAIL" for b in bins):
            binary = "FAIL" if not any(b == "PASS" for b in bins) else "PARTIAL"
        elif any(b == "PARTIAL" for b in bins):
            binary = "PARTIAL"
        else:
            binary = "PASS"
        return {"process_id": pid, "binary": binary, "lanes": lanes}

    def _md(self, payload: dict) -> str:
        lines = [
            f"# SESSION {payload['stamp']} — Nibras Operator Chat·Plan·Run·consent",
            "",
            f"**Wave:** {payload.get('wave')} · **Canvas:** `{payload.get('canvas_pack')}`",
            f"**Summary:** {json.dumps(payload['summary'])}",
            "",
            "| Process | Rollup | Chat | Plan | Operator run |",
            "|---------|--------|------|------|--------------|",
        ]
        for r in payload["processes"]:
            lanes = r.get("lanes") or {}
            lines.append(
                "| `{pid}` | **{roll}** | {c} | {p} | {o} |".format(
                    pid=r["process_id"],
                    roll=r["binary"],
                    c=(lanes.get("chat_brief") or {}).get("binary"),
                    p=(lanes.get("agent_plan") or {}).get("binary"),
                    o=(lanes.get("operator_run") or {}).get("binary"),
                )
            )
        lines += ["", "## Detail", ""]
        for r in payload["processes"]:
            lines.append(f"### `{r['process_id']}` — {r['binary']}")
            for name, lane in (r.get("lanes") or {}).items():
                lines.append(f"- **{name}:** {lane.get('binary')} — {str(lane.get('notes') or lane.get('preview') or '')[:300]}")
            lines.append("")
        return "\n".join(lines)
