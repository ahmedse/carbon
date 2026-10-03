# aast-med Pulse — Teaching-Wave Spec

**Status: FROZEN. Version 1.0. 3 Oct 2026.**

Owner: Pulse-for-medicine teaching wave. This is **Phase 1 of a two-phase
program**. It defines the principles, exact rules, benchmarks, and excellence
ladders that close the teaching-readiness blockers. **Phase 2 implementation may
not begin until this file exists and is frozen** (see §5).

This spec authorizes **no implementation**. It is docs + canvas only: no code,
no plugin change, no `domain_packs` value change, no golden change, no commit,
no deploy. `manage.sh` is never started or killed by an agent.

Why this file exists: a teaching-readiness assessment returned verdict
**Partially** — KB ready (873 citable / 13-of-13; offline conformance 117 cases
= 9 Ask-door cases × 13 courses, 22 pytest tests),
KG additive and **not** a teaching dependency, **no structured teach/lecture
path**, and doors do **not** consume the keyword index. The user ordered that
principles, rules, benchmarks, and excellence ladders be well defined **before**
any further implementation. This file is that definition.

Frozen contracts this spec obeys, without exception: `READINESS-SPEC.md`,
`L5-PASSABILITY.md`, `CONTENT-ENGINE-SPEC.md` (incl. AMENDMENT), `DEFERRED.md`,
ADR-0046, ADR-0047, ADR-0049 / Pulse 2.1, ADR-0050 (domain-free core),
RULE_21, RULE_35, RULE_36 / PB-63, and `.cursor/rules/pulse-2-1-contract.mdc`.

---

## 0. Principles (non-negotiable)

These invariants bind **every** workstream in §3. A workstream that cannot
honor one of these does not ship; it is re-specified, not waived.

1. **ai-toolkit.** The work follows the repo's `.ai-toolkit` decisions and
   playbooks. No parallel/unrecorded process. ADRs are read first; a new
   capability that contradicts an ADR needs an ADR change, not a shortcut.
2. **ui/ux patterns + components.** Any surface uses the existing patterns and
   components. No new design language, no one-off widget, no gradient/emoji/
   shadow styling in canvases.
3. **ADR-0046 (Chat never host-mutates).** Chat reads, advises, drafts, and
   clarifies. A write is Plan → Approve → Run → RULE_21 step consent, or the
   host UI. A Chat turn also never fetches and never OCRs. A "teach draft" is a
   **proposal**; a staff member applies it in the existing Extra tab. Nothing in
   this wave may enable Confirm/Decline for a host write in Chat (RULE_35).
4. **ADR-0047 (ConversationState / ContextPack / Arbiter).** Any new
   routing/state lands as a typed field (`Decision`, `ConversationState`,
   `open_question.kind`, `active_plans`) or an Arbiter signal plus a golden.
   Never a history scan, never an apply/yes allowlist, never a module-level
   phrase table.
5. **Domain-free core (ADR-0050).** `backend/ai/engine/**` gains **no** host or
   brand words, **no** phrase tables (`tuple[str]` / `frozenset` of words),
   **no** new routing `re.compile`, **no** new `StagedExit`. All vocabulary
   lives in the pack (`domain_packs/<id>/**`). `python -m ai.eval.pack_contract
   --gate` must pass and `python -m ai.eval.pulse_gauge --gate` must show **no
   meter rose** (`harness_budget` must not rise on any meter).
6. **No golden loosening.** Every existing file under
   `domain_packs/aast-med/gold/**` stays byte-identical unless a change is
   Master-approved on host evidence. A test updated to a newly measured state
   must not reduce an assertion's strength.
7. **No `people:view` for `emp_1067`.** Never grant it to pass a coworker
   golden.
8. **No new tables / migrations.** The only medicine tables are the Moodle
   plugin's `local_pulse_consent` + `local_pulse_audit` (already created by the
   pilot). Carbon creates no table; no second Postgres, no Neo4j, no pgvector.
9. **`student_cohorts` stays empty.** Evaluator/repo state is empty. A local
   Docker pilot setting behind `pilot_students=1` is the recorded
   PILOT-EXCEPTION, not permission to fill production. R16 holds.
