# TASK.md - Project Master Control File
**Master:** GitHub Copilot (Claude Opus 4.5)  
**Date:** February 1, 2026  
**Version:** 2.0 - User Features + Deep AI Priority

---

# 🎯 STRATEGIC PRIORITY

## TOP 3 USER FEATURES + DEEP AI

| Priority | Feature | User Value | Timeline | Status |
|----------|---------|------------|----------|--------|
| 🥇 P0 | **Emission Calculator** | "System calculates CO2e for me" | Weeks 1-2 | ✅ **DELIVERED** |
| 🥈 P1 | **Dashboard with Totals** | "See my Scope 1/2/3 at a glance" | Week 3 | ✅ **DELIVERED** |
| 🥉 P2 | **Basic Charts** | "Visualize my emissions over time" | Week 4 | ✅ **DELIVERED** |
| 🤖 P3 | **Deep AI (Software 3.0)** | "AI that thinks, acts, and advises" | Weeks 5-10 | 🔴 TODO |

---

# 🔍 COMPREHENSIVE SYSTEM AUDIT

## 1. EXECUTIVE SUMMARY

**Carbon Management Platform** is a multi-tenant SaaS for carbon emissions tracking, data collection, and GHG Protocol compliance reporting. The platform includes an AI Copilot for intelligent assistance.

### Overall Health Score: 🟢 88/100 ⬆️ (+16)

| Component | Status | Score | Notes |
|-----------|--------|-------|-------|
| Backend Core | ✅ Stable | 85/100 | Django, REST API, RBAC working |
| Frontend | ✅ Stable | 85/100 | React/Vite/MUI functional |
| Data Models | ✅ Complete | 90/100 | Multi-tenant + Emissions schema ready |
| Authentication | ✅ Working | 90/100 | JWT + RBAC operational |
| **Emission Calculator** | ✅ **COMPLETE** | 95/100 | **229 calculations, auto-calc engine** |
| **Dashboard** | ✅ **COMPLETE** | 95/100 | **Professional glass-morphism UI** |
| **Charts/Viz** | ✅ **COMPLETE** | 95/100 | **Chart.js - Pie, Bar, Line charts** |
| AI Copilot Backend | 🟡 Partial | 70/100 | **MVP + RAG ingestion pipeline** |
| AI Copilot Frontend | 🟡 Partial | 75/100 | **UI complete, backend sync needed** |
| RAG Knowledge Base | ✅ **BUILT** | 80/100 | **100 chunks, 14 docs, 5 categories** |
| AI Agents/Tools | 🔴 Not Started | 10/100 | **No action agents yet** |
| Reports Engine | ✅ **COMPLETE** | 90/100 | **GHG Protocol-compliant reports** |
| DevOps | ✅ Ready | 80/100 | Docker Compose working |

---

## 2. DETAILED COMPONENT AUDIT

### 2.1 BACKEND (Django + DRF)

**Location:** `/home/ahmed/carbon/backend/`

#### Strengths ✅
- Clean Django 5.2 architecture
- Proper multi-tenant model with `Tenant` → `Project` → `Module` hierarchy
- Scoped RBAC with `ScopedRole` model (tenant/project/module levels)
- Dynamic schema system (`DataTable`, `DataField`, `DataRow`)
- Audit logging (`SchemaChangeLog`, `RoleAssignmentAuditLog`)
- JWT authentication with token blacklist
- CORS and CSRF properly configured

#### Weaknesses 🔴
- No calculation/emission factor engine
- No report generation pipeline
- No scheduled tasks/Celery integration
- Limited test coverage
- Missing API rate limiting

#### Files Reviewed:
- [core/models.py](backend/core/models.py) - Project, Module, Feedback
- [accounts/models.py](backend/accounts/models.py) - User, Tenant, ScopedRole
- [dataschema/models.py](backend/dataschema/models.py) - DataTable, DataField, DataRow
- [config/settings.py](backend/config/settings.py) - Django configuration

---

### 2.2 AI COPILOT BACKEND

**Location:** `/home/ahmed/carbon/backend/ai_copilot/`

#### Current Architecture:
```
ai_copilot/
├── models.py          # ConversationMessage, ProactiveInsight, UserAIPreference
├── views.py           # ChatViewSet, InsightViewSet, PreferenceViewSet, QAViewSet
├── serializers.py     # DRF serializers
├── urls.py            # REST router
└── services/
    ├── poe_client.py      # POE API for GPT-4o (~$0.005/call)
    ├── memory.py          # Redis conversation buffer (20 msg, 24h TTL)
    ├── rag_engine.py      # ChromaDB + sentence-transformers
    └── context_engine.py  # Real-time DB context for prompts
```

#### Strengths ✅
- POE API integration (cost-effective LLM access)
- Redis-backed conversation memory
- ChromaDB vector database ready
- Context Engine pulls real project data
- Streaming support (pseudo-streaming via chunking)
- Token counting and cost estimation
- QA endpoint for data quality checks

#### Critical Gaps 🔴

1. **RAG Knowledge Base is EMPTY**
   - ChromaDB folder is empty (`chroma_db/` has no data)
   - Only 5 basic GHG documents in `seed_ghg_protocol_basics()`
   - No ISO 14064, CSRD/ESRS, sector-specific emission factors
   - No citation/source tracking in responses

2. **No Action Agents**
   - AI can only chat, cannot take actions
   - No tool routing (calculations, data entry, report generation)
   - No confirmation steps for risky operations

3. **No Proactive Intelligence**
   - `ProactiveInsight` model exists but no generation logic
   - No scheduled insight creation
   - No anomaly detection or deadline alerts

4. **Limited Context Awareness**
   - Context Engine is good but not integrated deeply
   - No multi-project context
   - No time-series trend analysis

5. **Missing Evaluation Framework**
   - No retrieval accuracy metrics
   - No response quality testing
   - No user feedback analysis

---

### 2.3 AI COPILOT FRONTEND

**Location:** `/home/ahmed/carbon/carbon-frontend/src/components/ai/`

#### Current Components:
- `AICopilotPanel.jsx` (644 lines) - Main chat interface
- `ChatMessage.jsx` - Message bubbles
- `ProactiveInsightCard.jsx` - Insight display
- `AIPreferencesDialog.jsx` - User settings
- `ResizableLayout.jsx` - Panel resizing

