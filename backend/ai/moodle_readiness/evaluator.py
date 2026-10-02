"""Readiness evaluator — the single source of truth for the four frozen ladders.

Given typed :class:`ReadinessInputs`, :func:`evaluate` computes which rungs pass.
It mirrors the benchmark rules in ``docs/pulse/aast-med/READINESS-SPEC.md``
verbatim and **hardcodes no rung result**: every rung is a list of gates over
the inputs. Missing any required artifact means not-PASS.

:func:`repo_inputs` reads the committed gold (``gold/l5.yaml``) and the default
notice registry so a report reflects the real repository state. It never
invents a student cohort: ``student_cohorts`` is an input and stays empty.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "GateResult",
    "ReadinessInputs",
    "ReadinessReport",
    "RungResult",
    "evaluate",
    "repo_inputs",
]

REPO_ROOT = Path(__file__).resolve().parents[3]
GOLD_DIR = REPO_ROOT / "domain_packs" / "aast-med" / "gold"

#: Minimum plugin version that carries the four tabs + Course door (K10 Stage 2).
PLUGIN_VERSION_MIN = 2026100215

#: L5 curriculum benchmark constants (spec § L5). Read, not assumed, in report.
L5_SAMPLE_SIZE = 100
L5_MIN_PASSAGE_CITE = 95
L5_MAX_EXTRA_FACT = 2
R11_REQUIRED_N = 4
R12_REQUIRED_N = 2

_BLOCKED_K10 = "real-world: production Moodle install + staff notice to the cohort"
_BLOCKED_K11 = "real-world: student cohort + consent + authored gold (R11/R12/R12 needs 2 students)"
_BLOCKED_B5 = "real-world: cohort + consent + audit + R12; true only after K11"
_BLOCKED_B6 = "real-world: authored lecture->ILO->assessment edges; later product, no store now"
_BLOCKED_C7 = "real-world: session/outcome edges only after C6 and L5"


@dataclass(frozen=True)
class GateResult:
    id: str
    ok: bool
    measure: str


@dataclass(frozen=True)
class RungResult:
    id: str
    name: str
    status: str  # "pass" | "not_pass"
    gates: tuple[GateResult, ...]
    blocked_by: str
    benchmark: str

    @property
    def passed(self) -> bool:
        return self.status == "pass"


@dataclass(frozen=True)
class ReadinessInputs:
    """Typed inputs. Every field defaults to the honest current state."""

    # ── K10 staff production ────────────────────────────────────────────────
    production_installed: bool = False
    plugin_version: int = 0
    plugin_version_min: int = PLUGIN_VERSION_MIN
    hmac_configured: bool = False
    staff_cohorts_non_empty: bool = False
    listed_courses_all_have_c6_gold: bool = False
    staff_notice_published: bool = False
    # ── K11 students / L5 ───────────────────────────────────────────────────
    student_cohorts_non_empty: bool = False
    student_notice_published: bool = False
    consent_gate_present: bool = False
    rbac_path_present: bool = False
    audit_path_present: bool = False
    l5_status: str = "not_passable"
    l5_sample_size: int = 0
    l5_min_passage_cite: int = 0
    l5_max_extra_fact: int = 0
    r11_frozen_n: int = 0
    r11_required_n: int = R11_REQUIRED_N
    r12_frozen_n: int = 0
    r12_required_n: int = R12_REQUIRED_N
    # ── B4 / B5 memory ──────────────────────────────────────────────────────
    memory_short_typed: bool = False
    memory_long_store_present: bool = False
    # ── B6 / C7 graph ───────────────────────────────────────────────────────
    c6_green_all_listed: bool = False
    c7_edges_built: bool = False
    graph_present: bool = False


@dataclass(frozen=True)
class ReadinessReport:
    rungs: tuple[RungResult, ...]

    @property
    def by_id(self) -> dict[str, RungResult]:
        return {r.id: r for r in self.rungs}

    @property
    def passed_ids(self) -> tuple[str, ...]:
        return tuple(r.id for r in self.rungs if r.passed)

    def as_dict(self) -> dict[str, Any]:
        return {
            "rungs": [
                {
                    **{k: v for k, v in asdict(r).items() if k != "gates"},
                    "gates": [asdict(g) for g in r.gates],
                }
                for r in self.rungs
            ]
        }


def _status(gates: tuple[GateResult, ...]) -> str:
    return "pass" if gates and all(g.ok for g in gates) else "not_pass"


def _l5_passable(inputs: ReadinessInputs) -> bool:
    return inputs.l5_status == "passable"


def _evaluate_k10(i: ReadinessInputs) -> RungResult:
    gates = (
        GateResult("production_installed", i.production_installed, "plugin installed on the production Moodle 4.1 site"),
        GateResult("plugin_version", i.plugin_version >= i.plugin_version_min, f"plugin version >= {i.plugin_version_min}"),
        GateResult("hmac_configured", i.hmac_configured, "Ask URL + pane URL + HMAC secret set, signature verifies"),
        GateResult("staff_cohorts_non_empty", i.staff_cohorts_non_empty, "staff_cohorts names at least one cohort"),
        GateResult("listed_courses_c6_gold", i.listed_courses_all_have_c6_gold, "every enabled shortname has C6 gold"),
        GateResult("staff_notice_published", i.staff_notice_published, "R15+R18 notice sent to exactly that cohort"),
    )
    return RungResult(
        "K10",
        "Staff on production",
        _status(gates),
        gates,
        _BLOCKED_K10,
        "On the real Moodle, a staff cohort member on a listed course gets a cited answer and "
        "the exact lecture miss; HMAC verifies; the notice names cohort + shortnames.",
    )


def _evaluate_k11(i: ReadinessInputs) -> RungResult:
    gates = (
        GateResult("l5_passable", _l5_passable(i), "L5 status is passable"),
        GateResult("l5_sample_size", i.l5_sample_size >= L5_SAMPLE_SIZE, f"gold sample size >= {L5_SAMPLE_SIZE} per shortname"),
        GateResult("l5_min_passage_cite", i.l5_min_passage_cite >= L5_MIN_PASSAGE_CITE, f">= {L5_MIN_PASSAGE_CITE} of {L5_SAMPLE_SIZE} cite a passage"),
        GateResult("l5_max_extra_fact", 0 < i.l5_max_extra_fact <= L5_MAX_EXTRA_FACT, f"< {L5_MAX_EXTRA_FACT} added facts per shortname"),
        GateResult("r11_frozen", i.r11_frozen_n >= i.r11_required_n, f"R11 frozen cases >= {i.r11_required_n}"),
        GateResult("r12_frozen", i.r12_frozen_n >= i.r12_required_n, f"R12 frozen cases >= {i.r12_required_n}"),
        GateResult("student_notice_published", i.student_notice_published, "separate student-visible notice published (R16)"),
        GateResult("student_cohorts_non_empty", i.student_cohorts_non_empty, "student_cohorts names at least one cohort"),
        GateResult("consent_gate_present", i.consent_gate_present, "consent gate constructed and enforcing"),
        GateResult("rbac_path_present", i.rbac_path_present, "RBAC: user can already open the course"),
        GateResult("audit_path_present", i.audit_path_present, "append-only allow/deny + consent audit"),
    )
    return RungResult(
        "K11",
        "Students and the frozen gate",
        _status(gates),
        gates,
        _BLOCKED_K11,
        "L5 passable for every listed shortname, student notice published, student_cohorts non-empty, "
        "consent + RBAC + audit path present before any student turn.",
    )


def _evaluate_b4(i: ReadinessInputs) -> RungResult:
    gates = (
        GateResult("short_memory_typed", i.memory_short_typed, "typed ConversationState / resolved_topic, no history scan"),
    )
    return RungResult(
        "B4",
        "Short memory",
        _status(gates),
        gates,
        "",
        "Short memory is typed conversation state; no second store and no prose scan.",
    )


def _evaluate_b5(i: ReadinessInputs) -> RungResult:
    gates = (
        GateResult("long_store_present", i.memory_long_store_present, "per-student store exists behind the gate"),
        GateResult("student_cohorts_non_empty", i.student_cohorts_non_empty, "cohort non-empty"),
        GateResult("consent_gate_present", i.consent_gate_present, "consent present"),
        GateResult("audit_path_present", i.audit_path_present, "audit present"),
        GateResult("r12_frozen", i.r12_frozen_n >= i.r12_required_n, f"R12 frozen cases >= {i.r12_required_n}"),
    )
    return RungResult(
        "B5",
        "Long per-student memory",
        _status(gates),
        gates,
        _BLOCKED_B5,
        "Non-empty student cohort plus consent and audit plus R12; must never mix another student's log.",
    )


def _evaluate_b6(i: ReadinessInputs) -> RungResult:
    gates = (
        GateResult("graph_present", i.graph_present, "lecture->ILO->assessment edges exist and are queryable"),
        GateResult("c6_green_all_listed", i.c6_green_all_listed, "C6 green for every listed shortname"),
    )
    return RungResult(
        "B6",
        "Lecture graph",
        _status(gates),
        gates,
        _BLOCKED_B6,
        "Authored, passage-grounded lecture->ILO->assessment edges. Indexing is not a graph; no Neo4j.",
    )


def _evaluate_c7(i: ReadinessInputs) -> RungResult:
    gates = (
        GateResult("c6_green_all_listed", i.c6_green_all_listed, "C6 green for every listed shortname"),
        GateResult("l5_passable", _l5_passable(i), "L5 passable"),
        GateResult("c7_edges_built", i.c7_edges_built, "session/outcome edges exist"),
    )
    return RungResult(
        "C7",
        "Session and outcome edges",
        _status(gates),
        gates,
        _BLOCKED_C7,
        "Built only after C6 is green and L5 is passable. Not a gate; not Carbon's schema knowledge_graph.",
    )


def evaluate(inputs: ReadinessInputs | None = None) -> ReadinessReport:
    """Compute every rung from the typed inputs. Pure; no I/O."""
    data = inputs if isinstance(inputs, ReadinessInputs) else ReadinessInputs()
    rungs = (
        _evaluate_k10(data),
        _evaluate_k11(data),
        _evaluate_b4(data),
        _evaluate_b5(data),
        _evaluate_b6(data),
        _evaluate_c7(data),
    )
    return ReadinessReport(rungs=rungs)


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml

        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, Exception):  # noqa: BLE001 — report degrades, never crashes
        return {}
    return doc if isinstance(doc, dict) else {}


def repo_inputs(*, memory_short_typed: bool = True, **overrides: Any) -> ReadinessInputs:
    """Read the real repository state into :class:`ReadinessInputs`.

    ``l5_status``, the sample size, cite/extra bars and R11/R12 frozen counts
    come from ``domain_packs/aast-med/gold/l5.yaml``. ``student_cohorts``,
    consent, RBAC, audit and production install default to their honest
    closed state — this function never invents a cohort.

    ``memory_short_typed`` defaults True because the typed-state field is a
    code fact (B4); passing False flips B4 to not-PASS, proving it is an input.
    """
    gold = _load_yaml(GOLD_DIR / "l5.yaml")
    benchmark = gold.get("curriculum_benchmark") if isinstance(gold.get("curriculum_benchmark"), dict) else {}
    r11 = gold.get("r11_draft") if isinstance(gold.get("r11_draft"), dict) else {}
    r12 = gold.get("r12_same_lecture_two_students") if isinstance(gold.get("r12_same_lecture_two_students"), dict) else {}
    base = ReadinessInputs(
        l5_status=str(gold.get("status") or "not_passable"),
        l5_sample_size=int(benchmark.get("sample_size") or 0),
        l5_min_passage_cite=int(benchmark.get("min_passage_cite") or 0),
        l5_max_extra_fact=int(benchmark.get("max_extra_fact") or 0),
        r11_frozen_n=int(r11.get("frozen_n") or 0),
        r11_required_n=int(r11.get("required_n") or R11_REQUIRED_N),
        r12_frozen_n=int(r12.get("frozen_n") or 0),
        r12_required_n=int(r12.get("required_n") or R12_REQUIRED_N),
        memory_short_typed=bool(memory_short_typed),
    )
    if not overrides:
        return base
    return ReadinessInputs(**{**asdict(base), **overrides})
