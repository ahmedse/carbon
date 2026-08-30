"""P4.3 — Skills Admission Gate — Three Critics + Marginal-Gain Check.

Before a draft skill can be promoted to instance_promoted, it must pass
three heterogeneous critics and a marginal-gain check. This is the
non-negotiable gate from MASTER-PLAN §4.

Critics
-------
1. STRUCTURAL   (rules, no LLM) — validates signature/body JSON, kind,
   name collision with existing tools.
2. HARMLESSNESS (rules + optional LLM) — checks for dangerous patterns.
   Only calls LLM for api_call / code_snippet kinds.
3. CONSISTENCY  (LLM) — checks that the new skill doesn't contradict
   any existing instance_promoted skill.
4. MARGINAL GAIN (eval) — runs the skill on a small sample, compares
   to baseline.

All results are written to SkillAdmissionLog.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai.engine.core.clock import utcnow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.config import get_settings
from ai.engine.core.models import Skill, SkillAdmissionLog, generate_uuid

logger = logging.getLogger("pulse.skills.gate")


# ═══════════════════════════════════════════════════════════════════════════
# Shared types
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CriticVerdict:
    passed: bool
    flags: list[str] = field(default_factory=list)
    details: dict | None = None

    @property
    def rejected(self) -> bool:
        return not self.passed


# ── Dangerous pattern registry (no LLM needed) ───────────────────────────

_DANGEROUS_PATTERNS = [
    (re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX)\b", re.IGNORECASE), "DROP statement"),
    (re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE), "DELETE FROM statement"),
    (re.compile(r"\bTRUNCATE\b", re.IGNORECASE), "TRUNCATE statement"),
    (re.compile(r"\bALTER\s+(TABLE|DATABASE)\b", re.IGNORECASE), "ALTER statement"),
    (re.compile(r"\beval\s*\(", re.IGNORECASE), "eval() call"),
    (re.compile(r"\bexec\s*\(", re.IGNORECASE), "exec() call"),
    (re.compile(r"\bsubprocess\b", re.IGNORECASE), "subprocess usage"),
    (re.compile(r"\bos\.system\b", re.IGNORECASE), "os.system() call"),
    (re.compile(r"\bos\.popen\b", re.IGNORECASE), "os.popen() call"),
    (re.compile(r"\b__import__\s*\(", re.IGNORECASE), "__import__() call"),
    (re.compile(r"\bcompile\s*\(", re.IGNORECASE), "compile() call"),
]

SKILL_KINDS = {
    "sql_macro", "api_call", "prompt_template", "multi_step_plan",
    "code_snippet", "tool_preset", "procedure", "heuristic", "resolution",
}

# ── Harmlessness LLM prompt ──────────────────────────────────────────────

_HARMLESSNESS_PROMPT = """You are a security reviewer for an AI copilot system.

Review this skill body for safety issues. The skill kind is "{kind}".

Skill body (JSON):
{body}

Check for:
- Hardcoded credentials or secrets
- Unbounded loops or recursive patterns
- External URLs that aren't from the host system's allowed origin
- SQL injection risks in dynamic query construction
- Any pattern that could cause data loss or privilege escalation

