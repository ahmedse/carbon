# Blueprint review — Opus grounded-tutor / ERP-coworker conversation

Owner: Pulse-for-medicine blueprint-review (subagent), 3 Oct 2026.
Source reviewed: the Claude-Opus-5.5 conversation *"I need to build an ai
tutor for a course on Moodle …"*
(`~/.cursor/projects/home-ahmed-ws-carbon/uploads/3nMkRiZKVzGhaLNYW4yd-0.md`).
Scope: turn the LEARNINGS into project artifacts. No engine change, no golden
loosened, no rung marked, no commit. Local/dev claims are labelled as such.

Current honest state this review assumes (unchanged here): coverage
**873/969** live-Moodle rows, **13** listed courses, offline conformance
**117 cases (9 Ask-door cases × 13 courses; 22 pytest tests)**, the S3 live-assessment guard built, the readiness machinery
`backend/ai/moodle_readiness/` present and **default-OFF**, a **LOCAL (dev)**
K10 bring-up done, and a **LOCAL (dev)** K11 pilot PASS (pilot label only).
Production **K10 / K11 / B5 / B6 / C7 remain `not_pass`**.

This review agrees with the Opus document on almost every engineering instinct.
Where we differ, we differ because a frozen Pulse contract is *stricter* about
grounding. Those differences are recorded as divergences and as a prioritized
adoption backlog, each item written as PRINCIPLE → RULE → BENCHMARK.

---

## 1. CONVERGENCE MAP

Each Opus principle, mapped to the exact Pulse rule, gate, or benchmark that
already implements it.