10. **No rung marked green without scored evidence.** A score from a dated,
    full live run, or `--gate` on committed artifacts. A stub, a unit bank, one
    PASS, or a `--noreload` process never flips a rung. K4/K9 stay red;
    production K10/K11/B5/B6/C7 stay unmarked; the LOCAL (dev) K11 pilot stays
    labelled **K11 (local pilot)**.
11. **SOAK 2026-09-23 FAIL stays.** Do not overwrite it. Dry-run / SKIP / FAIL
    do not increment a streak.
12. **No `manage.sh` start/kill by agents.** No live smoke without STACK-HOLD.
13. **Additivity.** The knowledge graph and the keyword index are **additive
    artifacts**, never required for teaching, for any door answer, or for any
    existing golden. Removing either must leave every door answer and every
    golden unchanged.
14. **Honest levels.** Every ladder below states its CURRENT level, marked
    honestly. Nothing in this spec flips a rung.

---

## 1. Excellence ladders

Each ladder gives an **id**, **name**, the exact **pass criterion** (command +
threshold), a **do-not-claim-if guard**, and the **CURRENT** level, marked
honestly.

### 1.1 L-T · Teaching

| Rung | Name | Pass criterion (command + threshold) | Do not claim if |
|---|---|---|---|
| **T0** | Grounded tutor Q&amp;A | `python -m pytest ai/tests/test_moodle_conformance.py -o addopts= -p no:_testbrand -q` green; gold `conformance-13.yaml` = **117 cases (9 Ask-door cases × 13 courses; 22 pytest tests)** on 13/13 courses; every factual answer is a verbatim substring of the selected passage, miss is exactly `This is not in this lecture.` | Any answer contains a model sentence, a filename, or a fact absent from the cited passage. **CURRENT.** |
| **T1** | Grounded multi-passage lesson **draft** | A staff-triggered draft command emits a lesson whose **every** curriculum-fact sentence carries a verbatim span (exact substring) and a passage id from the open activity — **no new facts**. Requires the **B3 grounding/faithfulness pass** (§1.6). Benchmark: B3 gold ≥50 draft assertions, **100% verbatim, 0 fabricated spans**; `test_moodle_teach.py` green; R11 4/4 (draft labelled draft, no Moodle write). | Any sentence states a curriculum fact without a verbatim substring; any passage id is not in the bank for the open activity; any draft claims a Moodle write. **TARGET.** |
| **T2** | Structured lesson (ILO + worked example + assessment), staff-approved | Every ILO, worked example, and assessment item maps to a cited passage; every assessment answer is a verbatim span; the only write is a staff **Apply** in the Extra tab (ADR-0046). Command: `test_moodle_teach.py` + the T2 gold green. | Any ILO/assessment edge is model-invented or ungrounded; Chat applies the lesson; a student surface is opened. **TARGET (after T1).** |
| **T3** | Adaptive / spaced | Practice order changes per learner while the cited curriculum answer is identical for two students on the same lecture; withdrawal stops use. | Requires a non-empty student cohort + consent + audit + R12 (B5). **not_passable — BY-REAL-WORLD.** |

**T1+ requires the B3 grounding/faithfulness pass. Definition of B3:**

B3 is a **deterministic, offline faithfulness check**, not an LLM judge in the
default path.

- **Rule.** Each emitted curriculum-fact sentence is accepted only if it
  contains a **verbatim substring** (exact characters) of the single passage it
  cites, and that passage id resolves in the bank for the open activity. A
  sentence with no verbatim span is **dropped, never printed**. A draft is
  labelled `draft` and claims no Moodle write (R11). No phrase table and no
  `re.compile` are added to `engine/**`; the check is pack/door code.
- **Gold.** `domain_packs/aast-med/gold/teach-b3.yaml` (new, authored in
  Phase 2): ≥50 assertions of the form `(draft sentence) → passage id →
  verbatim span`, plus out-of-scope cases that must be refused.
- **Threshold.** **100% of graded sentences carry a verbatim span; 0 fabricated
  spans; 0 non-resolving passage ids.** An optional LLM entailment pass may
  **flag** a draft for human review but may never **certify** it, and it must
  not run on a Chat turn.

### 1.2 L-R · Retrieval