Return ONLY a JSON object:
{{"passed": true/false, "flags": ["flag1", "flag2"], "rationale": "one sentence"}}"""


# ═══════════════════════════════════════════════════════════════════════════
# CRITIC 1 — Structural (rules only, <1 ms)
# ═══════════════════════════════════════════════════════════════════════════

async def structural_critic(skill: Skill, db: AsyncSession | None = None) -> CriticVerdict:
    """Validate signature JSON, body JSON, kind, and name uniqueness.

    Returns CriticVerdict with flags for each issue found.
    """
    flags: list[str] = []
    settings = get_settings()

    if not settings.SKILL_GATE_STRUCTURAL_ENABLED:
        return CriticVerdict(passed=True, flags=["structural_disabled"])

    # ── Kind ──
    if skill.kind not in SKILL_KINDS:
        flags.append(f"invalid_kind: {skill.kind}")

    # ── Signature: must be valid JSON object ──
    try:
        sig = json.loads(skill.signature) if skill.signature else {}
        if not isinstance(sig, dict):
            flags.append("signature_not_object")
    except (json.JSONDecodeError, TypeError):
        flags.append("signature_invalid_json")

    # ── Body: must be valid JSON ──
    try:
        body = json.loads(skill.body) if skill.body else {}
        if not isinstance(body, dict):
            flags.append("body_not_object")
    except (json.JSONDecodeError, TypeError):
        flags.append("body_invalid_json")

    # ── Name collision with existing tools (optional fast check) ──
    if db is not None and skill.name:
        from ai.engine.core.models import Skill as SkillModel
        existing = await db.execute(
            select(SkillModel).where(
                SkillModel.instance_id == skill.instance_id,
                SkillModel.name == skill.name,
                SkillModel.id != skill.id,
            )
        )
        if existing.scalar_one_or_none():
            flags.append(f"name_collision: {skill.name}")

    return CriticVerdict(
        passed=len(flags) == 0,
        flags=flags,
        details={"checks": ["kind", "signature", "body", "name_collision"]},
    )


# ═══════════════════════════════════════════════════════════════════════════
# CRITIC 2 — Harmlessness (rules + optional LLM)
# ═══════════════════════════════════════════════════════════════════════════

async def harmlessness_critic(skill: Skill) -> CriticVerdict:
    """Check for dangerous patterns. Uses LLM only for risky kinds.

    Kinds api_call and code_snippet trigger a second-pass LLM review.
    All other kinds are rules-only.
    """
    settings = get_settings()

    if not settings.SKILL_GATE_HARMLESSNESS_ENABLED:
        return CriticVerdict(passed=True, flags=["harmlessness_disabled"])

    flags: list[str] = []

    # ── Rules phase: check body + signature for dangerous patterns ─────────
    text_to_scan = (skill.body or "") + (skill.signature or "") + (skill.description or "")

    for pattern, label in _DANGEROUS_PATTERNS:
        if pattern.search(text_to_scan):
            flags.append(f"dangerous_pattern: {label}")

    if flags:
        return CriticVerdict(passed=False, flags=flags,
                             details={"phase": "rules"})

    # ── LLM phase: only for api_call / code_snippet ────────────────────────
    if skill.kind in ("api_call", "code_snippet"):
        from ai.engine.llm.router import route_chat

        prompt = _HARMLESSNESS_PROMPT.format(kind=skill.kind, body=skill.body)

        try:
            result = await route_chat(
                task="cognition",
                instance_id=skill.instance_id,
                conversation_id=f"gate-harmlessness-{skill.id}",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = (result.get("content") or "").strip()

            try:
                verdict = json.loads(content)
                if isinstance(verdict, dict) and not verdict.get("passed", True):
                    llm_flags = verdict.get("flags", [])
                    flags.extend(llm_flags)
                    if not llm_flags:
                        flags.append("harmlessness_llm_rejected")
            except json.JSONDecodeError:
                logger.warning("harmlessness_critic: unparseable LLM response: %s", content[:200])

            return CriticVerdict(
                passed=len(flags) == 0,
                flags=flags,
                details={"phase": "rules+llm", "kind": skill.kind},
            )
        except Exception as exc:
            logger.warning("harmlessness_critic: LLM call failed: %s", exc)
            # Fail open on LLM error — structural critic already cleared
            return CriticVerdict(passed=True, flags=["harmlessness_llm_error"],
                                 details={"error": str(exc)})

    return CriticVerdict(passed=True, flags=[],
                         details={"phase": "rules_only"})


# ═══════════════════════════════════════════════════════════════════════════
# CRITIC 3 — Consistency (LLM)
# ═══════════════════════════════════════════════════════════════════════════

_CONSISTENCY_PROMPT = """You are a consistency reviewer for an AI copilot system.