| Opus principle (where) | Pulse implementation (exact) | Checkable gate / benchmark |
|---|---|---|
| **Grounding layers** (tutor §5): hard content filter, retrieval gate, cite every claim, treat context as data, injection defense. | `ai/moodle_bank.select_for_turn` filters by `course` + `activity_id` + `world` before any text is considered; `cite_open_activity` returns a passage only when exactly **one** passage matches, and otherwise returns `MISS`. Doors in `ai/moodle_page.py` (`course/identity/greet/staff/fact/lecture/section/quiz/explain/topic/reference/closed`), reached through `ai/moodle_host.prepare_ask` → `door_answer`. | `test_moodle_c6.py`, `test_moodle_k6_coverage.py`, `test_moodle_body.py`; `gold/conformance-13.yaml` over `test_moodle_conformance.py` = **117 cases (9 Ask-door cases × 13 courses; 22 pytest tests)**. The miss is the exact sentence `This is not in this lecture.` |
| **Citations required, structured output, reject unsupported answers** (tutor §5.5–5.7). | A cite is a **passage id + a verbatim substring** of that passage, never a model sentence. T2 caps explain at 3 spans, all substrings of one activity; a non-substring proposal is dropped. | `test_moodle_tutor.py`, `test_moodle_body.py`; the T1/T2 rungs on the canvas. `pack_contract --gate` proves the pack shape. |
| **Ingestion: chunk by structure, attach metadata** (tutor §4b). | One passage = one file/page/label/book; metadata is the passage id `shortname:kind:activity[:filename]`; a module joins its bank passage by **local cmid, then section + family + name** (`roster_key` / `match_roster_activity` in `ai/moodle_bank.py`). Ingest: `scripts/ingest_aast_med_local_files.py`, `scripts/ingest_aast_med_external.py`. | `test_moodle_join_coverage.py` (9 tests), `test_moodle_k6_files.py`, `test_moodle_k6_coverage.py`. |
| **Intent pipeline** (intent §2): context resolution, safety/scope, classification, entity linking, slot check, clarify/route/refuse. | One call emits a `Decision` (`engine/cognition/turn/decision.py`, closed `Command` ops); `Arbiter.decide` logs one `TurnDecision` (`engine/cognition/turn/arbiter.py`); `engine/text/normalize.py` normalizes only ("Do not add intent regexes here"); affirmations live only in `dialogue/affirmation.py` (`engine/cognition/dialogue/affirmation.py`). | ADR-0049 P1 (`PULSE_UNDERSTAND=v21`); `pulse_gauge --gate` keeps `re_compile`/`staged_exits` flat. |
| **Query rewriting + dialogue state** (intent §7): a standalone request; a small typed state. | `ConversationState` (`engine/cognition/state_store.py`: `focus`, `intent`, `slots`, `open_question`, `active_plans`); medicine keeps `moodle_ask_state.resolved_topic`. Follow-ups resolve against **typed state**, never a history scan. | ADR-0047; `test_moodle_readiness.py::test_turn_path_never_names_readiness`; the B4 rung. |
| **Safety and scope as first-class intents** (intent §10). | `ai/moodle_refusals.py` + `domain_packs/aast-med/refusals.yaml` (`clinical_care`, `assignment_text`, `question_bank`, `mentorship_caseload`); L0 course-list answers in `ai/moodle_host.py`. Vocabulary lives in the pack, not the engine. | `test_moodle_c4.py`, conformance refuse cases; ADR-0050. |
| **Exam integrity: detect a pasted exam during an active quiz window** (intent §9; tutor roadmap v3). | **S3 guard**: `ai/moodle_integrity.py` + `domain_packs/aast-med/integrity.yaml`, wired at the top of `prepare_ask` (L160), `page_context_from_snapshot` (L216), and `door_answer` (L290) in `ai/moodle_host.py`. Typed signed-snapshot signals only (open `quiz`/`qbank`/`lesson`, or an active signed window); never a message-phrase scan. | `test_moodle_conformance.py` (exam/MCQ refusal), the S3 tests; conformance **117 cases (9 Ask-door cases × 13 courses; 22 pytest tests)**. |
| **Knowledge-graph edges approved by teachers; every node/edge points to a SourceChunk** (KG §5.Build.5–6). | **B6/C7** in `docs/pulse/aast-med/READINESS-SPEC.md` §6: edges from each lecture to its ILOs to assessments, each grounded in a cited passage id; C7 only after C6 green and L5 passable. The readiness evaluator `evaluate(ReadinessInputs)` marks a rung `pass` only when every gate is true. | `ai/moodle_readiness/evaluator.py`; `test_moodle_readiness.py`; `gold/l5.yaml`. Status **not_passable** (deliberate — see §2). |
| **Action risk tiers Read / Draft / Write / High-risk + confirm** (ERP §6). | ADR-0046 / RULE_35: Chat never host-mutates; writes are **Plan → Approve → Run → RULE_21 `/steps/confirm/`**. Chat write tools become `handoff_agent` (`validate_decision`). Medicine Ask is read-only (P6); the plan dial is off. | `.ai-toolkit/decisions/0046-pulse-chat-no-host-mutation-stage.md`, `.cursor/rules/pulse-chat-agent-mode-contract.mdc`, `.ai-toolkit/decisions/0014-pulse-chat-agent-mode-split.md`; RULE_21. |
| **Numbers must come from a tool; the LLM must not calculate** (ERP §6). | `engine/cognition/turn/grounding.py` (ADR-0049 P6): every number in a reply must appear in the tool payload. Medicine doors are deterministic — a number is a verbatim span of the passage, or it is not emitted. | `grounding.py` + its tests; ESS bound lookup/write spend **0 LLM** (`ai.eval.intelligence_ladder.score_l5`). |
| **Refuse when no data; "I couldn't find that"** (tutor §5.2). | P5 "Silence is a correct answer": `MISS` = `This is not in this lecture.`; L0 = `This is not on the course list.`; `closed_answer`. | `test_moodle_l0.py`, `test_moodle_a2_course_off.py`, conformance cross-course miss. |
| **Evaluation set of 100+ questions; per-change reruns** (tutor §9). | Offline conformance: `gold/conformance-13.yaml`, 13 courses × 9 Ask-door cases = **117 cases**, realized by **22 pytest tests** in `test_moodle_conformance.py` (all passing; not re-run here). L5 curriculum draft: `gold/l5-curriculum.draft.yaml` (1300 items, 100/shortname). | `pack_contract --gate`; `test_moodle_l5_draft.py` (18 tests). | 

