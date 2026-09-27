# AASTMT College of AI — Alamein  
## Graduation projects 2026–27: four studios (v2)

**Status:** v2 draft — revised after external review  
**Date:** 27 September 2026  
**Replaces:** the cohort plan in v1 (`2026-alamein-college-of-ai-project-bank.md`). v1 stays as the **three-year catalogue** of 24 cards. This v2 is **what we run this year**.  
**Campus:** Arab Academy for Science, Technology & Maritime Transport — Alamein  
**Supervision:** one industrial academic supervisor, College of Medicine co-supervisors, one independent co-examiner per studio

---

## 0. What changed from v1

| # | v1 | v2 | Why |
|---|---|---|---|
| 1 | 24 cards, 6 teams | **4 studios**, 8–12 students | One supervisor and two doctors cannot carry six teams |
| 2 | Packs bound "after review", doctor gold "after packs" | **Packs bound weeks 0–3, doctors write gold in parallel** with students building on public seed data | Data was on the wrong side of the calendar |
| 3 | "Fabrication = 0" | **Rate with 95% interval on a bank of stated size, against a baseline that fails on the same bank** | Zero misses on 40 items still allows ~7% |
| 4 | No pre-registration | **Signed claim sheet at week 6** (Appendix A) | Stops thresholds being chosen after results |
| 5 | Claims run inside the mentor's systems | **Open-core rule**: the headline metric reproduces on an open stack | Examiner must be able to rerun it |
| 6 | "If it booms" | **Adoption path**, plus an IP and conflict-of-interest note signed at kickoff | Supervisor grades work that could feed his company |
| 7 | Medicine: "no EHR" | Same line, plus **ethics exemption letter, device-scope statement, double-annotated gold with κ, doctor incentives** | Needed for publication and any later pilot |
| 8 | Kuwait series "sanitized" | **Licence decision in week 1**; open fallback is the reproducible spine | "Sanitized" is not a licence |
| 9 | GP-18 teaching tenant as a thesis | **Supervisor deliverable, due week 4** | It is infrastructure |
| 10 | Campus carbon as a team | Campus is the **host** for Studio 2, not a team | Least student-magnetic, thinnest data |
| 11 | No budget, no selection | **Budget and student-selection lines** per studio | They were missing |

---

## 1. The law

**A number, a code, an alert, a mark, or a write is not allowed until a pack, a span, a consent, or an evidence id can carry it. The student must be able to fail that test in public, and a baseline must fail the same test, on the same bank, in the same viva.**

---

## 2. Calendar and gates (30 weeks)

| Gate | Week | What must be true |
|---|---|---|
| **G0 Bind** | 0–3 | Pack bound (files, strip list, licence). Open-core repo skeleton. IP/COI note signed. Ethics exemption requested. Co-examiner named. |
| **G1 Baseline + claim** | 6 | A baseline that fails. Scorer v1. **Claim sheet signed** (Appendix A). Bank v1 hash recorded. |
| **G2 Applied** | 14 | Applied depth passes on frozen bank v1. Mid-year jury with the co-examiner. |
| **G3 Systems** | 22 | Systems depth. Adversarial probe round. Bank v2 frozen. |
| **G4 Freeze** | 26 | Worst of three dated runs is the reported number. Write-up starts. |
| **Viva** | 28–30 | The examiner reruns the headline metric from the student repo. |

**Swap rule.** A studio with no bound pack by week 4 is swapped to its fallback, not delayed.

**Doctor workshops run in weeks 1–6**, while students build on public seed data:

| Workshop | Who | Freezes | Studio | Week |
|---|---|---|---|---|
| 1 Safety pack | Clinical pharmacology | ~50 UG drugs × interaction / disease / allergy / pregnancy / renal / dose rows | 3 | 1–3 |
| 2 Prescription gold | Pharmacology + internist | ~200 teaching scripts | 3 | 4–6 |
| 3a Coding gold EN | Medical records coder or internist who codes | ~100 synthetic discharges + codes + spans | 4 | 2–6 |
| 3b Coding gold AR | Bilingual clinician | ~60 Arabic / mixed notes | 4 | 8–12 |

---

## 3. Rules that apply to every studio