#### Strengths ✅
- VS Code-style grouped conversations
- Real-time streaming UI
- Proactive insights display
- User preferences management
- Resizable/collapsible panel
- LocalStorage persistence

#### Gaps 🔴
- No voice input
- No code/formula syntax highlighting
- No action buttons for AI suggestions
- No context sharing (selected data, current page)
- Limited error recovery

---

### 2.4 DATA MODEL ASSESSMENT

**Current Schema Supports:**
- Multi-tenant organizations
- Scoped projects with modules
- Dynamic tables/fields/rows
- Scope 1/2/3 classification on modules
- Evidence file attachments
- Full audit trails

**Missing for Carbon Accounting:**
- Emission Factor library (country/sector/fuel type)
- Calculation definitions (formulas, conversions)
- Reporting periods/cycles
- Verification/approval workflows
- Benchmark data

---

## 3. PRIORITIZED TASK QUEUE (REVISED)

### 🎯 NEW PRIORITY ORDER

```
PHASE 0: Emission Calculator ───────────────────────► Weeks 1-2
PHASE 1: Dashboard + Charts ────────────────────────► Weeks 3-4  
PHASE 2: Deep AI - Knowledge & RAG ─────────────────► Weeks 5-6
PHASE 3: Deep AI - Agent Architecture ──────────────► Weeks 7-8
PHASE 4: Deep AI - Proactive Intelligence ──────────► Weeks 9-10
```

---

### PHASE 0: EMISSION CALCULATOR (Priority: ✅ COMPLETE)
**Timeline: Weeks 1-2**
**User Value:** "System calculates CO2e for me"
**Status:** ✅ DELIVERED - 229 calculations, 2,516.09 tonnes CO2e tracked

| ID | Task | Description | Owner | Status |
|----|------|-------------|-------|--------|
| 0.1 | **Emission Factor Model** | Create database model for emission factors (fuel, electricity, vehicles, refrigerants) | Worker | ✅ DONE |
| 0.2 | **Emission Factor Data Seeding** | Seed 500+ emission factors (global electricity grids, fuels, vehicles, GWPs) | Worker | ✅ DONE |
| 0.3 | **Calculation Engine Core** | Build calculation service: `CO2e = Activity × Factor × GWP` | Worker | ✅ DONE |
| 0.4 | **Calculation API Endpoints** | REST API for calculations (single, batch, by scope) | Worker | ✅ DONE |
| 0.5 | **Auto-Calculate on Data Entry** | Trigger calculation when user enters data | Worker | ✅ DONE |
| 0.6 | **Calculation Audit Trail** | Log all calculations with inputs, outputs, factors used | Worker | ✅ DONE |
| 0.7 | **Unit Conversion Library** | Convert between kWh/MJ/BTU, liters/gallons, km/miles, etc. | Worker | ✅ DONE |
| 0.8 | **Scope Assignment Logic** | Auto-assign Scope 1/2/3 based on emission source type | Worker | ✅ DONE |

**Deliverables:**
- `backend/emissions/models.py` - EmissionFactor, Calculation, CalculationLog
- `backend/emissions/services/calculator.py` - Core calculation engine
- `backend/emissions/services/unit_converter.py` - Unit conversion utilities
- `backend/emissions/views.py` - API endpoints
- `backend/emissions/management/commands/seed_emission_factors.py` - Data seeding
- Test coverage for all calculations

---

### PHASE 1: DASHBOARD + CHARTS (Priority: ✅ COMPLETE)
**Timeline: Weeks 3-4**
**User Value:** "See my Scope 1/2/3 at a glance" + "Visualize emissions over time"
**Status:** ✅ DELIVERED - Professional glass-morphism UI, Chart.js visualizations

| ID | Task | Description | Owner | Status |
|----|------|-------------|-------|--------|
| 1.1 | **Dashboard API Endpoints** | Aggregation endpoints: totals by scope, module, period | Worker | ✅ DONE |
| 1.2 | **Dashboard Summary Cards** | Frontend cards showing total CO2e, Scope 1/2/3 breakdown | Worker | ✅ DONE |
| 1.3 | **Scope Breakdown Pie Chart** | Pie/donut chart for Scope distribution | Worker | ✅ DONE |
| 1.4 | **Time Series Line Chart** | Emissions over time (monthly/quarterly/yearly) | Worker | ✅ DONE |
| 1.5 | **Module Comparison Bar Chart** | Compare emissions by module/category | Worker | ✅ DONE |
| 1.6 | **Period Selector Component** | Filter by date range, reporting period | Worker | ✅ DONE |
| 1.7 | **Dashboard State Persistence** | Remember user's dashboard preferences | Worker | ✅ DONE |
| 1.8 | **Export Dashboard as PDF** | Download dashboard snapshot | Worker | ✅ DONE |

**Deliverables:**
- `backend/reports/views.py` - Dashboard aggregation API
- `carbon-frontend/src/pages/Dashboard.jsx` - Main dashboard page
- `carbon-frontend/src/components/dashboard/` - Chart components
- Chart library integration (Recharts or Chart.js)
- Responsive design for all screen sizes

---

### PHASE 2: DEEP AI - Knowledge & RAG (Priority: 🟡 IN PROGRESS)
**Timeline: Weeks 5-6**
**User Value:** "AI is an expert on carbon accounting"
**Status:** 🟡 IN PROGRESS - Task 2.1 Complete, Starting Task 2.5

| ID | Task | Description | Owner | Status |
|----|------|-------------|-------|--------|
| 2.1 | **Knowledge Ingestion Pipeline** | Management command to ingest PDFs, markdown, text with chunking | Worker | ✅ DONE |
| 2.2 | **GHG Protocol Full Ingestion** | Ingest complete GHG Protocol Corporate Standard | Worker | ✅ DONE |
| 2.3 | **Emission Factor Knowledge** | Seed all emission factors into RAG for Q&A | Worker | ✅ DONE |
| 2.4 | **Regulatory Framework Ingestion** | ISO 14064, CSRD/ESRS, SEC Climate Rule summaries | Worker | ✅ DONE |
| 2.5 | **Hybrid Search Implementation** | Combine semantic + keyword search (BM25 + embeddings) | Worker | 🔴 TODO |
| 2.6 | **Reranking Layer** | Add Cohere Rerank or cross-encoder for better retrieval | Worker | 🔴 TODO |
| 2.7 | **Source Citations in Responses** | AI returns sources with page/section references | Worker | 🔴 TODO |
| 2.8 | **RAG Evaluation Pipeline** | RAGAS metrics: faithfulness, relevance, context precision | Worker | 🔴 TODO |
| 2.9 | **Knowledge Versioning** | Track document versions, update without breaking | Worker | 🔴 TODO |

