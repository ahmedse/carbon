"""Per-message tool digests (PV2-1C · Intelligence Contract §4.3 HistoryBlock).

A digest is a ≤ 200-char, scalar-only restatement of what a turn's tools
returned ("call_host_api get_my_loan_eligibility: eligible=true,
max_amount=8000, currency=SAR"), persisted on the assistant message so the
model can recall tool facts turns later without re-querying.

Never a raw payload:
  * only successful, non-staged tool results contribute;
  * only scalar leaves (bool / number / short string) are kept;
  * internal ids and restricted identifiers (national id, IBAN, secrets…) are
    dropped (RULE_23);
  * records carrying an ``org_unit_id`` outside the user's retrieval scope
    (``{"org_unit_ids": [...], "org_unit_id": n}`` — the same dict the S2
    applicability-first filter consumes) are dropped (RULE_20). With no scope,
    only unscoped records survive.

Pure function — no Django, no I/O.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable

DIGEST_MAX_CHARS = 200

_MAX_RECORDS_PER_TOOL = 3
_MAX_VALUE_CHARS = 40

_RECORD_LIST_KEYS = ("results", "rows", "items", "records", "entities", "data")

_RESTRICTED_KEY_RE = re.compile(
    r"password|passwd|secret|token|api_?key|credential|iban|swift|"
    r"national_?id|iqama|ssn|passport|bank_?account|account_?number|"
    r"card_?number|cvv|pin_?code|hash|salt",
    re.IGNORECASE,
)

_PLUMBING_KEYS = frozenset({
    "status_code", "requires_confirmation", "execution_id", "kind", "operation",
    "method", "endpoint", "reasoning", "confirmation_message", "action", "route",
    "error", "detail", "latency_ms", "tool_call_id", "self_heal",
})


def _parse(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw.strip() or None
    return raw


def _allowed_org_units(scope: dict | None) -> set[str]:
    if not isinstance(scope, dict):
        return set()
    allowed = {str(x) for x in scope.get("org_unit_ids") or [] if x is not None}
    if scope.get("org_unit_id") is not None:
        allowed.add(str(scope["org_unit_id"]))
    return allowed


def _record_in_scope(record: dict, allowed: set[str]) -> bool:
    org = record.get("org_unit_id", record.get("org_unit"))
    if isinstance(org, dict):
        org = org.get("id")
    if org is None:
        return True
    return str(org) in allowed


def _skip_key(key: str) -> bool:
    k = str(key).lower()
    return (
        k in _PLUMBING_KEYS
        or k == "id"
        or k.endswith("_id")
        or k.endswith("_ids")
        or bool(_RESTRICTED_KEY_RE.search(k))
    )


def _fmt_value(value: Any) -> str | None:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, str):
        text = " ".join(value.split())
        if not text:
            return None
        return text if len(text) <= _MAX_VALUE_CHARS else text[: _MAX_VALUE_CHARS - 1] + "…"
    return None


def _record_fields(record: dict, allowed: set[str]) -> list[str]:
    fields: list[str] = []
    for key, value in record.items():
        if _skip_key(key):
            continue
        if isinstance(value, dict):
            if not _record_in_scope(value, allowed):
                continue
            for child_key, child in value.items():
                if _skip_key(child_key):
                    continue
                text = _fmt_value(child)
                if text is not None:
                    fields.append(f"{child_key}={text}")
            continue
        if isinstance(value, list):
            continue
        text = _fmt_value(value)
        if text is not None:
            fields.append(f"{key}={text}")
    return fields


def _tool_label(item: dict) -> str:
    name = str(item.get("tool_name") or "tool")
    args = item.get("tool_args") or {}
    api_name = args.get("api_name") if isinstance(args, dict) else None
    return f"{name} {api_name}" if api_name else name


_PAYSLIP_IDENTITY_CODES = ("gross", "gosi", "loan_installment", "net")


def _line_type_code(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("code") or value.get("name") or "").strip().lower()
    return str(value or "").strip().lower()


def _fmt_amount(value: Any) -> str | None:
    text = _fmt_value(value)
    if text is None:
        return None
    try:
        number = float(text.replace(",", ""))
    except (TypeError, ValueError):
        return text
    if number == int(number):
        return str(int(number))
    return f"{number:g}"


def _compact_payslip_identity(data: Any) -> str | None:
    """One identity chunk: ``count=4, gross=6500, gosi=1200, …``.

    Default per-record digest is 200-char and drops net when four lines
    are present. Payslip recall needs the identity, not employee_name.
    """
    records: list[dict] = []
    if isinstance(data, list):
        records = [row for row in data if isinstance(row, dict)]
    elif isinstance(data, dict):
        raw = data.get("results")
        if not isinstance(raw, list):
            return None
        records = [row for row in raw if isinstance(row, dict)]
    else:
        return None
    lines: dict[str, str] = {}
    for row in records:
        code = _line_type_code(row.get("line_type"))
        if code not in _PAYSLIP_IDENTITY_CODES:
            continue
        amount = _fmt_amount(row.get("amount"))
        if amount is not None:
            lines[code] = amount
    if not lines:
        return None
    parts = [f"count={len(records)}"]
    for code in _PAYSLIP_IDENTITY_CODES:
        if code in lines:
            parts.append(f"{code}={lines[code]}")
    return ", ".join(parts)


def _nested_name(value: Any) -> str | None:
    if isinstance(value, dict):
        text = value.get("name") or value.get("full_name") or value.get("label")
        return str(text).strip() if text else None
    if isinstance(value, str) and value.strip():
        if " — " in value:
            return value.split(" — ", 1)[1].strip()
        return value.strip()
    return None


def _compact_profile_identity(data: Any) -> str | None:
    """One identity chunk for get_my_profile — not two colliding name= fields."""
    if not isinstance(data, dict) or isinstance(data.get("results"), list):
        return None
    emp = data.get("employee_no")
    if emp in (None, ""):
        return None
    if not (data.get("org_unit") or data.get("manager") or data.get("job_title")):
        return None
    parts = [f"employee_no={emp}"]
    dept = _nested_name(data.get("org_unit")) or data.get("org_unit_label") or data.get("department")
    if dept:
        parts.append(f"department={dept}")
    manager = _nested_name(data.get("manager")) or data.get("manager_label")
    if manager:
        parts.append(f"manager={manager}")
    title = data.get("job_title")
    if title:
        parts.append(f"job_title={title}")
    return ", ".join(str(p) for p in parts)


def _digest_payload(data: Any, allowed: set[str]) -> list[str]:
    """Return one ``k=v, …`` chunk per in-scope record."""
    if isinstance(data, dict) and "data" in data and "status_code" in data:
        data = data["data"]
    compact = _compact_payslip_identity(data)
    if compact:
        return [compact]
    profile = _compact_profile_identity(data)
    if profile:
        return [profile]

    records: list[dict] = []
    header: list[str] = []
    if isinstance(data, list):
        records = [r for r in data if isinstance(r, dict)]
    elif isinstance(data, dict):
        list_key = next(
            (k for k in _RECORD_LIST_KEYS if isinstance(data.get(k), list)), None
        )
        if list_key is not None:
            records = [r for r in data[list_key] if isinstance(r, dict)]
            if _record_in_scope(data, allowed):
                header = _record_fields(
                    {k: v for k, v in data.items() if k != list_key}, allowed
                )
        else:
            records = [data]
    elif isinstance(data, str):
        text = _fmt_value(data)
        return [text] if text else []

    chunks: list[str] = []
    if header:
        chunks.append(", ".join(header))
    for record in records:
        if len(chunks) >= _MAX_RECORDS_PER_TOOL:
            break
        if not _record_in_scope(record, allowed):
            continue
        fields = _record_fields(record, allowed)
        if fields:
            chunks.append(", ".join(fields))
    return chunks


def build_tool_digest(
    completed_tools: Iterable[dict] | None,
    scope: dict | None,
    max_chars: int = DIGEST_MAX_CHARS,
) -> str:
    """Build the ≤ ``max_chars`` digest for one turn's completed tools."""
    allowed = _allowed_org_units(scope)
    parts: list[str] = []
    for item in completed_tools or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        data = _parse(item.get("result"))
        if data is None:
            continue
        if isinstance(data, dict) and (
            data.get("requires_confirmation") or data.get("action") == "chat_handoff"
        ):
            continue
        chunks = _digest_payload(data, allowed)
        if chunks:
            parts.append(f"{_tool_label(item)}: " + "; ".join(chunks))

    digest = " | ".join(parts)
    if len(digest) > max_chars:
        digest = digest[: max_chars - 1].rstrip(" ,;|") + "…"
    return digest
