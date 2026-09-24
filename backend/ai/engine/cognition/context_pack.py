"""ContextPack + IdentityBlock for every Chat and Agent LLM stage (PV2-2A/2B).

Engine-only: no Django / host imports. Audience values arrive via
``user_info["audience"]`` from the host.

Every ``route_chat`` system prompt in ``turn/**`` and ``plan/**`` must
originate from ``build_context_pack(...).system_prompt()``. Stage-specific
wording lives only in TaskBlock — never as a stage-local identity prompt
(ADR-0047). Agent surfaces use RULE_21 autonomy
(``AGENT_PLAN_AUTONOMY`` / ``AGENT_DISCOVERY_AUTONOMY``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable
from zoneinfo import ZoneInfo

# ── Hard character budgets (documented; clip in builders) ─────────────────
IDENTITY_BLOCK_MAX_CHARS = 2000
STATE_BLOCK_MAX_CHARS = 600
HISTORY_BLOCK_MAX_CHARS = 3500
KNOWLEDGE_BLOCK_MAX_CHARS = 2500
MEMORY_BLOCK_MAX_CHARS = 1200
TASK_BLOCK_MAX_CHARS = 8000
HISTORY_MESSAGE_MAX = 8
HISTORY_MSG_CLIP = 400

VALID_AUDIENCES = frozenset({"ess", "hr", "admin"})
DEFAULT_AUDIENCE = ("hr",)
MY_AUDIENCE = ("ess", "hr")

VALID_SURFACES = frozenset({"chat", "agent_plan", "agent_discovery"})
VALID_STAGES = frozenset({
    "draft",
    "understand",
    "critic",
    "intent",
    "synthesis",
    "verify",
    "verify_correct",
    "escalate",
    "weather_normalize",
    "recovery",
    "fanout",
    "fanout_synthesis",
    # Agent plan / discovery stages (PV2-2B)
    "decompose",
    "observe",
    "plan_synthesis",
    "discovery_clarify",
})

# ADR-0046 Chat autonomy (one-liner). Agent surfaces get RULE_21 wording.
CHAT_AUTONOMY = (
    "Autonomy (Chat · ADR-0046): advise, draft, explain, and hand off — "
    "never claim to have submitted or staged a host write. For leave / loan / "
    "attendance / payroll mutations, direct the user to Agent or My."
)
AGENT_PLAN_AUTONOMY = (
    "Autonomy (Agent plan · RULE_21): stage host effects only with explicit "
    "user consent; never claim commit before receipt."
)
AGENT_DISCOVERY_AUTONOMY = (
    "Autonomy (Agent discovery · RULE_21): collect missing slots and propose "
    "a plan; never execute host writes without staged consent."
)

# ── Stage TaskBlock templates (task wording ONLY — no persona / date / user) ─

TASK_CRITIC = """TASK — Critic / quality review:
Review the draft response against the provided knowledge context.

RULES:
1. Fix ungrounded claims — anything not supported by the knowledge context.
2. Flag data that appears to come from a different user or instance than the requester (a consistency flag; actual tenancy enforcement is deterministic, not this review).
3. Fix incorrect API references — wrong endpoint names, wrong parameters.
4. Suggest a more plausible or more complete alternative when the draft is weak, vague, or omits an important consideration.
5. If the draft is clean, return "pass". If minor fixes needed, return "rewrite" with corrected text. If the draft is unsupported, incoherent, or harmful in plain content terms, return "veto". State-changing actions are vetoed separately by deterministic gates, not by this review.