**Deliverables:**
- `backend/ai_copilot/management/commands/ingest_knowledge.py`
- `backend/ai_copilot/services/hybrid_search.py`
- `backend/ai_copilot/services/reranker.py`
- 200+ knowledge documents in ChromaDB
- Evaluation test set (50+ Q&A pairs)
- Retrieval accuracy ≥95%

---

### PHASE 3: DEEP AI - Agent Architecture (Priority: 🟡 HIGH)
**Timeline: Weeks 7-8**
**User Value:** "AI can DO things, not just chat"

| ID | Task | Description | Owner | Status |
|----|------|-------------|-------|--------|
| 3.1 | **Tool Framework (LangGraph)** | Set up LangGraph for multi-agent orchestration | Worker | 🔴 TODO |
| 3.2 | **Intent Router** | Classify user intent: question, calculation, report, action | Worker | 🔴 TODO |
| 3.3 | **Calculator Tool** | AI can invoke emission calculations | Worker | 🔴 TODO |
| 3.4 | **Data Query Tool** | AI can query user's emissions data | Worker | 🔴 TODO |
| 3.5 | **Data Quality Agent** | Find missing data, outliers, incomplete records | Worker | 🔴 TODO |
| 3.6 | **Report Draft Agent** | Generate narrative summaries of emissions | Worker | 🔴 TODO |
| 3.7 | **Compliance Check Agent** | Gap analysis against GHG Protocol requirements | Worker | 🔴 TODO |
| 3.8 | **Confirmation Flow** | User confirms before AI takes actions | Worker | 🔴 TODO |
| 3.9 | **Action Audit Trail** | Log all AI actions with user approval | Worker | 🔴 TODO |

**Deliverables:**
- `backend/ai_copilot/agents/` - Agent modules
- `backend/ai_copilot/tools/` - Tool definitions
- `backend/ai_copilot/services/router.py` - Intent classification
- Frontend action buttons and confirmation dialogs
- Action audit logging

---

### PHASE 4: DEEP AI - Proactive Intelligence (Priority: 🟢 MEDIUM)
**Timeline: Weeks 9-10**
**User Value:** "AI alerts me before problems happen"

| ID | Task | Description | Owner | Status |
|----|------|-------------|-------|--------|
| 4.1 | **Celery Integration** | Set up Celery for background tasks | Worker | 🔴 TODO |
| 4.2 | **Insight Generation Scheduler** | Periodic job to analyze data and generate insights | Worker | 🔴 TODO |
| 4.3 | **Missing Data Detector** | Alert when required fields are empty | Worker | 🔴 TODO |
| 4.4 | **Anomaly Detector** | Flag unusual spikes or drops in emissions | Worker | 🔴 TODO |
| 4.5 | **Deadline Tracker** | Remind about reporting deadlines | Worker | 🔴 TODO |
| 4.6 | **Trend Analysis** | "Your Scope 2 increased 15% vs last quarter" | Worker | 🔴 TODO |
| 4.7 | **Reduction Suggestions** | AI recommends emission reduction opportunities | Worker | 🔴 TODO |
| 4.8 | **Email/Push Notifications** | Send alerts via email or browser push | Worker | 🔴 TODO |
| 4.9 | **Insight Relevance Scoring** | Prioritize insights by impact and urgency | Worker | 🔴 TODO |

**Deliverables:**
- Celery configuration with Redis broker
- `backend/ai_copilot/tasks/` - Celery tasks
- `backend/ai_copilot/services/insights/` - Insight generators
- Email template system
- Frontend notification integration

---

## 4. CURRENT ACTIVE TASK

### TASK ID: 2.5
### TITLE: Hybrid Search Implementation
### STATUS: 🔴 TODO
### PRIORITY: 🟡 HIGH
### ASSIGNED: Worker Agent
### DATE: 2026-02-01

---

## 🎉 MILESTONES ACHIEVED

**P0-P2 DELIVERED:** Emission Calculator, Dashboard, and Charts are COMPLETE!
- 229 calculations totaling 2,516.09 tonnes CO2e
- Professional glass-morphism dashboard with Chart.js
- Demo: http://localhost:5173/emissions/dashboard

**TASK 2.1-2.4 DELIVERED:** Knowledge Ingestion Pipeline COMPLETE!
- 100 chunks across 14 documents in 5 categories
- Document loader, text chunker, enhanced RAG engine
- Management command: `python manage.py ingest_knowledge`

---

## OBJECTIVE

Implement hybrid search combining **semantic search** (embeddings) with **keyword search** (BM25) for improved retrieval accuracy. This addresses cases where:
- Exact terminology matters (e.g., "Scope 1", "GWP", "AR6")
- Semantic meaning alone misses specific terms
- Users search with technical jargon

---

## DETAILED REQUIREMENTS

### 1. INSTALL BM25 LIBRARY

Add to `requirements.txt`:
```
rank-bm25>=0.2.2
```

### 2. CREATE HYBRID SEARCH SERVICE

**File:** `/home/ahmed/carbon/backend/ai_copilot/services/hybrid_search.py`