| Rung | Name | Pass criterion (command + threshold) | Do not claim if |
|---|---|---|---|
| **R0** | Exact-substring over whole-file passages | Today a passage is a whole file (`SHORT:kind:activity[:file]`); `cite_open_activity` returns a cite only when exactly one passage matches, else `MISS`. 117-case conformance (9 doors × 13 courses; 22 pytest tests) green. | A second search overrides a unique cite; a miss is not the exact `MISS`. **CURRENT.** |
| **R1** | Keyword index wired to doors behind a **new B3 retrieval gold** | Index the 6,622 committed chunk rows (`domain_packs/aast-med/index/<shortname>.jsonl`) for **recall only**, behind a new gold `domain_packs/aast-med/gold/retrieval-b3.yaml`: ≥**40** cases, each a **title-door miss** that a **unique** passage window answers. Thresholds: **recall ≥ 0.90 (≥36/40)** and **precision = 1.00** (0 fabricated spans, 0 non-unique answers). The unique-passage rule is unchanged on every miss. **No existing golden moves**, `pulse_gauge --gate` shows **no meter rose**, `pack_contract --gate` exit 0. | Any existing golden/budget moves; a non-unique hit is emitted as a cite; keyword code lands in `engine/**` or as a phrase table. **TARGET.** |
| **R2** | Hybrid (keyword + overlap windows) | Combine a keyword hit with overlap windows across adjacent chunks; deterministic, documented tie-break. Threshold: **recall ≥ 0.95**, precision **1.00**, conformance still **117 cases (9 Ask-door cases × 13 courses; 22 pytest tests)**, golds unchanged. | Recall rises by loosening the unique-cite rule or by touching a golden. **TARGET (after R1).** |
| **R3** | Semantic default-OFF opt-in | Embeddings/vector retrieval behind an explicit opt-in, default-OFF, with a contract change + C6 green + L5 passable. | Any default-on vector store, second Postgres, pgvector, or external search service. **BLOCKED-BY-REAL-WORLD + CONTRACT.** |

**R1 gold definition (the NEW B3 retrieval gold).** File
`domain_packs/aast-med/gold/retrieval-b3.yaml`. Each case records:
`shortname`, `open_activity`, a `query` for which the R0 whole-file title door
returns `MISS`, the `expected_passage_ref`, and the **verbatim** `expected_span`
inside that passage. ≥40 cases across the 13 listed courses. A case is only
valid if the R0 door genuinely misses it and exactly **one** passage answers it.
This gold is **new evidence**; it does not edit or replace any existing gold.

### 1.3 L-C · Content coverage

| Rung | Name | Pass criterion (command + threshold) | Do not claim if |
|---|---|---|---|
| **C0** | Formats (office incl. `.ppsx` + pptx notes, pdf, txt/md/json/html) | The content-engine readers read PDF (text layer), OOXML office (`.pptx/.pptm/.ppsx` **including speaker notes**), legacy `.ppt`, `.docx`, `.txt/.md/.json/.csv/.html`, and image (OCR). Counts in §2.2 stay at or above the recorded baseline. | A format is claimed read while its bank rows are empty placeholders; a filename or intro is treated as a passage. **CURRENT.** |
| **C1** | Extra-as-course-content citable (`extra:<name>`) | `.txt/.md/.json` under `local_pulse/extra` are read through the same registry and written to `course-extra-13`, citable as `extra:<name>` (verbatim only); students stay 403 on manage. | An extra passage is emitted as a model sentence, or a student can reach manage. **CURRENT.** |
| **C2** | OCR | English OCR text is citable only when it is a **verbatim** substring of the stored file; **Arabic is non-citable** (`status=pending_signoff`, `bank/ocr-pending/<shortname>.jsonl`) until a recorded human sign-off of the exact quote. Threshold: 0 model sentences in any door; every vision label is `citable=False`. | Arabic OCR text is emitted as a cite before sign-off; a vision description becomes a passage. **English CURRENT; Arabic BLOCKED-BY-REAL-WORLD.** |
| **C3** | Drive | `acquire.drive_acquire` is reachable only from the staff Index job, **default-OFF** behind `PULSE_CONTENT_DRIVE_ENABLED` + credentials; per-source status recorded; never a Chat turn. | Drive runs on a Chat turn, or is enabled by default. **Built, default-OFF; enabling is BY-REAL-WORLD.** |

