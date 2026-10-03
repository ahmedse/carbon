# R2-GOLD integrity remediation note (aast-med)

Date: 2026-10-03 · Scope: `domain_packs/aast-med/gold/retrieval-r2.yaml` and
`backend/ai/tests/test_moodle_retrieval_r2.py` only.

## What was found (truth before)

- `domain_packs/aast-med/gold/retrieval-r2.yaml` was a **12-case / 2-course**
  file (MED213:7, MED520:5), 5,310 bytes, mtime **2026-10-03 15:13:25**.
- `backend/ai/tests/test_moodle_retrieval_r2.py` was the matching reduced
  revision, mtime **2026-10-03 15:13:35**.
- The 12-case version passed at R2 (15 collected, 15 passed), and R1
  (`retrieval-b3.yaml`, 65 cases) stayed 65/65. So nothing was *broken* by the
  reduction — the **72/72** claim documented for the audited version simply was
  no longer backed by the file on disk.

Both gold YAMLs are **untracked in git** (`git status` shows `??`), so no VCS
object held the 72-case revision. `git log`/`stash`/`reflog` had nothing.

## Recovery source (found, not hand-written)

- `/tmp/scan_r2.log` (mtime 15:01:00) is the audited derivation log:
  `MED213:6 · MED520:6 · MED5310:0 · NMD1000..NMD4201:6 each · TOTAL 72 across 12 courses`.
- `/tmp/scan_r2.py` (mtime 15:00:42) is the deterministic generator.
- Re-running it against today's committed `domain_packs/aast-med/index/<short>.jsonl`
  and bank reproduced **exactly** the same per-course counts (72 across 12
  courses). It calls `cite_topic_index_windowed`, which is the same function
  `cite_topic_index(..., allow_window=True)` delegates to, so the re-derivation
  matches the production R2 path.

The reduced 12-case file was **not** a truncation of the generated file (its
per-course split MED213:7 / MED520:5 differs from the generated MED213:6 /
MED520:6), i.e. it was a separate, hand-curated subset.

## What was restored

- `retrieval-r2.yaml` rewritten to the **72-case / 12-course** gold, re-verified
  programmatically against the committed bank: **ok/total = 72/72** where a case
  is ok iff the `expected_span` is an exact substring of the stored text of
  `expected_passage_ref`, R0 is a genuine `_topic_rows` miss, R1
  (`allow_window=False`) is `None`, and R2 (`allow_window=True`) returns the
  unique `(passage_id, span)`.
- Courses: MED213, MED520, NMD1000, NMD1103, NMD1301, NMD1402, NMD2101,
  NMD2303, NMD2403, NMD3101, NMD3304, NMD4201 (12 of 13). **MED5310 genuinely
  yields 0 qualifying cases** and is not padded.
- `test_moodle_retrieval_r2.py` is unchanged in logic (it parametrizes over
  `_CASES` dynamically) except a stale "40/40" docstring corrected to "65/65".

## Verification (after)

- `pytest ai/tests/test_moodle_retrieval.py ai/tests/test_moodle_retrieval_r2.py`
  → **144 passed** (R2 file: 75 collected = 72 params + 3; R1 file: 69 collected,
  b3 65/65 through the R1 door).
- `python -m ai.eval.pack_contract --gate` → exit 0, `violations=0`.
- `python -m ai.eval.pulse_gauge --gate` → exit 0, "no meter rose, no ladder
  level regressed".
- `retrieval-b3.yaml` byte-identical: sha256
  `56fe1a02b3d7631d78e88cdc07e5213aca645bf55e29f0200ca4bf50f47d1cae`
  before and after.

## Root-cause evidence (no attribution)

- The evidence shows a **rewrite between 15:01 and 15:13:25**: the generator's
  72-case log is 15:01:00 and the reduced file's mtime is 15:13:25; the test file
  follows at 15:13:35. The reduced file is a curated 12-case subset, not a
  truncation.
- At 15:11 the `/tmp/ws7-*` directories held freshly regenerated per-course
  indexes and `/tmp/ws7_seed*.txt` showed `build == committed` (all `match=True`),
  and `/tmp/ws7_pack.log` (15:14:33) / `/tmp/ws7_gauge.log` (15:14:34) show the
  gates were run immediately after the rewrite.
- Any process that writes `retrieval-r2.yaml` or the R2 test can produce this:
  the file is untracked, and the repo has no `.bak`/swap copy. The 72-case
  content survived only because the generator is deterministic. Recommendation:
  track both golds in git (or add a `.bak`) so a future rewrite is recoverable
  without re-derivation.
