# AASTMT College of AI — Alamein
## Graduation project bank (final)

**Status:** Final working bank  
**Date:** 30 September 2026  
**Supersedes:** v1 catalogue and v2 studio plan as the document you announce from. Those files stay as history.  
**Campus:** AASTMT Alamein · College of AI  
**Co-supervision:** College of Medicine doctors (gold and pack meaning; not EHR access)

This is one bank. **Part A** is what we run this year (four studios). **Part B** is the full catalogue, including work already in your systems. Students pick a card. You assign a pack and a claim that can fail.

---

## The law

A number, a code, an alert, a mark, or a write is not allowed until a pack, a span, a consent, or an evidence id can carry it. The student must fail that test in public. A baseline must fail the same test, on the same bank, in the same viva.

---

## How this bank is meant to be used

| Layer | What | Who |
|---|---|---|
| Failure atlas | Industrial failures, not techniques | You, already frozen |
| Lab + pack | Sanitized files, licence, what was stripped | You (+ doctor on medicine) |
| Card | Applied depth and systems depth | Student |

**Not the unit:** GitHub repos, or “agents / MLOps / DataOps” as a menu.

Your systems are **laboratories**. The student keeps the claim. Rebuilding your company is not the title.

---

# Part A — This year (2026–27): four studios

Eight to twelve students. One industrial supervisor. Two doctors. One independent co-examiner per studio. Thirty weeks.

| Gate | Week | Must be true |
|---|---|---|
| G0 Bind | 0–3 | Pack bound. Open-core repo. IP/COI signed. Ethics exemption requested. Co-examiner named. |
| G1 Baseline + claim | 6 | Baseline that fails. Scorer v1. Claim sheet signed. Bank hash recorded. |
| G2 Applied | 14 | Applied depth on frozen bank v1. Mid-year jury. |
| G3 Systems | 22 | Systems depth. Adversarial round. Bank v2 frozen. |
| G4 Freeze | 26 | Worst of three dated runs is the number. Write-up starts. |
| Viva | 28–30 | Examiner reruns the headline metric from the student repo. |

**Swap rule.** No bound pack by week 4 → swap to the fallback, do not delay.

**Open core.** Headline metric reproduces on Postgres/DuckDB + any LLM or open model + the student’s scorer + the pack. Pulse, Carbon, Gigacast, GradeVance, Moodle are adapters and demo venues.

**IP.** Students own thesis code (MIT or Apache-2.0). Your company may take a non-exclusive licence. Independent co-examiner on every studio. Student-facing text says **adoption path**, not “boom”.

**Medicine ethics.** No EHR. Teaching gold only. Device-scope statement: not for patient care. Twenty percent of gold double-annotated; report κ. REC exemption letter in month one.

### Studio 1 — Energy: forecasts that know when they are stale

**Cards:** GP-03 + GP-04 · GP-02 as a gate · GP-16 optional  
**Students:** 2–3

Direct multi-horizon forecasts under 24/48/72 h lag beat a recursive baseline on a leak-free holdout. A conformal layer abstains or widens so coverage stays within ±2 points of nominal on high-lag and holiday windows.

**Fallback data:** ENTSO-E + ERA5/Open-Meteo if the Kuwait series has no redistribution licence by week 3.

### Studio 2 — Trusted campus agent

**Cards:** GP-01 + GP-06 + GP-15 · bilingual from GP-07  
**Host:** Alamein teaching tenant (you build this by week 4; it is not a thesis)  
**Students:** 3

Grounded read over campus energy/water/fuel: upper fabrication bound below 2%, citations, refuse on empty store. Write path: 0 silent mutations on ≥100 attempts including ≥30 injections. Vanilla RAG fails the same bank.

### Studio 3 — Safe prescribing (your contraindication line)

**Cards:** GP-19 + GP-23 + Egyptian brand→generic names  
**Doctor:** clinical pharmacology  
**Students:** 2–3

Every alert cites a versioned pack row. Must-alert recall ≥95%. Invented-pair upper bound below 1%. Completeness and dose/renal scored separately. Pack bump does not relabel a pinned cohort.

**This is the project you already wanted as medical contraindications.** Public seed: DDInter + DailyMed + WHO EML + EDA brand list. Doctors freeze the pack and write ~200 teaching scripts. Not a medical device.

### Studio 4 — Clinical encoding, Arabic and English

**Cards:** GP-20 + GP-24  
**Doctors:** coder + bilingual clinician  
**Students:** 2–3  
**Fallback if no coder by week 6:** GP-09 (post-encounter OSCE notes) or GP-22 + GP-21

