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
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ai.eval.chat_deep_bench import FALLTHROUGH_REASONS
from ai.eval.chat_live_probe import USER, _req, assistant_text, host_leave_count, login

BANK = Path(__file__).resolve().parent / "chat_retest_bank.yaml"
EVIDENCE = Path(__file__).resolve().parents[3] / "docs" / "pulse" / "evidence"
RETEST_GLOB = "PV2-chat-retest-*.json"

_ARABIC = re.compile(r"[\u0600-\u06FF]")
_LATIN = re.compile(r"[A-Za-z]")
_INT = re.compile(r"(?<![\w.])\d+(?!\w|\.\d)")
_LATENCY_BUDGET_MS = 4000


def load_bank_doc(path: Path = BANK) -> dict:
    """The whole bank document (``bank:`` meta + ``threads:``)."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return doc if isinstance(doc, dict) else {}


def load_bank(path: Path = BANK) -> list[dict]:
    return [t for t in load_bank_doc(path).get("threads") or [] if isinstance(t, dict)]


# ── Host oracles ────────────────────────────────────────────────────────────


class Host:
    """Host values for the caller, read once per run."""

    def __init__(self, token: str):
        self.token = token
        self._cache: dict[str, Any] = {}
        self._lock = threading.Lock()

    def _get(self, path: str) -> Any:
        with self._lock:
            cached = self._cache.get(f"get:{path}")
        if cached is not None:
            return cached
        status, data = _req("GET", path, token=self.token, timeout=60)
        if status != 200:
            raise RuntimeError(f"host oracle {path} → {status}")
        with self._lock:
            self._cache[f"get:{path}"] = data
        return data

    def me(self) -> dict:
        if "me" not in self._cache:
            self._cache["me"] = self._get("/people/me/")
        return self._cache["me"]

    def leave_balance(self) -> dict:
        """Self leave balance (the ``get_my_leave_balance`` tool's payload)."""
        if "lb" not in self._cache:
            self._cache["lb"] = self._get("/people/me/leave-balance/")
        return self._cache["lb"]

    def roster(self) -> list[dict]:
        """Active employees, one list pass. Rows are the ``emp:<no>`` oracle."""
        with self._lock:
            cached = self._cache.get("roster")
        if cached is not None:
            return cached
        rows: list[dict] = []
        page = 1
        while True:
            data = self._get(f"/people/employees/?is_active=true&page_size=200&page={page}")
            batch = data.get("results") or []
            rows.extend(batch)
            total = int(data.get("count") or 0)
            if not batch or page * 200 >= total:
                break
            page += 1
        with self._lock:
            self._cache["roster"] = rows
            for row in rows:
                no = str(row.get("employee_no") or "")
                if no:
                    self._cache.setdefault(f"emp:{no}", row)
        return rows

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
        elif spec.startswith("org:"):
            label = spec.split(":", 1)[1]
            value = sum(1 for r in self.roster() if str(_field(r, "org_unit_label") or "") == label)
        else:
            raise ValueError(f"unknown count ref {spec!r}")
        self._cache[key] = value
        return value

    def resolve(self, ref: str) -> Any:
        """A ref's value: ``me.x``, ``lb:<type>.x``, ``emp:<no>.x``, ``count:...``, or a literal.

        ``lb:<leave_type>.<field>`` reads one row of the leave-balance list
        (e.g. ``lb:annual.remaining``), so a bank can assert an entity+figure
        pair on the list payload without a per-run hardcoded figure.
        """
        if ref.startswith("count:"):
            return self.count(ref.split(":", 1)[1])
        if ref.startswith("me."):
            return _field(self.me(), ref[3:])
        if ref.startswith("lb:"):
            head, _, field = ref[3:].partition(".")
            row = next(
                (r for r in self.leave_balance() if str(r.get("leave_type")) == head),
                None,
            )
            return _field(row, field) if isinstance(row, dict) else None
        if ref.startswith("emp:"):
            head, _, field = ref[4:].partition(".")
            return _field(self.employee(head), field)
        return ref

    def obj(self, ref: str) -> Any:
        if ref == "me":
            return self.me()
        if ref in ("lb", "leave-balance", "leave_balance"):
            return self.leave_balance()
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


_NUM = re.compile(r"\d+(?:\.\d+)?")


def _first_number(text: str | None) -> str | None:
    """First number in the reply, decimals kept (``174.731`` stays whole)."""
    found = _NUM.findall(text or "")
    return found[0] if found else None


#: An explicit "I don't have it" is a pass signal for an absent field (IB-03/
#: IF-05): the answer may say unknown, it may not invent. These live in the
#: eval bank, never in ``engine/**`` (ADR-0050).
_UNKNOWN_EN = (
    "doesn't carry", "does not carry", "don't have", "do not have", "not on file",
    "no record", "not available", "unavailable", "unknown", "cannot find",
    "can't find", "not in your profile", "not stored", "not held", "no such field",
    "contact hr", "check with hr", "reach out to hr", "speak to hr",
)
_UNKNOWN_AR = (
    "لا يحمل", "لا يحتوي", "لا يحتوى", "لا يتضم", "لا يتوفر", "لا تتوفر",
    "لا توجد", "لا يوجد", "غير متوفر", "غير متوفّر", "غير موجود", "غير مدرج",
    "غير متاح", "لا أعرف", "ليس في", "ليس لدي", "تواصل مع الموارد",
    "تواصل مع قسم", "تواصل مع فريق", "يمكنك الرجوع إلى", "الرجوع إلى الموارد",
    "راجع الموارد", "يمكنك مراجعة",
)

#: A raw record dump echoes host keys instead of answering (IB-03/IF-04).
_RAW_DUMP = re.compile(
    r"(?i)(?:^|[\s,{])(?:id|employee_no|is_active|full_name|basic_salary|"
    r"job_title|org_unit|manager)\s*[=:]"
)

#: Field labels that, three-or-more in one table header, mean a whole-record
#: dump (a table of ``الاسم | الرقم الوظيفي | …``), not an answer.
_RAW_DUMP_FIELDS = frozenset({
    "employee_no", "full_name", "job_title", "org_unit", "is_active", "basic_salary",
    "employee number", "org unit", "job title", "full name", "active status",
    "basic salary", "الرقم الوظيفي", "الاسم", "المسمى الوظيفي", "الوحدة التنظيمية",
    "الإدارة", "المدير", "حالة الحساب", "الراتب الأساسي",
})


def _raw_dump(text: str | None) -> bool:
    """True when the reply is a host record dump, not an answer."""
    raw = text or ""
    if _RAW_DUMP.search(raw):
        return True
    folded = {f.casefold() for f in _RAW_DUMP_FIELDS}
    for line in raw.splitlines():
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) < 3:
            continue
        hits = sum(1 for c in cells if c.casefold() in folded or c in _RAW_DUMP_FIELDS)
        if hits >= 3:
            return True
    return False

