# Content Distillation + Hybrid Index — engine spec (aast-med)

Owner: Pulse-for-medicine content-pipeline (subagent), 3 Oct 2026.
Scope: the extraction/distillation capability of the aast-med passage bank, and
the spec for a future Content Distillation + Hybrid Index engine.
Status: **spec + a read-only capability reporter only.** No OCR, no network
fetch, no vector store, no graph, no table, no engine change, no golden
loosened, no rung marked. Local/dev counts are labelled. Production rungs stay
unmarked.

Frozen contracts this spec obeys, without exception:

- Pulse 2.1 contract / ADR-0049 / ADR-0050 — `backend/ai/engine/**` stays
  domain-free and brand-free; no new `StagedExit`, no routing `re.compile`, no
  module-level phrase table; `harness_budget` must not rise.
- ADR-0046 / RULE_35 — a Chat turn never host-mutates and never fetches.
- ADR-0047 / RULE_36 — measure, don't claim; a stub or one PASS never upgrades
  a miss.
- READINESS-SPEC §6 — **indexing is not a graph**; B6/C7 stay `not_passable`;
  no Neo4j, no second Postgres, no pgvector, no `student_cohorts`.

---

## 0. The honest answer (do we have a distillation engine?)

**No.** There is no general content-distillation engine. There are **7 narrow
committed reader functions covering 5 source families**, each hard-wired to one
script, plus a plugin-side tutor upload path for `.txt/.md/.json`:

| # | Reader function (exact) | Family | Yields |
|---|---|---|---|
| 1 | `scripts/ingest_aast_med_external.py::_pdf_text` (L96) | PDF text layer | real text |
| 2 | `scripts/ingest_aast_med_external.py::_office_text` (L83) | OOXML office (`pptx`/`pptm`/`ppsx`/`docx`) | real slide/body text |
| 3 | `scripts/ingest_aast_med_external.py::_legacy_ppt_text` (L229) | legacy `.ppt` (OLE2/CFB) | real slide text + real speaker notes |
| 4 | `scripts/ingest_aast_med_external.py::google_presentation` (L322) | Google Slides | real text (public export) |
| 5 | `scripts/ingest_aast_med_external.py::google_document` (L332) | Google Docs | real text (public export) |
| 6 | `scripts/ingest_aast_med_external.py::google_file` (L335) | Google Drive file | real text when office/PDF |
| 7 | `scripts/ingest_aast_med_external.py::youtube_caption` (L364) | YouTube captions | real caption text |

The dispatcher that routes a stored file to readers 1/2/3 is
`scripts/ingest_aast_med_local_files.py::_extract` (L117). The plugin `.txt/.md`
`.json` path is **not a Carbon reader**: the Moodle plugin supplies already
split `passages` to `ai.moodle_bank.write_extra_index` (L160) through
`ai.moodle_host_api.MoodleIndexView` (L144).

What is **absent**: a MIME/extension registry/dispatcher for arbitrary input;
any OCR; any image/vision reader; a general external-web reader; a folder
reader; a media/audio transcriber; a hybrid index (keyword or semantic); any
knowledge graph or store. Unknown/unreadable input is not routed to an explicit
`unreadable` status by a dispatcher — it is simply left as a placeholder row
with a printed reason in the ingest script, and reported as unread.

---

## 1. Capability audit — format → reader → citable → count

Two views, both real and both counted (not guessed):

- **Bank-row view** — raw rows in `domain_packs/aast-med/bank/**` (13 listed
  courses). "text" = the row carries a non-empty `text` field.
- **Join / coverage view** — `ai.moodle_extraction_gap.report()` over
  `ai.moodle_bank.course_roster` (the committed-bank join, deduped by
  section+family+name). Active **934**, loaded **860**, unread **74**.

`citable` means: today a Chat turn may emit a **verbatim substring** of this
text as a passage cite (`ai.moodle_bank.cite_open_activity`, unique-passage
rule). A label that is never a passage is non-citable by rule.

### 1.1 Matrix