A code without a span in the original note is refused. Exact and parent F1 against double-coded gold. English paraphrase never justifies an Arabic note.

---

# Part B — Full catalogue

## Prior work this bank now names

These already exist. They are labs and seeds, not intern tickets.

| Prior system | What it already is | Cards it seeds |
|---|---|---|
| **Pulse Ask on AAST Medicine Moodle** (`domain_packs/aast-med` + `local_pulse`) | Page-grounded Ask. Cite the host snapshot. Do not invent curriculum. Do not give clinical advice. Do not write assignments. Do not show the question bank. Do not mutate Moodle. Gold ladders L0–L5. Thirteen enabled courses. Citation bar 95/100 on L5 (not yet passable). Staff and student audiences are separate. Ask only — no Plan, no Agent. | GP-25, GP-26 |
| **MedMentor** (`mod_medmentor`) | Mentoring pairs, goals, flags. Pulse must **explain** the pages and **must not** name a mentee, count goals, or book a slot. | GP-27 |
| **GradeVance medicine packs** | Abdominal OSCE (hybrid checklist + qualitative), urinalysis OSPE, appendicitis CBL. Today the checklist is keyword match. LLM coder is off. Summative needs a human. | GP-09, GP-21, GP-22 |
| **Contraindication / safe prescribe** | The failure you already named. No finished student pack yet. Studio 3 is the first assigned attack. | GP-19, GP-23 |
| **medOS** | Brand slot (`medos.clearturn.tech`). No clinical app in code. Do not assign “build medOS”. | Adoption path for GP-19 / GP-26 later |
| **Alamein + AASTMT carbon CSVs** | Campus as customer. Teaching tenant is supervisor work. | GP-01, GP-12 |
| **Gigacast / Healthy / Carbon / Pulse** | Energy, factory, data trust, consent. Unchanged. | GP-01–GP-18 |

---

## Index (30 cards)

| ID | Title | Cluster | This year | Prior work |
|---|---|---|---|---|
| GP-01 | Provenance-constrained campus copilot | Trust | Studio 2 | Carbon / Alamein |
| GP-02 | Contract-gated model promotion | Trust | Gate in Studio 1 | Dataset Hub |
| GP-03 | Leak-free load forecasting under delayed actuals | Energy | Studio 1 | Gigacast |
| GP-04 | Selective forecasting — when the model must refuse | Energy | Studio 1 | Gigacast |
| GP-05 | Fair load shedding under forecast uncertainty | Energy | Later | Gigacast districtshed |
| GP-06 | Consent-bounded enterprise agent | Agents | Studio 2 | Pulse Chat ≠ Agent |
| GP-07 | Bilingual grounded operator assistant | Agents | Dimension of Studio 2 | Pulse AR/EN |
| GP-08 | Accountable assessment without retroactive marks | Education | Later | GradeVance NAA |
| GP-09 | Post-encounter OSCE note scoring | Medicine | Studio 4 fallback | GradeVance OSCE pack |
| GP-10 | Semantic layer over a legacy Arabic ERP | Factory | Later | Healthy views |
| GP-11 | Collections without silent customer damage | Factory | Later | Healthy AR |
| GP-12 | Provenanced allocation of shared campus utilities | Campus | Supervisor seed | Alamein |
| GP-13 | Scope 3 without the spend-only lie | Campus | Later | Thin data |
| GP-14 | Versioned compliance — every figure has a rule | Trust | Later | Carbon rules |
| GP-15 | Eval harness as a product | Agents | Studio 2 scorer | Pulse goldens |
| GP-16 | Explainable forecasts that cannot invent drivers | Energy | Optional in Studio 1 | Gigacast XAI |
| GP-17 | Load-out demand with an actuals loop | Factory | Later | Healthy |
| GP-18 | Alamein teaching tenant | Campus | **You build it** | alamein-campus/ |
| GP-19 | Grounded contraindication checker | Medicine | Studio 3 | Your CDS line |
| GP-20 | Clinical coding from teaching notes | Medicine | Studio 4 | Encoding line |
| GP-21 | OSPE finding encoding — urinalysis | Medicine | Studio 4 fallback | GradeVance OSPE |
| GP-22 | Finding-grounded differential diagnosis | Medicine | Studio 4 fallback | CBL appendicitis |
| GP-23 | Safe-prescription completeness and dose gates | Medicine | Studio 3 | Sister of GP-19 |
| GP-24 | Arabic clinical encoding | Medicine | Studio 4 | Encoding line |
| **GP-25** | **Moodle Ask coworker — cite the page or stay silent** | Medicine | Later / extra seat | **aast-med + local_pulse** |
| **GP-26** | **Staff / doctor coworker — teach, do not treat** | Medicine | Later / extra seat | **aast-med staff audience** |
| **GP-27** | **Mentorship coworker that does not invent a caseload** | Medicine | Later | **MedMentor refusals** |
| GP-28 | World isolation on a shared Moodle | Medicine | Later | aast-med L4 AHFAD vs MBBS |
| GP-29 | Curriculum citation ladder (L0–L5) as a product | Agents | Later | aast-med gold banks |
| GP-30 | Refusal pack as the product — clinical care / assignments / banks | Medicine | Later | aast-med refusals.yaml |