**Per-format counts already achieved (baseline; §2.2 must not fall below these)
and the gap.** Raw committed-bank rows, 13 listed courses:

| Format / source | Bank rows (total / with text) | Join state | Gap |
|---|---|---|---|
| PDF (text layer) | 318 / 317 | loaded | 1 scanned Arabic PDF (`MED5310`) |
| Scanned PDF | 1 | unread | OCR + human sign-off |
| PPTX | 166 / 166 | loaded | none |
| PPTM | 1 / 1 | loaded | none |
| PPSX | 2 / 2 | loaded | registry dispatch fixed |
| PPT (legacy OLE2) | 18 / 9 recovered | loaded | none (`legacy_ppt=0`) |
| DOCX | 57 / 57 | loaded | none |
| TXT/MD/JSON/CSV | 0 (extra-only) | extra path | extra bank `course-extra-13` |
| HTML | 0 | `external_web` unread 40 | arbitrary-web reader |
| Image | 0 | not counted | no reader / vision |
| Google Slides | 99 / 92 | 7 unread | not-public |
| Google Docs | 7 / 3 | 4 unread | not-public |
| Google Drive file | 28 / 27 | 1 unread | not-public |
| docs link (no id) | 35 / 0 | unread | unresolved link |
| YouTube | 78 / 61 | 17 unread | no caption track |
| External web | 0 | 40 unread | no reader |
| Media MP4 | 4 / 0 | 4 unread | no transcriber |
| Moodle page | 59 / 58 | loaded | 1 |
| Moodle label | 80 / 80 | loaded | none |

Join totals: active **934**, loaded **860**, unread **74** (`external_web` 40,
`remote_youtube` 17, `remote_google` 12, `media` 4, `scanned_pdf` 1). Only the
1 scanned PDF is document-recoverable; the rest are remote bodies or media.

### 1.4 L-G · Knowledge graph (additive)

| Rung | Name | Pass criterion (command + threshold) | Do not claim if |
|---|---|---|---|
| **G0** | Built + provenance | `domain_packs/aast-med/graph/<shortname>.jsonl`, **4,925 nodes / 23,364 edges**; every edge carries a **real `passage_ref`**; an edge without one is dropped. No Neo4j, no second Postgres, no `knowledge_graph` table. | Any edge has no passage id; a store is created. **CURRENT.** |
| **G1** | Queried by staff tools | A read-only staff tool answers "which lectures teach X" over the graph, each result returning its passage id; not on a Chat turn; no golden moves. | The graph is queried on a Chat turn, or a graph answer is emitted without a passage id. **TARGET (BY-CODE).** |
| **G2** | Teacher-approved ILO / assessment edges (B6 / C7) | Lecture→ILO→assessment edges are authored, **human/teacher-approved**, passage-grounded; C7 only after C6 green and L5 passable, each edge to a real session. B6/C7 stay `not_passable` until approved. | A graph edge is model-generated; B6/C7 is marked green from indexing alone. **not_passable — BY-REAL-WORLD.** |

**The graph is NOT required for teaching.** Removing it leaves every door
answer and every golden unchanged (CONTENT-ENGINE-SPEC §S6; READINESS-SPEC §6
"indexing is not a graph").

### 1.5 L-P · Production readiness (references existing ladders)

This ladder references — and does not rewrite — the frozen K10/K11/B5/B6/C7
ladders in `READINESS-SPEC.md`. It splits each into **implementable locally**
vs **BY-REAL-WORLD**.

| Rung (frozen source) | Local-implementable | BY-REAL-WORLD evidence needed |
|---|---|---|
| **K10** staff (`READINESS-SPEC` §2) | Evaluator, `K10-RUNBOOK.md`, plugin notice lever, HMAC logic, admin desk | Production Moodle **4.1** install + HMAC secret + a named staff cohort + the R15+R18 notice sent to exactly that cohort |
| **K11** students (`READINESS-SPEC` §3) | Gate machinery (`ai/moodle_readiness/`, default-deny), consent/audit tables, R11 draft cases, L5 curriculum counts | Real (non-pilot) student cohort + student notice + consent/RBAC/audit at production scale + **R12 with two real students** |
| **B5** long memory (`READINESS-SPEC` §5) | Typed short memory (B4, green) | Non-empty cohort + consent + audit + R12; per-student store behind the gate. **No table.** |
| **B6 / C7** graph (`READINESS-SPEC` §6) | Passage-id provenance checks | Authored, human-approved passage-grounded edges; C7 needs real session edges |
| **Medicine L5** (`L5-PASSABILITY.md`) | 100-question gold per shortname (draft authored, 1300 items), R11 4/4 | Human review + freeze of the curriculum gold (sign-off, not machinery); production cohort for the R12 freezes |