---

## 2. DIVERGENCE TABLE

Where Opus recommends something we deliberately do **not** do, the contract
reason, and the trade-off we accept.

| Opus recommendation | What Pulse does instead | Contract reason | Trade-off we accept |
|---|---|---|---|
| **Vector RAG + pgvector as the base** (tutor §4c, §8). | Deterministic doors over a JSONL passage bank; a unique passage or an exact `MISS`. No embeddings. | The **B3 gate** is unmet: there is no retrieval gold that a query the title-door fails, where a unique passage would answer without loosening cite uniqueness. A second search can override a unique cite; RAG moves the failure (field table: RAG still hallucinated 17–33%). ADR-0050 keeps the search vocabulary in the pack; Pulse 2.1 budget forbids a new engine search. | **Stricter grounding, weaker semantic recall.** A paraphrase or synonym that is not a verbatim substring of the passage misses even when a vector search would find it. Mitigation considered: keyword/BM25 only (backlog B2), never vectors. |
| **Knowledge graph / GraphRAG now** (KG §Recommendation). | B6/C7 stay `not_passable`; no Neo4j, no second Postgres, no pgvector, no `student_cohorts`. | READINESS-SPEC §6: "indexing is not a graph." C7 only after C6 green and L5 passable; edges must be human-approved and passage-grounded. Carbon's schema `knowledge_graph` is a different product. | **No prerequisite / multi-hop / course-wide "main themes" reasoning** for now. Those waits on authored, teacher-approved edges. |
| **Faithfulness check as a core stage** (tutor §5.7: a second LLM call or entailment model). | Not required today: medicine has **no LLM-written door**. Every emitted sentence is a verbatim span of a selected passage. | T2: "a proposal that is not a substring is dropped, never printed." An LLM-written sentence is not a citation (P2). | **Recall is exact-substring only**; a faithful paraphrase that is not verbatim still misses. A faithfulness pass is adopted as future-proofing for any LLM-written door (backlog B3), not as a substitute for verbatim cites. |
| **Long per-student memory / adaptive learning / mastery tracking** (KG §Why a KG, tutor §6). | **B5 `not_passable`.** No table exists or may be created. | Requires a non-empty production cohort + consent + audit + R12; R16 forbids `student_cohorts` before L5. ADR-0046: no write before consent. | No personalization now; curriculum answers stay identical for two students on the same lecture (R12). The LOCAL (dev) pilot supplies consent/audit for two students only. |
| **Text-to-SQL, ERP writes, agent tool loop** (ERP §3–§6). | Out of scope for medicine: Ask is read-only, the plan dial is off, and no write tool is exposed. | ADR-0046/RULE_35; P6 "Ask does not change the college." | No ERP-style analytics/actions on the medicine surface. The risk-tier design is nonetheless the template we already obey. |
| **Fine-tuning / a model's latent knowledge** (tutor §1). | **Agreed** with Opus: rejected as a grounding mechanism. | We cite a passage or we miss. | None (convergence, recorded for completeness). |
| **Vision LLM writes a text description to index** (tutor §4a diagrams). | A model-written description is **never** a citable span. If adopted at all, it is a retrieval-only label or teacher-approved text. | P2/T2: a claim is a verbatim citation; a generated description that becomes a cited sentence would put model prose in a door. | Diagram content is not citable today; the backlog item (B1) constrains vision to non-citable labels. | 

---

## 3. ADOPTION BACKLOG

Prioritized. Each item is PRINCIPLE → RULE → BENCHMARK, tagged
**BLOCKED-BY-CODE** (agent-doable, no live data) or **BLOCKED-BY-REAL-WORLD**
(needs a live artifact, human action, or policy decision), mapped to the rung it
serves, and flagged when a contract forbids it now.

### B1 · Extraction upgrades — speaker notes, OCR, LibreOffice, vision *(priority 1)*