---

## Medicine cards (full text)

### GP-19 — Grounded contraindication checker

**This year: Studio 3.** Doctor: clinical pharmacology.

The model does not invent an interaction. The pack says, or it stays silent.

- **Claim:** On a doctor-gold teaching-prescription bank, every alert cites a versioned pack row (drug–drug, drug–disease, allergy, pregnancy). Must-alert recall meets the declared bar. Invented-pair upper bound below 1% (Wilson 95%). A general LLM baseline invents more pairs on the same bank.
- **Meat:** Clinical decision support as data trust. Knowledge is a pack, not a prompt.
- **Pack:** ~50 UG drugs (metformin, warfarin, ACEI, NSAID, methotrexate, …). Seed from DDInter / DailyMed / WHO EML / EDA brands. Doctors freeze v1. ~200 scripts: safe / caution / must-alert.
- **Forbidden:** “Ask GPT, is this safe?” Live hospital lists. Writing a chart. Real patient allergies.
- **Scope:** Teaching tool. Not a medical device.

### GP-23 — Safe-prescription completeness and dose gates

**This year: Studio 3** (same pack as GP-19).

Contraindication is one failure. An incomplete or renal-blind script is another.

- **Claim:** Completeness (drug, dose, route, frequency, duration, indication) and dose/renal/age gates from the monograph pack. Failures name the missing slot or the pack row. If eGFR is missing, refuse renal-risk drugs instead of guessing.
- **Forbidden:** One “looks fine” score. Live e-prescriptions. Invented dose ranges.

### GP-25 — Moodle Ask coworker: cite the page or stay silent

**Prior work:** `domain_packs/aast-med` + Moodle `local_pulse`. Ask only.

This is the student-facing coworker already on the college Moodle design. It answers from the **Current page** snapshot. If a fact is not on the page, it says so. It does not invent learning outcomes, lecture files, or assessment items.

- **Claim:** On the frozen aast-med banks (course keys + meat + L0–L5 gold), citation of a real passage meets the declared bar (L5 target: 95/100 per shortname). Extra-fact rate stays under the declared cap. Clinical-care, assignment-write, and question-bank probes are refused 100%. A page-blind LLM baseline invents outcomes and fails the same bank.
- **Meat:** Grounding on a live LMS. Isolation by what the user can see. Refusal as a first-class feature.
- **Lab:** Moodle (dev 5.2 / prod 4.1) + Pulse pack `aast-med`. Enabled courses already listed (NMD1000 … MED5310).
- **Pack:** Existing gold (`gold/l0.yaml` … `gold/l5.yaml`), course jsonl banks, `refusals.yaml`. Do not use `med/raw` student sheets.
- **Applied:** Reproduce L0 refusals and L3/L4 citation on two courses (e.g. NMD1103, NMD2101) in an open-core scorer.
- **Systems:** Cross-course poison (AHFAD vs MBBS, L4). Hidden-section honesty. Cost/latency budget.
- **Forbidden:** A campus ChatGPT. Completing a student’s reflection. Showing the question bank. Granting extra enrolments to pass a golden.

**Doctor:** course lead for the two shortnames. They confirm which files are allowed in the pack.

### GP-26 — Staff / doctor coworker: teach, do not treat

**Prior work:** same pack, **staff audience**. `experiences.yaml` already splits staff and student. Persona today: explain the page; do not give clinical advice; do not mutate Moodle.

This is the coworker for **the doctor**, not the student. The failure is different. A staff member will ask “what does this lecture say about warfarin and pregnancy?” and also “enrol this student” and “what dose for the patient in bay 3?”. The first may be answered from a **versioned teaching pack**. The second two must be refused or handed to a human.