Return ONLY valid JSON — no markdown, no code fences, no explanation:
{"verdict": "pass"|"rewrite"|"veto", "rewritten_text": "...", "veto_reason": "..."}"""

TASK_VERIFY = """TASK — Fact-check:
You receive: (1) an AI assistant's answer and (2) the raw tool results the answer was based on.
Identify any specific numbers, dates, names, or percentages in the answer that contradict the tool results.
Reply with JSON:
{"passed": true/false, "unsupported_claims": ["claim1", ...], "verified_claims": ["claim1", ...], "corrected_text": "corrected answer or null if passed=true"}"""

TASK_VERIFY_CORRECT = """TASK — Correct a false 'no data' answer:
The previous AI answer incorrectly stated that no data was available.
The tool results below contain REAL data.
Write a corrected, concise answer to the user's question using those values.
Start with the headline finding. Include the key numbers.
NEVER say 'no data', 'not available', or any similar phrase.
Never invent values outside the tool results."""

TASK_WEATHER_LOCATION = """TASK — Weather location normalize:
The user is answering the assistant's previous clarifying question about a location for a weather lookup.
Using the conversation so far — ESPECIALLY any candidate places the assistant already offered —
resolve the user's short reply to the single place they meant.
Correct spelling. If the reply names a region rather than a city, pick its single most prominent city.
Reply with ONLY 'City, Country' — no other words, no explanation."""

TASK_WEATHER_QUESTION = """TASK — Weather place extract:
Extract the single place the user is asking about for a weather lookup.
Ignore greetings, misspellings, and any trailing question (e.g. 'is it suitable for beach swimming?').
Correct the spelling of the place name.
If the place is a REGION rather than a city (e.g. 'north coast egypt', 'the south of france'),
resolve it to its single most prominent city.
Reply with ONLY 'City, Country' — no other words, no explanation."""

TASK_ESCALATE = """TASK — Disambiguate:
The assistant attempted to answer the user's question but could not resolve some entities.
Write ONE short, specific disambiguating question asking the user which entity they meant.
You MAY suggest 2-3 concrete normalised candidates as a short bullet list, but ALWAYS ask
the user to confirm which one they meant. Do NOT fabricate data. Do NOT answer as if you
found results. Do NOT mention tools, APIs, or fetching."""

TASK_RECOVERY = """TASK — Tool-failure recovery:
Explain the failure in plain business language using ONLY the tool failure payload
(detail / error_kind / hints).
NEVER claim the action succeeded or that anything was submitted/created/changed.
NEVER invent numbers, balances, or dates not in the payload.
NEVER mention tools, APIs, HTTP codes, stack traces, or 'invented'.
Do NOT retry or pretend you will auto-retry a write — ask the user what to change
(another day, leave type, etc.) if that is the fix.
If error_kind is invalid_leave_type, map common synonyms using hints
(عارضة/casual → emergency) and ask them to confirm the corrected type.
If overlap or insufficient_balance, say so clearly and ask for another day or type.
Match the user's language when possible (Arabic if they wrote Arabic).
Keep it short: 2–4 sentences max."""

TASK_SYNTHESIS = """TASK — Tool-result synthesis:
Write the final reply to the user's question using ONLY the tool results in the user message.
Delivery intent: {delivery_guide}
SCOPING (critical): answer EXACTLY what the user asked. If the user's question names a
specific entity — a module, branch, scope, table, product, or other named item — scope the
entire answer to THAT entity only. Only when the user asks for an overview, a comparison,
or 'all' should you show the full breakdown.
ORG-NAME GUARD: the platform's own organisation / campus / company name is NOT a
filterable sub-entity — when the user names the whole organisation, treat it as 'all data'.
AUTHZ GUARD: when a tool result includes `unauthorized: true`, a `capability` denial, or a
message that access/permission is required, state that clearly. NEVER paraphrase an
authorization failure as 'no data', 'not found', or 'missing salary record'.
NON-EMPTY GUARD: if the tool results contain ANY calculations or rows, you MUST report those
values — NEVER say 'no data is available' when the tool returned data.
FORMAT: open with a **bold one-line takeaway**, then write 2-3 sentences of explanatory prose.
Do NOT include any tables or structured data — data tables are appended automatically.
Close with 2-4 bold-lead 'Key takeaways' bullet points.
Do not mention tools, API calls, or fetching.
Do NOT include charts or diagrams unless the user explicitly asked.{hints_note}"""

TASK_DRAFT = """TASK — Draft the next assistant reply for this Chat turn.
Follow the identity, state, knowledge, and memory blocks above.
Use tools only when live data is required. Answer date / identity / language questions
from the Identity block with zero tool calls."""

TASK_FANOUT = """TASK — Orchestrator fan-out decision:
Decide whether this user request would benefit from parallel decomposition across worker agents.
If the request has multiple independent sub-questions or requires diverse expertise, call
delegate_to_workers. If it's a simple single-focus question, respond with a brief text reply
(no tool call) and the pipeline will fall through to single-pass processing.
When the user asks to retrieve, analyse, or compare data — even without the word "plan" —
fan out to the appropriate specialist workers. Prefer fan-out for aggregation, trend,
comparison, ranking, or cross-domain questions. Only decline for greetings, simple factual
lookups, or clarification requests."""

TASK_FANOUT_SYNTHESIS = """TASK — Orchestrator synthesis:
Synthesize the following worker findings into a single coherent response to the user's
original request. Do NOT mention workers or internal mechanics — just present the combined
answer naturally."""

# ── Agent plan / discovery TaskBlocks (PV2-2B) ─────────────────────────────

TASK_DECOMPOSE = """TASK — Plan decompose:
Decompose the user task into phases and steps. Respond with JSON only — no markdown,
no code fences, no prose outside the JSON object.
Available tools, host API catalog names, and registered skills appear in the user
message — use only those names.
Each step's intent must describe the action with bound values (amounts, dates,
leave types, api_name) — never invent free-form identity text for the user or org.
Mutations stage with consent (RULE_21); never claim a host write already committed."""

TASK_OBSERVE = """TASK — Observe tool result:
Decide whether the tool result (plus any prior step results) fully answers the
original question, or whether ONE more read-only tool call is needed.
Reply with ONLY a JSON object — no prose, no markdown fences:
{"answer": "final or interim answer text", "needs_followup": false,
 "followup_tool": null, "followup_args": null}