```python
"""
Hybrid Search Service
Combines BM25 keyword search with semantic vector search
"""

from typing import List, Dict, Tuple, Optional
from rank_bm25 import BM25Okapi
import numpy as np
from .rag_engine import RAGEngine


class HybridSearch:
    """
    Hybrid search combining BM25 and semantic embeddings.
    
    Uses Reciprocal Rank Fusion (RRF) to merge rankings:
    RRF(d) = Σ 1/(k + rank(d)) for each ranking
    """
    
    def __init__(
        self,
        rag_engine: RAGEngine = None,
        alpha: float = 0.5,  # Weight for semantic search (0-1)
        k: int = 60,  # RRF constant
    ):
        """
        Args:
            rag_engine: RAG engine for semantic search
            alpha: Weight for semantic search (1-alpha for BM25)
            k: RRF constant (higher = more weight to lower ranks)
        """
        self.rag = rag_engine or RAGEngine()
        self.alpha = alpha
        self.k = k
        self.bm25 = None
        self.corpus_ids = []
        self.corpus_texts = []
        self._build_bm25_index()
    
    def _build_bm25_index(self):
        """Build BM25 index from ChromaDB documents."""
        # Get all documents from ChromaDB
        collection = self.rag.collection
        results = collection.get(include=["documents", "metadatas"])
        
        if results and results['documents']:
            self.corpus_texts = results['documents']
            self.corpus_ids = results['ids']
            
            # Tokenize for BM25
            tokenized = [doc.lower().split() for doc in self.corpus_texts]
            self.bm25 = BM25Okapi(tokenized)
    
    def search(
        self,
        query: str,
        n_results: int = 10,
        category: str = None,
        semantic_weight: float = None,
    ) -> List[Dict]:
        """
        Hybrid search with RRF fusion.
        
        Args:
            query: Search query
            n_results: Number of results to return
            category: Optional category filter
            semantic_weight: Override alpha for this query
            
        Returns:
            List of results with scores and sources
        """
        alpha = semantic_weight if semantic_weight is not None else self.alpha
        
        # 1. Semantic search via RAG
        semantic_results = self.rag.search_with_sources(
            query, n_results=n_results * 2, category=category
        )
        
        # 2. BM25 keyword search
        bm25_results = self._bm25_search(query, n_results * 2)
        
        # 3. Fuse with RRF
        fused = self._rrf_fusion(
            semantic_results, 
            bm25_results, 
            alpha=alpha,
            n_results=n_results
        )
        
        return fused
    
    def _bm25_search(self, query: str, n_results: int) -> List[Dict]:
        """Perform BM25 keyword search."""
        if not self.bm25:
            return []
        
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top indices
        top_indices = np.argsort(scores)[::-1][:n_results]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    'id': self.corpus_ids[idx],
                    'content': self.corpus_texts[idx],
                    'score': float(scores[idx]),
                    'method': 'bm25'
                })
        
        return results
    
    def _rrf_fusion(
        self,
        semantic_results: List[Dict],
        bm25_results: List[Dict],
        alpha: float,
        n_results: int
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion of two result lists.
        
        RRF score = alpha * 1/(k+rank_semantic) + (1-alpha) * 1/(k+rank_bm25)
        """
        scores = {}
        content_map = {}
        
        # Score semantic results
        for rank, result in enumerate(semantic_results, 1):
            doc_id = result.get('id') or hash(result['content'][:100])
            scores[doc_id] = scores.get(doc_id, 0) + alpha / (self.k + rank)
            content_map[doc_id] = result
        
        # Score BM25 results  
        for rank, result in enumerate(bm25_results, 1):
            doc_id = result.get('id') or hash(result['content'][:100])
            scores[doc_id] = scores.get(doc_id, 0) + (1 - alpha) / (self.k + rank)
            if doc_id not in content_map:
                content_map[doc_id] = result
        
        # Sort by fused score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        results = []
        for doc_id in sorted_ids[:n_results]:
            result = content_map[doc_id].copy()
            result['hybrid_score'] = scores[doc_id]
            results.append(result)
        
        return results
    
    def refresh_index(self):
        """Rebuild BM25 index after new documents added."""
        self._build_bm25_index()
```

### 3. INTEGRATE WITH RAG ENGINE

Update `rag_engine.py` to optionally use hybrid search:

```python
def search_hybrid(
    self,
    query: str,
    n_results: int = 5,
    category: str = None,
    semantic_weight: float = 0.5,
) -> List[Dict]:
    """Search using hybrid semantic + keyword approach."""
    from .hybrid_search import HybridSearch
    hybrid = HybridSearch(rag_engine=self, alpha=semantic_weight)
    return hybrid.search(query, n_results, category)
```

### 4. UPDATE AI COPILOT VIEWS

Modify the chat endpoint to use hybrid search for RAG retrieval.

---

## VERIFICATION STEPS

```bash
# 1. Install dependency
pip install rank-bm25

# 2. Test hybrid search in Django shell
python manage.py shell -c "
from ai_copilot.services.hybrid_search import HybridSearch
hs = HybridSearch()
results = hs.search('What is Scope 1 emissions?', n_results=5)
for r in results:
    print(f'Score: {r[\"hybrid_score\"]:.4f} - {r.get(\"source\", \"unknown\")[:50]}')
"

# 3. Compare semantic vs hybrid
python manage.py shell -c "
from ai_copilot.services.rag_engine import RAGEngine
from ai_copilot.services.hybrid_search import HybridSearch

query = 'GWP AR6 methane CH4'

# Semantic only
rag = RAGEngine()
sem = rag.search_with_sources(query, n_results=3)
print('SEMANTIC:')
for r in sem:
    print(f'  {r[\"score\"]:.2f} - {r[\"source\"][:40]}')

# Hybrid
hs = HybridSearch()
hyb = hs.search(query, n_results=3)
print('HYBRID:')
for r in hyb:
    print(f'  {r[\"hybrid_score\"]:.4f} - {r.get(\"source\", \"?\")[:40]}')
"
```

---

## EXPECTED DELIVERABLES

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | `ai_copilot/services/hybrid_search.py` | 🔴 TODO |
| 2 | `rag_engine.py` updated with `search_hybrid()` | 🔴 TODO |
| 3 | `requirements.txt` updated with rank-bm25 | 🔴 TODO |
| 4 | Integration with AI chat endpoint | 🔴 TODO |

---

## SUCCESS CRITERIA

- [ ] BM25 index builds from ChromaDB corpus
- [ ] RRF fusion produces combined rankings
- [ ] Technical terms like "GWP", "AR6", "Scope 1" rank higher
- [ ] Search quality verified with test queries

---

## END OF TASK 2.5

---

## COMPLETED TASK 2.1 (ARCHIVED)