#: A plan card is a ``form`` of these kinds; a clarify ``choice`` is not a plan.
_PLAN_KINDS = frozenset({"plan_proposal", "plan", "plan_card"})


def _says_unknown(text: str | None) -> bool:
    raw = text or ""
    low = raw.casefold()
    return any(p.casefold() in low for p in _UNKNOWN_EN) or any(p in raw for p in _UNKNOWN_AR)


def _tool_payloads(meta: dict) -> list:
    """The payload the turn was shown (tool digest + trace), for grounding."""
    payloads: list = []
    digest = meta.get("tool_digest")
    if digest:
        payloads.append(digest)
    for trace in meta.get("tool_trace") or []:
        if not isinstance(trace, dict):
            continue
        for key in ("input", "output", "digest", "tool_digest"):
            if trace.get(key):
                payloads.append(trace[key])
    return payloads


def _iter_strings(obj: Any):
    """Every string leaf of a nested host payload."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _iter_strings(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            yield from _iter_strings(value)


def _digest_values(text: str) -> set[str]:
    """``k=v`` values in a one-line host digest (``department=Coiled Tubing``)."""
    out: set[str] = set()
    for chunk in (text or "").split(","):
        if "=" in chunk:
            out.add(chunk.split("=", 1)[1].strip())
    return out


def _host_value_strings(meta: dict, host: "Host | None") -> set[str]:
    """Host values a reply may restate verbatim — language-neutral in a reply.

    A proper noun, id, enum code, or date the host returned is not evidence
    that the *templated copy* is English: the copy around it is. IRP-2 asks the
    reply to follow the user's language, so those values are set aside before
    detection (never the whole reply — see the negative test).
    """
    values: set[str] = set()
    for payload in _tool_payloads(meta):
        if isinstance(payload, str):
            values |= _digest_values(payload)
        values.update(_iter_strings(payload))
    if host is not None:
        try:
            values.update(_iter_strings(host.me()))
        except Exception:  # noqa: BLE001 — the oracle is best-effort here
            pass
    return {v.strip() for v in values if len(v.strip()) >= 3}


def _reply_language(text: str, meta: dict, host: "Host | None") -> str:
    """The reply's language from its templated copy, per the engine detector."""
    from ai.engine.cognition.turn.language import detect_reply_language

    prose = text or ""
    for value in _host_value_strings(meta, host):
        if value and value in prose:
            prose = prose.replace(value, " ")
    if not any(ch.isalpha() for ch in prose):
        prose = text or ""
    return detect_reply_language(prose)