Rules:
- If it fully answers, set needs_followup=false and write the grounded answer.
- If you need another tool, set needs_followup=true, name a followup_tool from
  the allowed read-only set in the user message, and set followup_args.
- Ground the answer ONLY in the given results — never invent data.
- Pre-consent / step wording uses bound values and catalog confirmation
  templates only — never invent free-form identity text."""

TASK_PLAN_SYNTHESIS = """TASK — Plan synthesis:
Combine the step results into one final user-facing response, following the plan's
synthesis_instruction. Report what completed and what failed honestly.
Do not claim a host write succeeded unless a step result confirms receipt.
Do not invent identity, amounts, or dates absent from the step results.
Keep the reply concise and in the user's language when known."""

TASK_DISCOVERY_CLARIFY = """TASK — Discovery clarify:
Before proposing a plan, clarify the user's outcome with short focused questions.
Ask ONE concise question at a time. When you have enough information, complete.
Scope rules (critical):
- Only clarify outcomes Agent can plan: reports, board packs, data-quality rules,
  data workflows, exports.
- Never map personal leave / vacation / إجازة to DQ rules, approvals, or
  data-source onboarding. If the user wants personal leave, respond with
  {"action":"complete"} only if they clearly asked for a leave-compliance
  REPORT; otherwise keep asking for the report outcome — the host may already
  have redirected them.
- Do not ask 'what outcome on the Carbon Data Trust Platform' for trivia, names,
  or personal HR actions.
- If the user wants a data-quality rule (validate/check/flag a field, not-null,
  unique, allowed values, range, regex, format like an email or phone number),
  you MUST find out exactly WHICH field and table the rule applies to before
  completing — ask for the specific field/column name (or DataField id) and
  table. Never complete discovery for a DQ rule while the target field is still
  unknown.
Never invent free-form identity text; slot labels come from the brief and
bound values only."""