| Format / source | Reader (exact code path) | Real / label / none | Citable? | Bank rows (total / with text) | Join state |
|---|---|---|---|---|---|
| **PDF (text layer)** | `_pdf_text` (pypdf) via `_extract` | real | yes | **318 / 317** | loaded as `SHORT:file:cmid:name` |
| **Scanned PDF (no layer)** | `_pdf_text` returns `""` → `empty:no_text` | none | no | 1 of the 318 (`MED5310` Arabic قانون) | **unread**, `scanned_pdf=1`; needs OCR |
| **PPTX** | `_office_text` (`ppt/slides/slideN.xml`) via `_extract` | real | yes | **166 / 166** | loaded |
| **PPTM** | `_office_text` via `_extract` | real | yes | **1 / 1** | loaded |
| **PPSX** | `_office_text` *can* read it, but `_extract`'s `_OFFICE={.pptx,.pptm,.docx}` (L43) excludes `.ppsx` | real (today) | yes | **2 / 2** | loaded — **registry gap** (re-ingest would reject `.ppsx`) |
| **PPT (legacy OLE2)** | `_legacy_ppt_text` via `_extract` | real | yes | **18 / 9** (9 empty placeholder + 9 appended filled) | loaded (append-only; `legacy_ppt=0` unread) |
| **DOCX** | `_office_text` (`word/document.xml`) via `_extract` | real | yes | **57 / 57** | loaded |
| **Speaker notes (OOXML)** | `_office_text` reads **slides only** | none | no | — (embedded in pptx) | not extracted; `.ppt` notes *are* extracted |
| **TXT / MD / JSON / CSV** | no Carbon reader; Extra path only (`write_extra_index` ← plugin) | real **if indexed** | yes if indexed | **0** (`course-extra-13` absent) | extra-only, never a course file |
| **HTML (arbitrary web)** | none (`_export` handles `text/plain`/zip only) | none | no | 0 | `external_web` unread 40 |
| **PNG / JPG / JPEG / image** | none anywhere; office/PDF readers drop embedded images | none | no | **0** bank rows | not counted; no reader, no vision |
| **Google Slides** | `google_presentation` (public `/export/txt`, fallback `/export/pptx`) | real when public | yes | **99 / 92** | 7 unread (`remote_google`) |
| **Google Docs** | `google_document` (public `/export?format=txt`) | real when public | yes | **7 / 3** | 4 unread |
| **Google Drive file** | `google_file` (`uc?export=download`, office/PDF sniff) | real when public | yes | **28 / 27** | 1 unread |
| **docs.google.com link, no id** | `unresolved_docs_link` → `unavailable/unresolved_link` | none | no | **35 / 0** | part of `external_web` unread |
| **YouTube** | `youtube_caption` (ANDROID `youtubei/v1/player` timedtext) | real caption | yes | **78 / 61** (16 empty, 1 unavailable) | **17 unread** (`remote_youtube`) |
| **External web URL** | none | none | no | 0 body rows | **40 unread** = 18 docs.google.com links + 22 arbitrary sites |
| **Folders** | none (`roster_family("folder")→other`; not ingestible) | none | no | 0 counted | invisible to coverage |
| **Media MP4** | `_extract` → `unavailable:legacy_video` | none | no | **4 / 0** | **4 unread** (`media`) |
| **Moodle page / label / book** | `load_c3` (stored signed-snapshot text) | real | yes | page **59/58**, label **80/80**, book 0 | loaded |
| **Moodle section title** | snapshot section door (L1), not a bank passage | real (structure) | yes (snapshot) | **9 / 9** rows | metadata, not a `load_c3` passage |
| **Moodle url (intro)** | meat `kind:url` text is **not read by any loader** (`load_c4_files` skips url) | dead text | no | **269 / 269** | ignored; join uses `course-ext-13` |

### 1.2 Join-view unread decomposition (`ai.moodle_extraction_gap.report()`)

| Technique bucket | Unread | What it is |
|---|---|---|
| `external_web` | **40** | 18 docs.google.com links with no source id + 22 arbitrary websites (SharePoint/MedHub/…) |
| `remote_youtube` | **17** | 16 videos with no caption track + 1 player error |
| `remote_google` | **12** | public export unavailable/not-public (7 Slides + 4 Docs + 1 Drive) |
| `media` | **4** | `.mp4` files, no local reader |
| `scanned_pdf` | **1** | `MED5310` Arabic PDF, no text layer → OCR |
| **Total unread** | **74** | active **934** · loaded **860** |