- **PRINCIPLE.** A claim is a citation; a passage exists only when real text
  exists (P2 / T1). Opus's extraction table (tutor §4a) is the right target.
- **RULE.** An extractor writes a passage only when the stored file yields real
  text; a legacy `.ppt`, a scanned PDF, a video, or a folder stays unread with a
  printed reason — never a guess (`scripts/ingest_aast_med_local_files.py`
  docstring and `_extract`). Add: (a) PowerPoint speaker notes
  (`ppt/notesSlides/*.xml`) and comment text; (b) OCR for a PDF with no
  extractable layer; (c) LibreOffice-headless `.ppt` → `.pptx`; (d) vision
  descriptions **only** as non-citable retrieval labels, never a door sentence.
  Do not loosen any golden.
- **BENCHMARK.** Coverage (loaded ingestible / Pulse-active ingestible) rises by
  **exactly** the number of newly written passages; `test_moodle_k6_files.py`
  and `test_moodle_join_coverage.py` stay green; a recovered file counts as
  loaded only when the recovered body is a verbatim substring of the stored
  file; `pack_contract --gate` exit 0.
- **RUNG.** T1, B0–B2 (Index/coverage); feeds C6/L5.
- **TAG.** LibreOffice/pptx notes/OCR machinery: **BLOCKED-BY-CODE**. OCR text
  sign-off (a verbatim cite must be exact) and any vision text: **BLOCKED-BY-
  REAL-WORLD** (human review). **Contract flag:** vision output must never
  become a citable span (see §2).
- **Measured reach (offline join-level view, `ai/moodle_extraction_gap.py`):**
  of **83** unread Pulse-active ingestible rows, **9** are legacy `.ppt`
  (LibreOffice) and **1** is a `.pdf` with no text (OCR) → **10** document-
  recoverable. The other **73** are not document-extraction work: **40**
  external website links, **12** Google Docs/Slides, **17** YouTube captions,
  **4** media files. Speaker notes and vision **do not move the unread count**
  — every unread office row is already loaded or not office; they deepen an
  already-loaded lecture. The canvas's **105** is the live-Moodle row view; this
  is the committed-bank join view. (See §4.)
- **Update 3 Oct 2026 (B1 recovery run).** All **9** legacy `.ppt` decks were
  read and appended to the bank: NMD2101 ×6, NMD4201 ×2, MED520 ×1. LibreOffice
  is **not installed** on this host (no sudo), so the recovery uses a committed
  direct OLE2/CFB reader (`_legacy_ppt_text` in
  `scripts/ingest_aast_med_external.py`) that copies slide text atoms verbatim
  and keeps a speaker note only when it is real note text — the slide-master
  placeholder prompt is dropped. Extraction is append-only: the empty
  placeholder row is never rewritten, and an already-owned ref is never
  duplicated. The offline join view is now **74** unread, **860/934** loaded,
  **`legacy_ppt = 0`**; the live-Moodle 864/969 is now **873/969** (105 → 96
  unread). The **1** scanned Arabic PDF stays unread — OCR text needs a verbatim
  cite and remains **BLOCKED-BY-REAL-WORLD** sign-off — and vision descriptions
  stay non-citable labels (**BLOCKED-BY-REAL-WORLD**). No rung is marked.

### B2 · Keyword / BM25 hybrid, no vector store *(priority 2)*

- **PRINCIPLE.** A claim is a citation; a second search must not override a
  unique cite (P2 / B3).
- **RULE.** Keyword/BM25 body-topic recall lives in the pack or the door, never
  in `engine/**`. No engine `re.compile`, no phrase table;
  `harness_budget` must not rise on any meter; the unique-passage rule stands.
  On a miss the answer is still the exact `MISS`.
- **BENCHMARK.** The B3 gate condition: a retrieval gold of queries the
  title-door fails where a **unique** passage answers. Measure keyword recall
  and confirm a passage still has exactly one owner
  (`test_moodle_k6_coverage.py`); `pulse_gauge --gate` flat.