TASK_AGENT_PLAN_DRAFT = """TASK — Agent plan step draft:
Execute the current plan step using the tools and bound args in the user message.
GROUNDING RULES — follow them exactly:
- You have tools available. Use them to do real work instead of guessing. When a
  tool matches the step, call it right away — do not answer in prose instead of
  using it, and do not say you cannot run/execute tasks.
- When the user asks you to plan, orchestrate, or run a task (e.g. 'run agent
  planner', 'plan a data quality audit'), call plan_task IMMEDIATELY with their
  request as the brief — do not ask for more details first.
- NEVER claim an action succeeded (e.g. 'rule created') unless a tool result
  confirms it.
- The create_dq_rule tool only STAGES a proposal — it returns a confirmation
  execution. Nothing is written until the user confirms. Tell the user a
  confirmation button appeared; do NOT say the rule was created.
- The plan_task tool DRAFTS a plan and returns a plan id in pending_approval; it
  does not execute anything. After calling it, tell the user the plan id and that
  it awaits approval in the Tasks panel. Never claim a task ran or completed.
- If a tool errors, report the error plainly.
- When the user asks what you can do, use the capability-list tool so the app can
  attach the matching page links as small buttons under your reply.
A5 legibility: pre-consent step text must use bound values and bilingual catalog
confirmation templates — never invent free-form identity text."""

TASK_AGENT_PLAN_REASON = """TASK — Agent plan reasoning step:
Reason from prior step results to complete this step. No tool calls.
Do not invent numbers, dates, or identity absent from prior results.
Do not claim any host write succeeded."""


def entry_audience(entry: dict | None) -> tuple[str, ...]:
    """Resolve the audience tags for one catalog / nav entry.

    Unmarked → ``hr``. Names containing ``_my_`` → ``ess`` + ``hr``.
    Explicit ``audience:`` lists are normalised to the valid enum.
    """
    if not isinstance(entry, dict):
        return DEFAULT_AUDIENCE
    raw = entry.get("audience")
    if isinstance(raw, str):
        raw = [raw]
    if isinstance(raw, (list, tuple)) and raw:
        tags = tuple(
            t for t in (str(x).strip().lower() for x in raw) if t in VALID_AUDIENCES
        )
        if tags:
            return tags
    name = str(entry.get("name") or "")
    if "_my_" in name:
        return MY_AUDIENCE
    # Navigation routes are self-service + HR.
    if entry.get("type") in ("app", "route", "nav") or str(
        entry.get("path") or ""
    ).startswith("/my"):
        return MY_AUDIENCE
    return DEFAULT_AUDIENCE


def filter_catalog_by_audience(
    catalog: list[dict] | None,
    audience: Iterable[str] | None,
) -> list[dict]:
    """Keep catalog entries whose audience intersects ``audience``."""
    user_aud = {
        str(a).strip().lower()
        for a in (audience or ())
        if str(a).strip().lower() in VALID_AUDIENCES
    } or {"ess"}
    out: list[dict] = []
    for entry in catalog or []:
        if not isinstance(entry, dict):
            continue
        if set(entry_audience(entry)) & user_aud:
            out.append(entry)
    return out


def normalize_catalog_audiences(catalog: list[dict] | None) -> list[dict]:
    """Return a copy of catalog with explicit ``audience`` on every entry."""
    out: list[dict] = []
    for entry in catalog or []:
        if not isinstance(entry, dict):
            continue
        copy = dict(entry)
        copy["audience"] = list(entry_audience(entry))
        out.append(copy)
    return out


def validate_catalog_audiences(catalog: list[dict] | None) -> list[str]:
    """Return error strings for invalid ``audience`` tags (empty = ok)."""
    errors: list[str] = []
    for i, entry in enumerate(catalog or []):
        if not isinstance(entry, dict):
            continue
        raw = entry.get("audience")
        if raw is None:
            continue
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, (list, tuple)):
            errors.append(
                f"api_catalog[{i}].audience: must be a list, got {type(raw).__name__}"
            )
            continue
        for tag in raw:
            t = str(tag).strip().lower()
            if t not in VALID_AUDIENCES:
                name = entry.get("name") or i
                errors.append(
                    f"api_catalog[{name}].audience: invalid tag {tag!r} "
                    f"(expected one of {sorted(VALID_AUDIENCES)})"
                )
    return errors