`B4` is green **as a field** (flippable input). No production medicine rung is
green. **BY-CODE** = only code/authoring remains; **BY-REAL-WORLD** = a live
artifact, human action, or policy decision is required.

### 1.6 The B3 grounding/faithfulness pass (single definition)

Used by **L-T T1/T2** and **L-R R1**. It is **one** contract, defined once:
every curriculum-fact sentence a door/draft emits must contain a **verbatim
substring** of the **single** passage it cites; the passage id must resolve in
the bank for the open activity; a span-less sentence is dropped; no phrase
table and no `re.compile` in `engine/**`; the check is offline and
deterministic; an LLM may flag but never certify. Gold: `teach-b3.yaml` (T1/T2)
and `retrieval-b3.yaml` (R1). Threshold: **100% verbatim (draft), precision 1.00
(retrieval), 0 fabricated spans.**

---

## 2. Benchmarks (measurable, with commands)

All commands run from `backend/` unless noted. Every number below is a
**threshold that must not regress**.

### 2.1 Offline conformance — 117 cases (9 Ask-door cases × 13 courses; 22 pytest tests)

```
DJANGO_SETTINGS_MODULE=config.settings python -m pytest \
  ai/tests/test_moodle_conformance.py -o addopts= -p no:_testbrand -q
```

Threshold: **green**, and gold `domain_packs/aast-med/gold/conformance-13.yaml`
resolves **117 cases (9 Ask-door cases × 13 courses)** across **13/13** listed courses, realized by **22** pytest tests in the file (all passing; not re-run here).
A change to any door rule updates the gold in the same change.

### 2.2 Per-course citable counts

```
python -c "from ai.moodle_extraction_gap import report; \
[print(g.shortname, g.active, g.loaded, g.unread) for g in report()]"
```

Threshold: **no course's `loaded` below its recorded baseline**, and the join
totals stay active **934** / loaded **860** / unread **74**. Baseline per course
(citable passages / coverage): MED213 35 · MED520 64 · MED5310 7 (1 scanned) ·
NMD1000 98 · NMD1103 26 · NMD1301 40 · NMD1402 22 · NMD2101 244 · NMD2303 17 ·
NMD2403 21 · NMD3101 144 · NMD3304 17 · NMD4201 138. A one-off cite of section
titles is not a benchmark pass.

### 2.3 Gates

```
python -m ai.eval.pack_contract --gate     # exit 0; aast-med v2 violations=0
python -m ai.eval.pulse_gauge --gate       # pass; no meter rose, no level regressed
```

Thresholds: `pack_contract` exit **0** with **0** violations for
`aast-med v2 moodle-education`. `pulse_gauge` **pass** — `harness_budget` must
not rise on any meter (`staged_exits`, `re_compile`, `arabic_regex`,
`runner_lines`, `tool_choice_uses`, `routing_phrase_sets`,
`domain_terms_in_core`, `brand_literals_in_core`). Current baseline:
`domain_terms_in_core=0`, `brand_literals_in_core=0`.

### 2.4 Moodle pytest selection

```
DJANGO_SETTINGS_MODULE=config.settings python -m pytest ai/tests/ -k moodle \
  -o addopts= -p no:_testbrand -q
```

Threshold: **green**, count not below the recorded baseline (**277 passed**,
3752 deselected at 3 Oct 2026). Run on an isolated `TEST_DB_NAME` if a
concurrent worker holds the test DB. New tests are **added**; no existing
assertion is weakened.

### 2.5 Canvas typecheck

```
tsc -p canvases/tsconfig.json
```