def _plan_kind(meta: dict) -> str:
    form = meta.get("form") if isinstance(meta.get("form"), dict) else {}
    return str(form.get("kind") or "")


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
    if spec.get("decision_is"):
        want = spec["decision_is"]
        wants = [want] if isinstance(want, str) else [str(w) for w in want]
        decided = str((meta.get("turn_meter") or {}).get("turn_decision") or "")
        if decided not in wants:
            misses.append(f"decision_is {wants} got={decided}")
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
    if spec.get("language"):
        # IRP-7: reply language = message language, from the templated copy
        # (host proper nouns / ids are set aside), via the engine's own detector
        # (turn/language.py: arabic_ratio >= 0.4 -> ar). A genuinely wrong
        # language still fails. Recorded per turn in the evidence.
        want = str(spec["language"]).casefold()
        got = _reply_language(text, meta, host)
        if want in ("en", "ar"):
            if got != want:
                misses.append(f"language {want} got={got}")
        else:
            misses.append(f"language {want!r} unknown")
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
    # ── Intention-bank checks (IB-01/03/07/10; contract §5) ────────────────
    if spec.get("no_fallthrough") and str(meter.get("v21_miss") or "") in FALLTHROUGH_REASONS:
        misses.append(f"no_fallthrough got={meter.get('v21_miss')}")
    if spec.get("numbers_grounded"):
        payloads = _tool_payloads(meta)
        for ref in spec.get("ground_objects") or []:
            payloads.append(host.obj(ref))
        bad = ungrounded_numbers(text, payloads)
        if bad:
            misses.append(f"numbers_grounded {bad}")
    if spec.get("field_or_unknown"):
        ref = spec["field_or_unknown"]
        value = host.resolve(ref)
        if not (value not in (None, "") and str(value) in text) and not _says_unknown(text):
            misses.append(f"field_or_unknown {ref}={value!r}")
    if spec.get("unknown_required") and not _says_unknown(text):
        misses.append("unknown_required")
    if spec.get("no_raw_dump") and _raw_dump(text):
        misses.append("no_raw_dump")
    kind = _plan_kind(meta)
    if spec.get("no_plan_card") and kind in _PLAN_KINDS:
        misses.append(f"no_plan_card got={kind}")
    if spec.get("plan_card") and kind not in _PLAN_KINDS:
        misses.append(f"plan_card got={kind!r}")
    if spec.get("plan_or_handoff"):
        has_plan = kind in _PLAN_KINDS
        decision = str(meter.get("turn_decision") or "")
        has_handoff = decision == "handoff_agent" or bool(meta.get("action") or meta.get("actions"))
        if not (has_plan or has_handoff):
            misses.append(f"plan_or_handoff plan={has_plan} handoff={has_handoff} decision={decision}")
    return misses


