"""
Central configuration — ALL settings from .env.
Never import os.environ directly in other modules. Use get_settings().
For instance-specific env vars (e.g. PERFORMARC_DB_URL), use resolve_env_var().

Instance isolation: every instance gets its own data directory under
instances/{name}/data/.  Use resolve_instance_paths(name) to get the
per-instance DB path, ChromaDB directory, etc.  The legacy shared
paths (data/pulse.db, data/chroma/) are only used as fallbacks during
migration and for backwards compatibility.
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Pulse Core ──
    PULSE_ENV: str = "development"
    PULSE_PORT: int = 9100
    PULSE_SECRET_KEY: str = "change-me"
    PULSE_DB_PATH: str = "./data/pulse.db"
    PULSE_DB_URL: str = ""           # if non-empty, overrides PULSE_DB_PATH (e.g. postgresql+asyncpg://...)
    PULSE_LOG_LEVEL: str = "INFO"

    # ── Frontend Dev Servers ──
    WIDGET_PORT: int = 5174
    STUDIO_PORT: int = 5177

    # ── Host System (default / fallback) ──
    HOST_DB_URL: str = ""
    HOST_DB_SCHEMA: str = "public"
    HOST_DB_READ_ONLY: bool = True
    HOST_API_URL: str = ""
    HOST_EVAL_USER_TOKEN: str = ""  # optional JWT for tenancy_probes; never logged
    # Instance-specific env vars (e.g. PERFORMARC_DB_URL) are resolved
    # dynamically via resolve_env_var() — no need to declare them here.

    # ── LLM ──
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = "anthropic/claude-haiku-4.5"          # deep mode / fallback
    LLM_NORMAL_MODEL: str = "anthropic/claude-haiku-4.5"   # normal mode
    LLM_EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_COGNITION_MODEL: str = "anthropic/claude-haiku-4.5"
    LLM_INTROSPECT_MODEL: str = ""               # schema enrichment; falls back to LLM_MODEL
    EVAL_MODEL: str | None = None                # eval/judge model; falls back to LLM_MODEL
    PULSE_ALLOW_EXPENSIVE_MODELS: bool = False  # override cost guardrail

    # ── Eval Policy (Wave 9C — token-safe gating) ─────────────────────
    EVAL_ENABLED: bool = True                     # master switch; false refuses all eval runs
    EVAL_POLICY: str = "smoke"                    # smoke | full — smoke caps runs; full allows unbounded
    EVAL_MAX_CASES: int = 5                       # default cap when --limit omitted (smoke policy)
    EVAL_ALLOWED_SUITES: str = (                  # suite whitelist (comma-separated)
        "regression,hallucination,consistency,tenancy_probes"
    )

    # ── LLM Cost Tracking ──
    LLM_DAILY_BUDGET_USD: float = 5.0            # per-instance daily spend cap
    LLM_COST_MODELS: str = (
        '{"Claude-Haiku-4.5": {"input": 1.0, "output": 5.0},'
        ' "Claude-Sonnet-4.5": {"input": 3.0, "output": 5.0},'
        ' "GPT-4o": {"input": 2.5, "output": 10.0},'
        ' "GPT-4o-mini": {"input": 0.15, "output": 0.6}}'
    )  # JSON: model → {input, output} cost per 1M tokens

    # ── Agent ──
    AGENT_UNIFIED_FINALIZE: bool = True          # collapse _wisdom_review + _enrich + _follow_ups into 1 LLM call
    AGENT_MAX_WORKERS: int = 6          # P3.1: max parallel workers per run
    AGENT_WORKER_TIMEOUT_SEC: int = 60  # P3.1: per-worker timeout
    AGENT_ORCHESTRATOR_ENABLED: bool = True  # P3.2: orchestrator fan-out gate

    # ── Guardrails (P3.3) ──
    GUARDRAIL_MAX_TOOL_CALLS_PER_RUN: int = 20
    GUARDRAIL_MAX_TOKENS_PER_RUN: int = 100_000
    GUARDRAIL_BUDGET_ENFORCEMENT: bool = True
    GUARDRAIL_REDACTED_TOOLS: str = '[]'

    # ── Autonomy (Wave 8A) ──
    DEFAULT_AUTONOMY_LEVEL: str = "off"  # off | low | medium | high

    # ── Per-run Budget (P3.4) ──
    RUN_TOKEN_BUDGET_DEFAULT: int = 50_000       # default per-run cap (tokens)
    RUN_TOKEN_BUDGET_WORKER_SHARE: float = 0.4   # max fraction of run budget for all workers combined
    RUN_TOKEN_BUDGET_MIN_WORKER: int = 2_000     # minimum budget per worker

    # ── Cognition Loop ──
    COGNITION_PIPELINE_SPINE: bool = True     # BE-01-5: spine is the default path
    COGNITION_HEALTH_INTERVAL: int = 3600
    COGNITION_FRESHNESS_INTERVAL: int = 21600
    COGNITION_SNAPSHOT_INTERVAL: int = 86400
    COGNITION_ERROR_CHECK_INTERVAL: int = 3600
    COGNITION_SCHEMA_DRIFT_INTERVAL: int = 86400
    COGNITION_SYNTHESIS_INTERVAL: int = 86400
    COGNITION_REFLECTION_INTERVAL: int = 604800
    COGNITION_DECAY_INTERVAL: int = 86400
    COGNITION_DECAY_AFTER_DAYS: int = 30
    COGNITION_EPISODIC_DECAY_INTERVAL: int = 86400  # B4: episodic memory decay sweep (24h)
    COGNITION_DISTILLATION_INTERVAL: int = 86400   # PR-14: daily episodic→semantic sweep
    COGNITION_PROMOTION_INTERVAL: int = 604800      # PR-14: weekly fact promotion (7 days)
    COGNITION_FACT_DECAY_INTERVAL: int = 2592000    # PR-14: monthly fact decay (30 days)
    COGNITION_SELF_REFLECT_INTERVAL: int = 604800   # PR-15: weekly self-reflection (7 days)

    # ── Consolidation Sweep (P4.2) ──
    CONSOLIDATION_SWEEP_MAX_LLM_CALLS: int = 10        # max LLM calls per sweep
    CONSOLIDATION_SWEEP_MIN_CONFIDENCE: float = 0.6     # min confidence to create a skill
    CONSOLIDATION_SWEEP_ENABLED: bool = True

    # ── Skills Admission Gate (P4.3) ──
    SKILL_GATE_STRUCTURAL_ENABLED: bool = True
    SKILL_GATE_HARMLESSNESS_ENABLED: bool = True
    SKILL_GATE_CONSISTENCY_ENABLED: bool = True
    SKILL_GATE_MARGINAL_GAIN_ENABLED: bool = True
    SKILL_GATE_MARGINAL_GAIN_SAMPLE_SIZE: int = 5
    SKILL_GATE_MARGINAL_GAIN_MAX_REGRESSION: float = 0.05  # max allowed drop in pass_rate
    SKILL_GATE_MARGINAL_GAIN_SUITE: str = "regression"
    SKILL_GATE_MARGINAL_GAIN_BASELINE_PATH: str = ""  # if empty, uses instances/{instance}/data/scorecard.json

    # ── Task Handler (Phase 7 — Carbon AI Modules) ──
    TASK_DQ_VALIDATE_TIMEOUT: int = 10          # seconds — sync (Carbon expects 10s)
    TASK_DQ_SUGGEST_TIMEOUT: int = 60           # seconds — async (Carbon expects 60s)
    TASK_NL_QUERY_TIMEOUT: int = 30             # seconds
    TASK_NL_QUERY_MAX_ROWS: int = 100           # max rows returned
    TASK_ANOMALY_MIN_HISTORY: int = 6           # minimum profile snapshots needed
    TASK_DEFAULT_TIMEOUT: int = 30              # fallback for unknown task types

    # ── Embedding Store ──
    VECTOR_BACKEND: str = "chromadb"       # "chromadb" | "pgvector"
    PGVECTOR_EMBEDDING_DIM: int = 1536     # vector dimension (1536 for text-embedding-3-small, 384 for all-MiniLM-L6-v2)
    CHROMA_PERSIST_DIR: str = "./data/chroma"

    # ── Hybrid Retrieval (BE-02-2) ──
    RETRIEVAL_LLM_RERANK: bool = True    # use LLM to rerank fused (pgvector+BM25) results
    RETRIEVAL_HYBRID_ALPHA: float = 0.6  # vector weight in score fusion; BM25 weight = 1-alpha

    # ── Knowledge Graph ──
    KG_FORCE_REANALYZE: bool = False   # set True to re-run schema analysis on every startup
    KG_SQL_VALIDATION_RETRY: bool = True  # retry LLM once with validation errors appended

    # ── Data Profiling ──
    KG_DATA_PROFILING_ENABLED: bool = True          # run profiling after schema analysis
    KG_PROFILE_SAMPLE_SIZE: int = 10000             # max rows sampled per table
    KG_PROFILE_MAX_CARDINALITY: int = 50            # max distinct values stored in value_list
    KG_PROFILE_TTL_HOURS: int = 24                  # skip re-profiling if profile is younger
    KG_PROFILE_PII_ENABLED: bool = True             # auto-detect PII columns
    KG_PROFILE_PII_PATTERNS: str = ""               # comma-separated extra PII column-name patterns
    KG_RELATIONSHIP_MATCH_THRESHOLD: float = 0.7    # min overlap ratio to keep an inferred FK edge

    # ── Query Execution (Stage 5) ──
    KG_QUERY_TIMEOUT_MS: int = 15000         # per-query statement timeout in milliseconds
    KG_QUERY_ROW_LIMIT: int = 100            # max rows returned per execution
    KG_MAX_RETRIES: int = 2                  # max error-driven SQL repair attempts
    KG_FEEDBACK_ENABLED: bool = True         # store per-query feedback in kg_query_feedback

    # ── Response Synthesis (Stage 6) ──
    KG_ANSWER_CACHE_TTL: int = 300           # seconds to cache identical question+SQL answers
    KG_MAX_DISPLAY_ROWS: int = 10            # max rows surfaced in structured answer payload
    KG_CURRENCY_SYMBOL: str = "$"            # currency prefix for monetary columns
    KG_LOCALE: str = "en_US"                 # locale for number formatting

    # ── Caching (Stage 9) ──
    KG_CACHE_ENABLED: bool = True
    KG_CACHE_QUERY_TTL: int = 300            # Layer 1: default SQL result TTL (seconds)
    KG_CACHE_SEMANTIC_TTL: int = 3600        # Layer 2: utterance result TTL (seconds)
    KG_CACHE_MATERIALIZED_TTL: int = 14400   # Layer 3: pre-computed rollup TTL (4 hours)
    KG_CACHE_WARMUP_ENABLED: bool = True
    KG_CACHE_WARMUP_TOP_N: int = 50          # top N queries to re-execute during warm-up
    KG_CACHE_WARMUP_LOOKBACK_DAYS: int = 30  # days of history to mine for warm-up queries
    KG_CACHE_SEMANTIC_THRESHOLD: float = 0.92  # cosine similarity for fuzzy semantic match
    KG_CACHE_TABLE_TTLS: str = "{}"          # JSON: {"realtime_table": 60, "batch_table": 14400}

    # ── Error Recovery (Stage 10) ──
    KG_RECOVERY_ENABLED: bool = True
    KG_RECOVERY_EMPTY_RESULT: bool = True       # enable empty-result probe + fuzzy match
    KG_RECOVERY_TIMEOUT: bool = True            # enable timeout SQL simplification
    KG_RECOVERY_FUZZY_THRESHOLD: float = 0.8   # min SequenceMatcher ratio for "did you mean"
    KG_RECOVERY_TIME_RANGE_DAYS: int = 90      # days for time-range simplification on timeout
    KG_RECOVERY_AUDIT_ENABLED: bool = True     # write KgRecoveryLog rows

    # ── Feedback Loop (Stage 11) ──
    KG_FEEDBACK_LOOP_ENABLED: bool = True
    KG_FEEDBACK_QUALITY_NEUTRAL: float = 0.7           # default quality score when no signal
    KG_FEEDBACK_REPHRASE_WINDOW_SEC: int = 120         # max seconds between turns to count as rephrase
    KG_FEEDBACK_DRIFT_THRESHOLD: float = 0.65          # rolling avg below this triggers drift alert
    KG_FEEDBACK_DRIFT_WINDOW_DAYS: int = 7             # rolling window for drift detection
    KG_FEEDBACK_REVIEW_AUTO_APPROVE: bool = False       # auto-approve high-confidence corrections

    # ── Multi-Step Planning (Stage 12) ──
    KG_MULTI_STEP_ENABLED: bool = True
    KG_MULTI_STEP_MAX_STEPS: int = 6          # max steps in a single plan
    KG_MULTI_STEP_CONFIRM_THRESHOLD: int = 4  # ask user confirmation above this many steps
    KG_MULTI_STEP_PARALLEL: bool = True       # execute independent steps in parallel

    # ── Host API Call Discipline (N1) ──
    API_DISCIPLINE_ENABLED: bool = False      # route call_host_api GETs through validate→execute→retry
    API_MAX_RETRIES: int = 1                  # max error-driven API retries (transient / param repair)
    API_RETRY_BACKOFF_MS: int = 250           # base backoff between API retries (scaled by attempt)

    # ── Bootstrap Loop ──
    KG_BOOTSTRAP_ENABLED: bool = True
    KG_BOOTSTRAP_PERIODIC_HOURS: int = 168    # scheduled re-crawl every N hours (default: 7 days)
    KG_BOOTSTRAP_FEEDBACK_THRESHOLD: int = 20 # unresolved corrections that trigger re-bootstrap
    KG_BOOTSTRAP_HOST_CODE_PATH: str = ""     # path to host codebase for code crawler (empty = skip)

    # ── Proactive Intelligence (Stage 13) ──
    KG_PROACTIVE_ENABLED: bool = True
    KG_PROACTIVE_EVAL_INTERVAL: int = 300     # trigger evaluation every N seconds (default: 5 min)
    KG_PROACTIVE_BRIEFING_HOUR: int = 7       # hour-of-day (0-23) for daily briefing generation
    KG_PROACTIVE_COOLDOWN_DEFAULT: int = 3600 # default cooldown between re-fires (seconds)
    KG_PROACTIVE_EXPIRY_HOURS: int = 4        # info-level insights expire after N hours
    KG_PROACTIVE_MAX_INSIGHTS_PER_EVAL: int = 10  # cap insights per evaluation cycle
    KG_PROACTIVE_DEDUP_WINDOW_MINUTES: int = 30   # group co-occurring triggers within this window
    KG_PROACTIVE_DISMISS_LEARNING: bool = True     # feed dismissals back to trigger tuning

    # ── Studio Auth ──
    STUDIO_USERNAME: str = "admin"
    STUDIO_PASSWORD: str = "change-me"
    # Optional comma-separated list of additional admin usernames that share
    # STUDIO_PASSWORD. STUDIO_USERNAME is always included. Lets multiple named
    # admins (e.g. "ahmed,admin") sign in with the same password.
    STUDIO_USERNAMES: str = ""
    STUDIO_JWT_EXPIRY_HOURS: int = 8

    # ── Local Auth (standalone instances, auth.mode: local) ──
    AUTH_BCRYPT_ROUNDS: int = 12          # bcrypt cost factor for password hashing
    AUTH_LOCAL_JWT_EXPIRY_HOURS: int = 72 # local user sessions (longer for standalone apps)

    # ── CORS ──
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8001"

    # ── MCP Integration ──
    MCP_SERVERS: str = ""  # JSON list: [{"name":"brave","command":"npx","args":[...],"env":{...}}]
    MCP_TOOL_PREFIX: str = "mcp_"  # prefix for MCP-imported tools (e.g. "mcp_brave_web_search")
    MCP_CONNECT_TIMEOUT: int = 10  # seconds to wait for MCP server handshake
    MCP_MAX_TOOLS_PER_SERVER: int = 50  # cap tools per server

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # ── Security: weak-secret defaults are warned in dev, fatal in production ──
    #
    # The single source of truth for these checks lives here so a production
    # deployment cannot start with weak secrets regardless of which entry point
    # is used (uvicorn, CLI, tests with PULSE_ENV=production, etc.).

    _WEAK_SECRETS = frozenset({
        "", "change-me", "change-me-to-a-random-string",
        "secret", "password", "admin", "test",
    })
    _MIN_SECRET_LEN = 32  # PULSE_SECRET_KEY
    _MIN_PASSWORD_LEN = 12  # STUDIO_PASSWORD

    def studio_allowed_usernames(self) -> list[str]:
        """All admin usernames that may sign in with STUDIO_PASSWORD.

        Always includes STUDIO_USERNAME, plus any names in the comma-separated
        STUDIO_USERNAMES list. Order-preserving and de-duplicated.
        """
        names: list[str] = []
        for raw in [self.STUDIO_USERNAME, *self.STUDIO_USERNAMES.split(",")]:
            name = (raw or "").strip()
            if name and name not in names:
                names.append(name)
        return names

    # ── Cost guardrail: models that are too expensive to ever run by default ──
    # Matched case-insensitively as substrings against every LLM_*_MODEL value.
    # If one is configured, Pulse auto-downgrades it to the cheap fallback and
    # logs a loud warning, so an accidental .env edit can never silently rack
    # up cost. Override deliberately with PULSE_ALLOW_EXPENSIVE_MODELS=true.
    _EXPENSIVE_MODEL_MARKERS = (
        "opus", "gpt-5", "gpt-4.5", "o1-", "o1 ", "claude-sonnet-4",
        "claude-3-opus", "claude-opus",
    )
    # Models retired/disabled on the provider (return 500 non_owner_disabled).
    # Matched case-insensitively as substrings; auto-healed to the cheap
    # fallback so a stale production .env can never 500 the whole service.
    _RETIRED_MODEL_MARKERS = (
        "claude-3.5-haiku", "claude-3-5-haiku",
    )
    # Bare/unversioned model names that are invalid on the provider — matched
    # case-insensitively as exact strings (not substrings) so that valid
    # versioned names like "Claude-Haiku-4.5" are not accidentally caught.
    _RETIRED_EXACT_MODELS = frozenset([
        "claude-haiku",   # bare name, no version — returns 500; use Claude-Haiku-4.5
        "claude-sonnet",  # bare name, no version
    ])
    _CHEAP_FALLBACK_MODEL = "anthropic/claude-haiku-4.5"
    _MODEL_FIELDS = (
        "LLM_MODEL", "LLM_NORMAL_MODEL", "LLM_COGNITION_MODEL", "LLM_INTROSPECT_MODEL",
    )

    @field_validator("DEFAULT_AUTONOMY_LEVEL")
    @classmethod
    def validate_autonomy_level(cls, v: str) -> str:
        allowed = {"off", "low", "medium", "high"}
        if v not in allowed:
            raise ValueError(f"DEFAULT_AUTONOMY_LEVEL must be one of {sorted(allowed)}, got '{v}'")
        return v

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        import warnings
        if not v or not v.strip():
            warnings.warn(
                "CORS_ORIGINS is empty. The widget and studio will not be able to connect.",
                stacklevel=2,
            )
        if "*" in (v or ""):
            warnings.warn(
                "CORS_ORIGINS contains a wildcard '*'. This is unsafe with "
                "allow_credentials=True and browsers will reject it. Use explicit origins.",
                stacklevel=2,
            )
        return v

    @model_validator(mode="after")
    def _enforce_cost_guardrail(self) -> "Settings":
        """Block accidentally-expensive LLM models unless explicitly allowed.

        Self-healing: an offending model is rewritten to the cheap fallback so
        the service keeps running cheaply instead of failing or burning budget.
        """
        import logging
        import os

        if self.PULSE_ALLOW_EXPENSIVE_MODELS:
            return self

        log = logging.getLogger("pulse.config")
        for field in self._MODEL_FIELDS:
            value = getattr(self, field, "") or ""
            low = value.lower()
            if any(marker in low for marker in self._EXPENSIVE_MODEL_MARKERS):
                log.warning(
                    "Cost guardrail: %s=%r is a forbidden expensive model. "
                    "Auto-downgrading to %s. Set PULSE_ALLOW_EXPENSIVE_MODELS=true "
                    "to override deliberately.",
                    field, value, self._CHEAP_FALLBACK_MODEL,
                )
                object.__setattr__(self, field, self._CHEAP_FALLBACK_MODEL)
            elif any(marker in low for marker in self._RETIRED_MODEL_MARKERS):
                log.warning(
                    "Model guardrail: %s=%r is retired on the provider and would "
                    "500. Auto-healing to %s.",
                    field, value, self._CHEAP_FALLBACK_MODEL,
                )
                object.__setattr__(self, field, self._CHEAP_FALLBACK_MODEL)
            elif low in self._RETIRED_EXACT_MODELS:
                log.warning(
                    "Model guardrail: %s=%r is a bare/unversioned model name "
                    "that returns 500 on the provider. Auto-healing to %s.",
                    field, value, self._CHEAP_FALLBACK_MODEL,
                )
                object.__setattr__(self, field, self._CHEAP_FALLBACK_MODEL)
        return self

    @model_validator(mode="after")
    def _enforce_security_invariants(self) -> "Settings":
        """Hard-fail in production on weak secrets; warn in development.

        Production = `PULSE_ENV` starts with "prod" (case-insensitive).
        This catches PULSE_ENV=production, production-eu, prod, etc.
        """
        import warnings

        env = (self.PULSE_ENV or "").strip().lower()
        is_production = env.startswith("prod")

        problems: list[str] = []

        # PULSE_SECRET_KEY
        if self.PULSE_SECRET_KEY in self._WEAK_SECRETS:
            problems.append(
                f"PULSE_SECRET_KEY is a known weak value ({self.PULSE_SECRET_KEY!r})."
            )
        elif len(self.PULSE_SECRET_KEY) < self._MIN_SECRET_LEN:
            problems.append(
                f"PULSE_SECRET_KEY is too short (len={len(self.PULSE_SECRET_KEY)}, "
                f"min={self._MIN_SECRET_LEN})."
            )

        # STUDIO_PASSWORD
        if self.STUDIO_PASSWORD in self._WEAK_SECRETS:
            problems.append(
                f"STUDIO_PASSWORD is a known weak value ({self.STUDIO_PASSWORD!r})."
            )
        elif len(self.STUDIO_PASSWORD) < self._MIN_PASSWORD_LEN:
            problems.append(
                f"STUDIO_PASSWORD is too short (len={len(self.STUDIO_PASSWORD)}, "
                f"min={self._MIN_PASSWORD_LEN})."
            )

        # CORS in production: must be a non-empty explicit allowlist (no wildcard,
        # no localhost). The permissive localhost regex is dev-only (see main.py).
        if is_production:
            origins = [o.strip() for o in (self.CORS_ORIGINS or "").split(",") if o.strip()]
            if not origins:
                problems.append("CORS_ORIGINS is empty in production; the widget cannot connect.")
            if any("*" in o for o in origins):
                problems.append("CORS_ORIGINS contains a wildcard '*', which is unsafe in production.")
            if any(("localhost" in o or "127.0.0.1" in o) for o in origins):
                problems.append("CORS_ORIGINS lists localhost/127.0.0.1 in production.")

        if not problems:
            return self

        message = (
            "Insecure configuration detected:\n  - "
            + "\n  - ".join(problems)
            + f"\nSet strong values in .env (PULSE_ENV={env!r})."
        )

        if is_production:
            # Pydantic will surface this as a ValidationError at import time —
            # the process cannot start.
            raise ValueError(message)
        else:
            warnings.warn(message, stacklevel=2)

        return self


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def resolve_env_var(ref: str, default: str = "") -> str:
    """Resolve a ${VAR_NAME} reference from Settings first, then os.environ.

    This allows instance YAML files to reference any env var (e.g.
    ${PERFORMARC_DB_URL}) without needing to declare it in the Settings class.
    """
    if not isinstance(ref, str) or not ref.startswith("${") or not ref.endswith("}"):
        return ref
    var_name = ref[2:-1]
    # Try Settings first (covers HOST_DB_URL, HOST_API_URL, etc.)
    value = getattr(get_settings(), var_name, None)
    if value:
        return value
    # Fall back to os.environ (covers instance-specific vars like PERFORMARC_DB_URL)
    return os.environ.get(var_name, default)


# ── Instance-scoped paths ────────────────────────────────────────────────────
#
# Every instance gets its own isolated data directory:
#   instances/{name}/data/pulse.db
#   instances/{name}/data/chroma/
#
# This replaces the old shared data/pulse.db and data/chroma/ layout.
# The legacy shared paths are only used as fallbacks for backwards compat.

_INSTANCES_ROOT = Path(__file__).resolve().parent.parent / "instances"


def resolve_instance_paths(instance_name: str) -> dict:
    """Return per-instance storage paths.

    Returns dict with keys: db_path, chroma_dir, data_dir.
    The paths are NOT validated — callers should ensure directories exist.
    """
    data_dir = _INSTANCES_ROOT / instance_name / "data"
    return {
        "data_dir": str(data_dir),
        "db_path": str(data_dir / "pulse.db"),
        "chroma_dir": str(data_dir / "chroma"),
    }


def ensure_instance_dirs(instance_name: str) -> dict:
    """Create per-instance data directories if they don't exist.

    Returns the same dict as resolve_instance_paths().
    """
    paths = resolve_instance_paths(instance_name)
    Path(paths["data_dir"]).mkdir(parents=True, exist_ok=True)
    Path(paths["chroma_dir"]).mkdir(parents=True, exist_ok=True)
    return paths