**Open core.** The student repo reproduces the headline metric on an open stack: Postgres or DuckDB, any LLM API or open model, the student's scorer, the frozen pack. Carbon, Pulse, Gigacast, and GradeVance are **adapters and demo venues**, never the only path to the number.

**Claims are statistical.** Every rate is reported with a Wilson 95% interval and the bank size. Every studio has a baseline that is expected to fail and is run on the same frozen bank. The thesis is the **difference**.

**Adversarial round.** Every bank includes planted failures. Studio 2 includes prompt injection inside retrieved evidence.

**Cost and latency.** Every studio reports cost and latency per item against a declared budget.

**Gold reliability.** Any human-written gold states how many raters, the double-annotated share (at least 20%), and κ.

**Data.** No GOFSCO raw data. No `med/raw` student sheets. No live ERP writes. No hospital EHR or lab system data. No identifiable OSCE or PBL scripts. Healthy ERP is cohort 2 only, after a written data agreement.

---

## 4. IP, conflict of interest, examination

Signed at kickoff by student, supervisor, and co-examiner.

1. **Students own their thesis code** under a permissive licence (MIT or Apache-2.0). The university's IP policy applies as normal.
2. **The supervisor's company** may take a **non-exclusive** licence to student code, and gets no rights to the student's thesis, data, or publications beyond that.
3. **The supervisor declares the interest** in writing. Every studio has an **independent co-examiner** who grades the claim, not the product fit.
4. Student-facing text says **adoption path**, never "boom". A student may spin out independently. The open-core rule makes that possible.
5. **Publications** list the doctors who wrote the gold as co-authors, where the doctor chooses.

---

## 5. The four studios

### Studio 1 — Energy: forecasts that know when they are stale

**Merges:** GP-03 + GP-04, with GP-02 as a requirement and GP-16 optional · **Atlas:** P3, P1, P2  
**Students:** 2–3 · **Selection:** one strong in time series, one in statistics

**Claim.** Direct multi-horizon forecasts under 24, 48, and 72 hour actuals lag beat a recursive baseline on a leak-free holdout. A conformal layer abstains or widens so that coverage stays within ±2 points of nominal on high-lag and holiday windows.

**Outcomes**

- O1 Leak-free dataset builder with (origin, horizon, available-at) pairs, plus a leak test suite that fails when any future value enters a feature.
- O2 24-hour, 48-hour, and 7-day engines versus a recursive baseline, with MAPE reported by horizon and lag.
- O3 Conformal intervals and abstention, with a coverage-versus-MAPE curve and the abstain rate.
- O4 Resolver that picks the engine from observed lag. Promotion gate that blocks a model whose training window fails freshness or validity.
- O5 (optional, one student) Explanation text that cannot name a feature absent from the attribution payload, tested with a planted missing-feature probe.

**Pre-registered metrics:** leak tests 100%; direct beats recursive at 48 hours and beyond by a declared margin (for example, at least 10% relative); coverage 88–92% at nominal 90% on every tagged window; gate blocks 100% of injected stale, null, and unit-break windows.

**Data:** Kuwait load and weather **only if** written redistribution permission exists by week 3. Reproducible spine: ENTSO-E Transparency load for a cooling-dominated system (Greece, Cyprus, or Spain) with ERA5 or Open-Meteo weather. Verify reuse terms. Stretch: an Egyptian series via EETC or EgyptERA (send one letter, do not wait on it).

**Roadmap:** W1–4 builder, leak tests, recursive baseline · W5–6 claim sheet · W7–14 direct engines, gate · W15–22 conformal, abstention, resolver, probes · W23–26 freeze · W27–30 write-up

**Budget:** modest GPU or CPU hours. Gradient boosting is enough.

**Value.** *Education:* temporal leakage and calibrated uncertainty. *Industry:* utility-grade forecasting credibility. *Adoption path:* forecasting-with-intervals service for utilities and factories. This is closer to a consultancy seed than a product.

---

### Studio 2 — Trusted campus agent: reads with a citation, writes with consent, judged by its own harness

**Merges:** GP-01 + GP-06 + GP-15, with GP-07's Arabic/English dimension · **Host:** Alamein teaching tenant (supervisor-built, week 4) · **Atlas:** P1, P6, P9  
**Students:** 3 (read path · write path · harness) · **Selection:** one systems/security-minded student