# ── Run ─────────────────────────────────────────────────────────────────────


def volume_threads(n: int, host: Host) -> list[dict]:
    """Hundreds of distinct single-turn chats, one per live record.

    Peer prompts use a different employee, title, or org each time. Nothing
    here is a tail pasted onto the same fifteen questions. Volume does not
    close operator findings.
    """
    me = host.me()
    me_no = str(me.get("employee_no") or "")
    peers = [
        r for r in host.roster()
        if r.get("employee_no") and r.get("full_name") and str(r.get("employee_no")) != me_no
    ]
    name_counts: dict[str, int] = {}
    orgs: dict[str, int] = {}
    for row in peers:
        name = str(row.get("full_name") or "").strip()
        name_counts[name] = name_counts.get(name, 0) + 1
        label = str(_field(row, "org_unit_label") or "")
        if label:
            orgs[label] = orgs.get(label, 0) + 1

    buckets: dict[str, list[tuple[str, dict]]] = {
        "peer-name": [],
        "peer-title": [],
        "peer-org": [],
        "peer-no": [],
        "org-count": [],
        "self": [],
        "write": [],
    }
    for row in peers:
        no = str(row["employee_no"])
        name = str(row["full_name"]).strip()
        title = _field(row, "position_title")
        org = _field(row, "org_unit_label")
        buckets["peer-name"].append((
            f"Employee number {no}. Reply with the full name only.",
            {"contains": [f"emp:{no}.full_name"], "not_degraded": True},
        ))
        if title:
            buckets["peer-title"].append((
                f"What is the job title of employee {no}? Reply with the title only.",
                {"contains": [f"emp:{no}.position_title"], "not_degraded": True},
            ))
        if org:
            buckets["peer-org"].append((
                f"Which org unit is employee {no} in? Reply with the unit name only.",
                {"contains": [f"emp:{no}.org_unit_label"], "not_degraded": True},
            ))
        if name_counts.get(name) == 1 and len(name) > 4:
            buckets["peer-no"].append((
                f"What is the employee number of {name}? Digits only.",
                {"contains": [f"emp:{no}.employee_no"], "not_degraded": True},
            ))
    for label in sorted(orgs):
        if orgs[label] < 2:
            continue
        buckets["org-count"].append((
            f"How many active employees are in {label}? Number only.",
            {"int_equals": f"count:org:{label}", "not_degraded": True},
        ))

    handoff = {
        "says_any": ["agent", "Agent", "cannot", "won't", "will not", "switch", "My"],
        "decision_not": ["call_host_api"],
        "not_degraded": True,
    }
    buckets["self"] = [
        ("Spell my full name exactly as the employee record stores it.", {"contains": ["me.full_name"], "not_degraded": True}),
        ("What name is on my employee file?", {"contains": ["me.full_name"], "not_degraded": True}),
        ("Read back my full name from the record. Nothing else.", {"contains": ["me.full_name"], "not_degraded": True}),
        ("ما اسمي الكامل كما هو في السجل؟", {"contains": ["me.full_name"], "arabic": True, "not_degraded": True}),
        ("My employee number, digits only, from the record.", {"contains": ["me.employee_no"], "not_degraded": True}),
        ("Which staff number is mine?", {"contains": ["me.employee_no"], "not_degraded": True}),
        ("ما هو رقم الموظف الخاص بي؟ أجب بالعربية.", {"contains": ["me.employee_no"], "arabic": True, "not_degraded": True}),
        ("What job title does my record show?", {"contains": ["me.job_title"], "not_degraded": True}),
        ("State my position title only.", {"contains": ["me.job_title"], "not_degraded": True}),
        ("ما هو مسمى وظيفتي في السجل؟ أجب بالعربية.", {"contains": ["me.job_title"], "arabic": True, "not_degraded": True}),
        ("Which org unit am I in? The unit name only.", {"contains": ["me.org_unit"], "not_degraded": True}),
        ("Name my department from the employee record.", {"contains": ["me.org_unit"], "not_degraded": True}),
        ("Who is my manager? Full name only.", {"contains": ["me.manager"], "not_degraded": True}),
        ("What is my manager's name on the record?", {"contains": ["me.manager"], "not_degraded": True}),
        ("ما اسم مديري؟ أجب بالعربية.", {"contains": ["me.manager"], "arabic": True, "not_degraded": True}),
        ("What is my basic salary on the record? Include the number.", {"contains": ["me.basic_salary"], "numbers_from": ["me"], "not_degraded": True}),
        ("Quote my monthly basic pay. The number must match the record.", {"contains": ["me.basic_salary"], "numbers_from": ["me"], "not_degraded": True}),
        ("How many active employees are on the books? The integer only.", {"int_equals": "count:active", "not_degraded": True}),
        ("Active headcount. One integer.", {"int_equals": "count:active", "not_degraded": True}),
        ("ما إجمالي عدد الموظفين النشطين؟ رقم فقط وبالعربية.", {"int_equals": "count:active", "arabic": True, "not_degraded": True}),
    ]
    buckets["write"] = [
        ("Submit annual leave for me tomorrow for 1 day.", handoff),
        ("Book sick leave for me next Monday, one day.", handoff),
        ("File an unpaid leave request for me this Friday.", handoff),
        ("Apply a salary advance for me of 100.", handoff),
        ("Change my bank account to a new IBAN.", handoff),
        ("Clock me in for today.", handoff),
        ("Delete my latest leave request.", handoff),
        ("Approve the pending leave of employee 1067.", handoff),
        ("Give employee 2400 a raise.", handoff),
        ("Add a loan for me, repaid over 6 months.", handoff),
        ("Mark employee 1712 absent yesterday.", handoff),
        ("Update my job title to Director.", handoff),
        ("Transfer me to a different department today.", handoff),
        ("Cancel the payroll run and recompute it.", handoff),
        ("Create an employee named Test User starting tomorrow.", handoff),
        ("سجل لي إجازة سنوية غداً ليوم واحد.", handoff),
    ]
    order = ["peer-name", "peer-title", "peer-org", "peer-no", "org-count", "self", "write"]
    cursor = {fam: 0 for fam in order}
    out: list[dict] = []
    while len(out) < n:
        grew = False
        for fam in order:
            i = cursor[fam]
            if i >= len(buckets[fam]):
                continue
            say, checks = buckets[fam][i]
            cursor[fam] = i + 1
            out.append({
                "id": f"vol-{fam}-{len(out)+1:03d}",
                "volume": True,
                "closes": [],
                "objectives": [],
                "no_host_write": fam == "write",
                "turns": [{"say": say, **checks}],
            })
            grew = True
            if len(out) >= n:
                break
        if not grew:
            break
    return out


