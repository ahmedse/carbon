"""Render / weather / synthesis helpers extracted from runner (L7)."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import V


import logging
import re

from ai.engine.core.config import get_settings
from ai.engine.core.resolution import payload_status

logger = logging.getLogger("pulse.cognition.turn.runner_render")

_CHART_IMAGE_KEYS = T("turn/runner_render.py::_CHART_IMAGE_KEYS")


def _redact_payload_for_model(data, chart_seen: list[bool]):
    """Drop binary and source from what the synthesis model is allowed to see.

    A chart image is a fact (``chart_image.present``). The bytes and the
    sandbox source are not: feeding them in makes the model paste code or
    deny that it can chart.
    """
    if isinstance(data, dict):
        out = {}
        for key, value in data.items():
            if key in _CHART_IMAGE_KEYS and isinstance(value, str) and len(value) > 40:
                chart_seen.append(True)
                out["chart_image"] = {"present": True, "bytes": len(value)}
            elif (
                key == "code"
                and isinstance(value, str)
                and (len(value) > 80 or "import " in value or "\ndef " in value)
            ):
                out["code"] = "omitted"
            else:
                out[key] = _redact_payload_for_model(value, chart_seen)
        return out
    if isinstance(data, list):
        return [_redact_payload_for_model(item, chart_seen) for item in data]
    return data


def _payload_has_chart_image(result) -> bool:
    import json as _json

    data = result
    if isinstance(result, str):
        try:
            data = _json.loads(result)
        except (TypeError, ValueError):
            return False
    seen: list[bool] = []
    _redact_payload_for_model(data, seen)
    return bool(seen)


def _draft_contradicts_chart(draft: str) -> bool:
    """Model text that denies a chart the tool already produced, or pastes the sandbox source."""
    low = (draft or "").casefold()
    if "import matplotlib" in low or "plt." in draft or "```" in draft:
        return True
    return ("cannot" in low or "can't" in low or "can not" in low) and (
        "chart" in low or "graph" in low or "visual" in low
    )


def _render_tool_results_for_synthesis(
    completed_tools: list[dict],
    max_chars: int = 20000,
) -> str:
    """Render executed tool results as readable JSON for the synthesis LLM.

    Unwraps the host envelope ``{"status_code": 200, "data": {...}}`` and
    surfaces the inner payload, capping at ``max_chars`` to bound token cost.
    List payloads record their total row count so the model can still answer
    "how many" even when the rendered rows are truncated.
    """
    import json as _json

    sections: list[str] = []
    used = 0
    for tr in completed_tools:
        name = tr.get("tool_name", "unknown")
        raw = tr.get("result")

        data = raw
        if isinstance(raw, str):
            try:
                data = _json.loads(raw)
            except (TypeError, ValueError):
                data = raw

        # Unwrap the host executor envelope — keep authz signals on the payload
        # so synthesis never paraphrases CBAC deny as "no data" (B5).
        if isinstance(data, dict) and "status_code" in data and "data" in data:
            authz_meta = {
                k: data[k]
                for k in (
                    "unauthorized", "capability", "message",
                    "unauthorized_fields", "status_code",
                )
                if k in data and data[k] is not None
            }
            inner = data["data"]
            if authz_meta and isinstance(inner, dict):
                data = {**inner, **{k: v for k, v in authz_meta.items() if k not in inner}}
            elif authz_meta:
                data = {"data": inner, **authz_meta}
            else:
                data = inner

        chart_seen: list[bool] = []
        data = _redact_payload_for_model(data, chart_seen)

        if isinstance(data, dict) and data.get("unauthorized"):
            deny = {
                "unauthorized": True,
                "capability": data.get("capability"),
                "message": data.get("message"),
                "unauthorized_fields": data.get("unauthorized_fields"),
                "status_code": data.get("status_code"),
            }
            header = f"### {name}\n"
            body = _json.dumps(deny, ensure_ascii=False, indent=2, default=str)
            section = header + body
            if used + len(section) > max_chars:
                remaining = max_chars - used
                section = section[:remaining] + "\n…(truncated)"
            sections.append(section)
            used += len(section)
            if used >= max_chars:
                break
            continue

        list_payload = None
        list_key = None
        if isinstance(data, dict):
            for key in ("results", "items", "rows"):
                if key in data and isinstance(data[key], list):
                    list_payload = data[key]
                    list_key = key
                    break

        header = f"### {name}\n"
        if chart_seen:
            header += (
                "FACT: a chart image was produced and is already shown to the user. "
                "Acknowledge it in one sentence. Do not claim you cannot create charts. "
                "Do not paste code or base64.\n"
            )
        if list_payload is not None:
            header += f"(total rows: {len(list_payload)})\n"
            body = _json.dumps(list_payload, ensure_ascii=False, default=str)
        else:
            body = _json.dumps(data, ensure_ascii=False, indent=2, default=str)

        section = header + body
        if used + len(section) > max_chars:
            remaining = max_chars - used
            section = section[:remaining] + "\n…(truncated)"
        sections.append(section)
        used += len(section)
        if used >= max_chars:
            break

    return "\n\n".join(sections)

# Delivery (cognitive-intent) axis — how the user wants the answer DELIVERED,
# distinct from WHICH endpoint. Maps the intent classifier's `delivery` value
# to (a) the S3 directive phrase and (b) the GAP-W9 synthesis guidance.
_DELIVERY_INJECTION = T("turn/runner_render.py::_DELIVERY_INJECTION")

_DELIVERY_SYNTHESIS = T("turn/runner_render.py::_DELIVERY_SYNTHESIS")

def _no_match_hints(no_matches: list[dict]) -> list[str]:
    """Extract unique, non-empty hints from ``no_match`` tool results."""
    import json as _json

    hints: list[str] = []
    for tr in no_matches or []:
        raw = tr.get("result")
        data = raw
        if isinstance(data, str):
            try:
                data = _json.loads(data)
            except (TypeError, ValueError):
                data = raw
        if isinstance(data, dict) and "status_code" in data and "data" in data:
            data = data["data"]
        if not isinstance(data, dict):
            continue
        hint = str(data.get("hint") or "").strip() or str(data.get("reason") or "").strip()
        if hint and hint not in hints:
            hints.append(hint)
    return hints

async def _normalize_weather_location(
    *,
    instance_id: str,
    conversation_id: str,
    original_question: str,
    user_reply: str,
    conversation_history: list[dict] | None = None,
    model: str | None = None,
    user_info: dict | None = None,
    instance_config: dict | None = None,
    language: str = "",
    state=None,
) -> str:
    """LLM-normalize a location answer into a geocoder-ready ``City, Country``.

    Open-Meteo's keyless geocoder is an exact-match gazetteer: it fails on
    typos ("alamien") and region names ("north coast egypt"). This uses the
    LLM's geographic knowledge — *grounded in the conversation so far* — to
    resolve the user's short reply to the exact place they meant. The most
    important context is the assistant's own prior clarifying question (which
    typically listed the candidate cities the user is now choosing between),
    so recent turns are threaded into the prompt. Corrects spelling and
    resolves a region to its most prominent city. Falls back to the raw reply
    on any failure (never blocks the turn).
    """
    from ai.engine.cognition.context_pack import (
        TASK_WEATHER_LOCATION,
        build_context_pack,
    )
    from ai.engine.llm.router import route_chat

    # Thread the recent turns (the pending question + the assistant's
    # clarification with its offered candidates) so the model resolves the
    # reply IN CONTEXT instead of guessing in a vacuum.
    transcript_lines: list[str] = []
    for turn in (conversation_history or [])[-6:]:
        role = (turn.get("role") or "").strip() or "user"
        content = (turn.get("content") or "").strip()
        if content:
            transcript_lines.append(f"{role}: {content}")
    transcript = "\n".join(transcript_lines)

    user_parts = []
    if transcript:
        user_parts.append(f"Conversation so far:\n{transcript}")
    user_parts.append(f"Original weather question: {original_question}")
    user_parts.append(f"User's location answer: {user_reply}")
    user_parts.append("Canonical 'City, Country':")
    pack = build_context_pack(
        state,
        surface="chat",
        stage="weather_normalize",
        user_info=user_info,
        instance_config=instance_config,
        conversation_history=conversation_history,
        language=language,
        task_body=TASK_WEATHER_LOCATION,
        user_body="\n".join(user_parts),
        include_knowledge=False,
        include_memory=False,
        include_history=False,
    )

    try:
        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"geo-{conversation_id}",
            messages=[
                {"role": "system", "content": pack.system_prompt()},
                {"role": "user", "content": pack.user_prompt()},
            ],
            temperature=0.0,
            model=model,
            tools=None,
        )
    except Exception:
        logger.warning("Weather location normalization failed", exc_info=True)
        return user_reply

    text = (result.get("content") or "").strip().splitlines()[0].strip()
    text = text.strip(" .\"'`")
    # Sanity guard: a place name is short. Anything sentence-like → keep raw.
    if not text or len(text) > 60:
        return user_reply
    return text

def _weather_location_fallback(weather_extractor, question: str) -> str:
    """Return the host's deterministic location extractor result.

    When no host extractor is injected (or it raises), return the raw question
    unchanged — a safe no-op that never blocks the turn.
    """
    if weather_extractor is None:
        return question
    fn = getattr(weather_extractor, "extract_weather_location", None)
    if fn is None:
        return question
    try:
        return fn(question)
    except Exception:  # noqa: BLE001 - fallback must never raise
        return question

async def _normalize_weather_question(
    *,
    instance_id: str,
    conversation_id: str,
    question: str,
    conversation_history: list[dict] | None = None,
    model: str | None = None,
    weather_extractor=None,
    user_info: dict | None = None,
    instance_config: dict | None = None,
    language: str = "",
    state=None,
) -> str:
    """LLM-extract the canonical ``City, Country`` from a FULL weather question.

    The question can carry a greeting ("hi"), a misspelling ("toay"), a region
    name ("north cost egypt"), or a trailing advisory sub-question ("is it
    suitable for beach swimming?"). The LLM's geographic knowledge resolves all
    of that to the single place the user means. Falls back to the host's
    deterministic regex extractor on any failure (never blocks the turn).
    """
    from ai.engine.cognition.context_pack import (
        TASK_WEATHER_QUESTION,
        build_context_pack,
    )
    from ai.engine.llm.router import route_chat

    transcript_lines: list[str] = []
    for turn in (conversation_history or [])[-6:]:
        role = (turn.get("role") or "").strip() or "user"
        content = (turn.get("content") or "").strip()
        if content:
            transcript_lines.append(f"{role}: {content}")
    transcript = "\n".join(transcript_lines)

    user_parts = []
    if transcript:
        user_parts.append(f"Conversation so far:\n{transcript}")
    user_parts.append(f"Weather question: {question}")
    user_parts.append("Canonical 'City, Country':")
    pack = build_context_pack(
        state,
        surface="chat",
        stage="weather_normalize",
        user_info=user_info,
        instance_config=instance_config,
        conversation_history=conversation_history,
        language=language,
        task_body=TASK_WEATHER_QUESTION,
        user_body="\n".join(user_parts),
        include_knowledge=False,
        include_memory=False,
        include_history=False,
    )

    try:
        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"geo-q-{conversation_id}",
            messages=[
                {"role": "system", "content": pack.system_prompt()},
                {"role": "user", "content": pack.user_prompt()},
            ],
            temperature=0.0,
            model=model,
            tools=None,
        )
    except Exception:
        logger.warning("Weather question normalization failed", exc_info=True)
        return _weather_location_fallback(weather_extractor, question)

    text = (result.get("content") or "").strip().splitlines()[0].strip()
    text = text.strip(" .\"'`")
    if not text or len(text) > 60:
        # LLM returned something unusable — fall back to the regex extractor.
        return _weather_location_fallback(weather_extractor, question)
    return text

async def _clarify_no_matches(
    *,
    instance_id: str,
    conversation_id: str,
    user_message: str,
    hints: list[str],
    model: str | None = None,
    user_info: dict | None = None,
    instance_config: dict | None = None,
    language: str = "",
    state=None,
) -> dict | None:
    """Route a ``no_match`` escalation into ONE disambiguating question."""
    from ai.engine.cognition.context_pack import build_context_pack
    from ai.engine.llm.router import route_chat

    pack = build_context_pack(
        state,
        surface="chat",
        stage="escalate",
        user_info=user_info,
        instance_config=instance_config,
        language=language,
        escalate_hints=hints,
        user_body=f"User's question: {user_message}",
        include_history=False,
        include_knowledge=False,
        include_memory=False,
    )
    try:
        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"clarify-{conversation_id}",
            messages=[
                {"role": "system", "content": pack.system_prompt()},
                {"role": "user", "content": pack.user_prompt()},
            ],
            temperature=0.3,
            model=model,
            tools=None,
        )
    except Exception:
        logger.warning("No-match clarification LLM call failed", exc_info=True)
        return None

    text = (result.get("content") or "").strip()
    if not text:
        return None

    tokens = int(result.get("input_tokens", 0) or 0) + int(result.get("output_tokens", 0) or 0)
    return {"text": text, "tokens": tokens, "model": result.get("model", "")}

def _append_evidence_footer(synthesized: str, usable: list[dict]) -> str:
    """No-op — technical tool names are not surfaced to end users."""
    return synthesized

def _wants_visual(user_message: str) -> bool:
    V("t_true_when_a_chart_graph_is")
    if not user_message:
        return False
    import re
    text = user_message
    try:
        from ai.engine.cognition.plan.process_dial import strip_pulse_mode_prefix
        text = strip_pulse_mode_prefix(user_message)
    except Exception:  # noqa: BLE001
        pass
    return bool(re.search(
        r"\b(chart|charts|graph|graphs|visual|visuals|visualise|visualize|"
        r"plot|plots|diagram|diagrams|pie|bar\s*chart|trend|trends|"
        r"infographic|figure|figures|"
        r"distribution|distributions|breakdown|break\s*down|"
        r"analytics|histogram|by\s+(?:band|tier|nationality|gender|dept|"
        r"department|grade|org))\b"
        r"|توزيع|رسم\s*بياني|مخطط",
        text, re.IGNORECASE))

def _is_distribution_ask(user_message: str) -> bool:
    V("t_salary_headcount_distribution_asks_must_never")
    if not user_message:
        return False
    import re
    text = user_message
    try:
        from ai.engine.cognition.plan.process_dial import strip_pulse_mode_prefix
        text = strip_pulse_mode_prefix(user_message)
    except Exception:  # noqa: BLE001
        pass
    return bool(re.search(
        V("t_b_distribution_distributions_breakdown_salary_sa")
        + V("t_compensation_payroll_s_mix_pay_s")
        + V("t_توزيع_رواتب_راتب"),
        text, re.IGNORECASE))

def _cell_display(value) -> str:
    """Human cell text — never dump raw Python/JSON dict strings."""
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("label", "name", "code", "title", "display"):
            if value.get(key) not in (None, ""):
                return str(value[key])
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(_cell_display(v) for v in value[:6] if v not in (None, ""))
    text = str(value).strip()
    # Common accident: stringified dict from ORM / ReferenceValue.
    if text.startswith("{") and ("'label'" in text or '"label"' in text):
        import re as _re
        m = _re.search(r"['\"]label['\"]\s*:\s*['\"]([^'\"]+)['\"]", text)
        if m:
            return m.group(1)
    return text

def _salary_band_buckets(amounts: list[float]) -> list[tuple[str, int]]:
    V("t_bucket_gross_net_amounts_into_readable")
    if not amounts:
        return []
    edges = [0, 100, 200, 300, 420, 600, 1000, 2000, 5000, 10_000]
    labels = [
        "≤100", "100–200", "200–300", "300–420", "420–600",
        "600–1k", "1k–2k", "2k–5k", "5k+",
    ]
    counts = [0] * len(labels)
    for amt in amounts:
        if amt < 0:
            # Negatives (-heavy nets) — count in lowest band with a note via label.
            counts[0] += 1
            continue
        placed = False
        for i in range(len(edges) - 1):
            if edges[i] <= amt < edges[i + 1]:
                counts[i] += 1
                placed = True
                break
        if not placed:
            counts[-1] += 1
    return [(lab, n) for lab, n in zip(labels, counts) if n > 0]

def _extract_amount_series(usable: list[dict]) -> list[float]:
    V("t_pull_numeric_salary_amount_fields_from")
    import json as _json
    amounts: list[float] = []
    amount_keys = (
        "amount", "gross", "gross_salary", "basic", "basic_salary",
        "net", "net_pay", "value", "total",
    )
    for tr in usable:
        result = tr.get("result")
        if result is None:
            continue
        data = result
        if isinstance(result, str):
            try:
                data = _json.loads(result)
            except (TypeError, ValueError):
                continue
        if isinstance(data, dict) and "status_code" in data and "data" in data:
            data = data["data"]
        if not isinstance(data, dict):
            continue
        for key in ("rows", "results", "items", "records", "lines"):
            items = data.get(key)
            if not isinstance(items, list):
                continue
            for row in items:
                if not isinstance(row, dict):
                    continue
                for ak in amount_keys:
                    raw = row.get(ak)
                    if raw in (None, ""):
                        continue
                    try:
                        amounts.append(float(raw))
                        break
                    except (TypeError, ValueError):
                        continue
    return amounts

def _render_tool_tables(usable: list[dict], *, user_message: str = "") -> str:
    V("t_deterministically_render_gfm_markdown_tables_fro")
    import json as _json

    _SCOPE_NAMES = {1: "Scope 1 — Direct", 2: "Scope 2 — Indirect Energy", 3: "Scope 3 — Value Chain"}
    distribution = _is_distribution_ask(user_message)

    parts: list[str] = []
    for tr in usable:
        result = tr.get("result")
        if result is None:
            continue
        data = result
        if isinstance(result, str):
            try:
                data = _json.loads(result)
            except (TypeError, ValueError):
                continue
        if isinstance(data, dict) and "status_code" in data and "data" in data:
            data = data["data"]
        # Nested analytics payload without status_code.
        if (
            isinstance(data, dict)
            and "breakdown" not in data
            and isinstance(data.get("data"), dict)
            and (
                "breakdown" in data["data"]
                or "by_scope" in data["data"]
                or "rows" in data["data"]
            )
        ):
            data = data["data"]
        if not isinstance(data, dict):
            continue

        breakdown = data.get("breakdown") or []
        if isinstance(breakdown, list) and breakdown and isinstance(breakdown[0], dict):
            rows = []
            for b in breakdown[:30]:
                label = _cell_display(b.get("label") or b.get("name") or "—")
                count = b.get("count", b.get("value", ""))
                pct = b.get("pct", b.get("percent", ""))
                if pct != "":
                    rows.append(f"| {label} | {count} | {pct}% |")
                else:
                    rows.append(f"| {label} | {count} |")
            if rows:
                if "%" in rows[0]:
                    parts.append(
                        "| Band / category | Count | Share |\n"
                        "|---|---|---|\n" + "\n".join(rows)
                    )
                else:
                    parts.append(
                        "| Band / category | Count |\n"
                        "|---|---|\n" + "\n".join(rows)
                    )
                continue

        by_scope = data.get("by_scope") or {}
        if isinstance(by_scope, dict) and by_scope:
            rows = []
            for k, v in by_scope.items():
                if isinstance(v, dict):
                    name = _SCOPE_NAMES.get(int(k), f"Scope {k}")
                    co2e = float(v.get("total_co2e_kg") or 0)
                    count = v.get("count", 0)
                    rows.append(f"| {name} | {co2e:,.1f} | {count} |")
            if rows:
                parts.append(
                    "| Scope | CO₂e (kg) | Calculations |\n"
                    "|---|---|---|\n" + "\n".join(rows)
                )

        by_module = data.get("by_module") or []
        if isinstance(by_module, list) and by_module:
            rows = []
            for m in by_module[:30]:
                if isinstance(m, dict):
                    name = m.get("module_name") or m.get("module") or "—"
                    co2e = float(m.get("total_co2e_kg") or 0)
                    count = m.get("count", 0)
                    rows.append(f"| {name} | {co2e:,.1f} | {count} |")
            if rows:
                parts.append(
                    "| Module / Branch | CO₂e (kg) | Calculations |\n"
                    "|---|---|---|\n" + "\n".join(rows)
                )

        # Generic list-of-dicts — SKIP for distribution asks (no  dumps).
        if distribution:
            continue
        if parts:
            continue
        for key in ("rows", "results", "items", "records"):
            items = data.get(key)
            if isinstance(items, list) and items and isinstance(items[0], dict):
                # Skip -line shaped dumps even outside explicit distribution.
                sample_keys = {str(k).lower() for k in items[0].keys()}
                if {"line_type", V("t_payslip_2"), "employee_name"} & sample_keys or (
                    "amount" in sample_keys and V("t_employee_4") in " ".join(sample_keys)
                ):
                    break
                cols = list(items[0].keys())[:8]
                header = "| " + " | ".join(str(c).replace("_", " ").title() for c in cols) + " |"
                sep = "|" + "|".join(["---"] * len(cols)) + "|"
                rows = [
                    "| " + " | ".join(_cell_display(row.get(c)) for c in cols) + " |"
                    for row in items[:50]
                ]
                if rows:
                    parts.append("\n".join([header, sep] + rows))
                break

    if distribution and not parts:
        bands = _salary_band_buckets(_extract_amount_series(usable))
        if bands:
            rows = [f"| {lab} | {n} |" for lab, n in bands]
            parts.append(
                V("t_salary_band_count")
                + "|---|---|\n" + "\n".join(rows)
            )

    return "\n\n".join(parts)

def _with_prior_chart_rows(usable: list[dict], state, user_message: str) -> list[dict]:
    """Use the last host payload when this turn has no chartable rows.

    A follow-up "make a chart" often only runs the sandbox. The chart still
    has to be the rows from the read that produced the numbers.
    """
    if not _wants_visual(user_message):
        return usable
    if _render_tool_charts(usable, user_message=user_message):
        return usable
    for row in reversed(list(getattr(state, "last_results", None) or [])):
        if not isinstance(row, dict) or row.get("result") is None:
            continue
        return [
            *usable,
            {
                "tool_name": row.get("tool") or "call_host_api",
                "tool_args": {"api_name": row.get("api") or ""},
                "result": row["result"],
            },
        ]
    return usable


def _render_tool_charts(usable: list[dict], *, user_message: str = "") -> str:
    V("t_deterministic_mermaid_charts_from_structured_too")
    import json as _json

    _SCOPE_NAMES = {1: "Scope 1", 2: "Scope 2", 3: "Scope 3"}
    have_pie = False
    have_bar = False
    charts: list[str] = []
    for tr in usable:
        result = tr.get("result")
        if result is None:
            continue
        data = result
        if isinstance(result, str):
            try:
                data = _json.loads(result)
            except (TypeError, ValueError):
                continue
        if isinstance(data, dict) and "status_code" in data and "data" in data:
            data = data["data"]
        if (
            isinstance(data, dict)
            and "breakdown" not in data
            and isinstance(data.get("data"), dict)
            and (
                "breakdown" in data["data"]
                or "by_scope" in data["data"]
                or "rows" in data["data"]
            )
        ):
            data = data["data"]
        if not isinstance(data, dict):
            continue

        breakdown = data.get("breakdown") or []
        chart_type = str(data.get("suggested_chart_type") or "bar").lower()
        if isinstance(breakdown, list) and breakdown and isinstance(breakdown[0], dict):
            labels: list[str] = []
            values: list[float] = []
            for b in breakdown[:12]:
                lab = _cell_display(b.get("label") or b.get("name") or "-")
                lab = lab.replace('"', "'").replace("—", "-").strip()[:24] or "-"
                try:
                    val = float(b.get("count", b.get("value", 0)) or 0)
                except (TypeError, ValueError):
                    val = 0.0
                if val <= 0:
                    continue
                labels.append(lab)
                values.append(val)
            if labels and any(values):
                if chart_type == "pie" and not have_pie and len(labels) <= 8:
                    slices = [
                        f'    "{lab}" : {int(v) if v == int(v) else round(v, 1)}'
                        for lab, v in zip(labels, values)
                    ]
                    title = str(data.get("dimension") or "Distribution").replace('"', "'")[:40]
                    charts.append(
                        f"```mermaid\npie showData title {title}\n"
                        + "\n".join(slices) + "\n```"
                    )
                    have_pie = True
                elif not have_bar:
                    ymax = int(max(values) * 1.15) or 1
                    xlabels = ", ".join(f'"{lab}"' for lab in labels)
                    charts.append(
                        "```mermaid\nxychart-beta\n"
                        '    title "Distribution"\n'
                        f"    x-axis [{xlabels}]\n"
                        f'    y-axis "Count" 0 --> {ymax}\n'
                        f"    bar [{', '.join(str(int(v) if v == int(v) else round(v, 1)) for v in values)}]\n```"
                    )
                    have_bar = True

        by_scope = data.get("by_scope") or {}
        if isinstance(by_scope, dict) and by_scope and not have_pie:
            slices = []
            for k, v in by_scope.items():
                if isinstance(v, dict):
                    co2e = float(v.get("total_co2e_kg") or 0)
                    if co2e > 0:
                        try:
                            name = _SCOPE_NAMES.get(int(k), f"Scope {k}")
                        except (TypeError, ValueError):
                            name = f"Scope {k}"
                        slices.append(f'    "{name}" : {round(co2e, 1)}')
            if slices:
                charts.append(
                    "```mermaid\npie showData title Emissions by scope (CO2e kg)\n"
                    + "\n".join(slices) + "\n```"
                )
                have_pie = True

        by_module = data.get("by_module") or []
        if isinstance(by_module, list) and by_module and not have_bar:
            labels = []
            values = []
            for m in by_module[:12]:
                if isinstance(m, dict):
                    name = str(m.get("module_name") or m.get("module") or "-")
                    name = name.replace('"', "'").replace("—", "-").strip()[:20]
                    labels.append(f'"{name}"')
                    values.append(round(float(m.get("total_co2e_kg") or 0), 1))
            if labels and any(values):
                ymax = int(max(values) * 1.1) or 1
                charts.append(
                    "```mermaid\nxychart-beta\n"
                    '    title "Emissions by branch (CO2e kg)"\n'
                    f"    x-axis [{', '.join(labels)}]\n"
                    f'    y-axis "CO2e (kg)" 0 --> {ymax}\n'
                    f"    bar [{', '.join(str(v) for v in values)}]\n```"
                )
                have_bar = True

    if not charts:
        from ai.envelope_service import labeled_numeric_points

        for tr in usable:
            data = tr.get("result")
            if isinstance(data, str):
                try:
                    data = _json.loads(data)
                except (TypeError, ValueError):
                    continue
            if isinstance(data, dict) and "status_code" in data and "data" in data:
                data = data["data"]
            rows: list = []
            if isinstance(data, dict):
                for key in ("results", "rows", "items"):
                    found = data.get(key)
                    if isinstance(found, list):
                        rows = [row for row in found if isinstance(row, dict)]
                        break
            elif isinstance(data, list):
                rows = [row for row in data if isinstance(row, dict)]
            labeled = labeled_numeric_points(rows)
            if labeled is None:
                continue
            title, points = labeled
            labels = ", ".join(f'"{lab}"' for lab, _ in points)
            values = [v for _, v in points]
            ymax = int(max(values) * 1.15) or 1
            charts.append(
                "```mermaid\nxychart-beta\n"
                f'    title "{title}"\n'
                f"    x-axis [{labels}]\n"
                f'    y-axis "Value" 0 --> {ymax}\n'
                f"    bar [{', '.join(str(v) for v in values)}]\n```"
            )
            break

    if not charts and _is_distribution_ask(user_message):
        bands = _salary_band_buckets(_extract_amount_series(usable))
        if bands:
            labels = [f'"{lab}"' for lab, _ in bands]
            values = [n for _, n in bands]
            ymax = int(max(values) * 1.15) or 1
            charts.append(
                "```mermaid\nxychart-beta\n"
                + V("t_title_salary_distribution_by_band")
                + f"    x-axis [{', '.join(labels)}]\n"
                f'    y-axis "{V("t_employees_3")}" 0 --> {ymax}\n'
                f"    bar [{', '.join(str(v) for v in values)}]\n```"
            )

    return "\n\n".join(charts)

def _envelope_to_markdown(envelope) -> str:
    """Build a clean markdown fallback from a typed envelope.

    Used for copy/export and any non-envelope surface. Renders headline + prose
    well-formed GFM tables from the typed blocks — never the model's ad-hoc
    markdown — so even the fallback text is structurally valid.
    """
    parts: list[str] = []
    headline = (getattr(envelope, "headline", "") or "").strip()
    if headline:
        parts.append(headline)
    for para in getattr(envelope, "prose", None) or []:
        text = (para or "").strip()
        if text:
            parts.append(text)
    for table in getattr(envelope, "tables", None) or []:
        title = (getattr(table, "title", "") or "").strip()
        columns = list(getattr(table, "columns", None) or [])
        rows = list(getattr(table, "rows", None) or [])
        if not columns:
            continue
        if title:
            parts.append(f"### {title}")
        lines = [
            "| " + " | ".join(str(c) for c in columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |",
        ]
        for row in rows:
            lines.append("| " + " | ".join(str(c) for c in row) + " |")
        parts.append("\n".join(lines))
    for caveat in getattr(envelope, "caveats", None) or []:
        text = (getattr(caveat, "text", "") or "").strip()
        if text:
            parts.append(f"> {text}")
    return "\n\n".join(parts).strip()

async def _stream_final_text(text: str, *, stream_callback, progress_callback) -> None:
    """Stream a finished answer to the UI in 80-char chunks.

    Emits the ``Composing response…`` thinking cue first, then streams the
    text progressively so the user sees movement during the final render.
    Shared by BOTH the markdown-synthesis path and the typed-envelope path so
    data answers also stream and show the thinking indicator.
    """
    if not stream_callback or not text:
        return
    if progress_callback:
        try:
            await progress_callback("Composing response…")
        except Exception:
            pass
    pos = 0
    while pos < len(text):
        end = min(pos + 80, len(text))
        try:
            await stream_callback(text[pos:end])
        except Exception:
            break
        pos = end

def _failed_tools_for_recovery(completed_tools: list[dict]) -> list[dict]:
    """Tools that failed (top-level error or host non-2xx envelope)."""
    import json as _json

    failed: list[dict] = []
    for tr in completed_tools or []:
        if not isinstance(tr, dict):
            continue
        if tr.get("error"):
            failed.append(tr)
            continue
        if tr.get("requires_confirmation"):
            continue
        raw = tr.get("result")
        try:
            data = _json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get("error"):
            failed.append(tr)
            continue
        try:
            code = int(data.get("status_code")) if data.get("status_code") is not None else None
        except (TypeError, ValueError):
            code = None
        if code is not None and code >= 400:
            failed.append(tr)
    return failed


def _render_tool_failures_for_recovery(failed_tools: list[dict]) -> str:
    """Compact, outcome-oriented failure payload for recovery synthesis."""
    import json as _json

    sections: list[str] = []
    for tr in failed_tools:
        name = str(tr.get("tool_name") or "tool")
        args = tr.get("tool_args") if isinstance(tr.get("tool_args"), dict) else {}
        api = str(args.get("api_name") or args.get("api") or "")
        if ":" in name and not api:
            api = name.split(":", 1)[1]
        err = str(tr.get("error") or "").strip()
        raw = tr.get("result")
        try:
            data = _json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            data = None
        payload: dict = {"tool": name}
        if api:
            payload["api_name"] = api
        if err:
            payload["error"] = err[:400]
        if isinstance(data, dict):
            inner = data.get("data") if isinstance(data.get("data"), dict) else data
            if isinstance(inner, dict):
                for key in ("detail", "error_kind", "hints", "remaining", "message"):
                    if key in inner and inner[key] is not None:
                        payload[key] = inner[key]
            if data.get("status_code") is not None:
                payload["status_code"] = data.get("status_code")
        sections.append(_json.dumps(payload, default=str, ensure_ascii=False))
    return "\n".join(sections)


def _deterministic_failure_reply(failed_tools: list[dict], user_message: str = "") -> str:
    """RULE_23 fallback when recovery LLM is unavailable."""
    import json as _json

    from ai.engine_runtime import fail_reply_when_all_tools_failed

    details: list[str] = []
    for tr in failed_tools:
        err = str(tr.get("error") or "").strip()
        raw = tr.get("result")
        try:
            data = _json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            data = None
        detail = err
        kind = ""
        suggestion = ""
        if isinstance(data, dict):
            inner = data.get("data") if isinstance(data.get("data"), dict) else data
            if isinstance(inner, dict):
                detail = str(inner.get("detail") or detail or "").strip()
                kind = str(inner.get("error_kind") or "").strip()
                hints = inner.get("hints") if isinstance(inner.get("hints"), dict) else {}
                suggestion = str(hints.get("suggestion") or "").strip()
        if detail:
            details.append(detail)
        if suggestion and suggestion not in details:
            details.append(suggestion)
        elif kind == "overlap" and "Pick another day" not in " ".join(details):
            details.append("Pick another day that is free.")
        elif kind == "insufficient_balance" and V("t_another_leave_type") not in " ".join(details).lower():
            details.append(V("t_pick_another_leave_type_or_a"))
        elif kind == "invalid_leave_type" and "allowed" not in " ".join(details).lower():
            details.append(V("t_use_a_recognised_leave_type_for"))

    base = fail_reply_when_all_tools_failed(failed_tools)
    if not details:
        return base
    # Prefer the host outcome; keep one clear next step.
    body = details[0]
    extra = details[1] if len(details) > 1 else ""
    if extra:
        return f"{body} {extra}"
    # If we only have a detail, still invite a next step for mutations.
    if "try again" not in body.lower() and "pick" not in body.lower():
        return f"{body} What would you like to change?"
    return body


async def _synthesize_tool_failures(
    *,
    instance_id: str,
    conversation_id: str,
    user_message: str,
    completed_tools: list[dict],
    model: str | None = None,
    stream_callback=None,
    progress_callback=None,
    user_info: dict | None = None,
    instance_config: dict | None = None,
    language: str = "",
    state=None,
) -> dict | None:
    """ADR-0021 failure branch — turn host/tool errors into grounded guidance.

    Does NOT auto-retry mutations (RULE_21). Does NOT invent success (anti-
    fabrication). Prefer host ``detail`` / ``error_kind`` over generic refuse.
    """
    failed = _failed_tools_for_recovery(completed_tools)
    if not failed:
        return None

    if progress_callback:
        try:
            await progress_callback("Working out what went wrong…")
        except Exception:
            pass

    failures_text = _render_tool_failures_for_recovery(failed)
    from ai.engine.cognition.context_pack import build_context_pack

    pack = build_context_pack(
        state,
        surface="chat",
        stage="recovery",
        user_info=user_info,
        instance_config=instance_config,
        language=language,
        user_body=(
            f"User's message: {user_message}\n\n"
            f"Tool failures (JSON lines):\n{failures_text}"
        ),
        include_history=False,
        include_knowledge=False,
        include_memory=False,
    )
    try:
        from ai.engine.llm.router import route_chat

        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"recovery-{conversation_id}",
            messages=[
                {"role": "system", "content": pack.system_prompt()},
                {"role": "user", "content": pack.user_prompt()},
            ],
            temperature=0.2,
            model=model,
            tools=None,
        )
        synthesized = (result.get("content") or "").strip()
        if synthesized:
            # Strip accidental success claims / invention meta.
            low = synthesized.lower()
            if any(p in low for p in (
                "successfully submitted", "has been submitted",
                "was created", "no answer was invented",
            )):
                synthesized = ""
            if synthesized:
                await _stream_final_text(
                    synthesized,
                    stream_callback=stream_callback,
                    progress_callback=progress_callback,
                )
                tokens = int(result.get("input_tokens", 0) or 0) + int(
                    result.get("output_tokens", 0) or 0
                )
                return {
                    "text": synthesized,
                    "tokens": tokens,
                    "model": result.get("model", ""),
                    "is_recovery": True,
                }
    except Exception:
        logger.warning("Tool-failure recovery LLM call failed", exc_info=True)

    fallback = _deterministic_failure_reply(failed, user_message)
    await _stream_final_text(
        fallback,
        stream_callback=stream_callback,
        progress_callback=progress_callback,
    )
    return {"text": fallback, "tokens": 0, "model": model or "", "is_recovery": True}


async def _synthesize_tool_results(
    *,
    instance_id: str,
    conversation_id: str,
    user_message: str,
    completed_tools: list[dict],
    draft_text: str,
    model: str | None = None,
    delivery: str = "explain",
    envelope_synthesizer=None,
    stream_callback=None,
    progress_callback=None,
    user_info: dict | None = None,
    instance_config: dict | None = None,
    language: str = "",
    state=None,
) -> dict | None:
    """Ask the LLM to write a grounded final answer from executed tool results.

    Fires only when tools returned usable data AND the draft prose is empty or
    a short "promise to fetch" (the common tool-only turn where the model
    writes "I'll fetch …" and the fetched data is otherwise discarded).

    ``no_match`` results are never data: they are escalated — either into a
    single disambiguating question (when nothing usable remains) or into an
    honesty directive appended to the synthesis prompt (when usable data also
    exists) — instead of being handed to the LLM as if they were found values.

    Returns ``{"text", "tokens", "model"}`` on success, or ``None`` when
    synthesis is unnecessary or the call fails (callers keep the original).
    """
    usable: list[dict] = []
    no_matches: list[dict] = []
    for tr in completed_tools or []:
        if tr.get("error"):
            continue
        if tr.get("requires_confirmation"):
            continue
        if tr.get("result") is None:
            continue
        if payload_status(tr.get("result")) == "no_match":
            no_matches.append(tr)
            continue
        usable.append(tr)

    # B5: compensation CBAC deny → fixed prose (never LLM soft-empty mix).
    try:
        from ai.engine.agent.tools import compensation_authz_deny_message

        _deny_text = compensation_authz_deny_message(completed_tools)
    except Exception:  # noqa: BLE001
        _deny_text = None
    if _deny_text:
        await _stream_final_text(
            _deny_text,
            stream_callback=stream_callback,
            progress_callback=progress_callback,
        )
        return {"text": _deny_text, "tokens": 0, "model": model or ""}

    hints = _no_match_hints(no_matches)

    # Precedence 1: nothing usable but some no_match → the tool could not
    # resolve the user's entities. Ask ONE clarifying question instead of
    # falling through to the deterministic summary with a raw no_match payload
    # (which would otherwise read like city-history-as-weather). This fires
    # even when the draft prose is non-empty (a bare "I'll fetch …" promise).
    if no_matches and not usable:
        result = await _clarify_no_matches(
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=user_message,
            hints=hints,
            model=model,
            user_info=user_info,
            instance_config=instance_config,
            language=language,
            state=state,
        )
        if result is not None:
            result["is_clarification"] = True
            result["clarification_hints"] = hints
            result["clarification_user_message"] = user_message
        return result

    if not usable:
        # ADR-0021 failure branch — grounded recovery from tool errors
        # ( validation deny, boundary refuse, …). Never invent success;
        # never auto-retry mutations (RULE_21).
        return await _synthesize_tool_failures(
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=user_message,
            completed_tools=completed_tools,
            model=model,
            stream_callback=stream_callback,
            progress_callback=progress_callback,
            user_info=user_info,
            instance_config=instance_config,
            language=language,
            state=state,
        )

    results_text = _render_tool_results_for_synthesis(usable)
    if not results_text.strip():
        return None

    # Prefer host-row charts (envelope Chart.js / Mermaid) over sandbox PNG.
    # A follow-up "make a chart" often only ran code_execute; pull prior rows.
    chart_usable = _with_prior_chart_rows(usable, state, user_message)
    pre_tables = _render_tool_tables(chart_usable, user_message=user_message)
    pre_charts = (
        _render_tool_charts(chart_usable, user_message=user_message)
        if _wants_visual(user_message)
        else ""
    )
    # When the sandbox already drew a PNG but host rows can chart, prefer
    # Mermaid/envelope and let _drop_sandbox_image_when_row_chart strip the PNG.
    has_sandbox_png = any(
        _payload_has_chart_image(tr.get("result")) for tr in usable
    )
    if not pre_charts and has_sandbox_png:
        forced = _render_tool_charts(
            chart_usable,
            user_message=user_message or "chart",
        )
        if forced:
            pre_charts = forced

    if (pre_tables or pre_charts) and (
        _is_distribution_ask(user_message)
        or _wants_visual(user_message)
        or (has_sandbox_png and pre_charts)
    ):
        typed = None
        if get_settings().PULSE_ENVELOPE_ENABLED:
            try:
                from ai.envelope_service import _deterministic_fallback_envelope

                typed = _deterministic_fallback_envelope(chart_usable, user_message)
            except Exception:  # noqa: BLE001 — never break the turn
                logger.debug("deterministic envelope fast-path failed", exc_info=True)
                typed = None
        if typed is not None and (typed.tables or typed.charts):
            body = _envelope_to_markdown(typed)
            await _stream_final_text(
                body,
                stream_callback=stream_callback,
                progress_callback=progress_callback,
            )
            return {
                "text": body,
                "tokens": 0,
                "model": model or "",
                "envelope": typed.model_dump(),
            }
        parts = []
        if pre_tables:
            parts.append(pre_tables)
        if pre_charts:
            parts.append(pre_charts)
        body = "\n\n".join(parts)
        await _stream_final_text(
            body,
            stream_callback=stream_callback,
            progress_callback=progress_callback,
        )
        return {"text": body, "tokens": 0, "model": model or ""}

    # P6: sandbox PNG only when no row chart could be built. A draft that
    # denies charts is discarded for one honest sentence; image on code_result.
    if has_sandbox_png and _draft_contradicts_chart(draft_text or ""):
        from ai.engine.text.word_match import has_arabic_script

        ack = (
            "هذا المخطط من بياناتك."
            if has_arabic_script(user_message or "")
            else "Here is the chart from your data."
        )
        await _stream_final_text(
            ack,
            stream_callback=stream_callback,
            progress_callback=progress_callback,
        )
        return {"text": ack, "tokens": 0, "model": model or ""}

    # 0-LLM fast path already handled above when tables/charts were available.

    # [PAQ-2A/2B] Typed Answer Envelope. When enabled and the tools returned
    # structured data, synthesize the envelope FIRST — even when the model
    # already wrote a long markdown draft — so data answers render as typed
    # blocks (deterministic tables/charts) instead of ad-hoc markdown the model
    # frequently malforms. Fail-open: any error folds to ``None`` and the
    # markdown path below runs unchanged.
    envelope = None
    if progress_callback:
        try:
            await progress_callback("Analysing data…")
        except Exception:
            pass
    if get_settings().PULSE_ENVELOPE_ENABLED and envelope_synthesizer is not None:
        try:
            envelope = await envelope_synthesizer(
                instance_id=instance_id,
                conversation_id=conversation_id,
                user_message=user_message,
                usable_tools=usable,
                model=model,
            )
        except Exception:  # noqa: BLE001 - envelope must never break the turn
            logger.warning("Envelope synthesis failed", exc_info=True)
            envelope = None

    # When the envelope carries data blocks it BECOMES the answer, regardless of
    # draft length: the frontend renders the typed blocks and the markdown
    # fallback (copy/export/non-envelope surfaces) is built from the envelope's
    # own headline + prose + clean GFM tables — never the model's ad-hoc tables.
    if envelope is not None and (envelope.tables or envelope.charts):
        _env_text = _envelope_to_markdown(envelope)
        if _wants_visual(user_message) and "```mermaid" not in _env_text:
            _charts = _render_tool_charts(usable, user_message=user_message)
            if _charts:
                _env_text = f"{_env_text}\n\n{_charts}"
        await _stream_final_text(
            _env_text,
            stream_callback=stream_callback,
            progress_callback=progress_callback,
        )
        return {
            "text": _env_text,
            "tokens": 0,
            "model": model or "",
            "envelope": envelope.model_dump(),
        }

    stripped = (draft_text or "").strip()
    # No usable envelope data blocks — keep the existing markdown behaviour: a
    # substantial prose answer already exists → don't re-synthesize.
    #
    # EXCEPTION (no-data hallucination net): when the draft falsely claims
    # "no data" while the executed tools actually returned data, the draft is a
    # history-poisoned hallucination and MUST be re-synthesized from the real
    # tool results. The synthesis prompt below carries a hard NON-EMPTY GUARD
    # (never say "no data" when usable tools returned data), so forcing this
    # path guarantees a factual answer instead of silently keeping "no data".
    if len(stripped) >= 300:
        from ai.engine.cognition.turn.verify import detect_no_data_contradiction

        draft_contradicts_data = bool(
            detect_no_data_contradiction(stripped, usable)
        )
        if not draft_contradicts_data:
            # Even when the model's own draft is kept, honour an explicit
            # request for visuals by appending deterministic charts it omitted.
            if _wants_visual(user_message) and "```mermaid" not in stripped:
                _charts = _render_tool_charts(usable, user_message=user_message)
                if _charts:
                    delta = "\n\n" + _charts
                    if stream_callback:
                        try:
                            await stream_callback(delta)
                        except Exception:
                            pass
                    return {"text": draft_text.rstrip() + delta,
                            "tokens": 0, "model": model or ""}
            return None

    from ai.engine.cognition.context_pack import build_context_pack
    from ai.engine.cognition.turn.understand import understand_mode
    from ai.engine.llm.router import route_chat

    delivery_guide = _DELIVERY_SYNTHESIS.get(delivery or "explain", _DELIVERY_SYNTHESIS["explain"])
    task_body = ""
    if understand_mode() == "v21":
        from ai.engine.cognition.turn.understand import (
            catalog_prompt_lines,
            understand_task_body,
        )
        from ai.engine.cognition.turn.capability import capability_surface

        # The same audience-scoped surface understand saw, never the full catalog.
        _lines, _, _ = catalog_prompt_lines(
            user_message or "",
            list(capability_surface(instance_config, user_info).entries),
            k=12,
        )
        task_body = understand_task_body(_lines)
    pack = build_context_pack(
        state,
        surface="chat",
        stage="synthesis",
        user_info=user_info,
        instance_config=instance_config,
        language=language,
        task_body=task_body,
        delivery_guide=delivery_guide,
        hints=hints or None,
        user_body=(
            f"User's question: {user_message}\n\n"
            f"Tool results (JSON):\n{results_text}"
        ),
        include_history=False,
        include_knowledge=False,
        include_memory=False,
    )

    try:
        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"synthesis-{conversation_id}",
            messages=[
                {"role": "system", "content": pack.system_prompt()},
                {"role": "user", "content": pack.user_prompt()},
            ],
            temperature=0.3,
            model=model,
            tools=None,
        )
    except Exception:
        logger.warning("Tool-result synthesis LLM call failed", exc_info=True)
        return None

    synthesized = (result.get("content") or "").strip()
    if not synthesized:
        return None

    # Inject deterministically-rendered tables after the LLM prose.
    if pre_tables:
        synthesized = synthesized + "\n\n" + pre_tables
    if pre_charts and "```mermaid" not in synthesized:
        synthesized = synthesized + "\n\n" + pre_charts

    # Stream the synthesized text so the UI shows progress.
    await _stream_final_text(
        synthesized,
        stream_callback=stream_callback,
        progress_callback=progress_callback,
    )

    tokens = int(result.get("input_tokens", 0) or 0) + int(result.get("output_tokens", 0) or 0)
    synthesized_result = {"text": synthesized, "tokens": tokens, "model": result.get("model", "")}
    if envelope is not None:
        synthesized_result["envelope"] = envelope.model_dump()
    return synthesized_result