**Claim.** On a frozen bilingual bank, a grounded copilot over campus energy, water, and fuel data states no figure absent from a retrieved payload (upper bound below 2%). It cites every figure, refuses on an empty store, and never mutates the host without explicit consent (0 of at least 100 attempts, including at least 30 injection attempts). A vanilla RAG baseline fails the same bank.

**Outcomes**

- O1 Bank of 200–250 items in parallel Arabic and English: numeric reads, multi-turn reference, empty store, access control (finance user versus hospital data), write intent, injection inside evidence, planted failures.
- O2 Grounded read path with payload-bound citations.
- O3 Write path: plan, then consent, then commit or fail visibly. Audit log. Recovery when a staged write dies.
- O4 Scorer with a CI-style report. The reported number is the worst of the dated runs. A stub never upgrades a miss.
- O5 Cost and latency per turn within budget.

**Pre-registered metrics:** fabrication upper bound below 2%; citation precision at least 95%; empty-store refusal at least 98%; silent mutation 0 across at least 100 attempts; reply language matches the user at least 98%; baseline rates reported.

**Data:** AASTMT GHG CSVs and Alamein journey tables with synthetic users. Public emission factors (IPCC, DEFRA). No production brands.

**Open-core note:** the consent claim needs a host. The student repo ships a **minimal open host** (a small API with the same write endpoints). Carbon is the second venue.

**Roadmap:** W1–4 bank v1 (100 items) and a failing baseline · W5–6 claim sheet · W7–14 grounding, citation, refusal, access probes · W15–22 Chat/Agent split, consent, recovery, injection round, bank v2 (250) · W23–26 freeze · W27–30 write-up

**Budget:** the largest API spend in the cohort. 250 items × repeated runs × two languages. Set a cap and a cheap default model.

**Value.** *Education:* grounding, authority, consent, and measurement. *Industry:* an honesty layer for enterprise copilots. *Adoption path:* **the harness is the most independently sellable artifact in the bank.** This studio must be strictly open-core.

---

### Studio 3 — Safe prescribing: the pack says, or it stays silent

**Merges:** GP-19 + GP-23 + Arabic/Egyptian drug-name normalisation · **Doctor:** clinical pharmacology (nephrology optional) · **Atlas:** P1, P2, P10  
**Students:** 2–3 · **Selection:** at least one student who can read a drug monograph

**Claim.** On a doctor-frozen bank of teaching prescriptions, every alert cites a versioned safety-pack row. Must-alert recall meets a pre-declared bar. Any alert without a pack id counts as invented (upper bound below 1%). Completeness and dose/renal gates are scored separately. A pack version bump does not relabel a pinned earlier cohort.

**Outcomes**

- O1 Safety pack v1 covering about 50 UG drugs, with provenance on every row (seed source or doctor) and Egyptian brand names mapped to generics. The doctors freeze it.
- O2 Checker that takes meds, conditions, allergies, age, and eGFR and returns alerts with pack ids. It refuses renal-risk drugs when eGFR is missing.
- O3 Completeness scorer: drug, dose, route, frequency, duration, indication.
- O4 Gold bank of about 200 scripts (safe, caution, must-alert, incomplete, wrong dose), 20% double-annotated, with κ.
- O5 General-LLM baseline measured on alert burden and invented pairs.
- O6 Pack v1 → v2 replay: only diffed rows change, and the prior cohort stays pinned.

**Pre-registered metrics:** must-alert recall at least 95%; invented-pair upper bound below 1%; alerts per script versus baseline; slot accuracy at least 95%; refusal when eGFR is missing 100%; gold κ at least 0.7.

**Data:** seed from DDInter 2.0 (check its licence; teaching use appears fine, commercial reuse may not be), DailyMed/openFDA labels for dose ranges, the WHO Essential Medicines list for scope, and the Egyptian Drug Authority list for brand names. Doctors write every script. No patient data.

**Scope statement in the thesis:** teaching tool, not a medical device, not for patient care.

**Roadmap:** W1–3 workshop 1 while students build the pack schema and name normaliser on the seed · W4–6 workshop 2, baseline, claim sheet · W7–14 checker and completeness on bank v1 · W15–22 renal and age gates, pack-bump replay, κ, adversarial scripts · W23–26 freeze · W27–30 write-up