Threshold: **0 diagnostics** over all `*.canvas.tsx` (TypeScript 5.9.2).

### 2.6 Regression definition

**A regression is any of the following moving in the wrong direction on any of
the above:**

1. any file under `domain_packs/aast-med/gold/**` changing (content or
   assertion strength) — **any existing golden moving is a regression**;
2. any `harness_budget` meter rising (`pulse_gauge --gate` fails);
3. any `pack_contract --gate` violation added;
4. any per-course `loaded` count falling below baseline;
5. conformance below **117 cases (9 Ask-door cases × 13 courses; 22 pytest tests)**;
6. the moodle pytest selection falling below baseline;
7. canvas typecheck above **0** diagnostics.

---

## 3. Workstream plan (for Phase 2)

Phase 2 is gated by §5 (freeze). Each workstream lists its **ladder target**,
**files likely touched**, the **benchmark that proves it**, and the **audit
method**. Nothing here is authorized in Phase 1.

### WS-1 · Retrieval wiring (L-R R1)

- **Ladder target:** R1 (then R2).
- **Files likely touched:** `backend/ai/moodle_bank.py`,
  `backend/ai/moodle_page.py`, `backend/ai/moodle_host.py`; new
  `domain_packs/aast-med/gold/retrieval-b3.yaml`; new
  `backend/ai/tests/test_moodle_retrieval.py`. **Not** `engine/**`.
- **Benchmark that proves it:** new retrieval gold ≥40 cases, recall **≥0.90**,
  precision **1.00**; conformance **117 cases (9 Ask-door cases × 13 courses; 22 pytest tests)**; **no golden moved**;
  `pulse_gauge --gate` no meter rose; `pack_contract --gate` exit 0.
- **Audit method:** read the new gold diff; confirm every case is an R0
  title-door miss with a **unique** answer; run §2.1–§2.3 and diff every
  existing golden by hash before/after.
- **Marker:** **BY-CODE** (the gold is authored first, then the wiring).

### WS-2 · Structured teach path (L-T T1, then T2)

- **Ladder target:** T1 (grounded multi-passage lesson draft) → T2 (structured
  lesson, staff-approved).
- **Files likely touched:** `backend/ai/moodle_page.py`,
  `backend/ai/moodle_host.py`, a new `backend/ai/moodle_teach.py` (draft
  builder only); pack vocabulary `domain_packs/aast-med/teach_asks.yaml`; new
  tests `backend/ai/tests/test_moodle_teach.py`; R11 cases
  `gold/l5-r11.draft.yaml` (already `status: draft`). **Not** `engine/**`.
  Chat proposes; the Extra tab applies.
- **Benchmark that proves it:** B3 grounding pass (§1.6) with
  `teach-b3.yaml` **100% verbatim, 0 fabricated spans**; R11 **4/4** (draft
  labelled, no Moodle write); conformance **117 cases (9 Ask-door cases × 13 courses; 22 pytest tests)**; no golden moved.
- **Audit method:** read the draft builder for any path that can print a
  non-substring sentence; confirm it is not imported by a Chat turn; run §2.1,
  §2.4, §2.3.
- **Marker:** **BY-CODE.**

### WS-3 · B3 grounding / faithfulness gold (L-T T1+ · L-R R1)

- **Ladder target:** the shared B3 pass that unblocks T1/T2 and R1.
- **Files likely touched:** new `domain_packs/aast-med/gold/teach-b3.yaml`; new
  `domain_packs/aast-med/gold/retrieval-b3.yaml`; new
  `backend/ai/tests/test_moodle_b3.py`. **Not** `engine/**` (no judge phrase
  table, no `re.compile` on a turn).
- **Benchmark that proves it:** teach gold ≥50 assertions, **100% verbatim**;
  retrieval gold precision **1.00**; both run offline with no network.
- **Audit method:** sample assertions and verify each verbatim span is an exact
  substring of the named passage in the committed bank; confirm the optional
  LLM flag path is not on any Chat turn.
- **Marker:** **BY-CODE.**

### WS-4 · Content coverage (L-C C2 / C3)

- **Ladder target:** C2 (OCR) and C3 (Drive, default-OFF).
- **Files likely touched:** `backend/ai/content_engine/**`,
  `backend/ai/moodle_content_job.py`, `plugins/local_pulse/**` (extra path);
  `domain_packs/aast-med/bank/ocr-pending/<shortname>.jsonl`. **No new table.**