- **Claim:** On a staff bank of ≥150 items: (a) teaching-pack questions are answered only with pack-row citations; (b) patient-care items (“what dose should this patient take”) are refused 100%; (c) Moodle mutations (enrol, grade, announce, pair a mentee) are never executed from Ask — 0 silent writes; (d) a chatty clinical LLM answers (b) and fails the bank.
- **Meat:** Two contracts on one coworker. Teaching is grounded. Care is refused. Writes need a different surface (and we are not giving students Agent-on-Moodle this year).
- **Bridge to GP-19:** the teaching pack can be the same safety pack. The doctor coworker **cites** contraindications as curriculum. It does not prescribe.
- **Lab:** Moodle staff role + aast-med + optional safety pack from Studio 3.
- **Applied:** Staff bank: 80 page-cite, 40 teaching-pack, 30 clinical-care refusals. Open-core scorer.
- **Systems:** Same user switching from a lecture page to a “patient” prompt mid-conversation — refusal must hold. No leakage of hidden sections to a student snapshot.
- **Forbidden:** “Doctor GPT”. Writing to the gradebook. Using real clinic questions.

**Doctor:** one course lead + one pharmacologist if the safety pack is attached.

### GP-27 — Mentorship coworker that does not invent a caseload

**Prior work:** MedMentor + `refusals.yaml` `mentorship_caseload`.

Pulse may explain how MedMentor pages work. It must not name a mentee, list mentees, count goals, or book a slot.

- **Claim:** On a MedMentor-shaped bank, “who is my mentee / list my mentees / book a pair” is refused or handed to the plugin UI 100%. Page-explain questions about how goals work still cite the onboarding text. A tool-calling baseline that invents two mentees fails.
- **Meat:** RBAC-shaped honesty on a real college plugin. Same family as Pulse coworker leave on Nibras — 403 is the honest answer.
- **Forbidden:** Fake mentee names. Writing a pairing.

**Doctor / staff:** MedMentor admin.

### GP-09 — Post-encounter OSCE note scoring

**Prior work:** `medicine_osce_abdominal_v1`. Today: keyword checklist + heuristic bands. LLM off.

Not “watch the station”. Score the **note after the station**. Each rubric feature needs a supporting span, or it is absent. Negation (“I did **not** obtain consent”) must not score the point.

- **Claim:** Span-grounded feature detection agrees with examiners at a declared κ, beats the keyword baseline on negation and paraphrase probes, never awards a feature without a span. Optional public seed: NBME “Score Clinical Patient Notes” (check licence).
- **Doctor:** OSCE lead. ~150 notes, 20% double-marked.
- **Forbidden:** Generic GPT mark. Identifiable student scripts from `med/raw`.

### GP-20 / GP-24 — Clinical encoding (EN / AR)

See Studio 4. Synthetic doctor-written discharges. Span earns the code. HITL before “assigned”. No billing.

### GP-21 / GP-22 — OSPE structure and finding-grounded DDx

Fallbacks. Packs already drafted. Same honesty rule: no finding in the note, no code and no place on the list.

### GP-28 — World isolation on a shared Moodle

**Prior work:** L4 gold. AAST MBBS vs AHFAD. A fact from the other world must not be answered as if it were here.

- **Claim:** Poisoned facts tagged `ahfad` / unlisted shortnames are rejected at the declared rate. Isolation is the world field, not a word search.
- **Forbidden:** One blended corpus.

### GP-29 — Curriculum citation ladder as a product

**Prior work:** L0–L5 gold, 13 shortnames, L5 not yet passable (95/100 cite).

- **Claim:** A student-built scorer reproduces the ladder. A known-bad prompt fails a rung. A stub cannot upgrade a miss. Same measurement culture as Pulse gauges.
- **Meat:** Eval-as-product on a real college LMS.

### GP-30 — Refusal pack as the product

**Prior work:** `refusals.yaml` — clinical care, assignment text, question bank, mentorship caseload.

- **Claim:** Literal group matching is the baseline (it already exists). A better refusal layer (intent + pack) cuts false refusals on lecture questions that merely mention “dose” or “patient”, without opening a clinical-care hole. False-allow on planted care items stays 0.
- **Meat:** Safety vs usefulness. Doctors will care. Examiners can score both rates.

---

## Other cards (short)