### TASK 2.1 ARCHIVED (COMPLETE)

**Completed:** 2026-02-01
**Deliverables:** Knowledge Ingestion Pipeline
- `ai_copilot/services/document_loader.py` (372 lines)
- `ai_copilot/services/text_chunker.py` (365 lines)
- `ai_copilot/services/rag_engine.py` (enhanced)
- `ai_copilot/management/commands/ingest_knowledge.py` (357 lines)
- `ai_copilot/knowledge/` - 14 documents, 5 categories

**Results:** 100 chunks, 14 documents, search quality verified

---

## 📦 ARCHIVED TASKS

<details>
<summary>Click to expand archived task details</summary>

### Phase 0 + Phase 1 Delivery Summary

All Phase 0 (Emission Calculator) and Phase 1 (Dashboard + Charts) tasks were completed as a unified demo system by the Worker Agent on 2026-02-01.

**Deliverables:**
- 229 emission calculations (2,516.09 tonnes CO2e)
- Professional glass-morphism dashboard
- Chart.js visualizations (Pie, Bar, Line)
- GHG Protocol-compliant reports
- Demo data for Acme Corporation FY 2025

**Files Created:**
- `backend/emissions/management/commands/seed_demo_data.py` (886 lines)
- `carbon-frontend/src/pages/EmissionsDashboard.jsx` (738 lines)
- `carbon-frontend/src/pages/EmissionsReport.jsx` (585 lines)
- Backend API endpoints for dashboard and reports

**Access:**
- Dashboard: http://localhost:5173/emissions/dashboard
- Report: http://localhost:5173/emissions/report
- Credentials: demo_admin@acme.com / demo123!

</details>

---

## 5. AI COPILOT 3.0 ARCHITECTURE

### 🎯 VISION: Carbon Intelligence Platform

#### 2.7 WASTE (15+ entries)
**Scope:** 3 (Value Chain)
**Category:** `waste`

| Waste Type | Code | Factor (kg CO2e) | Unit | Source |
|------------|------|------------------|------|--------|
| Mixed Municipal Waste (Landfill) | WASTE_MUN_LANDFILL | 0.446 | kg | DEFRA 2024 |
| Mixed Municipal Waste (Incineration) | WASTE_MUN_INCIN | 0.021 | kg | DEFRA 2024 |
| Paper (Landfill) | WASTE_PAPER_LAND | 1.042 | kg | DEFRA 2024 |
| Paper (Recycled) | WASTE_PAPER_REC | 0.021 | kg | DEFRA 2024 |
| Plastic (Landfill) | WASTE_PLASTIC_LAND | 0.021 | kg | DEFRA 2024 |
| Plastic (Recycled) | WASTE_PLASTIC_REC | 0.021 | kg | DEFRA 2024 |
| Plastic (Incineration) | WASTE_PLASTIC_INCIN | 2.100 | kg | DEFRA 2024 |
| Glass (Landfill) | WASTE_GLASS_LAND | 0.021 | kg | DEFRA 2024 |
| Glass (Recycled) | WASTE_GLASS_REC | 0.021 | kg | DEFRA 2024 |
| Metal (Landfill) | WASTE_METAL_LAND | 0.021 | kg | DEFRA 2024 |
| Metal (Recycled) | WASTE_METAL_REC | 0.021 | kg | DEFRA 2024 |
| Organic Waste (Landfill) | WASTE_ORG_LAND | 0.550 | kg | DEFRA 2024 |
| Organic Waste (Composted) | WASTE_ORG_COMP | 0.010 | kg | DEFRA 2024 |
| Organic Waste (Anaerobic Digestion) | WASTE_ORG_AD | 0.010 | kg | DEFRA 2024 |
| Construction Waste | WASTE_CONST | 0.100 | kg | DEFRA 2024 |
| Electrical Waste (WEEE) | WASTE_WEEE | 0.021 | kg | DEFRA 2024 |

---

#### 2.8 WATER (5+ entries)
**Scope:** 3 (Value Chain)
**Category:** `water`

| Type | Code | Factor (kg CO2e) | Unit | Source |
|------|------|------------------|------|--------|
| Water Supply | WATER_SUPPLY | 0.149 | m³ | DEFRA 2024 |
| Water Treatment | WATER_TREAT | 0.272 | m³ | DEFRA 2024 |
| Water Supply + Treatment | WATER_TOTAL | 0.421 | m³ | DEFRA 2024 |

---

#### 2.9 GLOBAL WARMING POTENTIALS (GWP Model - 15+ entries)

| Gas | Formula | AR5 100yr | AR6 100yr | AR5 20yr | AR6 20yr | CAS |
|-----|---------|-----------|-----------|----------|----------|-----|
| Carbon Dioxide | CO2 | 1 | 1 | 1 | 1 | 124-38-9 |
| Methane (Fossil) | CH4 | 30 | 29.8 | 85 | 82.5 | 74-82-8 |
| Methane (Biogenic) | CH4_BIO | 28 | 27.2 | 84 | 80.8 | 74-82-8 |
| Nitrous Oxide | N2O | 265 | 273 | 264 | 273 | 10024-97-2 |
| Sulfur Hexafluoride | SF6 | 23500 | 25200 | 17500 | 18300 | 2551-62-4 |
| Nitrogen Trifluoride | NF3 | 16100 | 17400 | 12800 | 13400 | 7783-54-2 |
| HFC-23 | CHF3 | 12400 | 14600 | 10800 | 12400 | 75-46-7 |
| HFC-32 | CH2F2 | 677 | 771 | 2430 | 2693 | 75-10-5 |
| HFC-125 | CHF2CF3 | 3170 | 3740 | 6090 | 6740 | 354-33-6 |
| HFC-134a | CH2FCF3 | 1300 | 1530 | 3790 | 4144 | 811-97-2 |
| HFC-143a | CH3CF3 | 4800 | 5810 | 6940 | 7840 | 420-46-2 |
| HFC-152a | CH3CHF2 | 138 | 164 | 506 | 591 | 75-37-6 |
| PFC-14 (CF4) | CF4 | 6630 | 7380 | 4880 | 5300 | 75-73-0 |
| PFC-116 (C2F6) | C2F6 | 11100 | 12400 | 8210 | 8940 | 76-16-4 |