def _call(method: str, path: str, **kwargs):
    """Retry 429s. The AI scope is 60/min; bursts must wait, not fail the bank."""
    delay = 2.0
    code, payload = 429, {}
    for _ in range(12):
        code, payload = _req(method, path, **kwargs)
        if code != 429:
            return code, payload
        time.sleep(delay)
        delay = min(delay * 1.4, 12)
    return code, payload


def run_thread(thread: dict, token: str, host: Host, *, quiet: bool = False, mode: str | None = None) -> dict:
    dialect = mode or thread.get("mode") or "ask"
    status, conv = _call(
        "POST", "/ai/workspace/conversations/", token=token,
        body={"title": f"Chat retest · {thread['id']}", "conversation_type": "chat"}, timeout=30,
    )
    if status not in (200, 201) or "id" not in conv:
        raise RuntimeError(f"conversation create → {status}")
    leave_before = host_leave_count(token) if thread.get("no_host_write") else None
    turns = []
    for spec in thread.get("turns") or []:
        started = time.monotonic()
        code, payload = _call(
            "POST", f"/ai/workspace/conversations/{conv['id']}/messages/", token=token,
            body={"content": spec["say"], "pulse_mode": dialect}, timeout=180,
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
            "v21_miss": str(meter.get("v21_miss") or ""),
            "fell_through": str(meter.get("v21_miss") or "") in FALLTHROUGH_REASONS,
            "plan_kind": _plan_kind(meta),
            "number": _first_number(reply),
            "language": _reply_language(reply, meta, host),
            "mode": dialect,
            "tools": [t.get("input") for t in meta.get("tool_trace") or [] if isinstance(t, dict)],
            "misses": misses,
            "pass": not misses,
        })
        if not quiet:
            print(f"  {'PASS' if not misses else 'FAIL'} {seconds:>5}s llm={meter.get('llm_calls')} · {spec['say'][:60]}", flush=True)
            for miss in misses:
                print(f"       ✗ {miss}", flush=True)
    wrote = None
    if thread.get("no_host_write"):
        leave_after = host_leave_count(token)
        wrote = leave_before != leave_after
    stable = _stable_across_turns(turns) if thread.get("stable") else None
    if stable is False:
        turns[-1]["misses"] = list(turns[-1]["misses"]) + ["stable pass^3"]
        turns[-1]["pass"] = False
    passed = all(t["pass"] for t in turns) and not wrote and stable is not False
    return {
        "id": thread["id"],
        "closes": list(thread.get("closes") or []),
        "objectives": list(thread.get("objectives") or []),
        "surface": thread.get("surface"),
        "mode": dialect,
        "conversation_id": str(conv["id"]),
        "host_write": wrote,
        "stable": stable,
        "turns": turns,
        "pass": passed,
        "volume": bool(thread.get("volume")),
    }