- **RUNG.** B3.
- **TAG.** **BLOCKED-BY-CODE** (the retrieval gold must be authored first).
- **Contract flag.** Do **not** introduce vectors/pgvector. Allowed only with
  cite uniqueness preserved and no budget rise.

### B3 · Faithfulness / entailment second pass for an LLM-written door *(priority 3)*

- **PRINCIPLE.** Every emitted sentence is supported by the cited passage.
- **RULE.** Only verbatim spans are emitted (T2); an LLM-written sentence is
  never a cite. If a future LLM-written door is ever authorised, a second pass
  drops unsupported sentences and every number must appear in the tool payload
  (`engine/cognition/turn/grounding.py`).
- **BENCHMARK.** 0 unsupported sentences; every emitted sentence is a substring
  of a cited passage; green with the pass **off** (today's doors are
  deterministic, so the pass is a no-op).
- **RUNG.** T2 / B1 (C6 honesty).
- **TAG.** **BLOCKED-BY-CODE**, but **not needed now**. **Contract flag:**
  wiring an LLM-written door before this pass violates the no-model-sentence
  rule.

### B4 · Explicit intent taxonomy + risk tags + learner signals in TYPED state *(priority 4)*

- **PRINCIPLE.** Understanding is one `Decision`; state is typed, not prose
  (ADR-0049 P1, ADR-0047). Opus's intent §4/§5 taxonomy and `learner_signal`.
- **RULE.** Taxonomy, risk tag, and learner signal are typed fields on
  `Decision` / `ConversationState` (`open_question.kind`, `active_plans`); no
  new engine phrase table, no routing `re.compile`, no history scan.
  Affirmations go through `dialogue/affirmation.py` only. A risk tag never
  grants a write (ADR-0046 stands).
- **BENCHMARK.** A multi-turn golden where a follow-up resolves against
  `open_question.kind`; `moodle_ask_state.resolved_topic` stays typed;
  `test_moodle_readiness.py::test_turn_path_never_names_readiness`;
  `pulse_gauge --gate` flat.
- **RUNG.** L2/L3/B4; S1.
- **TAG.** **BLOCKED-BY-CODE.**
- **Contract flag.** New routing exists only as an Arbiter signal + a golden —
  never a phrase table or `re.compile`.

### B5 · Real-student evaluation corpus + thumbs feedback *(priority 5)*

- **PRINCIPLE.** Measure, don't claim (measurement contract RULE_36 / PB-63).
- **RULE.** Distinct from the **117 authored conformance asks**: a corpus of
  real student questions with expected source pages, plus out-of-scope cases
  and a thumbs channel; run on every change to chunking/prompts/models. No live
  bank for a surface → that surface stays **missing**.
- **BENCHMARK.** ≥100 real questions with expected pages; refusal cases
  included; report faithfulness / relevance / context precision / recall (Ragas
  or DeepEval); never merge Chat and Tasks scores.
- **RUNG.** L2/L3/L5/K11; measurement contract. Feeds the L5 curriculum freeze.
- **TAG.** **BLOCKED-BY-REAL-WORLD** (needs real students; R16 forbids a
  student surface before L5; a policy/data decision).
- **Contract flag.** Cannot be gathered from the LOCAL (dev) two-student pilot
  and must not be presented as a live bank.

### B6 · Moodle quiz-timing via API to strengthen S3 *(priority 6)*

- **PRINCIPLE.** Never answer a live assessment (S3).
- **RULE.** Read the timing window from the Moodle API (a signed server call),
  not a client-supplied snapshot; the module list stays in
  `domain_packs/aast-med/integrity.yaml`; the guard never names the exam,
  its title, or its questions.
- **BENCHMARK.** An open quiz with an active window refuses via API-confirmed
  timing even when the client snapshot is stale or lying; the module-type
  refusal stays; a closed window does not refuse.
- **RUNG.** S3 → K10/K11.
- **TAG.** **BLOCKED-BY-REAL-WORLD** (needs the production Moodle API + HMAC
  install, i.e. K10).