---

### 3. IMPLEMENTATION DETAILS

#### 3.1 Create Directory Structure

```bash
cd /home/ahmed/carbon/backend
mkdir -p emissions/management/commands
touch emissions/management/__init__.py
touch emissions/management/commands/__init__.py
```

#### 3.2 Command Implementation Pattern

```python
# File: emissions/management/commands/seed_emission_factors.py

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from emissions.models import EmissionFactor, GWP
from datetime import date
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Seeds the database with emission factors and GWP values'

    def add_arguments(self, parser):
        parser.add_argument(
            '--category',
            type=str,
            help='Seed only a specific category (electricity, mobile_combustion, etc.)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            EmissionFactor.objects.all().delete()
            GWP.objects.all().delete()
        
        if options['dry_run']:
            self.stdout.write('DRY RUN - No changes will be made')
        
        category_filter = options.get('category')
        
        with transaction.atomic():
            if not category_filter or category_filter == 'gwp':
                self._seed_gwp(options['dry_run'])
            
            if not category_filter or category_filter == 'electricity':
                self._seed_electricity(options['dry_run'])
            
            # ... add more category seeders
            
        self.stdout.write(self.style.SUCCESS('Seeding complete!'))
    
    def _seed_electricity(self, dry_run=False):
        """Seed electricity grid emission factors."""
        self.stdout.write('Seeding electricity grid factors...')
        
        factors = [
            # (name, code, factor, country, country_code, source)
            ('US Grid Average', 'US_GRID_AVG', 0.417, 'United States', 'USA', 'EPA eGRID 2024'),
            # ... more factors
        ]
        
        count = 0
        for name, code, factor_value, country, country_code, source in factors:
            if dry_run:
                self.stdout.write(f'  Would create: {code}')
            else:
                obj, created = EmissionFactor.objects.update_or_create(
                    code=code,
                    defaults={
                        'name': name,
                        'category': 'electricity',
                        'scope': 2,
                        'factor_value': factor_value,
                        'factor_unit': 'kg CO2e',
                        'activity_unit': 'kWh',
                        'country': country,
                        'country_code': country_code,
                        'source': source,
                        'valid_from': date(2024, 1, 1),
                        'is_active': True,
                    }
                )
                if created:
                    count += 1
        
        self.stdout.write(f'  Created {count} electricity factors')
```

---

### 4. VERIFICATION STEPS

After implementing, run these commands to verify:

```bash
# 1. Run the seeder
cd /home/ahmed/carbon/backend
python manage.py seed_emission_factors

# 2. Verify counts
python manage.py shell -c "
from emissions.models import EmissionFactor, GWP
print(f'EmissionFactor count: {EmissionFactor.objects.count()}')
print(f'GWP count: {GWP.objects.count()}')
print(f'Categories: {list(EmissionFactor.objects.values_list(\"category\", flat=True).distinct())}')
"

# 3. Test category filter
python manage.py seed_emission_factors --category=electricity --dry-run

# 4. Test clearing
python manage.py seed_emission_factors --clear
```

---

### 5. EXPECTED OUTPUT

After successful seeding:
- **EmissionFactor:** 200+ entries minimum
- **GWP:** 15+ entries
- **Categories covered:** All 9 categories (electricity, stationary_combustion, mobile_combustion, fugitive, process, transport, waste, water, materials)
- **Scopes covered:** 1, 2, and 3

---

### 6. DELIVERABLES

1. ✅ `emissions/management/__init__.py`
2. ✅ `emissions/management/commands/__init__.py`
3. ✅ `emissions/management/commands/seed_emission_factors.py`
4. ✅ All emission factors seeded successfully
5. ✅ All GWP values seeded successfully
6. ✅ Command supports `--category`, `--clear`, `--dry-run` flags

---

### 7. REPORT FORMAT

Update TASK-RESULTS.md with:

```markdown
### Task 0.2: Emission Factor Data Seeding
**Status:** ✅ COMPLETE / 🔴 BLOCKED
**Started:** [timestamp]
**Completed:** [timestamp]

#### Work Summary
[Describe what you did]

#### Files Created
- emissions/management/commands/seed_emission_factors.py

#### Verification Results
- EmissionFactor count: [X]
- GWP count: [X]
- Categories: [list]

#### Issues Encountered
[Any blockers or problems]
```

---

## END OF TASK 0.2

---

## COMPLETED TASKS ARCHIVE

### Task 0.1: Emission Factor Database Model (COMPLETED)

**Status:** ✅ COMPLETE  
**Completed:** 2026-02-01

Created the `emissions` Django app with 4 models:
- `ReportingPeriod` - Configurable reporting cycles
- `EmissionFactor` - Emission conversion factors
- `GWP` - Global Warming Potentials
- `Calculation` - Emission calculation audit trail

See TASK-RESULTS.md for full details.

---

## PREVIOUS TASK (ARCHIVED)

### TASK ID: 0.1 (ARCHIVED)
### TITLE: Create Emission Factor Database Model (COMPLETED)

**Objective:** Design and implement the core database model for storing emission factors.

**Detailed Instructions:**

1. **Create New Django App**
   ```bash
   cd /home/ahmed/carbon/backend
   python manage.py startapp emissions
   ```