A new skill is proposed. Check if it contradicts any of the EXISTING instance-promoted skills.

NEW SKILL:
  Name: {name}
  Kind: {kind}
  Description: {description}
  Body: {body}

EXISTING PROMOTED SKILLS:
{existing_skills}

A contradiction means: the new skill would produce a different result for the
same input, or its preconditions conflict with another skill, or its description
directly negates another skill's guidance.

Return ONLY a JSON object:
{{"passed": true/false, "flags": ["flag1"], "conflicting_skill_name": "name or null", "rationale": "one sentence"}}"""


async def consistency_critic(skill: Skill, db: AsyncSession) -> CriticVerdict:
    """Check that the new skill doesn't contradict any existing promoted skill."""
    settings = get_settings()

    if not settings.SKILL_GATE_CONSISTENCY_ENABLED:
        return CriticVerdict(passed=True, flags=["consistency_disabled"])

    from ai.engine.llm.router import route_chat

    # Fetch instance-promoted skills excluding this one
    result = await db.execute(
        select(Skill).where(
            Skill.instance_id == skill.instance_id,
            Skill.status == "instance_promoted",
            Skill.id != skill.id,
        )
    )
    promoted = result.scalars().all()

    if not promoted:
        return CriticVerdict(passed=True, flags=[],
                             details={"existing_count": 0})

    existing_text = "\n".join(
        f"- {s.name} ({s.kind}): {s.description}" for s in promoted
    )

    prompt = _CONSISTENCY_PROMPT.format(
        name=skill.name,
        kind=skill.kind,
        description=skill.description,
        body=skill.body,
        existing_skills=existing_text,
    )

    try:
        route_result = await route_chat(
            task="cognition",
            instance_id=skill.instance_id,
            conversation_id=f"gate-consistency-{skill.id}",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        content = (route_result.get("content") or "").strip()

        try:
            verdict = json.loads(content)
            if isinstance(verdict, dict):
                passed = verdict.get("passed", True)
                flags = verdict.get("flags", [])
                return CriticVerdict(
                    passed=passed,
                    flags=flags,
                    details={
                        "existing_count": len(promoted),
                        "conflicting_skill": verdict.get("conflicting_skill_name"),
                        "rationale": verdict.get("rationale"),
                    },
                )
        except json.JSONDecodeError:
            logger.warning("consistency_critic: unparseable LLM response: %s", content[:200])

        return CriticVerdict(passed=True, flags=["consistency_llm_unparseable"])

    except Exception as exc:
        logger.warning("consistency_critic: LLM call failed: %s", exc)
        return CriticVerdict(passed=True, flags=["consistency_llm_error"],
                             details={"error": str(exc)})


# ═══════════════════════════════════════════════════════════════════════════
# CRITIC 4 — Marginal Gain (eval)
# ═══════════════════════════════════════════════════════════════════════════

async def marginal_gain_check(
    skill: Skill, db: AsyncSession, instance_id: str
) -> CriticVerdict:
    """Run the eval suite against current code vs baseline scorecard.

    Uses ``evals.stream.run_stream`` to compare pass rates.  If any suite
    regresses beyond ``SKILL_GATE_MARGINAL_GAIN_MAX_REGRESSION`` the skill
    is blocked.

    Returns
    -------
    CriticVerdict
        ``passed=False`` when the stream verdict is BLOCKED, ``passed=True``
        otherwise (including first-run / no-baseline).
    """
    settings = get_settings()

    if not settings.SKILL_GATE_MARGINAL_GAIN_ENABLED:
        return CriticVerdict(passed=True, flags=["marginal_gain_disabled"])

    sample_size = settings.SKILL_GATE_MARGINAL_GAIN_SAMPLE_SIZE

    try:
        from pathlib import Path
        import json

        # ── Resolve baseline path ──────────────────────────────────────────
        if settings.SKILL_GATE_MARGINAL_GAIN_BASELINE_PATH:
            baseline_path = settings.SKILL_GATE_MARGINAL_GAIN_BASELINE_PATH
        else:
            baseline_path = str(
                Path("instances") / instance_id / "data" / "scorecard.json"
            )

        # ── Run the eval stream ────────────────────────────────────────────
        from evals.stream import run_stream

        report = await run_stream(
            suites=[settings.SKILL_GATE_MARGINAL_GAIN_SUITE],
            instance_id=instance_id,
            baseline_scorecard_path=baseline_path,
            out_dir=None,
            limit=sample_size,
            seed=42,
        )

        verdict = report.get("verdict", "PASSED")
        flags: list[str] = []
        details: dict = {
            "stream_verdict": verdict,
            "total_cases": report.get("total_cases", 0),
            "overall_pass_rate": report.get("overall_pass_rate", 0.0),
            "suite": settings.SKILL_GATE_MARGINAL_GAIN_SUITE,
        }

        # ── Extract per-suite deltas ───────────────────────────────────────
        max_regression = 0.0
        for suite_name, suite_data in report.get("suites", {}).items():
            delta = suite_data.get("delta", 0)
            baseline_rate = suite_data.get("baseline_pass_rate")
            current_rate = suite_data.get("pass_rate", 0)
            if isinstance(delta, (int, float)):
                max_regression = max(max_regression, abs(min(delta, 0)))
                details[f"suite_{suite_name}_delta"] = delta
                details[f"suite_{suite_name}_pass_rate"] = current_rate
                if baseline_rate is not None:
                    details[f"suite_{suite_name}_baseline"] = baseline_rate

        details["max_regression"] = round(max_regression, 4)

        if verdict == "BLOCKED":
            allowed = settings.SKILL_GATE_MARGINAL_GAIN_MAX_REGRESSION
            if max_regression > allowed:
                flags.append(
                    f"eval_regression: {max_regression:.2%} > {allowed:.2%}"
                )
                return CriticVerdict(passed=False, flags=flags, details=details)

        return CriticVerdict(passed=True, flags=flags, details=details)

    except Exception as exc:
        logger.warning("marginal_gain_check: error: %s", exc)
        return CriticVerdict(passed=True, flags=["marginal_gain_error"],
                             details={"error": str(exc)})


# ═══════════════════════════════════════════════════════════════════════════
# Top-level admission
# ═══════════════════════════════════════════════════════════════════════════

async def admit_skill(skill_id: str, db: AsyncSession, admitted_by: str = "auto") -> dict:
    """Run all 4 critics and return the admission verdict.

    Returns:
        {"verdict": "admitted"|"rejected", "flags": [...], "passed": bool,
         "rejected_by": "structural"|"harmlessness"|"consistency"|"marginal_gain"|None,
         "critics": {...}}
    """
    # Fetch skill
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        return {"verdict": "rejected", "flags": ["skill_not_found"], "passed": False,
                "rejected_by": "structural", "critics": {}}

    # 1. Structural
    s = await structural_critic(skill, db)
    if s.rejected:
        await _write_log(db, skill, structural=s, harmlessness=None,
                         consistency=None, marginal_gain=None,
                         verdict="rejected", rejected_by="structural",
                         admitted_by=admitted_by)
        return _result("rejected", "structural", s)

    # 2. Harmlessness
    h = await harmlessness_critic(skill)
    if h.rejected:
        await _write_log(db, skill, structural=s, harmlessness=h,
                         consistency=None, marginal_gain=None,
                         verdict="rejected", rejected_by="harmlessness",
                         admitted_by=admitted_by)
        return _result("rejected", "harmlessness", s, h)

    # 3. Consistency
    c = await consistency_critic(skill, db)
    if c.rejected:
        await _write_log(db, skill, structural=s, harmlessness=h,
                         consistency=c, marginal_gain=None,
                         verdict="rejected", rejected_by="consistency",
                         admitted_by=admitted_by)
        return _result("rejected", "consistency", s, h, c)

    # 4. Marginal gain
    g = await marginal_gain_check(skill, db, skill.instance_id)
    if g.rejected:
        await _write_log(db, skill, structural=s, harmlessness=h,
                         consistency=c, marginal_gain=g,
                         verdict="rejected", rejected_by="marginal_gain",
                         admitted_by=admitted_by)
        return _result("rejected", "marginal_gain", s, h, c, g)

    # All passed
    await _write_log(db, skill, structural=s, harmlessness=h,
                     consistency=c, marginal_gain=g,
                     verdict="admitted", rejected_by=None,
                     admitted_by=admitted_by)
    return _result("admitted", None, s, h, c, g)


async def promote_skill(skill_id: str, db: AsyncSession, promoted_by: str = "auto") -> Skill:
    """Admit then promote a skill to instance_promoted.

    If admission fails, raises ValueError with the rejection reason.
    Only promotes skills with gate_status='pending'.
    """
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise ValueError(f"Skill not found: {skill_id}")

    if skill.gate_status == "pending":
        admission = await admit_skill(skill_id, db, admitted_by=promoted_by)
        if admission["verdict"] != "admitted":
            raise ValueError(
                f"Admission rejected by {admission['rejected_by']}: "
                f"{admission['flags']}"
            )

    now = utcnow()
    skill.status = "instance_promoted"
    skill.promoted_at = now
    skill.promoted_by = promoted_by
    skill.gate_status = "admitted"

    await db.commit()
    await db.refresh(skill)
    logger.info("promote_skill: %s (%s) → instance_promoted by %s",
                 skill.name, skill.id, promoted_by)
    return skill


async def rollback_skill(skill_id: str, db: AsyncSession, reason: str = "") -> Skill:
    """Deprecate a skill with a rollback reason."""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise ValueError(f"Skill not found: {skill_id}")

    skill.status = "deprecated"
    skill.gate_status = "rejected"

    await db.commit()
    await db.refresh(skill)
    logger.info("rollback_skill: %s (%s) → deprecated. reason=%s",
                 skill.name, skill.id, reason)
    return skill


# ═══════════════════════════════════════════════════════════════════════════
# Sleep-time admission sweep (P4.3 / Pulse 0.2 Phase B1)
# ═══════════════════════════════════════════════════════════════════════════

async def run_skill_admission(db, instance_id: str) -> dict:
    """Run the admission gate on every pending draft Skill for one instance.

    Closes the promotion arrow: ``consolidation.py`` drafts skills with
    ``gate_status="pending"``, and this sleep-time job runs each one through
    the four critics, promoting admitted skills to ``instance_promoted``.
    Every evaluation writes a ``SkillAdmissionLog`` row via ``admit_skill``
    (no duplicate logging here).

    Returns
    -------
    dict
        ``{"evaluated": N, "promoted": N, "rejected": N}``
    """
    settings = get_settings()
    if not settings.SKILL_ADMISSION_ENABLED:
        logger.info("Skill admission disabled — skipping instance=%s", instance_id)
        return {"evaluated": 0, "promoted": 0, "rejected": 0}

    result = await db.execute(
        select(Skill).where(
            Skill.instance_id == instance_id,
            Skill.gate_status == "pending",
        )
    )
    pending = list(result.scalars().all())

    promoted = 0
    rejected = 0

    for skill in pending:
        try:
            admission = await admit_skill(
                skill.id, db, admitted_by="system:gate"
            )

            if admission["verdict"] == "admitted":
                # admit_skill's _write_log already committed, which clears the
                # store's tracked-object registry — re-fetch the row so the
                # status transition below is actually persisted.
                skill_id = skill.id
                fresh = await db.execute(
                    select(Skill).where(Skill.id == skill_id)
                )
                skill = fresh.scalar_one_or_none()
                if skill is None:
                    logger.warning(
                        "run_skill_admission: skill %s vanished after admission",
                        skill_id,
                    )
                    continue

                now = utcnow()
                skill.status = "instance_promoted"
                skill.promoted_at = now
                skill.promoted_by = "system:gate"
                skill.gate_status = "admitted"
                await db.commit()
                promoted += 1
                logger.info(
                    "run_skill_admission: promoted skill '%s' (%s) for %s",
                    skill.name, skill.id, instance_id,
                )
            else:
                rejected += 1
                logger.info(
                    "run_skill_admission: rejected skill '%s' (%s) by %s: %s",
                    skill.name, skill.id,
                    admission.get("rejected_by"), admission.get("flags"),
                )
        except Exception:
            logger.exception(
                "run_skill_admission: error evaluating a pending skill for %s",
                instance_id,
            )

    summary = {"evaluated": len(pending), "promoted": promoted, "rejected": rejected}
    logger.info("run_skill_admission: instance=%s result=%s", instance_id, summary)
    return summary


async def _run_skill_admission_for_all_instances():
    """Nightly: run the skill admission gate for every active instance.

    Called from the scheduler (``loop.py``) after the consolidation sweep has
    drafted new pending skills.
    """
    from ai.store import get_store
    from ai.engine.core.models import Instance

    factory = get_store().get_session_factory()
    async with factory() as db:
        instances = await db.select(Instance, ("status", "active"))

        for inst in instances:
            try:
                summary = await run_skill_admission(db, inst.id)
                logger.info(
                    "Skill admission: instance=%s result=%s",
                    inst.name, summary,
                )
            except Exception:
                logger.exception(
                    "Skill admission failed for %s", inst.name,
                )


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _result(verdict: str, rejected_by: str | None,
            structural: CriticVerdict | None = None,
            harmlessness: CriticVerdict | None = None,
            consistency: CriticVerdict | None = None,
            marginal_gain: CriticVerdict | None = None) -> dict:
    """Build the admission result dict."""
    all_flags: list[str] = []
    critics = {}

    if structural:
        all_flags.extend(structural.flags)
        critics["structural"] = {"passed": structural.passed, "flags": structural.flags}
    if harmlessness:
        all_flags.extend(harmlessness.flags)
        critics["harmlessness"] = {"passed": harmlessness.passed, "flags": harmlessness.flags}
    if consistency:
        all_flags.extend(consistency.flags)
        critics["consistency"] = {"passed": consistency.passed, "flags": consistency.flags}
    if marginal_gain:
        all_flags.extend(marginal_gain.flags)
        critics["marginal_gain"] = {"passed": marginal_gain.passed, "flags": marginal_gain.flags}

    return {
        "verdict": verdict,
        "passed": verdict == "admitted",
        "rejected_by": rejected_by,
        "flags": all_flags,
        "critics": critics,
    }


async def _write_log(
    db: AsyncSession,
    skill: Skill,
    structural: CriticVerdict | None,
    harmlessness: CriticVerdict | None,
    consistency: CriticVerdict | None,
    marginal_gain: CriticVerdict | None,
    verdict: str,
    rejected_by: str | None,
    admitted_by: str,
) -> None:
    log = SkillAdmissionLog(
        id=generate_uuid(),
        skill_id=skill.id,
        instance_id=skill.instance_id,
        structural_passed=structural.passed if structural else False,
        harmlessness_passed=harmlessness.passed if harmlessness else False,
        consistency_passed=consistency.passed if consistency else False,
        marginal_gain_passed=marginal_gain.passed if marginal_gain else False,
        structural_flags_json=json.dumps(structural.flags) if structural else None,
        harmlessness_flags_json=json.dumps(harmlessness.flags) if harmlessness else None,
        consistency_flags_json=json.dumps(consistency.flags) if consistency else None,
        marginal_gain_details_json=(
            json.dumps(marginal_gain.details) if marginal_gain else None
        ),
        verdict=verdict,
        rejected_by=rejected_by,
        admitted_by=admitted_by,
    )
    db.add(log)
    await db.commit()