- **Contract flag.** The guard must not become a phrase check and must not
  expose the exam.

---

## 4. Measurement artifact (Optional Deliverable 3)

`backend/ai/moodle_extraction_gap.py` + `backend/ai/tests/test_moodle_extraction_gap.py`
is the only code added by this review. It is a **read-only report**, not a
feature: it writes nothing, calls no host, changes no answer, and is not
imported by any turn path (locked by its test). It classifies each unread
Pulse-active ingestible roster row by the extraction technique it would need.

Offline join-level view of the committed bank (13 listed courses):

| Technique | Unread rows | Document-extraction work? |
|---|---|---|
| `legacy_ppt` (LibreOffice) | 9 | yes |
| `scanned_pdf` (OCR) | 1 | yes |
| `external_web` (arbitrary website) | 40 | no |
| `remote_youtube` | 17 | no |
| `remote_google` (Docs/Slides) | 12 | no |
| `media` (video) | 4 | no |
| **Total unread** | **83** | **10 recoverable by conversion/OCR** |

Join-level totals: active **934**, loaded **851**, unread **83**. The canvas
**864/969** and its **105 unread** are the live-Moodle `mdl_course_modules` row
view; the two views differ only in the denominator (live rows vs the committed
bank join) and neither is a claim about a rung.

**Update 3 Oct 2026 (B1 recovery run):** the 9 `legacy_ppt` rows were read with
the committed direct reader and appended, so this committed-bank view is now
active **934**, loaded **860**, unread **74** (`legacy_ppt = 0`,
`scanned_pdf = 1`); the matching live-Moodle view moved from 864/969 to
**873/969** (unread 105 → 96). The 83 / 10 figures above are the pre-recovery
measurement this review recorded.

The honest headline: **document extraction can move at most 10 of the 83
offline unread rows** (9 legacy decks + 1 scanned PDF). The majority are remote
bodies (Drive/YouTube) or arbitrary web links that no document reader reaches;
they are B2 remote work, not extraction upgrades. Speaker notes and vision
descriptions improve *within-passage* recall on already-loaded lectures and do
not change the coverage numerator. (After the 3 Oct 2026 run, 9 of the 10 have
moved; only the scanned PDF remains, still OCR BLOCKED-BY-REAL-WORLD.)

---

## 5. Confirmations

- **No rung marked green.** K10/K11 (production), B5, B6, C7 remain
  `not_pass`; K4/K9 stay red; the LOCAL (dev) pilot label is unchanged.
- **No engine change.** Nothing added or edited under `backend/ai/engine/**`.
- **No golden loosened.** No file under `domain_packs/aast-med/gold/` was
  edited.
- **No `people:view`, no tables.** `student_cohorts` stays empty; no store
  created.
- **Gates (run in this review).** `python -m ai.eval.pack_contract --gate` →
  **exit 0** (aast-med v2 `violations=0`). `python -m ai.eval.pulse_gauge
  --gate` → **pass, no meter rose**. `pytest ai/tests/ -k moodle` →
  **244 passed, 3723 deselected** (was 224 before this review; the new
  measurement file adds 10). The new file alone:
  `test_moodle_extraction_gap.py` → **10 passed**. No existing test was
  loosened; no golden was edited.
- **Update 3 Oct 2026 (B1 recovery run).** After the 9 legacy `.ppt` decks were
  appended, `python -m ai.eval.pack_contract --gate` → **exit 0**, and
  `pytest ai/tests/ -k moodle` → **248 passed, 3723 deselected**. The new
  `test_moodle_legacy_ppt.py` adds 4 tests. Two existing tests were updated to
  the new measured state, not loosened: the extraction-gap "not vacuous" check
  now pins the scanned PDF, and the join-coverage "no passage" case now finds a
  course that still has an unread row (MED520 is fully loaded). No golden edited;
  no rung coloured.
- **Canvas.** Added the H2 "Blueprint review — convergence and adopted gaps";
  existing sections (readiness, conformance, S3) are intact; TypeScript check
  reports no errors; no rung colour changed.