def _clip(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= 1:
        return text[:max_chars]
    return text[: max_chars - 1].rstrip() + "…"


def _autonomy_for_surface(surface: str) -> str:
    if surface == "agent_plan":
        return AGENT_PLAN_AUTONOMY
    if surface == "agent_discovery":
        return AGENT_DISCOVERY_AUTONOMY
    return CHAT_AUTONOMY


def _resolve_timezone(instance_config: dict[str, Any] | None) -> str:
    cfg = instance_config or {}
    for key in ("timezone", "tz", "default_timezone"):
        val = (cfg.get(key) or "").strip()
        if val:
            return val
    return "Africa/Cairo"


def format_today_line(
    instance_config: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> str:
    """Render the IdentityBlock date line (today + timezone)."""
    tz_name = _resolve_timezone(instance_config)
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001 — fall back to UTC
        tz = ZoneInfo("UTC")
        tz_name = "UTC"
    stamp = now or datetime.now(tz)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=tz)
    else:
        stamp = stamp.astimezone(tz)
    return (
        f"Today's date: {stamp.strftime('%A, %B %d, %Y')} "
        f"({tz_name}, {stamp.strftime('%H:%M %Z')})"
    )


def _user_identity_lines(user_info: dict[str, Any] | None) -> list[str]:
    if not user_info:
        return [
            "User: Anonymous (no authenticated identity — do not expose private data)."
        ]
    lines: list[str] = []
    username = str(user_info.get("username") or "").strip()
    display = str(user_info.get("display_name") or username or "Unknown").strip()
    roles = user_info.get("roles") or []
    role_txt = ", ".join(str(r) for r in roles if r) if roles else ""
    audience = user_info.get("audience") or []
    aud_txt = ", ".join(sorted(str(a) for a in audience if a)) if audience else ""
    bits = [f"User: {display}"]
    if username and username != display:
        bits.append(f"username={username}")
    if role_txt:
        bits.append(f"roles={role_txt}")
    if aud_txt:
        bits.append(f"audience={aud_txt}")
    lines.append(" · ".join(bits))
    employee = user_info.get("employee") or None
    if isinstance(employee, dict) and employee:
        emp_bits = [
            str(employee[k])
            for k in ("full_name", "job_title", "org_unit")
            if employee.get(k)
        ]
        emp_no = employee.get("employee_no")
        if emp_no:
            emp_bits.insert(0 if not emp_bits else 1, f"employee_no={emp_no}")
        if emp_bits:
            lines.append("Employee: " + ", ".join(emp_bits))
    return lines


@dataclass
class IdentityBlock:
    """Shared persona + audience guidance + date/user/surface/autonomy (PV2-2A)."""

    persona: str = ""
    audience: frozenset[str] | set[str] | list[str] | tuple[str, ...] = field(
        default_factory=lambda: {"ess"}
    )
    guidance: dict[str, str] = field(default_factory=dict)
    date_line: str = ""
    user_lines: list[str] = field(default_factory=list)
    language: str = ""
    surface: str = "chat"
    autonomy: str = ""

    def _guidance_key(self) -> str:
        aud = {
            str(a).strip().lower()
            for a in (self.audience or ())
            if str(a).strip()
        }
        g = self.guidance or {}
        if "admin" in aud and (g.get("admin") or "").strip():
            return "admin"
        if "hr" in aud and (g.get("hr") or "").strip():
            return "hr"
        if (g.get("ess") or "").strip():
            return "ess"
        for key in ("admin", "hr", "ess"):
            if (g.get(key) or "").strip():
                return key
        return "ess"

    def render(self) -> str:
        # Priority under IDENTITY_BLOCK_MAX_CHARS (high → low):
        #   1. meta (date / user / language / surface / autonomy)
        #   2. audience guidance (role-scoped tools / rights)
        #   3. shared persona (clipped to fill remaining budget)
        # Never let a long persona erase date or ESS/HR guidance (PV2-2A).
        meta: list[str] = []
        if (self.date_line or "").strip():
            meta.append(self.date_line.strip())
        for line in self.user_lines or []:
            if (line or "").strip():
                meta.append(line.strip())
        if (self.language or "").strip():
            meta.append(f"Reply language: {self.language.strip()}")
        surface = (self.surface or "chat").strip() or "chat"
        # Only emit Surface/autonomy when this is a full ContextPack identity
        # (date_line set) OR when autonomy was explicitly provided. Persona-only
        # composition via compose_persona_for_audience stays persona+guidance.
        if (self.date_line or "").strip() or (self.autonomy or "").strip():
            meta.append(f"Surface: {surface}")
        if (self.autonomy or "").strip():
            meta.append(self.autonomy.strip())
        meta_text = "\n".join(meta)

        key = self._guidance_key()
        guidance = ((self.guidance or {}).get(key) or "").strip()
        persona = (self.persona or "").strip()

        fixed_parts = [p for p in (guidance, meta_text) if p]
        fixed = "\n\n".join(fixed_parts)
        if persona and fixed:
            reserved = len(fixed) + 2
            persona = _clip(persona, max(0, IDENTITY_BLOCK_MAX_CHARS - reserved))
            body = "\n\n".join(p for p in (persona, fixed) if p)
            return body if len(body) <= IDENTITY_BLOCK_MAX_CHARS else _clip(body, IDENTITY_BLOCK_MAX_CHARS)
        if persona and not fixed:
            return _clip(persona, IDENTITY_BLOCK_MAX_CHARS)
        return _clip(fixed, IDENTITY_BLOCK_MAX_CHARS)


def compose_persona_for_audience(
    instance_config: dict[str, Any] | None,
    audience: Iterable[str] | None,
) -> str:
    """Render IdentityBlock persona+guidance from instance.yaml (PV2-2C)."""
    cfg = instance_config or {}
    persona = cfg.get("persona") or ""
    if isinstance(persona, dict):
        # Archetype templates sometimes store structured persona; flatten.
        persona = (
            persona.get("text")
            or persona.get("body")
            or " ".join(str(v) for v in persona.values() if v)
        )
    guidance = cfg.get("guidance_by_audience") or {}
    if not isinstance(guidance, dict):
        guidance = {}
    return IdentityBlock(
        persona=str(persona or ""),
        audience=list(audience or ["ess"]),
        guidance={str(k): str(v or "") for k, v in guidance.items()},
    ).render()


def build_identity_block(
    *,
    instance_config: dict[str, Any] | None = None,
    user_info: dict[str, Any] | None = None,
    surface: str = "chat",
    language: str = "",
    now: datetime | None = None,
) -> IdentityBlock:
    """Full IdentityBlock for ContextPack (persona + date + user + autonomy)."""
    cfg = instance_config or {}
    persona = cfg.get("persona") or ""
    if isinstance(persona, dict):
        persona = (
            persona.get("text")
            or persona.get("body")
            or " ".join(str(v) for v in persona.values() if v)
        )
    guidance = cfg.get("guidance_by_audience") or {}
    if not isinstance(guidance, dict):
        guidance = {}
    audience = (user_info or {}).get("audience") or ["ess"]
    surf = surface if surface in VALID_SURFACES else "chat"
    lang = (language or "").strip() or str((user_info or {}).get("language") or "").strip()
    return IdentityBlock(
        persona=str(persona or ""),
        audience=list(audience),
        guidance={str(k): str(v or "") for k, v in guidance.items()},
        date_line=format_today_line(cfg, now=now),
        user_lines=_user_identity_lines(user_info),
        language=lang,
        surface=surf,
        autonomy=_autonomy_for_surface(surf),
    )


def render_history_content(message: dict[str, Any]) -> str:
    """Assistant history text with optional ≤200-char tool digest (PV2-1C).

    Engine-local copy of the host assembler helper so ContextPack never imports
    ``ai.context_assembler`` (import boundary).
    """
    content = str(message.get("content") or "")
    if (message.get("role") or "") != "assistant":
        return content
    meta = message.get("metadata_json") or {}
    if not isinstance(meta, dict):
        meta = {}
    digest = str(meta.get("tool_digest") or "").strip()
    if not digest:
        return content
    prefix = "\n[Tool results] "
    room = 200 - len(prefix)
    if len(digest) > room:
        digest = digest[: room - 1] + "…"
    return f"{content}{prefix}{digest}"


def _render_history_block(conversation_history: list[dict] | None) -> str:
    if not conversation_history:
        return ""
    lines: list[str] = ["CONVERSATION HISTORY (recent, with tool digests):"]
    for msg in (conversation_history or [])[-HISTORY_MESSAGE_MAX:]:
        if not isinstance(msg, dict):
            continue
        role = (msg.get("role") or "user").strip() or "user"
        content = render_history_content(msg).strip()
        if not content:
            continue
        lines.append(f"{role}: {_clip(content, HISTORY_MSG_CLIP)}")
    if len(lines) == 1:
        return ""
    return _clip("\n".join(lines), HISTORY_BLOCK_MAX_CHARS)


def _render_knowledge_block(retrieval: Any) -> str:
    chunks = getattr(retrieval, "knowledge_chunks", None) if retrieval is not None else None
    if chunks is None and isinstance(retrieval, dict):
        chunks = retrieval.get("knowledge_chunks")
    parts: list[str] = []
    for chunk in chunks or []:
        if isinstance(chunk, dict):
            content = (chunk.get("content") or "").strip()
        else:
            content = str(chunk or "").strip()
        if content:
            parts.append(f"- {content}")
    if not parts:
        return ""
    body = "\n".join(parts)
    return _clip(f"KNOWLEDGE:\n{body}", KNOWLEDGE_BLOCK_MAX_CHARS)


def _render_memory_block(retrieval: Any) -> str:
    chunks = getattr(retrieval, "memory_chunks", None) if retrieval is not None else None
    if chunks is None and isinstance(retrieval, dict):
        chunks = retrieval.get("memory_chunks")
    parts: list[str] = []
    for chunk in chunks or []:
        if isinstance(chunk, dict):
            content = (chunk.get("content") or "").strip()
        else:
            content = str(chunk or "").strip()
        if content:
            parts.append(f"- {content}")
    if not parts:
        return ""
    body = "\n".join(parts)
    return _clip(f"MEMORY:\n{body}", MEMORY_BLOCK_MAX_CHARS)


def _default_task_for_stage(
    stage: str,
    *,
    task_body: str = "",
    delivery_guide: str = "",
    hints: list[str] | None = None,
    escalate_hints: list[str] | None = None,
) -> str:
    if (task_body or "").strip():
        return _clip(task_body.strip(), TASK_BLOCK_MAX_CHARS)
    if stage == "critic":
        return TASK_CRITIC
    if stage == "verify":
        return TASK_VERIFY
    if stage == "verify_correct":
        return TASK_VERIFY_CORRECT
    if stage == "weather_normalize":
        # Callers distinguish location-reply vs full-question via task_body override.
        return TASK_WEATHER_QUESTION
    if stage == "escalate":
        hints_text = ", ".join(escalate_hints or []) if escalate_hints else "your request"
        return (
            TASK_ESCALATE
            + f"\nUnresolved entities: {hints_text}."
        )
    if stage == "recovery":
        return TASK_RECOVERY
    if stage == "synthesis":
        hints_note = ""
        if hints:
            hints_note = (
                "\nNote: the tool could not resolve these entities: "
                + ", ".join(hints)
                + ". If your answer would depend on them, say so and ask the "
                "user to clarify — do NOT invent values for them."
            )
        return TASK_SYNTHESIS.format(
            delivery_guide=delivery_guide or "explain the data clearly",
            hints_note=hints_note,
        )
    if stage == "fanout":
        return TASK_FANOUT
    if stage == "fanout_synthesis":
        return TASK_FANOUT_SYNTHESIS
    if stage == "decompose":
        return TASK_DECOMPOSE
    if stage == "observe":
        return TASK_OBSERVE
    if stage == "plan_synthesis":
        return TASK_PLAN_SYNTHESIS
    if stage == "discovery_clarify":
        return TASK_DISCOVERY_CLARIFY
    if stage == "draft":
        return TASK_DRAFT
    if stage == "intent":
        return task_body or (
            "TASK — Intent recognition: classify the user message against the "
            "closed endpoint / navigation label set provided in the user message."
        )
    return task_body or f"TASK — stage={stage}"


@dataclass
class ContextPack:
    """Composed prompt pack shared by every chat-turn LLM stage."""

    identity: str = ""
    state: str = ""
    history: str = ""
    knowledge: str = ""
    memory: str = ""
    task: str = ""
    user: str = ""
    surface: str = "chat"
    stage: str = "draft"

    def system_prompt(self) -> str:
        parts: list[str] = []
        for block in (
            self.identity,
            self.state,
            self.history,
            self.knowledge,
            self.memory,
            self.task,
        ):
            text = (block or "").strip()
            if text:
                parts.append(text)
        return "\n\n".join(parts)

    def user_prompt(self) -> str:
        return (self.user or "").strip()


def build_context_pack(
    state: Any = None,
    surface: str = "chat",
    stage: str = "draft",
    *,
    user_info: dict[str, Any] | None = None,
    instance_config: dict[str, Any] | None = None,
    conversation_history: list[dict] | None = None,
    retrieval: Any = None,
    language: str = "",
    user_message: str = "",
    task_body: str = "",
    user_body: str = "",
    delivery_guide: str = "",
    hints: list[str] | None = None,
    escalate_hints: list[str] | None = None,
    include_history: bool = True,
    include_state: bool = True,
    include_knowledge: bool = True,
    include_memory: bool = True,
    now: datetime | None = None,
) -> ContextPack:
    """Build a ContextPack for one LLM stage.

    ``task_body`` overrides the stage TaskBlock template (e.g. draft uses
    ``build_chat_prompt`` output; intent uses the closed-label classifier text).
    """
    surf = surface if surface in VALID_SURFACES else "chat"
    stg = stage if stage in VALID_STAGES else stage or "draft"

    identity = build_identity_block(
        instance_config=instance_config,
        user_info=user_info,
        surface=surf,
        language=language,
        now=now,
    ).render()

    state_text = ""
    if include_state and state is not None:
        try:
            from ai.engine.cognition.state_store import (
                STATE_BLOCK_MAX_CHARS as _SB_MAX,
                render_state_block,
            )
            state_text = render_state_block(state, max_chars=_SB_MAX)
        except Exception:  # noqa: BLE001 — pack must never raise for absent state
            state_text = ""

    history = _render_history_block(conversation_history) if include_history else ""
    knowledge = _render_knowledge_block(retrieval) if include_knowledge else ""
    memory = _render_memory_block(retrieval) if include_memory else ""

    task = _default_task_for_stage(
        stg,
        task_body=task_body,
        delivery_guide=delivery_guide,
        hints=hints,
        escalate_hints=escalate_hints,
    )
    task = _clip(task, TASK_BLOCK_MAX_CHARS)

    user = (user_body or "").strip()
    if not user and (user_message or "").strip():
        user = (user_message or "").strip()

    return ContextPack(
        identity=identity,
        state=state_text,
        history=history,
        knowledge=knowledge,
        memory=memory,
        task=task,
        user=user,
        surface=surf,
        stage=stg,
    )