Offline bank totals (raw rows, all 13 courses): `.pdf` 318 · `.pptx` 166 ·
`.docx` 57 · `.ppt` 18 · `.mp4` 4 · `.ppsx` 2 · `.pptm` 1 · page 59 · label 80 ·
section 9 · url 269 (dead). Ext: google-presentation 99 · youtube 78 ·
google-file 28 · google-document 7 · link 35. Keys (join manifest):
file 557 · url 269.

### 1.3 One-sentence headline

> **We do NOT have a general distillation engine; we have 7 narrow committed
> readers over 5 source families, no OCR, no image/vision, no generic web/
> folder/media reader, no hybrid index, and no graph — and the `74` unread
> committed-bank rows are mostly remote links and media, not a document-reader
> gap (only the 1 scanned Arabic PDF is document-recoverable, by OCR).**

No rung is marked by this audit.

---

## 2. Stage spec — PRINCIPLE · RULE · BENCHMARK · tag

Each stage carries a **BLOCKED-BY-CODE** (agent-doable, no live data) or
**BLOCKED-BY-REAL-WORLD** (needs a live artifact, human sign-off, API key, or a
policy decision) tag.

### S1. FORMAT REGISTRY (one dispatcher)

- **PRINCIPLE.** A stored object is read only through a declared reader, and an
  unknown object is an explicit status — never a silent empty passage (P2/T1).
- **RULE.** One registry maps MIME/extension → reader id. Every reader returns
  typed `TextUnit`s carrying **source coordinates** (page · slide · sheet ·
  timecode) and a `citable` flag. A format with no reader returns
  `status="unreadable"` with a cause token (e.g. `no_reader`, `scanned`,
  `encrypted`, `not_public`, `legacy_video`). No reader mutates the bank on a
  Chat turn; the registry is data, not routing in `engine/**`.
- **BENCHMARK.** Every raw bank row lands in exactly one declared format id; the
  sum of per-format totals equals the raw row count; `other`/unclassified stays
  `0`; no `engine/**` change; `pack_contract --gate` exit 0.
- **TAG.** **BLOCKED-BY-CODE.** (Today's classifier is
  `ai.moodle_extraction_gap.technique_for`, L81; this pass adds the read-only
  bank-row registry `ai/moodle_content_registry.py`.)

### S2. TEXTUAL READERS

- **PRINCIPLE.** Real text exists only when the file yields it; a passage is
  never a filename or an intro.
- **RULE.** Readers: pdf, docx, pptx, ppt, txt/md/json/csv, html.
  **Speaker notes are first-class `TextUnit`s** (`ppt/notesSlides/*.xml` for
  OOXML; already done for legacy `.ppt`). Follow the existing
  **sentence-boundary preservation** rule: dedupe removes whole sentences only
  (`_SENTENCE` split in `scripts/ingest_aast_med_local_files.py`), so a cite
  stays verbatim. The `.ppsx` dispatcher gap (S1) is a reader-routing fix, not
  a new reader.
- **BENCHMARK.** `test_moodle_k6_files.py` and `test_moodle_join_coverage.py`
  stay green; a recovered file counts as loaded only when the recovered body is
  a **verbatim substring** of the stored file; notes add `TextUnit`s without
  changing any existing passage's cite owner; `pack_contract --gate` exit 0.
- **TAG.** PPTX speaker notes + `.ppsx` dispatch + HTML/CSV: **BLOCKED-BY-CODE.**

### S3. IMAGE / OCR / VISION

- **PRINCIPLE.** A claim is a citation; model prose is never a door sentence
  (P2/T2).
- **RULE.** OCR text from a scanned page/image may become a `TextUnit` **only**
  when it is verbatim and human-signed-off; a vision-LLM description is stored
  **only as a non-citable retrieval label** (`citable=False`), never a passage a
  door may emit. An image that yields neither is `status="unreadable"`.
- **BENCHMARK.** A recovered scanned page counts as loaded only when its text is
  a verbatim substring of the stored file **and** a human signs the exact quote;
  every vision label is `citable=False`; `0` model sentences in any door; a
  written retrieval gold passes with `0` fabricated spans.
- **TAG.** OCR **machinery** is BLOCKED-BY-CODE; **OCR of the Arabic
  presentation/legal PDF (`MED5310`) is BLOCKED-BY-REAL-WORLD sign-off** (a
  verbatim cite must be exact); **vision text is BLOCKED-BY-REAL-WORLD.** No
  image reader exists today.