**Doctor time:** about 4 workshop afternoons + 20% double annotation. Offer co-authorship and teaching credit.

**Value.** *Education:* decision support as data trust; the "ask GPT if it is safe" reflex killed on their own campus. *Industry:* a prescribing-OSCE tool for the College of Medicine this year. *Adoption path:* formulary-aware, Arabic-brand-aware prescribing safety for the region. Clinical use is a regulated device pathway, so the honest pitch is "teaching product now, regulatory path later".

---

### Studio 4 — Clinical encoding: the span must earn the code, in Arabic and English

**Merges:** GP-20 + GP-24 · **Doctors:** a medical records coder or internist who codes, plus a bilingual clinician · **Atlas:** P8, P1  
**Students:** 2–3 · **Selection:** one student strong in Arabic NLP  
**Fallback if no coder by week 6:** GP-22 + GP-21 (finding-grounded differential diagnosis and urinalysis encoding). Those packs are already drafted, and the same grounding rule applies.

**Claim.** Code candidates from doctor-written English and Arabic teaching notes are each justified by a span in the **original** note. A code without a span is refused. Exact and parent-level F1 are reported against double-coded gold. Human review is required before a code is "assigned". An English paraphrase never justifies an Arabic note.

**Outcomes**

- O1 Codebook service over about 150 codes for the taught case families, acute abdomen and ED first.
- O2 Span-grounded top-k candidates, with refusal when no span exists.
- O3 Arabic and mixed notes (labs in English, history in Arabic) with character-offset spans.
- O4 Review queue with versioned inclusion and exclusion notes, and time-to-accept measured.
- O5 Gold: about 100 English and 60 Arabic synthetic discharges, 20% double-coded, with κ.

**Pre-registered metrics:** span support 100% by construction; exact and parent-level F1 with intervals; Arabic justification rate 100% on Arabic notes; gold κ at least 0.7; coder time-to-accept versus manual.

**ICD version — decide with the coder in week 1.** ICD-11 has an official WHO Arabic release, which makes Arabic/English parity a data fact. Egyptian hospitals may still code in ICD-10. The claim does not depend on the choice; the codebook does.

**Data:** doctor-written synthetic discharges, starting from the appendicitis CBL family. Public Arabic medical benchmarks (for example MedArabiQ) are exam-style questions, not clinical notes. They can sanity-check Arabic handling; the encoding gold must be written in-house. No MIMIC, no hospital scans.

**Roadmap:** W1–4 codebook and pipeline on 10 seed notes while workshop 3a runs · W5–6 claim sheet and a code-list baseline without spans that fails · W7–14 English encoding, review queue, F1 on bank v1 · W15–22 Arabic and mixed notes, double coding, versioned notes · W23–26 freeze · W27–30 write-up

**Doctor time:** about 3 afternoons for English, 2 for Arabic, plus double coding.

**Value.** *Education:* hierarchical classification, span grounding, accountable AI. *Industry:* medical-records teaching now; coder assistance later, where coders are scarce. *Adoption path:* an Arabic coding and problem-list assistant for regional hospitals.

---

## 6. Supervisor deliverables (not theses)

| Deliverable | For | Due |
|---|---|---|
| Alamein teaching tenant (was GP-18): org units, synthetic users, access roles, two data products, evidence on two sources | Studio 2 | W4 |
| Minimal campus allocation seed (from GP-12) | Studio 2 host data | W4 |
| Kuwait data licence decision + ENTSO-E/ERA5 fallback pack | Studio 1 | W3 |
| IP/COI notes, co-examiner names, ethics exemption request | All | W3 |
| Doctor workshop schedule and incentive agreement | Studios 3, 4 | W1 |
| API budget cap per studio | All | W1 |

---

## 7. What happened to the other v1 cards