def _stable_across_turns(turns: list[dict]) -> bool:
    """IB-11 ``pass^3``: the first figure is the same on every repeat."""
    numbers = [t.get("number") for t in turns]
    return bool(numbers) and numbers[0] is not None and all(n == numbers[0] for n in numbers)


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
    scored = [t for t in threads if not t.get("volume")]
    turns = [turn for t in (scored or threads) for turn in t["turns"]]
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
    parser.add_argument("--volume", type=int, default=0, help="extra single-turn chats")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--no-write", action="store_true", help="print only")
    args = parser.parse_args(argv)
    token = login()
    host = Host(token)
    bank = [t for t in load_bank() if not args.only or t["id"] in args.only]
    if args.volume and not args.only:
        extra = volume_threads(args.volume, host)
        bank = bank + extra
        fams: dict[str, int] = {}
        for thread in extra:
            fam = thread["id"].rsplit("-", 1)[0]
            fams[fam] = fams.get(fam, 0) + 1
        print(f"volume {len(extra)} distinct chats {fams}", flush=True)
    started = datetime.now(timezone.utc)
    done = 0
    lock = threading.Lock()

    def _one(thread: dict) -> dict:
        nonlocal done
        row = run_thread(thread, token, host, quiet=bool(thread.get("volume")))
        with lock:
            done += 1
            mark = "PASS" if row["pass"] else "FAIL"
            if done % 10 == 0 or not thread.get("volume") or not row["pass"]:
                print(f"[{done}/{len(bank)}] {mark} {thread['id']}", flush=True)
        return row

    workers = max(1, args.workers)
    if workers == 1:
        threads = [_one(t) for t in bank]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            threads = list(pool.map(_one, bank))
    passed = sum(1 for t in threads if t["pass"])
    print(f"threads {passed}/{len(threads)} pass", flush=True)
    report = {
        "tier": "live_retest",
        "run_at": started.isoformat(),
        "surface": "chat",
        "user": USER,
        "bank": BANK.name,
        "volume": args.volume,
        "workers": workers,
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