2. **Design EmissionFactor Model**
   
   Location: `/home/ahmed/carbon/backend/emissions/models.py`

   ```python
   class EmissionFactor(models.Model):
       """
       Stores emission conversion factors for calculating CO2e.
       Examples: 
       - Electricity (kWh) → kg CO2e
       - Diesel (liters) → kg CO2e
       - Flight (km) → kg CO2e
       """
       
       # Categories
       CATEGORY_CHOICES = [
           ('electricity', 'Electricity Grid'),
           ('stationary_combustion', 'Stationary Combustion'),
           ('mobile_combustion', 'Mobile Combustion'),
           ('fugitive', 'Fugitive Emissions'),
           ('process', 'Process Emissions'),
           ('transport', 'Transportation'),
           ('waste', 'Waste'),
           ('water', 'Water'),
           ('materials', 'Materials/Products'),
       ]
       
       SCOPE_CHOICES = [
           (1, 'Scope 1 - Direct'),
           (2, 'Scope 2 - Indirect (Energy)'),
           (3, 'Scope 3 - Value Chain'),
       ]
       
       # Identity
       name = models.CharField(max_length=200)  # "US Grid Average 2024"
       code = models.CharField(max_length=50, unique=True)  # "US_GRID_2024"
       
       # Classification
       category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
       subcategory = models.CharField(max_length=100, blank=True)  # "Natural Gas"
       scope = models.PositiveSmallIntegerField(choices=SCOPE_CHOICES)
       
       # Factor Details
       factor_value = models.DecimalField(max_digits=20, decimal_places=10)
       factor_unit = models.CharField(max_length=50)  # "kg CO2e"
       activity_unit = models.CharField(max_length=50)  # "kWh", "liter", "km"
       
       # GHG Breakdown (optional)
       co2_factor = models.DecimalField(max_digits=20, decimal_places=10, null=True)
       ch4_factor = models.DecimalField(max_digits=20, decimal_places=10, null=True)
       n2o_factor = models.DecimalField(max_digits=20, decimal_places=10, null=True)
       
       # Geographic Scope
       country = models.CharField(max_length=100, blank=True)  # "United States"
       country_code = models.CharField(max_length=3, blank=True)  # "USA"
       region = models.CharField(max_length=100, blank=True)  # "California"
       
       # Source & Validity
       source = models.CharField(max_length=200)  # "EPA eGRID 2024"
       source_url = models.URLField(blank=True)
       valid_from = models.DateField()
       valid_to = models.DateField(null=True, blank=True)
       
       # Metadata
       notes = models.TextField(blank=True)
       is_active = models.BooleanField(default=True)
       created_at = models.DateTimeField(auto_now_add=True)
       updated_at = models.DateTimeField(auto_now=True)
       
       class Meta:
           ordering = ['category', 'name']
           indexes = [
               models.Index(fields=['category', 'country_code']),
               models.Index(fields=['scope']),
               models.Index(fields=['code']),
           ]
       
       def __str__(self):
           return f"{self.name} ({self.factor_value} {self.factor_unit}/{self.activity_unit})"
   
   
   class GWP(models.Model):
       """
       Global Warming Potentials for different greenhouse gases.
       Used to convert CH4, N2O, HFCs, etc. to CO2 equivalent.
       """
       gas_name = models.CharField(max_length=100)  # "Methane"
       gas_formula = models.CharField(max_length=50)  # "CH4"
       
       # GWP values from different assessment reports
       gwp_ar5_100yr = models.DecimalField(max_digits=10, decimal_places=2, null=True)
       gwp_ar6_100yr = models.DecimalField(max_digits=10, decimal_places=2, null=True)
       gwp_ar5_20yr = models.DecimalField(max_digits=10, decimal_places=2, null=True)
       gwp_ar6_20yr = models.DecimalField(max_digits=10, decimal_places=2, null=True)
       
       # Metadata
       cas_number = models.CharField(max_length=20, blank=True)  # Chemical identifier
       notes = models.TextField(blank=True)
       
       class Meta:
           verbose_name = "Global Warming Potential"
           verbose_name_plural = "Global Warming Potentials"
       
       def __str__(self):
           return f"{self.gas_name} ({self.gas_formula}) - GWP: {self.gwp_ar6_100yr}"
   
   
   class Calculation(models.Model):
       """
       Stores calculated emissions for a data row.
       Links activity data to emission factors and results.
       """
       # Link to source data
       data_row = models.ForeignKey('dataschema.DataRow', on_delete=models.CASCADE, related_name='calculations')
       project = models.ForeignKey('core.Project', on_delete=models.CASCADE, related_name='calculations')
       module = models.ForeignKey('core.Module', on_delete=models.CASCADE, related_name='calculations')
       
       # Emission factor used
       emission_factor = models.ForeignKey(EmissionFactor, on_delete=models.PROTECT)
       
       # Calculation inputs
       activity_value = models.DecimalField(max_digits=20, decimal_places=6)
       activity_unit = models.CharField(max_length=50)
       
       # Results
       co2e_kg = models.DecimalField(max_digits=20, decimal_places=6)  # Total CO2e in kg
       co2_kg = models.DecimalField(max_digits=20, decimal_places=6, null=True)
       ch4_kg = models.DecimalField(max_digits=20, decimal_places=6, null=True)
       n2o_kg = models.DecimalField(max_digits=20, decimal_places=6, null=True)
       
       # Classification (denormalized for fast querying)
       scope = models.PositiveSmallIntegerField()
       category = models.CharField(max_length=50)
       
       # Reporting period
       reporting_year = models.PositiveIntegerField()
       reporting_month = models.PositiveSmallIntegerField(null=True)
       
       # Audit
       calculated_at = models.DateTimeField(auto_now_add=True)
       calculated_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
       calculation_method = models.CharField(max_length=100, default='auto')
       
       class Meta:
           ordering = ['-calculated_at']
           indexes = [
               models.Index(fields=['project', 'scope', 'reporting_year']),
               models.Index(fields=['module', 'reporting_year']),
           ]
       
       def __str__(self):
           return f"{self.activity_value} {self.activity_unit} → {self.co2e_kg} kg CO2e"
   ```

3. **Register in Admin**
   
   Location: `/home/ahmed/carbon/backend/emissions/admin.py`

4. **Add to INSTALLED_APPS**
   
   Update `/home/ahmed/carbon/backend/config/settings.py`

5. **Create and Run Migrations**
   ```bash
   python manage.py makemigrations emissions
   python manage.py migrate
   ```

**Verification:**
- Models created without errors
- Migrations applied successfully
- Admin interface accessible
- Can create EmissionFactor via admin

**Deliverables:**
1. `backend/emissions/` app directory
2. `backend/emissions/models.py` with EmissionFactor, GWP, Calculation
3. `backend/emissions/admin.py` with admin registrations
4. Applied migrations

---

## 5. AI COPILOT 3.0 ARCHITECTURE

### 🎯 VISION: Carbon Intelligence Platform

Transform from basic chatbot to full Software 3.0 AI system.