### S4. REMOTE ACQUISITION (YouTube · Google Drive · external web)

- **PRINCIPLE.** Grounding is a stored, citable passage; acquisition is a
  staff action, not a chat side effect (ADR-0046).
- **RULE.** Acquisition runs **only** inside a staff-triggered **Index job**
  (`ai.moodle_host_api.MoodleIndexView` + `scripts/ingest_aast_med_external.py`),
  **never** a Chat turn. Per-source **allow-list** (shortnames + link families),
  explicit **timeout**, and a typed **`unavailable`** status with a cause
  (`not_public`, `network`, `http_*`, `no_caption_track`). A caption or export
  body is stored only when the host returned text; a failure is a status row,
  never a summary of the intro. External web needs a reader before it can be
  acquired at all.
- **BENCHMARK.** In a Chat turn, `0` network calls (the module is not imported by
  a turn path — locked by test); every remote row carries `status` +
  `cause`; an unavailable row is never counted loaded; the allow-list and
  timeout are asserted.
- **TAG.** Index-job plumbing + allow-list: **BLOCKED-BY-CODE.** API keys,
  public-link access, and any live-network policy: **BLOCKED-BY-REAL-WORLD.**
  (Google export and YouTube captions already work for public items; the 12
  `remote_google` + 17 `remote_youtube` unread rows are mostly not-public / no
  caption.)

### S5. HYBRID CHUNKING + INDEX (contract-constrained)

- **PRINCIPLE.** Retrieval proposes, a unique verbatim passage disposes; a
  second search must never override a unique cite (P2/B3).
- **RULE.**
  - **Chunk model (structure-aware):** course → section → activity →
    slide/page/sheet/timecode. A chunk id is **stable** and source-coordinate
    bearing. Today a passage is a **whole file** (`SHORT:kind:activity[:file]`);
    splitting into per-slide/per-page `TextUnit`s requires S1/S2 coordinates.
  - **Hybrid, allowed now:** **exact/whole-word keyword** matching over the
    passage bank, deterministic, **no vector store, no embeddings, no second
    Postgres**. Keyword scoring lives in the **pack/door**, never `engine/**`,
    with **no** `re.compile` and no phrase table (Pulse 2.1 budget).
  - **Hybrid, NOT allowed now:** pgvector / a vector store / semantic
    embeddings / any external search service. **Semantic retrieval is gated
    behind a contract change + C6 green + L5 passable.** The unique-passage rule
    stands on every miss (still the exact `MISS`).
- **BENCHMARK.** Recall on a **written retrieval gold** (title-door misses that a
  **unique** passage answers; backlog B3 / `gold` authored) with **0 fabricated
  spans**; a passage still has exactly one owner
  (`test_moodle_k6_coverage.py`); `pulse_gauge --gate` flat (no meter rose).
- **TAG.** Keyword/BM25 in the pack + the retrieval gold: **BLOCKED-BY-CODE**
  (gold must be authored first). Semantic/vector: **BLOCKED-BY-REAL-WORLD +
  CONTRACT** (not authorized now).

### S6. KNOWLEDGE GRAPH (contents → sections → lecture titles → activities → passages)

- **PRINCIPLE.** Indexing is not a graph (READINESS-SPEC §6); an edge is a
  claim, so it needs a source (P2).
- **RULE.** Node/edge model:
  `course —contains→ section —contains→ lecture(activity) —hasText→ passage`;
  `lecture —teaches→ ILO`; `ILO —assessedBy→ assessment`. **Every edge carries a
  passage id as provenance; an edge with no passage id is dropped.** Edges are
  **teacher-approved** (B6), authored and reviewed — never model-generated.
  **No Neo4j, no second Postgres, no `knowledge_graph` table**; the graph is a
  versioned pack artifact (JSONL/YAML), default-OFF, and is **not required for
  teaching**.
- **BENCHMARK.** Every edge returns its passage id; the graph is queryable;
  B6.3; **C7 only after C6 green and L5 passable**, then each edge traces to a
  real session. C7 is not a gate.
- **TAG.** **BLOCKED-BY-REAL-WORLD** (authored, human-approved edges; C6 + L5).
  No graph code is authorized before C6/L5; no store is created now.

---

## 3. Ordered build plan (code-completable first)

