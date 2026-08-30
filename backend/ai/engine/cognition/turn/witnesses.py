"""Six-witness dataclasses for the cognition pipeline.

Each witness produces a typed result. Pipeline runner stitches them
sequentially and writes a TurnLedger row per stage.
"""
from dataclasses import dataclass, field


# ── S1 — Salience ──────────────────────────────────────────────────────────────

@dataclass
class SalienceResult:
    """Output of S1: intent classification without LLM (regex-based)."""
    weight: float = 1.0           # 0.0 (trivial) → 1.0 (urgent)
    domain: str = "general"       # "data" | "operational" | "conversational" | "identity"
    route: str = "fast"           # "fast" | "full" | "deep"
    salience_features: dict = field(default_factory=dict)


# ── S2 — Retrieval ─────────────────────────────────────────────────────────────

@dataclass
class RetrievalResult:
    """Output of S2: knowledge + memory context pack."""
    knowledge_chunks: list[dict] = field(default_factory=list)
    memory_chunks: list[dict] = field(default_factory=list)
    tool_suggestions: list[str] = field(default_factory=list)
    citation_ids: list[str] = field(default_factory=list)
    retrieval_latency_ms: float = 0.0


# ── S3 — Draft ─────────────────────────────────────────────────────────────────

@dataclass
class DraftResult:
    """Output of S3: LLM-generated draft with tool calls and citations."""
    text: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    claimed_citations: list[str] = field(default_factory=list)
    confidence: float = 0.8
    model_used: str = ""
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


# ── S4 — Critic ────────────────────────────────────────────────────────────────

@dataclass
class CriticVerdict:
    """Output of S4: rules-tier (and optional LLM-tier) safety review."""
    # "pass" | "pass_with_flag" | "rewrite" | "veto" | "knowledge_gap"
    # knowledge_gap: LLM produced uncertain/empty output on a specific query.
    # Runner escalates to a better model or returns honest-uncertainty response.
    verdict: str = "pass"
    flags: list[str] = field(default_factory=list)  # e.g. "ungrounded_claim", "cross_tenancy"
    rewritten_text: str = ""
    veto_reason: str = ""
    partial_knowledge: str = ""  # what the model DID say before deciding it didn't know


# ── S5 — Execute ───────────────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    """Output of S5: tool execution + streaming."""
    completed_tools: list[dict] = field(default_factory=list)
    streamed: bool = False
    execution_latency_ms: float = 0.0
    per_tool_latency_ms: dict[str, float] = field(default_factory=dict)


# ── Turn Ledger ────────────────────────────────────────────────────────────────

@dataclass
class TurnLedger:
    """Aggregate ledger for one turn — collects output from all six stages."""
    turn_id: str = ""
    instance_id: str = ""
    host_user_id: str | None = None
    conversation_id: str = ""
    user_message: str = ""
    salience: SalienceResult | None = None
    retrieval: RetrievalResult | None = None
    draft: DraftResult | None = None
    critic: CriticVerdict | None = None
    execution: ExecutionResult | None = None
    final_response: str = ""
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    total_llm_calls: int = 0
    # Phase 21-A: prompt/completion split + resolved model for usage attribution.
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model_used: str = ""
    created_at: str = ""
    # P3.2: Fan-out fields
    fan_out_used: bool = False
    fan_out_worker_count: int = 0
    fan_out_worker_ids: list[str] | None = None
    fan_out_artifact_refs: list[dict] | None = None
    fan_out_total_tokens: int = 0
    fan_out_latency_ms: float = 0.0
    # P3.4 — Budget tracking
    budget_snapshot: dict | None = None  # {budget, consumed, remaining, exceeded, justification}
    budget_exceeded: bool = False
    # C1 — adaptive reasoning lane: records any escalation to the reason model.
    # {trigger, from_model, to_model, verdict_before, verdict_after}
    reason_escalation: dict | None = None