```
┌────────────────────────────────────────────────────────────────────┐
│                     CARBON AI 3.0 ARCHITECTURE                     │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──────────┐    ┌─────────────────────────────────────────────┐  │
│  │  User    │───▶│  Intent Router (LLM classifier)             │  │
│  │  Query   │    └─────────────────────────────────────────────┘  │
│  └──────────┘              │                                      │
│                 ┌──────────┼──────────┬──────────┐               │
│                 ▼          ▼          ▼          ▼               │
│          ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│          │ Knowledge│ │  Data    │ │Calculate │ │  Report  │    │
│          │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │    │
│          └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘    │
│               │            │            │            │           │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    TOOL LAYER                               │ │
│  │  [RAG Search] [DB Query] [Calculator] [Report Gen] [API]   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│               │            │            │            │           │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    DATA LAYER                               │ │
│  │  [ChromaDB+Hybrid] [PostgreSQL] [Emission Factors] [Redis] │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  OBSERVABILITY: Langfuse traces │ RAGAS evals │ Feedback   │ │
│  └─────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

### Key Technologies for 3.0:

| Layer | Current | Target 3.0 |
|-------|---------|------------|
| LLM Provider | POE API (GPT-4o) | Direct OpenAI/Anthropic + fallback |
| Agent Framework | None | LangGraph multi-agent |
| RAG Search | Basic ChromaDB | Hybrid (semantic + BM25) + Reranking |
| Embeddings | MiniLM (384d) | text-embedding-3-large or Cohere |
| Observability | Basic logging | Langfuse/LangSmith tracing |
| Evaluation | None | RAGAS automated + human feedback |
| Guardrails | None | Guardrails AI for compliance safety |

---

## 6. WORKER AGENT PROMPT TEMPLATE

Use this prompt to instruct the worker agent:

```
You are a skilled software developer working on the Carbon Management Platform.

## Your Role
- You execute tasks assigned by the Project Master in TASK.md
- You report results in TASK-RESULTS.md
- You follow instructions precisely and completely
- You ask clarifying questions if task is ambiguous

## Current Task
Read TASK.md section "4. CURRENT ACTIVE TASK" for your assignment.

## Working Style
1. Read the entire task description carefully
2. Plan your approach before coding
3. Implement in small, testable increments
4. Test each component as you build
5. Document any deviations or blockers
6. Write clean, production-quality code
7. Update TASK-RESULTS.md with detailed status

## Quality Standards
- Follow existing code patterns in the project
- Add proper error handling
- Include logging for debugging
- Write docstrings for all functions
- Maintain type hints where used

## Communication Protocol
- For blockers: Add to TASK-RESULTS.md with [BLOCKER] tag
- For questions: Add to TASK-RESULTS.md with [QUESTION] tag
- For completions: Update task status to ✅ in TASK-RESULTS.md

## Files to Reference
- /home/ahmed/carbon/TASK.md (your assignments)
- /home/ahmed/carbon/TASK-RESULTS.md (your reports)
- /home/ahmed/carbon/backend/ (backend code)
- /home/ahmed/carbon/carbon-frontend/ (frontend code)

Begin by reading TASK.md and executing the current active task.
```

---

## 7. SUCCESS METRICS

### User Feature Targets (UPDATED)

| Metric | Before | After | Status |
|--------|--------|-------|--------|
| Emission Factors in DB | 0 | 100+ | ✅ DONE |
| Auto-calculations working | ❌ | ✅ | ✅ DONE |
| Dashboard available | ❌ | ✅ | ✅ DONE |
| Charts available | ❌ | ✅ | ✅ DONE |
| Total CO2e Tracked | 0 | 2,516 tonnes | ✅ DONE |

### AI Copilot 3.0 Targets

| Metric | Current | Target | Timeline |
|--------|---------|--------|----------|
| Knowledge docs in RAG | 5 | 200+ | Week 6 |
| Retrieval accuracy | Unknown | ≥95% | Week 6 |
| Tools/Actions available | 0 | 5+ | Week 8 |
| Proactive insights/day | 0 | 3-5 | Week 10 |
| Response latency (p50) | ~2s | <3s | Maintain |
| User satisfaction | No data | 4.5/5 | Week 10 |

---

## 8. APPENDIX: KEY FILE LOCATIONS

| Component | Path |
|-----------|------|
| **Emissions (NEW)** | `/home/ahmed/carbon/backend/emissions/` |
| Core Models | `/home/ahmed/carbon/backend/core/models.py` |
| Data Schema | `/home/ahmed/carbon/backend/dataschema/models.py` |
| AI Backend | `/home/ahmed/carbon/backend/ai_copilot/` |
| RAG Engine | `/home/ahmed/carbon/backend/ai_copilot/services/rag_engine.py` |
| Context Engine | `/home/ahmed/carbon/backend/ai_copilot/services/context_engine.py` |
| POE Client | `/home/ahmed/carbon/backend/ai_copilot/services/poe_client.py` |
| Memory | `/home/ahmed/carbon/backend/ai_copilot/services/memory.py` |
| Dashboard (NEW) | `/home/ahmed/carbon/carbon-frontend/src/pages/Dashboard.jsx` |
| Charts (NEW) | `/home/ahmed/carbon/carbon-frontend/src/components/dashboard/` |
| AI Frontend | `/home/ahmed/carbon/carbon-frontend/src/components/ai/` |
| AI API Client | `/home/ahmed/carbon/carbon-frontend/src/api/aiCopilot.js` |

---

## 9. 10-WEEK ROADMAP SUMMARY

```
WEEK 1  ████████████████████ Emission Factor Model + Data
WEEK 2  ████████████████████ Calculation Engine + API
WEEK 3  ████████████████████ Dashboard Backend + Frontend
WEEK 4  ████████████████████ Charts + Period Selector
WEEK 5  ████████████████████ RAG Knowledge Ingestion
WEEK 6  ████████████████████ Hybrid Search + Reranking
WEEK 7  ████████████████████ Agent Framework (LangGraph)
WEEK 8  ████████████████████ Tools: Calculator, Query, Report
WEEK 9  ████████████████████ Celery + Insight Generation
WEEK 10 ████████████████████ Proactive Alerts + Notifications
```

---

**Last Updated:** 2026-02-01  
**Version:** 3.0 - P0/P1/P2 Complete, Starting Deep AI  
**Next Review:** After Task 2.1 completion