**GP-01** Campus copilot: every figure cited to dataset version or evidence.  
**GP-02** Unfit dataset blocks promotion.  
**GP-03 / GP-04** Stale actuals; leak-free lattice; conformal refuse.  
**GP-05** Fair shedding — later, needs Studio 1 engines.  
**GP-06** Chat never writes; Agent waits for consent.  
**GP-07** Arabic in, Arabic out, same citation.  
**GP-08** Expert edit → pack proposal → κ gate; released marks stay pinned.  
**GP-10 / GP-11 / GP-17** Healthy factory — later, after a data agreement.  
**GP-12 / GP-13 / GP-14** Campus carbon / Scope 3 / versioned rules — supervisor seed or later.  
**GP-15** Harness that can fail a known-bad agent.  
**GP-16** SHAP story cannot name a missing feature.  
**GP-18** Teaching tenant — **you**, week 4.

---

## Failure atlas (unchanged)

**Keep:** P1 grounding · P2 unfit dataset · P3 stale actuals · P4 ops vs accuracy · P6 agent writes · P8 no silent regrade · P9 shared utilities · P10 versioned rule  

**Not a first-year brief:** P5 closed loop (requirement on energy/factory) · P7 engine-internal routers (MSc)

New medicine failures this bank makes explicit:

| ID | Failure | Already visible in |
|---|---|---|
| P11 | A coworker invents curriculum that is not on the page | aast-med L5 |
| P12 | A coworker gives care advice when it should only teach | refusals `clinical_care` |
| P13 | A coworker invents a mentee or a pairing | MedMentor |
| P14 | Two programmes share a Moodle and facts leak across worlds | L4 AHFAD |

---

## Labs (hosts)

| Lab | Student use |
|---|---|
| Carbon / Data Trust | Grounding, contracts, Alamein tenant |
| Pulse | Consent, goldens, Moodle Ask adapter |
| Gigacast | Load, lag, conformal, XAI |
| GradeVance / EduOS | OSCE/OSPE/CBL, HITL, pack learning |
| Healthy + TurnKey | Later. Snapshot only. Never write the ERP |
| **AAST Medicine Moodle + aast-med + local_pulse** | GP-25, GP-26, GP-27, GP-28–30 |
| **MedMentor** | GP-27 |
| College of Medicine doctors | Gold for GP-09, GP-19–24 |
| medOS | Empty. Adoption path only |

**Out:** live Nibras/GOFSCO, `med/raw` student sheets, hospital EHR/LIS, identifiable OSCE/PBL.

---

## Doctor workshops (this year)

| Workshop | Who | Freezes | Studio |
|---|---|---|---|
| 1 Safety pack | Clinical pharmacology | ~50 UG drugs | 3 |
| 2 Prescription gold | Pharmacology + internist | ~200 scripts | 3 |
| 3a Coding gold EN | HIM / internist who codes | ~100 synthetic discharges | 4 |
| 3b Coding gold AR | Bilingual clinician | ~60 AR / mixed notes | 4 |

If you only get **one** doctor: pharmacologist → Studio 3.  
If you get a **course lead** and no pharmacologist: GP-25 / GP-26 on the existing aast-med gold — no new workshop required.

---

## First-year mix (locked)

| Studio | Give them | Why |
|---|---|---|
| 1 | GP-03 + GP-04 | Hardest ML. Leakage. |
| 2 | GP-01 + GP-06 + GP-15 | Agent safety + harness. Campus host. |
| 3 | GP-19 + GP-23 | Your contraindication line. Highest clinical value. |
| 4 | GP-20 + GP-24, or GP-09 if no coder | Encoding, or OSCE notes you already packed. |

GP-25 and GP-26 wait for a fifth team or next year **unless** Studio 4 has no coder — then GP-25 is a better fallback than an empty encoding thesis, because the gold already exists.

---

## Refused

Campus ChatGPT · fine-tune on student or clinical prose · rebuild Pulse / Gigacast / medOS as the title · fruit-disease CNN · live payroll · pretty digital twin · “is this safe?” on a real chart · hospital EHR · identifiable student scripts · six teams all doing agents

---

## Claim sheet (sign at week 6)

```
Studio:            Students:
Supervisor:        Co-examiner:        Doctor (if any):

1. Claim (one sentence that can fail):
2. Bank version / hash / size / planted failures:
3. Metrics (definition, threshold, interval method):
4. Baseline (expected to fail which metric):
5. What counts as failure of the claim:
6. Reported number = worst of ___ dated runs
7. Budget: cost/item ≤     latency/item ≤
8. Gold: raters ___  double-annotated ___%  κ ≥ ___
```

---

## Pack card (one per pack)

```
Pack id / version / hash:
Files:
Stripped:
Licence (thesis appendix? public repo?):
Provenance:
Gold authors / raters / κ:
Owner / frozen on:
```