1. **S1 registry + capability reporter** — *done, default-OFF, this pass*
   (`ai/moodle_content_registry.py`, locked by
   `ai/tests/test_moodle_content_registry.py`). Read-only; no OCR/network/store.
2. **S1/S2 reader coordinates** — emit typed `TextUnit`s with page/slide/sheet/
   timecode; keep sentence boundaries. *(BY-CODE)*
3. **S2 gaps** — PPTX speaker notes; dispatch `.ppsx`/`.csv`/`.html`; keep the
   verbatim-substring recovery rule. *(BY-CODE)*
4. **S5 keyword retrieval + the written retrieval gold** (B3) — pack/door only,
   unique-cite preserved, no vectors, no `engine` phrase table. *(BY-CODE, needs
   authored gold)*
5. **S4 Index-job hardening** — per-source allow-list, timeout, typed
   `unavailable`, never a Chat call. *(BY-CODE; live network = BY-REAL-WORLD)*
6. **S3 OCR machinery** — a scanned-page reader behind `citable=False` until
   sign-off. *(BY-CODE)*
7. **S3 OCR sign-off (Arabic `MED5310`)** and **vision labels**.
   *(BY-REAL-WORLD)*
8. **S6/C7 KG edges** — authored, teacher-approved, passage-grounded; deferred
   until C6 green + L5 passable. *(BY-REAL-WORLD)*

## 4. What cannot be built now, and why

- **Vector store / semantic index** — no pgvector, no second Postgres, no
  embeddings (Pulse 2.1 + READINESS-SPEC §6); needs a contract change + C6/L5.
- **Knowledge graph / Neo4j / `knowledge_graph` table** — indexing is not a
  graph; edges need human approval and a passage (B6/C7).
- **Arabic scanned-PDF OCR as citable text** — a verbatim cite must be exact;
  needs human sign-off (`MED5310`).
- **Vision text as a citable passage** — a model sentence is never a cite; only
  a non-citable label, and only with sign-off.
- **External-web / folder / media (mp4) bodies** — no reader exists; media needs
  a transcriber (API + policy) and web needs a reader + allow-list.
- **Per-student long memory (`B5`)** — no table; needs cohort + consent + audit
  + R12. `student_cohorts` stays empty.
- **Live acquisition on a Chat turn** — ADR-0046 forbids it; acquisition is a
  staff Index job only.

## 5. Confirmations

- **No rung marked green.** K10/K11 (production), B5, B6, C7 stay
  `not_pass`/`not_passable`; K4/K9 red; the LOCAL (dev) K11 pilot label
  unchanged.
- **No engine change.** Nothing added or edited under `backend/ai/engine/**`.
- **No golden loosened.** No file under `domain_packs/aast-med/gold/` edited.
- **No new store; no OCR / network / vector / graph added.**
  `student_cohorts` stays empty. No `people:view`.
- **`moodle_page.py` / `moodle_host.py` untouched.**
- **Local/dev counts labelled.** All numbers are the committed-bank join view.

---

## AMENDMENT (3 Oct 2026) — OCR, hybrid index, and knowledge graph authorized and delivered

**This is an amendment, not a rewrite.** The frozen decision above is kept as
the record of what this spec originally authorized (a **read-only capability
reporter only** — no OCR, no hybrid index, no graph). Its non-goal line is now
**SUPERSEDED** for the aast-med pack: the user subsequently authorized OCR, a
hybrid keyword index, and a knowledge graph, and all three are delivered via
`backend/ai/content_engine/`.

Delivered state (on-disk, committed):

- **OCR** — `pytesseract` `eng+ara` (Tesseract 5.5.0), reader in
  `backend/ai/content_engine/`; invoked by the staff Index job only.
- **Hybrid keyword index** — **6,622 chunk rows** at
  `domain_packs/aast-med/index/` (13 courses).
- **Knowledge graph** — **4,925 nodes / 23,364 edges** at
  `domain_packs/aast-med/graph/` (versioned JSONL, no store).

What this amendment does **not** change:

- The graph stays **additive and NOT a teaching dependency**; B6 / C7 stay
  `not_pass`.
- The keyword index is deliberately **not wired to the Ask / Chat doors**.
- No `engine/**` change; no `gold/**` loosened; K10 / K11 (production), B5, B6,
  C7 stay unmarked; `student_cohorts` stays empty; no `people:view`.
- The §4 “what cannot be built now” list is otherwise still the honest roadmap.