- **Benchmark that proves it:** English OCR rows are verbatim and become
  `loaded`; the Arabic `MED5310` page is emitted only after a recorded exact
  sign-off; Drive stays default-OFF; per-course `loaded` never falls;
  `pack_contract --gate` exit 0.
- **Audit method:** verify each recovered row's body is a verbatim substring of
  the stored file; check no `engine/**` change; run §2.2–§2.3.
- **Marker:** OCR machinery **BY-CODE**; **Arabic OCR sign-off BY-REAL-WORLD**;
  **Drive enablement BY-REAL-WORLD + decision.**

### WS-5 · Production evidence (L-P)

- **Ladder target:** K10 / K11 / B5 / B6 / C7 (production), medicine L5 freeze.
- **Files likely touched:** `backend/ai/moodle_readiness/**`,
  `docs/pulse/aast-med/K10-RUNBOOK.md`, plugin config (site:config only).
- **Benchmark that proves it:** `evaluate(repo_inputs(production_installed=True,
  hmac_configured=True, staff_cohorts_non_empty=True,
  listed_courses_all_have_c6_gold=True, staff_notice_published=True)).by_id[
  "K10"].passed is True`; R12 with two **real** students; `student_cohorts`
  non-empty for a **recorded** production decision only.
- **Audit method:** the runbook evidence checklist; the evaluator is the reader,
  never hardcoded; the two-student transcript exists on disk.
- **Marker:** **BY-REAL-WORLD.** Exact evidence needed: production Moodle 4.1
  install + HMAC + named staff cohort + the R15+R18 notice (K10); a production
  student cohort + student notice + consent/RBAC/audit + two real student
  accounts on one lecture (K11/B5); authored, teacher-approved,
  passage-grounded edges (B6/C7); a human freeze/sign-off of the L5 curriculum
  gold and the Arabic OCR quote.

### WS-6 · Canvas, docs, gates (cross-cutting)

- **Ladder target:** all ladders (evidence + freeze hygiene).
- **Files likely touched:** `docs/pulse/aast-med/**`, the aast-med canvas,
  `backend/ai/eval/**` (read-only gate entrypoints).
- **Benchmark that proves it:** `pack_contract --gate` exit 0;
  `pulse_gauge --gate` pass; canvas typecheck **0**; conformance **117 cases (9 Ask-door cases × 13 courses; 22 pytest tests)**.
- **Audit method:** every canvas claim cites an on-disk artifact; no rung colour
  changes without a scored run; diff golds and meters before/after.
- **Marker:** **BY-CODE.**

---

## 4. Anti-shallow rules

"Thin / shallow" means a claim that looks like capability but carries no
scored evidence. It is **forbidden**:

1. **A door that cites without a verbatim span.** Any emitted fact must carry
   an exact substring of the cited passage; a sentence without one is a
   shallow cite.
2. **An index built but unused.** Shipping the keyword index while no door
   consumes it is not R1. R1 requires a scored retrieval gold, not rows on disk.
3. **A "teach" path that fabricates facts.** A draft that invents an ILO,
   example, or assessment fact is not teaching; it is the failure T1 closes.
4. **A green rung with no scored run.** No rung is marked from a demo, a stub,
   a single PASS, or a `--noreload` process. Only §2 evidence flips a rung.
5. **A gold loosened to pass.** Editing a threshold, a case, or an assertion
   strength to go green is a regression, not progress (§2.6).
6. **A canvas claim with no on-disk evidence.** Every rung row and count must
   trace to a file in the repo.

A workstream that cannot produce its §3 benchmark does not complete; it is
reported incomplete, not marked done.

---

## 5. Freeze

- **Status: FROZEN.**
- **Version:** 1.0.
- **Date:** 3 Oct 2026.
- **Gate:** **Phase 2 implementation may not begin until this file exists and
  is frozen.** No code, plugin change, `domain_packs` value change, golden
  change, commit, or deploy is authorized by this spec. `manage.sh` is never
  started or killed by an agent. `student_cohorts` stays empty; no rung is
  marked green by this file.
