# TASK-CARBON-AI-WAVE-A — Protocol + MockProvider

**Wave:** A of `CARBON-PHASE2-AI-INTELLIGENCE.md`  
**Estimate:** ~2 days  
**Depends on:** Nothing (greenfield — `backend/ai/` doesn't exist yet)  
**Blocks:** Wave B (Pulse Provider)

---

## 0. Context for Workers

You are building Phase 2 of Carbon's AI intelligence layer. Read these first:

| Doc | Path | Why |
|-----|------|-----|
| **Plan** | `plans/CARBON-PHASE2-AI-INTELLIGENCE.md` | Full vision, all waves, all dataclass definitions in §8 |
| **Contract spec** | `docs/PULSE_CONTRACT_SPEC.md` | The Pulse-Carbon contract (task types, response shapes) |
| **Existing gateway** | `backend/pulse_gateway.py` | Current HTTP layer (you're NOT editing this — just read for context) |
| **Settings** | `backend/config/settings.py` | Where `AI_PROVIDER_*` config goes (lines 460–466) |

**Hard rules (from plan §10):**
1. No hardcoded credentials. All from `settings.AI_PROVIDER_*`.
2. No Pulse imports in `ai/protocol.py`. Zero. Not even `django.conf`.
3. `ai/protocol.py` is pure Python — no Django, no providers, no HTTP.
4. `MockProvider` returns deterministic fake data — no randomness, no sleeps.
5. Tests before gates. All tests must pass before the wave is greenlit.

**Current state:** `backend/ai/` doesn't exist. You're creating it.

---

## 1. Deliverable A1 — `backend/ai/protocol.py`

**Worker:** Backend Worker  
**File:** `backend/ai/protocol.py` (new)  
**Goal:** Define the AIProvider ABC and all typed dataclasses. This file is the single source of truth for Carbon's AI contract.

### 1.1 Files to create

```
backend/ai/
├── __init__.py          # Empty (Django AppConfig comes in Wave C)
└── protocol.py          # ← THIS FILE
```

### 1.2 Exact contents of `protocol.py`

```python
"""
Carbon AI Intelligence — Protocol (Wave A)

THE CONTRACT. Zero imports from Django, Pulse, or any provider.
Pure ABCs and dataclasses.

Any AI backend (Pulse, Azure OpenAI, Claude, local LLM) implements
AIProvider. CarbonIntelligence (Wave C) delegates to AIProvider.
Swap backends by changing AI_PROVIDER_CLASS in settings — zero
code changes anywhere else.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ── Scope ────────────────────────────────────────────────────────────────

@dataclass
class Scope:
    """User scope — injected into every AI call."""
    org_unit_ids: list[str]          # ["*"] = all, ["ou-1","ou-2"] = scoped
    module_ids: list[str]             # Specific modules the user can access
    is_read_only: bool = False        # True → provider must not suggest mutations
    is_superuser: bool = False        # True → full access
    user_identifier: str = ""         # For audit trail


# ── Provider Status ─────────────────────────────────────────────────────

@dataclass
class ProviderStatus:
    name: str
    version: str
    healthy: bool
    modules_available: list[str] = field(default_factory=list)
    error: str | None = None
    latency_ms: int = 0


# ── 1. DQ Validate ──────────────────────────────────────────────────────

@dataclass
class DqRuleInput:
    id: str
    prompt: str
    fields: list[str]
    severity: str  # "info" | "warn" | "error"


@dataclass
class DqValidateRequest:
    rules: list[DqRuleInput]
    rows: list[dict[str, Any]]
    context: dict[str, Any] = field(default_factory=dict)
    scope: Scope | None = None


@dataclass
class DqRuleResult:
    rule_id: str
    status: str  # "pass" | "fail" | "skipped_unavailable"
    failing_rows: list[int] | None = None
    explanation: str | None = None
    confidence: float | None = None


@dataclass
class DqValidateResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    results: list[DqRuleResult] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 2. DQ Suggest ───────────────────────────────────────────────────────

@dataclass
class TableProfile:
    name: str
    description: str
    row_count: int
    columns: list[dict[str, Any]]


@dataclass
class DqSuggestRequest:
    table: TableProfile
    scope: Scope | None = None


@dataclass
class DqSuggestion:
    definition: dict[str, Any]  # Complete v1 rule definition
    rationale: str
    severity: str
    confidence: float
    dimension: str


@dataclass
class DqSuggestResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    suggestions: list[DqSuggestion] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 3. NL Query ─────────────────────────────────────────────────────────

@dataclass
class NlQueryRequest:
    question: str
    tables: list[str] | None = None
    max_rows: int = 100
    scope: Scope | None = None
    domain_vocabulary: dict[str, str] | None = None


@dataclass
class NlQueryResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    sql: str | None = None
    rows: list[dict[str, Any]] | None = None
    row_count: int = 0
    execution_ms: int = 0
    recovery_applied: bool = False
    error: dict[str, str] | None = None


# ── 4. NL Query Explain ─────────────────────────────────────────────────

@dataclass
class NlExplainRequest:
    question: str
    sql: str
    row_count: int
    sample_rows: list[dict[str, Any]]
    scope: Scope | None = None


@dataclass
class NlExplainResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    explanation: str | None = None
    caveats: list[str] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 5. Anomaly Detection ────────────────────────────────────────────────

@dataclass
class AnomalyDetectRequest:
    table_name: str
    profile_history: list[dict[str, Any]]
    sensitivity: float = 2.0
    volume_threshold_pct: float = 30.0
    scope: Scope | None = None


@dataclass
class DetectedAnomaly:
    metric: str
    expected_range: dict[str, float]
    observed: float
    z_score: float
    severity: str  # "error" | "warning"
    explanation: str | None = None


@dataclass
class AnomalyDetectResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    anomalies: list[DetectedAnomaly] = field(default_factory=list)
    history_snapshots: int = 0
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 6. Anomaly Explain ──────────────────────────────────────────────────

@dataclass
class AnomalyExplainRequest:
    table_name: str
    anomaly: dict[str, Any]
    scope: Scope | None = None


@dataclass
class AnomalyExplainResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    explanation: str | None = None
    investigation_steps: list[str] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 7. Report Draft ─────────────────────────────────────────────────────

@dataclass
class ReportDraftRequest:
    report_type: str
    period_start: str  # ISO date
    period_end: str    # ISO date
    scope: Scope | None = None


@dataclass
class ReportSection:
    title: str
    content: str  # Markdown
    sql: str | None = None
    data: list[dict[str, Any]] | None = None
    narrative: str | None = None
    caveat: str | None = None


@dataclass
class ReportDraftResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    title: str | None = None
    summary: str | None = None
    report_type: str = ""
    period_start: str = ""
    period_end: str = ""
    generated_at: str = ""
    sections: list[ReportSection] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 8. Schema Analyze ───────────────────────────────────────────────────

@dataclass
class SchemaChange:
    change: str
    table_name: str
    field_name: str | None = None


@dataclass
class SchemaAnalyzeRequest:
    schema_changes: list[SchemaChange]
    context: str | None = None
    scope: Scope | None = None


@dataclass
class SchemaImpact:
    change: str
    impact: str
    severity: str  # "low" | "medium" | "high" | "critical"
    suggested_action: str


@dataclass
class SchemaAnalyzeResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    analysis: list[SchemaImpact] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── 9. Fix Suggest ──────────────────────────────────────────────────────

@dataclass
class FixSuggestRequest:
    issue_type: str
    table_name: str
    issue_description: str
    affected_rows: list[dict[str, Any]] | None = None
    profile: dict[str, Any] | None = None
    scope: Scope | None = None


@dataclass
class FixSuggestion:
    description: str
    confidence: float
    estimated_affected_rows: int
    requires_confirmation: bool  # ALWAYS True — never auto-fix
    suggested_action_type: str


@dataclass
class FixSuggestResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    issue_type: str = ""
    table_name: str = ""
    suggestions: list[FixSuggestion] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0


# ── AIProvider ABC ──────────────────────────────────────────────────────

class AIProvider(ABC):
    """One abstract class. Nine methods. Each backend implements them."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def provider_version(self) -> str:
        ...

    @abstractmethod
    def health_check(self) -> ProviderStatus:
        ...

    @abstractmethod
    def validate_dq(self, request: DqValidateRequest) -> DqValidateResponse:
        ...

    @abstractmethod
    def suggest_dq(self, request: DqSuggestRequest) -> DqSuggestResponse:
        ...

    @abstractmethod
    def query_nl(self, request: NlQueryRequest) -> NlQueryResponse:
        ...

    @abstractmethod
    def explain_query(self, request: NlExplainRequest) -> NlExplainResponse:
        ...

    @abstractmethod
    def detect_anomalies(self, request: AnomalyDetectRequest) -> AnomalyDetectResponse:
        ...

    @abstractmethod
    def explain_anomaly(self, request: AnomalyExplainRequest) -> AnomalyExplainResponse:
        ...

    @abstractmethod
    def draft_report(self, request: ReportDraftRequest) -> ReportDraftResponse:
        ...

    @abstractmethod
    def analyze_schema(self, request: SchemaAnalyzeRequest) -> SchemaAnalyzeResponse:
        ...

    @abstractmethod
    def suggest_fix(self, request: FixSuggestRequest) -> FixSuggestResponse:
        ...
```

### 1.3 Verification checklist

- [ ] File exists at `backend/ai/protocol.py`
- [ ] `grep -c 'import' backend/ai/protocol.py` → ≤ 4 (only `__future__`, `abc`, `dataclasses`, `typing`)
- [ ] `grep 'django\|Pulse\|pulse\|requests\|httpx' backend/ai/protocol.py` → ZERO matches
- [ ] `python -c "from backend.ai.protocol import AIProvider; assert hasattr(AIProvider, 'validate_dq')"` succeeds
- [ ] All 9 request/response pairs have matching names: `XxxRequest` ↔ `XxxResponse`
- [ ] `Scope` dataclass has all 5 fields with correct defaults
- [ ] All `FixSuggestion.requires_confirmation` are `True` (hard rule)

---

## 2. Deliverable A2 — `backend/ai/tests/test_protocol.py`

**Worker:** Test Worker  
**File:** `backend/ai/tests/test_protocol.py` (new)  
**Goal:** Prove dataclass integrity — serialization round-trips, defaults, type correctness.

### 2.1 Files to create

```
backend/ai/tests/
├── __init__.py              # Empty
├── conftest.py              # (optional — not needed for Wave A)
└── test_protocol.py         # ← THIS FILE
```

### 2.2 Test cases (minimum)

| # | Test | What it proves |
|---|------|---------------|
| 1 | `test_scope_defaults` | Scope instantiates with all defaults correctly |
| 2 | `test_dq_validate_roundtrip` | DqValidateRequest → dict → DqValidateRequest via `dataclasses.asdict` + constructor |
| 3 | `test_dq_suggest_roundtrip` | DqSuggestRequest round-trip including nested TableProfile |
| 4 | `test_nl_query_roundtrip` | NlQueryRequest with domain_vocabulary round-trip |
| 5 | `test_nl_explain_roundtrip` | NlExplainRequest round-trip |
| 6 | `test_anomaly_detect_roundtrip` | AnomalyDetectRequest round-trip including profile_history |
| 7 | `test_anomaly_explain_roundtrip` | AnomalyExplainRequest round-trip |
| 8 | `test_report_draft_roundtrip` | ReportDraftRequest → ReportDraftResponse round-trip including nested ReportSection |
| 9 | `test_schema_analyze_roundtrip` | SchemaAnalyzeRequest → SchemaAnalyzeResponse round-trip including nested SchemaImpact |
| 10 | `test_fix_suggest_roundtrip` | FixSuggestRequest → FixSuggestResponse round-trip |
| 11 | `test_provider_status_roundtrip` | ProviderStatus round-trip |
| 12 | `test_all_responses_have_status_field` | Every *Response dataclass has `status: str` |
| 13 | `test_fix_suggest_requires_confirmation` | FixSuggestion.requires_confirmation always True |
| 14 | `test_response_error_defaults_to_none` | All Response `.error` defaults to None |

### 2.3 Pattern for each round-trip test

```python
import dataclasses
from backend.ai.protocol import DqRuleInput, DqRuleResult, DqValidateRequest, DqValidateResponse

def test_dq_validate_roundtrip():
    """DqValidateRequest → asdict → reconstruct → assert equality."""
    request = DqValidateRequest(
        rules=[
            DqRuleInput(id="r1", prompt="Check not null", fields=["col_a"], severity="error"),
        ],
        rows=[{"col_a": 1, "col_b": "x"}, {"col_a": None, "col_b": "y"}],
        context={"source": "test"},
        scope=None,
    )
    d = dataclasses.asdict(request)
    reconstructed = DqValidateRequest(**d)
    assert reconstructed.rules[0].id == "r1"
    assert reconstructed.rows[1]["col_b"] == "y"
    assert reconstructed.context["source"] == "test"
```

### 2.4 Run command

```bash
cd /home/ahmed/aast/carbon/backend
python -m pytest ai/tests/test_protocol.py -v
```

---

## 3. Deliverable A3 — `backend/ai/tests/test_protocol_swap.py`

**Worker:** Backend Worker + Test Worker (collaborate)  
**File:** `backend/ai/tests/test_protocol_swap.py` (new)  
**Goal:** Implement `MockProvider` (implements all 9 AIProvider methods with deterministic fake data) AND prove that if a real provider implements the same ABC, Carbon requires zero code changes.

### 3.1 The MockProvider

```python
from backend.ai.protocol import (
    AIProvider, Scope, ProviderStatus,
    DqValidateRequest, DqValidateResponse, DqRuleResult,
    DqSuggestRequest, DqSuggestResponse, DqSuggestion,
    NlQueryRequest, NlQueryResponse,
    NlExplainRequest, NlExplainResponse,
    AnomalyDetectRequest, AnomalyDetectResponse, DetectedAnomaly,
    AnomalyExplainRequest, AnomalyExplainResponse,
    ReportDraftRequest, ReportDraftResponse, ReportSection,
    SchemaAnalyzeRequest, SchemaAnalyzeResponse, SchemaImpact,
    FixSuggestRequest, FixSuggestResponse, FixSuggestion,
)


class MockProvider(AIProvider):
    """Deterministic fake provider. No randomness, no sleeps, no HTTP.
    
    Every method returns a realistic-but-fake response. Used to prove
    that CarbonIntelligence (Wave C) works identically with any provider
    that implements AIProvider.
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def provider_version(self) -> str:
        return "1.0.0-test"

    def health_check(self) -> ProviderStatus:
        return ProviderStatus(
            name="mock",
            version="1.0.0-test",
            healthy=True,
            modules_available=[
                "dq.validate", "dq.suggest", "carbon.query.nl",
                "carbon.query.explain", "carbon.anomaly.detect",
                "carbon.anomaly.explain", "carbon.report.draft",
                "carbon.schema.analyze", "carbon.fix.suggest",
            ],
        )

    def validate_dq(self, request: DqValidateRequest) -> DqValidateResponse:
        results = []
        for rule in request.rules:
            # Deterministic: pass if rule id contains "pass", fail otherwise
            passed = "pass" in rule.id.lower()
            results.append(DqRuleResult(
                rule_id=rule.id,
                status="pass" if passed else "fail",
                failing_rows=[0] if not passed else None,
                explanation=f"Mock check for rule {rule.id}",
                confidence=0.95,
            ))
        return DqValidateResponse(status="completed", results=results)
    
    # ... (all 9 methods)
```

### 3.2 Test cases for test_protocol_swap.py

| # | Test | What it proves |
|---|------|---------------|
| 1 | `test_mock_provider_is_ai_provider` | `isinstance(MockProvider(), AIProvider)` → True |
| 2 | `test_mock_health_check` | Returns ProviderStatus with healthy=True, 9 modules |
| 3 | `test_mock_validate_dq_pass` | Rule with "pass" in id → status="pass" |
| 4 | `test_mock_validate_dq_fail` | Rule without "pass" → status="fail", failing_rows populated |
| 5 | `test_mock_suggest_dq` | Returns 2 suggestions with fixed content |
| 6 | `test_mock_query_nl` | Returns deterministic SQL + rows |
| 7 | `test_mock_explain_query` | Returns explanation with caveats |
| 8 | `test_mock_detect_anomalies` | Returns 1 anomaly when volume_threshold_pct < observed delta |
| 9 | `test_mock_explain_anomaly` | Returns explanation + investigation_steps |
| 10 | `test_mock_draft_report` | Returns report with 2 sections |
| 11 | `test_mock_analyze_schema` | Returns schema impact analysis |
| 12 | `test_mock_suggest_fix` | Returns fix suggestions with requires_confirmation=True |
| 13 | `test_swap_providers_same_interface` | Call all 9 methods on MockProvider, verify return types match ABC |
| 14 | `test_mock_scope_respected` | Pass scope → verify scope is present in response context (if applicable) |

### 3.3 The swap test (key gate)

```python
def test_swap_providers_same_interface():
    """
    THE GATE. Prove any AIProvider impl works identically.
    
    If this test passes with MockProvider, it will pass with PulseProvider
    (Wave B), AzureProvider (future), ClaudeProvider (future), etc.
    """
    provider = MockProvider()
    
    # Call all 9 methods with minimal valid inputs
    r1 = provider.validate_dq(DqValidateRequest(rules=[], rows=[]))
    assert isinstance(r1, DqValidateResponse)
    assert r1.status == "completed"
    
    r2 = provider.suggest_dq(DqSuggestRequest(table=TableProfile(
        name="test", description="desc", row_count=0, columns=[]
    )))
    assert isinstance(r2, DqSuggestResponse)
    
    r3 = provider.query_nl(NlQueryRequest(question="test"))
    assert isinstance(r3, NlQueryResponse)
    
    # ... all 9 methods
    
    # Health check
    status = provider.health_check()
    assert status.healthy is True
    assert len(status.modules_available) == 9
```

---

## 4. Deliverable A4 — Settings

**Worker:** Backend Worker  
**File:** `backend/config/settings.py` (edit)  
**Goal:** Add `AI_PROVIDER_CLASS`, `AI_PROVIDER_URL`, `AI_PROVIDER_API_KEY` settings.

### 4.1 Add after the existing PULSE section (after line ~466)

```python
# ── AI Provider (Phase 2 — swappable intelligence backends) ─────────────
# Swap AI backends by changing AI_PROVIDER_CLASS. Everything else in Carbon
# remains unchanged. The provider class MUST implement ai.protocol.AIProvider.
AI_PROVIDER_CLASS = os.environ.get(
    "AI_PROVIDER_CLASS",
    "ai.providers.pulse.PulseProvider"
)
AI_PROVIDER_URL = os.environ.get(
    "AI_PROVIDER_URL",
    PULSE_URL  # Default: same as current Pulse URL
)
AI_PROVIDER_API_KEY = os.environ.get(
    "AI_PROVIDER_API_KEY",
    PULSE_API_KEY  # Default: same as current Pulse key
)

# ── AI Intelligence ─────────────────────────────────────────────────────
AI_CACHE_TTL_SECONDS = int(os.environ.get("AI_CACHE_TTL_SECONDS", 300))
AI_MAX_CHAT_HISTORY = int(os.environ.get("AI_MAX_CHAT_HISTORY", 50))
AI_RATE_LIMIT_PER_MINUTE = int(os.environ.get("AI_RATE_LIMIT_PER_MINUTE", 30))
```

Note: `PULSE_URL` and `PULSE_API_KEY` already exist at lines 465–466. Reference them as defaults.

---

## 5. Gates — Wave A

All four must pass before Wave A is greenlit.

- [ ] **G1:** `backend/ai/protocol.py` exists with 0 imports from Django/Pulse/providers
  - Verify: `grep -c 'django\|Pulse\|pulse\|requests\|httpx' backend/ai/protocol.py` → 0
- [ ] **G2:** `MockProvider` passes all 14 test cases in `test_protocol_swap.py`
  - Verify: `python -m pytest ai/tests/test_protocol_swap.py -v` → 14 passed
- [ ] **G3:** All dataclass round-trip tests pass
  - Verify: `python -m pytest ai/tests/test_protocol.py -v` → 14 passed
- [ ] **G4:** `AI_PROVIDER_CLASS`, `AI_PROVIDER_URL`, `AI_PROVIDER_API_KEY` exist in `settings.py`
  - Verify: `grep 'AI_PROVIDER' backend/config/settings.py` → 3 matches
- [ ] **G5:** `python -c "from backend.ai.protocol import AIProvider; print('OK')"` → OK
- [ ] **G6:** `python -c "from django.conf import settings; assert hasattr(settings, 'AI_PROVIDER_CLASS')"` → no error

---

## 6. Worker Activation Prompts

### Worker 1: Backend Worker (A1 + A3 MockProvider + A4 Settings)

```
TASK: Carbon Wave A — Protocol + MockProvider + Settings

You are implementing the first wave of Carbon's AI intelligence layer.

DELIVERABLES:
1. Create backend/ai/__init__.py (empty)
2. Create backend/ai/protocol.py — EXACTLY as specified in §1.2 of TASK-CARBON-AI-WAVE-A.md
   - 20 dataclasses covering all 9 task types + Scope + ProviderStatus
   - AIProvider ABC with 12 abstract methods (health_check + 9 tasks + 2 properties)
   - ZERO imports from Django, Pulse, requests, httpx
3. Create backend/ai/tests/test_protocol_swap.py
   - Implement MockProvider(AIProvider) with deterministic fake data for all 9 methods
   - Every method returns a typed response dataclass
   - No randomness, no sleeps, no HTTP
4. Edit backend/config/settings.py — add AI_PROVIDER_CLASS, AI_PROVIDER_URL, AI_PROVIDER_API_KEY
   after the existing PULSE section (after line ~466), exactly as in §4.1

CRITICAL RULES:
- protocol.py must have ZERO imports from Django, Pulse, or any HTTP library
- MockProvider.provider_name must return "mock"
- FixSuggestion.requires_confirmation must be True in ALL responses
- Do NOT edit pulse_gateway.py

VERIFY:
- python -c "from backend.ai.protocol import AIProvider, Scope" → no error
- python -c "from django.conf import settings; print(settings.AI_PROVIDER_CLASS)" → no error
- grep -c 'django\|Pulse\|requests' backend/ai/protocol.py → 0

FILES TO CREATE:
- backend/ai/__init__.py
- backend/ai/protocol.py
- backend/ai/tests/__init__.py
- backend/ai/tests/test_protocol_swap.py

FILES TO EDIT:
- backend/config/settings.py
```

### Worker 2: Test Worker (A2 + A3 tests)

```
TASK: Carbon Wave A — Protocol Tests + Swap Test

You are writing the test suite that gates Wave A.

DELIVERABLES:
1. Create backend/ai/tests/__init__.py (empty)
2. Create backend/ai/tests/test_protocol.py — 14 tests minimum (§2.2)
   - Every *Request and *Response dataclass round-trips through asdict → constructor
   - test_all_responses_have_status_field
   - test_fix_suggest_requires_confirmation
   - test_response_error_defaults_to_none
3. Complete backend/ai/tests/test_protocol_swap.py — 14 tests minimum (§3.2)
   - test_mock_provider_is_ai_provider (isinstance check)
   - test_mock_health_check (9 modules, healthy=True)
   - One test per AIProvider method (9 total)
   - test_swap_providers_same_interface (calls all 9 methods, checks return types)
   - test_mock_scope_respected

TEST PATTERN (round-trip):
    request = SomeRequest(...)
    d = dataclasses.asdict(request)
    reconstructed = SomeRequest(**d)
    assert reconstructed.field == expected_value

TEST PATTERN (provider):
    provider = MockProvider()
    response = provider.validate_dq(DqValidateRequest(rules=[...], rows=[...]))
    assert isinstance(response, DqValidateResponse)
    assert response.status == "completed"

CRITICAL RULES:
- Tests must be self-contained — no Django database, no HTTP calls
- MockProvider must NOT be imported from test_protocol.py (only test_protocol_swap.py)
- Use pytest conventions (test_ prefix, plain assert)
- Do NOT use pytest-django fixtures (no @pytest.mark.django_db)

RUN:
    cd /home/ahmed/aast/carbon/backend
    python -m pytest ai/tests/test_protocol.py ai/tests/test_protocol_swap.py -v

EXPECTED: 28 tests passed (14 + 14)
```

---

## 7. Post-Wave A Handoff

After Wave A is greenlit (all 6 gates pass):

```
Wave A → Wave B handoff:

The protocol is frozen. MockProvider proves the ABC works.
CarbonIntelligence (Wave C) already knows what it needs.

For Wave B (Pulse Provider):
- Implement PulseProvider(AIProvider) in backend/ai/providers/pulse.py
- Map each AIProvider method to POST /tasks with the correct task type
- Reference existing pulse_gateway.py for HTTP patterns (timeout handling, error envelopes)
- DO NOT edit pulse_gateway.py (deprecated in Wave C, deleted later)

Key mapping:
  validate_dq(request)    → POST /tasks  type: "dq.validate"
  suggest_dq(request)     → POST /tasks  type: "dq.suggest"
  query_nl(request)       → POST /tasks  type: "carbon.query.nl"
  explain_query(request)  → POST /tasks  type: "carbon.query.explain"
  detect_anomalies(req)   → POST /tasks  type: "carbon.anomaly.detect"
  explain_anomaly(req)    → POST /tasks  type: "carbon.anomaly.explain"
  draft_report(request)   → POST /tasks  type: "carbon.report.draft"
  analyze_schema(request) → POST /tasks  type: "carbon.schema.analyze"
  suggest_fix(request)    → POST /tasks  type: "carbon.fix.suggest"
  health_check()          → GET  /tasks/modules?instance_id=carbon
```

---

## 8. Pulse Wave 6 Status

**Wave 6 (Archetypes) does NOT block Carbon Wave A.** They are in separate repositories:

| Wave | Repo | Blocks |
|------|------|--------|
| Carbon Wave A | `/home/ahmed/aast/carbon/` | Nothing |
| Pulse Wave 6 | `/home/ahmed/clearturn/pulse/` | Nothing (independent) |

Pulse Wave 6 is SPEC READY at `plans/pulse-v0.3/phase-06-archetypes/TASK-BE-06.md`. It can proceed independently or after Carbon Wave A — no coordination needed.