| v1 card | This year | Later |
|---|---|---|
| GP-02 | Requirement inside Studio 1 | — |
| GP-05 fair load shedding | — | Cohort 2, on Studio 1 engines |
| GP-07 bilingual assistant | Dimension of Studio 2 | — |
| GP-08 accountable assessment | — | Cohort 2 with education faculty |
| GP-09 OSCE hybrid rubrics | — | Cohort 2 with OSCE lead |
| GP-10, GP-11, GP-17 factory cards | — | Cohort 2, after a Healthy data agreement |
| GP-12 campus allocation | Supervisor seed | Thesis when data thickens |
| GP-13 Scope 3 | — | Not before Scope 3 data thickens |
| GP-14 versioned compliance | — | Cohort 2 or MSc |
| GP-15 eval harness | Studio 2 scorer, reused by all | — |
| GP-16 faithful explanations | Optional in Studio 1 | Cohort 2 |
| GP-18 teaching tenant | Supervisor deliverable | — |
| GP-21, GP-22 | Studio 4 fallback | Cohort 2 |
| GP-23, GP-24 | Merged into Studios 3 and 4 | — |
| Atlas P7 | — | MSc |

---

## 8. Data plan

| Pack | Primary | Open fallback | Licence risk | Owner | Deadline |
|---|---|---|---|---|---|
| Load + weather | Kuwait series | ENTSO-E + ERA5/Open-Meteo; EETC letter for Egypt | Redistribution permission — decide W1 | Supervisor | W3 |
| Campus energy/water/fuel | AASTMT GHG CSVs + Alamein journey | Synthetic tenant, same schema | Low; strip user data | Supervisor | W4 |
| Safety pack | Workshop 1 | DDInter 2.0 + DailyMed + WHO EML + EDA brand list | DDInter licence terms — check before any commercial use | Pharmacologist | W3 |
| Prescription gold | Workshop 2 | None — must be written | Ethics exemption letter | Pharmacologist + internist | W6 |
| Coding gold EN | Workshop 3a | ICD codebook only | Ethics exemption; course licence | Coder | W6 |
| Coding gold AR | Workshop 3b | ICD-11 Arabic for codebook only | Same | Bilingual clinician | W12 |
| OSCE/CBL profiles (fallback) | Existing drafts | — | Doctor-written slips only | OSCE lead | fallback only |

**Out, always:** GOFSCO raw, `med/raw`, hospital EHR or lab data, identifiable student scripts.

---

## 9. Budget (order of magnitude, to be fixed at W1)

| Line | Studio | Note |
|---|---|---|
| LLM API | 2 (largest), 3, 4 | Repeated runs on 200–250 item banks; cap per studio; cheap default model |
| Compute | 1 | CPU/GPU hours for training and conformal calibration |
| Doctor time | 3, 4 | About 4–5 afternoons each + double annotation; co-authorship and teaching credit |
| Storage | All | Pinned bank and pack versions with hashes |

---

## 10. Review answers (to v1 §14)

| Question | Answer in v2 |
|---|---|
| Doability | Four studios. Pairs merged. GP-13 and GP-18 are not theses this year. |
| Viva strength | Every studio has a baseline that fails, a claim sheet, intervals, and an examiner rerun. |
| Appeal versus meat | One agent studio, one energy, two medicine. The room is not a chatbot club. |
| Ethics | No-EHR line kept. Exemption letter, device-scope statement, κ on gold. |
| Overlap | GP-19 + GP-23 one studio with two scores. GP-20 + GP-24 one pipeline with two languages. |
| Gaps | Drug-name normalisation, injection probes, cost/latency, gold κ — added. Imaging and vitals — still no defensible data. |
| First cohort | Four, not six. |
| Adoption versus thesis | Open core, IP note, co-examiner, "adoption path" wording. |

---

## Appendix A — Claim sheet (signed at week 6)

```
Studio:                         Students:
Supervisor:                     Co-examiner:           Doctor (if any):

1. Claim (one sentence that can fail):

2. Bank
   Version / hash:              Size:
   Composition (categories and counts):
   Planted failures:            Adversarial items:

3. Metrics (definition, threshold, interval method)
   M1:
   M2:
   M3:

4. Baseline (what it is, expected to fail on which metric):

5. What counts as failure of the claim:

6. Reported number = worst of ___ dated runs on the frozen bank.

7. Budget: cost per item ≤ ____   latency per item ≤ ____

8. Gold reliability (if human gold): raters ___  double-annotated ___%  κ ≥ ___

Signatures and date:
```

## Appendix B — Pack card (one per pack)

```
Pack id / version / hash:
Files:
What was stripped:
Licence and permitted use (thesis appendix? public repo?):
Provenance per row or file:
Gold: authors, raters, double-annotated share, κ:
Owner:                          Frozen on:
```
