# AASTMT College of AI — Alamein  
## Graduation project bank (industrial mentorship)

**Status:** Working draft for review  
**Date:** 27 September 2026  
**Campus:** Arab Academy for Science, Technology & Maritime Transport — Alamein  
**Programme:** College of AI graduation projects  
**Mentor profile:** Academic supervisor with industry systems (data trust, agents, model ops, education, medicine)  
**Medicine:** College of Medicine colleagues available as co-supervisors (gold and pack meaning; not EHR access)

This document is the full brief: method, problem atlas, laboratories, 24 project cards, medicine track, ethics, and how to assign a first cohort. It is meant to be reviewed as a *programme*, not as a list of intern tickets or a list of paper titles with no host.

---

## 0. How to read this

Students pick a **card**, not a technology. The supervisor assigns a **sanitized pack** and a **metric that can fail**. Applied depth ships the loop. Systems / research depth makes a claim a thesis chapter could carry.

| Layer | Artifact | Who | When |
|---|---|---|---|
| 0 | Problem atlas — industrial failure modes | Supervisor | Before any student brief |
| 1 | Lab + sanitized pack | Supervisor (+ doctor on medicine cards) | Before announcement |
| 2 | Project cards (Applied / Systems) | Supervisor | After the atlas is frozen |

**Unit of grouping:** failure modes.  
**Not the unit:** GitHub repos, or technique catalogs (agents / MLOps / DataOps as a table of contents).

Systems (Carbon, Pulse, Gigacast, GradeVance, Healthy, Alamein teaching tenant) are **laboratories**. The student’s claim is theirs. If a seed becomes a product, that is allowed. Rebuilding the mentor’s company is **not** the title.

---

## 1. Thesis of the bank

Industry already fails in public: copilots invent numbers, models promote on stale data, agents write without consent, graders silently change last semester’s marks, hospitals get ungrounded “is this safe?” answers, and campuses publish a single carbon total with no owner.

A College of AI at Alamein can teach the **meat**: grounding, contracts, leakage, consent, HITL learning, fairness under uncertainty, clinical packs that refuse to invent. Students get work they want on a CV. Examiners get a scorer, not a demo. Doctors get teaching gold they can defend. The campus can be the first customer, not a slide theme.

---

## 2. Method lock

1. Freeze failures first (done — §4).  
2. Bind packs (exact files, what is stripped, license) — next operational work.  
3. Assign cards. Two depths per card.  
4. Supervise **measurement**. Do not shop a model to keep a signed score.  
5. Medicine: two doctor workshops beat a year of hospital ethics.

A card without a claim that can fail is not assigned.

---

## 3. Laboratories (hosts, not titles)

| Lab | What it actually is | Student use |
|---|---|---|
| **Carbon / Data Trust** | Governed core: catalog, DQ, MDM, evidence, dataset contracts, health scores. Domain apps sit on top. AASTMT instance and Alamein campus scenario exist. | Grounding, contracts, allocation, teaching tenant |
| **Pulse** | In-hand AI engine. Chat is advisory. Agent writes only with consent. Numbers in an answer must appear in the tool payload. Intelligence is measured; levels that the scorer would deny are not claimed. | Honesty, handoff, write-intent goldens on a **safe** host |
| **Gigacast** | National electrical load + weather. Multi-horizon lattice because actuals go stale. Promotion gates, leak-free holdout, SHAP, load-shedding fairness. | Stale actuals, selective prediction, fairness, faithful XAI |
| **GradeVance / EduOS** | Measure then judge. HITL for summative. Expert edits become versioned packs (κ / canary / publish) — not silent weight updates. Packs: NAA reflective, medicine OSCE/OSPE/CBL. | Assessment, OSCE, coding review queues |
| **Healthy + TurnKey** | Legacy Arabic ERP, large `readable.*` view set, read-only. Pipelines: returns/load-out, churn, demand, AR, transaction-type as a **DQ guard**. Serving, drift, SHAP. | Snapshot only. Never write the ERP. |
| **Alamein teaching tenant** | Org units: Medicine, Hospital, Transport, Finance, Student Hotels. Scopes 1–3 as a Data Trust journey. | Campus as customer; isolation from production brands |
| **College of Medicine** | OSCE/OSPE/CBL faculty, pharmacology, pathology, HIM/coding. Moodle teaching hub exists. | Co-supervision and gold. **Not** a live EHR. |

**Out of the first bank as hosts:** live Nibras/GOFSCO payroll and stores, `med/raw` student spreadsheets, production hospital charts, older agri/CV satellites.

**Nibras / GOFSCO** is a *problem source* (compliance as versioned rules). It is not a classroom database. Students get a synthetic pack or they stay on Alamein / Gigacast / GradeVance / teaching medicine gold.

---

## 4. Problem atlas (frozen)

**Keep (8):** P1, P2, P3, P4, P6, P8, P9, P10  
**Kill for the first bank (2):** P5 (folds into P3/P4 as a requirement, not its own brief), P7 (too engine-internal; later MSc)

Kill means “not in the first announcement,” not “untrue.”

| ID | Failure | Industry cost | Lab | Pack (intent) | Metric |
|---|---|---|---|---|---|
| **P1** | A number is not allowed to be said until it is grounded | A number without provenance becomes a decision, then a liability | Pulse + Carbon / Alamein | Alamein emissions + grounding goldens | Fabrication = 0; every figure cites dataset version or evidence id |
| **P2** | A dataset can be complete and still unfit to train or serve | A green score that never blocks a model poisons training and serving | Dataset Hub + Gigacast or Healthy snapshot | Hourly series with injected contract failures | Promotion blocked when contract fails; false-green rate |
| **P3** | Last truth is late (24–72h) | Operators decide on stale actuals; recursive forecasts leak | Gigacast | Kuwait load + weather (sanitized) | Holdout MAPE by horizon; leak tests; resolver when lag jumps |
| **P4** | The model improved and operations got worse | MAPE down, shedding or collections worse | Gigacast districtshed or Healthy load-out | Shedding scenarios or AR/returns | Accuracy **and** fairness/regret. MAPE-only = fail |
| **P6** | An agent that is helpful on writes is a liability | Silent mutation is a production incident | Pulse on Alamein (not payroll) | Write-intent goldens | 0 silent host mutations; honest handoff |
| **P8** | Judgment that learns without rewriting the past | Last semester’s marks move after a silent update | GradeVance / EduOS | NAA or one OSCE pack | Agreement with expert gold; publish-gate refuses when κ drops |
| **P9** | Shared utilities have no honest owner | Campus electricity / cooling / hospital vs college | Carbon + Alamein | Alamein journey + AASTMT inventory CSVs | Allocation provenance; evidence completeness ≠ calculation correctness |
| **P10** | Compliance is a versioned rule, not a PDF | Audit day: the figure cannot be traced to the rule | Carbon synthetic pack (not live GOFSCO) | Factors/rules or synthetic spec | Every regulated figure → rule version + dataset version |

**Killed**

- **P5 Closed loop** — required on P3/P4/GP-17, not a standalone first-bank brief.  
- **P7 Twelve routers, one turn** — Pulse-internal; later MSc.

---

## 5. Project bank — index (24)

| ID | Title | Cluster | Attacks | Size | Doctor co-supervisor |
|---|---|---|---|---|---|
| GP-01 | Provenance-constrained campus copilot | Trust | P1 | 1–2 | — |
| GP-02 | Contract-gated model promotion | Trust | P2 | 1–2 | — |
| GP-03 | Leak-free load forecasting under delayed actuals | Energy | P3 | 1–2 | — |
| GP-04 | Selective forecasting — when the model must refuse | Energy | P1 · P3 | 1–2 | — |
| GP-05 | Fair load shedding under forecast uncertainty | Energy | P4 | 1–2 | — |
| GP-06 | Consent-bounded enterprise agent | Agents | P6 | 2 preferred | — |
| GP-07 | Bilingual grounded operator assistant | Agents | P1 · P6 | 1–2 | — |
| GP-08 | Accountable assessment — expert edits without retroactive marks | Education | P8 | 1–2 | — |
| GP-09 | Medicine station scoring with hybrid rubrics | Medicine | P8 | 2 preferred | Clinical skills / OSCE lead |
| GP-10 | Semantic layer over a legacy Arabic ERP | Factory | P2 | 2 | — |
| GP-11 | Collections that maximize cash without silent customer damage | Factory | P4 | 1–2 | — |
| GP-12 | Provenanced allocation of shared campus utilities | Campus | P9 | 1–2 | — |
| GP-13 | Scope 3 without the spend-only lie | Campus | P9 · P10 | 1–2 | — |
| GP-14 | Versioned compliance — every figure has a rule | Trust | P10 | 1–2 | — |
| GP-15 | Eval harness as a product | Agents | P1 · P6 | 1–2 | — |
| GP-16 | Explainable forecasts that cannot invent drivers | Energy | P1 · P3 | 1 possible | — |
| GP-17 | Load-out demand with an actuals loop | Factory | P4 · P2 | 1–2 | — |
| GP-18 | Teaching-tenant data trust — Alamein as a living lab | Campus | P1 · P9 · P10 | 2 | — |
| GP-19 | Grounded contraindication checker | Medicine | P1 · P10 | 2 + pharmacologist | Clinical pharmacology / IM |
| GP-20 | Clinical coding from teaching notes | Medicine | P8 · P1 | 2 + coder | HIM / internist who codes |
| GP-21 | OSPE finding encoding — urinalysis to structure | Medicine | P8 · P1 | 1–2 + pathologist | Clinical pathology |
| GP-22 | Finding-grounded differential diagnosis | Medicine | P1 | 1–2 + CBL clinician | Surgery / EM / Y3 CBL |
| GP-23 | Safe-prescription completeness and dose gates | Medicine | P2 · P10 | 1–2 + pharmacologist | Clinical pharmacology / nephrology |
| GP-24 | Arabic clinical encoding | Medicine | P1 · P8 | 2 + bilingual clinician | Bilingual clinician + coding lead |

Each card below uses the same shape: hook, claim that can fail, meat, academic appeal, student appeal, boom seed, lab, pack, Applied, Systems, forbidden cheap answer.

---

## 6. Cards

### GP-01 — Provenance-constrained campus copilot

**Cluster:** Trust · **Attacks:** P1 · **Size:** 1–2 students  

A copilot that is not allowed to say a number it cannot point to.

- **Claim:** Every operational figure in an answer is present in a retrieved payload and cited to a dataset version or evidence id. Fabrication on a golden bank is zero.  
- **Meat:** Grounding, retrieval contracts, citation, refusal when the store is empty. Not prompt craft.  
- **Academic:** Factual consistency and attribution. Examiner sees a scorer, not a demo chat.  
- **Student:** They ship an assistant people will actually try. The flex is that it refuses.  
- **If it booms:** Carbon / Pulse campus product. The honesty layer every enterprise copilot is missing.  
- **Lab:** Pulse + Carbon · Alamein teaching tenant  
- **Pack:** Alamein journey tables + evidence files · Pulse grounding goldens  
- **Applied:** Copilot over Alamein electricity, fuel, water. Golden: 0 invented tCO₂e / kWh.  
- **Systems:** Citation must survive multi-turn anaphora. RBAC: a finance user never sees hospital medical-gas kg.  
- **Forbidden:** RAG chatbot that restates a CSV. Granting extra permissions to pass a test.

### GP-02 — Contract-gated model promotion

**Cluster:** Trust · **Attacks:** P2 · **Size:** 1–2 students  

A green dashboard that cannot stop a bad model is decoration.

- **Claim:** A model version cannot promote if its training or serving dataset fails a published contract (completeness, validity, freshness). False-green rate is measured.  
- **Meat:** Data-centric AI. Contracts as gates, not scores.  
- **Academic:** Data quality as a decision procedure. Data-centric ML and MLOps promotion.  
- **Student:** They fail a model on purpose and that is the win.  
- **If it booms:** Dataset Hub · TurnKey promotion. The gate utilities and factories will pay for.  
- **Lab:** Carbon Dataset Hub + Gigacast datahub (or Healthy snapshot)  
- **Pack:** Gigacast hourly series with injected stale / null / unit-break windows  
- **Applied:** Block promotion on freshness and validity. Show the audit row.  
- **Systems:** Separate data-contract failure from concept drift. Do not un-promote for the wrong reason.  
- **Forbidden:** A completeness KPI with no blocking behaviour.

### GP-03 — Leak-free load forecasting under delayed actuals

**Cluster:** Energy · **Attacks:** P3 · **Size:** 1–2 students  

The last truth is 24–72 hours late. Recursion looks good and cheats.

- **Claim:** Direct multi-horizon forecasts under generation lag beat a recursive baseline on leak-free holdout. Resolver chooses the right horizon when lag jumps.  
- **Meat:** Temporal leakage, origin-anchored pairs, promotion MAPE by horizon.  
- **Academic:** Strong thesis. Leakage is examinable. Comparable to published load-forecasting work.  
- **Student:** Real megawatts, real weather. The project they put on a CV.  
- **If it booms:** Gigacast champion lattice. A ministry-grade engine, not a Kaggle notebook.  
- **Lab:** Gigacast aihub + datahub  
- **Pack:** Kuwait hourly load + weather (sanitize ministry series) · holdout after a cut date  
- **Applied:** Day-ahead + 2-day engines, leak tests, MAPE table by horizon.  
- **Systems:** Add 7-day outlook + resolver when lag jumps. Closed-loop actuals un-promote a stale champion.  
- **Forbidden:** Recursive multi-step. A single MAPE. Training past the cutoff.

### GP-04 — Selective forecasting — when the model must refuse

**Cluster:** Energy · **Attacks:** P1 · P3 · **Size:** 1–2 students  

Knowing when not to speak is more industrial than a better MAPE.

- **Claim:** A selective predictor with conformal or interval guarantees refuses or widens when lag, weather, or drift makes the point forecast unsafe. Coverage is calibrated.  
- **Meat:** Uncertainty, conformal prediction, abstention. Honesty as a statistical object.  
- **Academic:** High examiner appeal. Selective classification / conformal literature is mature.  
- **Student:** They build the model that knows it is lost.  
- **If it booms:** Gigacast intervals + Pulse “I will not invent a MW.”  
- **Lab:** Gigacast · optional Pulse narration of intervals only  
- **Pack:** Same Kuwait series · tagged high-lag and holiday windows  
- **Applied:** Intervals + abstain below a coverage target. Plot coverage vs MAPE.  
- **Systems:** Tie abstention to the promotion gate. Narrate uncertainty without inventing drivers (see GP-16).  
- **Forbidden:** Softmax-as-confidence. Pretty bands with no coverage test.

### GP-05 — Fair load shedding under forecast uncertainty

**Cluster:** Energy · **Attacks:** P4 · **Size:** 1–2 students  

The forecast got better. The city got treated worse.

- **Claim:** A shedding policy evaluated on forecast-plus-actuals dominates a greedy MW-error policy on a fairness/regret metric, without silent starvation of a district.  
- **Meat:** Accuracy is not the objective. Policy under uncertain forecasts.  
- **Academic:** Algorithmic fairness meets operations research. Two metrics, one thesis.  
- **Student:** Hour-by-hour district schedules. The most dramatic demo in the bank.  
- **If it booms:** Gigacast districtshed. Ministries buy fairness they can explain.  
- **Lab:** Gigacast districtshed  
- **Pack:** Forecasts from GP-03 or committed engines + district demand profiles (synthetic if needed)  
- **Applied:** Two policies (e.g. proportional vs priority). Report MAPE and a fairness gap.  
- **Systems:** Policies under interval forecasts (GP-04). Robustness when the forecast is biased.  
- **Forbidden:** MAPE-only leaderboard. A UI for shedding with no metric.

### GP-06 — Consent-bounded enterprise agent

**Cluster:** Agents · **Attacks:** P6 · **Size:** 2 students preferred  

Helpful on writes is a liability. Advice and effect are different jobs.

- **Claim:** On a write-intent bank, Chat never mutates the host. Agent stages a plan, waits for consent, then commits or fails visibly. Silent mutation = 0.  
- **Meat:** Agent safety, authority, handoff. The lesson industry is failing in public.  
- **Academic:** HCI + security of tool-using LLMs. A measurable safety property.  
- **Student:** They get to build an agent — and the grade is that it refuses.  
- **If it booms:** Chat / Agent split as a product pattern other campuses will copy.  
- **Lab:** Pulse on Alamein (data-entry / evidence), never live payroll  
- **Pack:** Write-intent goldens on a teaching tenant  
- **Applied:** Two surfaces. Write-intent → honest handoff. 0 silent host writes.  
- **Systems:** Bound steps with 0 unnecessary LLM calls. Recovery when a staged write dies.  
- **Forbidden:** Confirm in Chat for host APIs. Live payroll as the host. Claiming “it submitted” when only the host UI did.

### GP-07 — Bilingual grounded operator assistant

**Cluster:** Agents · **Attacks:** P1 · P6 · **Size:** 1–2 students  

Arabic in, Arabic out, same number, same citation. Language is not a skin.

- **Claim:** Reply language matches the user, including critic/synthesis. Slot carry works in AR and EN. No figure appears that failed the grounding check.  
- **Meat:** Language fidelity plus grounding. GCC/Egypt operational reality.  
- **Academic:** Multilingual NLG. Code-switching and numeral handling are examinable.  
- **Student:** The assistant operators would actually use.  
- **If it booms:** AR/EN as a wedge across campus, energy, and later clinical teaching UIs.  
- **Lab:** Pulse + Alamein or Gigacast bilingual XAI notes  
- **Pack:** Parallel AR/EN question bank over the same host facts  
- **Applied:** Language golden 100% on a 40-turn bank. Grounding still 0 fabrication.  
- **Systems:** Mixed AR/EN turns. Numerals, units, and org names do not flip language mid-citation.  
- **Forbidden:** Google-translate the English answer. A language toggle that bypasses tools.

### GP-08 — Accountable assessment — expert edits without retroactive marks

**Cluster:** Education · **Attacks:** P8 · **Size:** 1–2 students  

The engine learns. Last semester’s marks do not move.

- **Claim:** Expert corrections become versioned pack proposals. A κ/canary gate refuses activation when agreement drops. Released cohorts stay pinned.  
- **Meat:** HITL learning as config intelligence, not silent fine-tunes. Reproducibility versus validity.  
- **Academic:** Assessment theory, inter-rater reliability, learning analytics.  
- **Student:** Education × AI without the cheap autograder smell.  
- **If it booms:** GradeVance / EduOS. A product a quality board can defend.  
- **Lab:** GradeVance on EduOS  
- **Pack:** NAA reflective gold (expert-coded cycles) under course license — no public student prose  
- **Applied:** Formative run + expert edit + proposal. Show pin of the released cohort.  
- **Systems:** Publish-gate: refuse bump when κ drops. Canary on a held slice before activate.  
- **Forbidden:** One LLM call = grade. Unsupervised fine-tune on student text. Silent regrade.

### GP-09 — Medicine station scoring with hybrid rubrics

**Cluster:** Medicine · **Attacks:** P8 · **Size:** 2 preferred (AI + medical-education pairing)  
**Doctor:** Clinical skills / OSCE lead  

OSCE/OSPE is a checklist and a judgement. Neither is “ask the model for 8/10.”

- **Claim:** A hybrid rubric (quantitative checklist + qualitative bands) agrees with a gold station at a declared κ, with HITL on the summative path.  
- **Meat:** Clinical assessment design. Measurement before judgement.  
- **Academic:** Medical education research. Faculty of Medicine will understand the problem.  
- **Student:** Medicine + AI on their own campus.  
- **If it booms:** EduOS medicine vertical. OSCE/OSPE/CBL packs as a product line.  
- **Lab:** GradeVance · profiles already drafted (abdominal OSCE, urinalysis OSPE, appendicitis CBL)  
- **Pack:** Those profiles, de-identified. No identifiable clinical reflections.  
- **Applied:** One station, checklist + bands, HITL review queue, gold agreement.  
- **Systems:** Two stations, calibration across markers, student-invariant scoring.  
- **Forbidden:** Generic GPT mark. Identifiable student or patient reflections.

### GP-10 — Semantic layer over a legacy Arabic ERP

**Cluster:** Factory · **Attacks:** P2 · **Size:** 2 students  

1,047 decoded views. The model does not get to train on the wrong invoice type.

- **Claim:** A contracted semantic layer (entities, units, transaction classes) over a read-only ERP extract raises downstream fitness and blocks known poison columns.  
- **Meat:** MENA reality: Arabic legacy ERPs, cryptic views, dirty types.  
- **Academic:** Schema matching, ontology, weak supervision. Rare in this region.  
- **Student:** Detective work. They feel like they opened a factory.  
- **If it booms:** Reusable “Arabic ERP → trust layer” for mid-market manufacturing.  
- **Lab:** Healthy snapshot (read-only) + Carbon contracts  
- **Pack:** Bounded view set (invoice lines, items, aging) — never live write  
- **Applied:** Map 8–12 views to 3 contracts. Transaction-type classifier as a DQ guard.  
- **Systems:** Measure lift on one downstream pipeline (returns or AR) when the layer is on vs off.  
- **Forbidden:** SQL dump plus a notebook. Writing to the ERP. Claiming all views were used.

### GP-11 — Collections that maximize cash without silent customer damage

**Cluster:** Factory · **Attacks:** P4 · **Size:** 1–2 students  

AUC is not a collection policy.

- **Claim:** A ranker plus a policy beats a balance-only queue on recovered cash **and** a regret/fairness metric (e.g. small-buyer starvation, false-hardship rate).  
- **Meat:** Cost-sensitive learning. The second metric is the education.  
- **Academic:** Credit scoring + fairness.  
- **Student:** Money, ranking, a queue they can show.  
- **If it booms:** AR pipeline wedge into distributor ERPs.  
- **Lab:** Healthy collections snapshot  
- **Pack:** Customer aging + balances (anonymized accounts)  
- **Applied:** Rank a queue. Report cash proxy and a fairness gap versus greedy.  
- **Systems:** Policy that uses uncertainty. Closed loop if “paid this week” actuals exist.  
- **Forbidden:** F1 on churn with no policy. Real names in a public repo.

### GP-12 — Provenanced allocation of shared campus utilities

**Cluster:** Campus · **Attacks:** P9 · **Size:** 1–2 students  

Who owns the chilled water — college, hotel, or hospital?

- **Claim:** Shared electricity, cooling, and water allocate to org units with an explicit rule version and evidence. Completeness of evidence is scored separately from calculation correctness.  
- **Meat:** Environmental accounting as a data-trust problem. Two scores, one campus.  
- **Academic:** GHG Protocol allocation + information quality.  
- **Student:** Their campus. Medicine, hotels, hospital, transport.  
- **If it booms:** AASTMT Carbon / Alamein tenant. Template for multi-faculty campuses.  
- **Lab:** Carbon emissions + Alamein  
- **Pack:** Alamein journey + AASTMT inventory CSVs (Smart Village, Abu Qir, South Valley)  
- **Applied:** Allocate Scope 1–2 for three org units. Evidence pack per total.  
- **Systems:** Change allocation rule version; show which totals move; pin the old report.  
- **Forbidden:** One campus total. A dashboard with no lineage. Invented emission factors.

### GP-13 — Scope 3 without the spend-only lie

**Cluster:** Campus · **Attacks:** P9 · P10 · **Size:** 1–2 students  

Cost × factor is what everyone ships. It is also what auditors distrust.

- **Claim:** A hybrid Scope 3 method (activity data where evidence exists, spend-based only where it does not) reports coverage and uncertainty, not a fake precise total.  
- **Meat:** Honesty about missing activity data.  
- **Academic:** Hybrid LCA / EEIO. Uncertainty in inventories.  
- **Student:** Sustainability that is not a poster.  
- **If it booms:** Procurement-grade Scope 3, not marketing-grade.  
- **Lab:** Carbon · Alamein finance / procurement  
- **Pack:** Alamein S3 tables + existing campus Scope 3 CSVs — **thin**; students may extend with labelled evidence  
- **Applied:** Split spend-based vs activity-based lines. Report % of tCO₂e that is evidence-backed.  
- **Systems:** Refuse a single-point Scope 3 when coverage is below a gate.  
- **Forbidden:** One spend factor on all procurement. Claiming precision the evidence does not support.

### GP-14 — Versioned compliance — every figure has a rule

**Cluster:** Trust · **Attacks:** P10 · **Size:** 1–2 students  

A PDF policy is not a system. The slip must point to rule R on dataset D.

- **Claim:** Every regulated figure in a teaching inventory or synthetic artifact traces to a versioned rule and a dataset version. Replay after a rule bump changes only what the diff says.  
- **Meat:** Software supply chain for numbers. The compliance thesis without production payroll data.  
- **Academic:** Provenance, reproducibility, computational law.  
- **Student:** Forensic. They feel like auditors.  
- **If it booms:** Compliance plane — carbon-shaped now, payroll-shaped later.  
- **Lab:** Carbon rules + factors (synthetic mid-market pack)  
- **Pack:** Alamein emission factors + calculation rules, or a synthetic WPS-like spec written once  
- **Applied:** Trace 10 figures to rule+dataset. Replay after one bump. Show the diff.  
- **Systems:** Two rule versions live; reports pin; no silent recast of a signed period.  
- **Forbidden:** Live payroll / GOFSCO raw. A compliance essay with no executable lineage.

### GP-15 — Eval harness as a product

**Cluster:** Agents · **Attacks:** P1 · P6 · **Size:** 1–2 students  

If you cannot fail the claim, you do not have a claim. Marketing is not a score.

- **Claim:** A student-built bank plus scorer detects fabrication, silent writes, language drift, and slot-loss. A known-bad prompt or agent fails the gate. A known-good one passes.  
- **Meat:** Measurement culture. The rarest skill in the agent market.  
- **Academic:** Evaluation methodology. Meta, but examinable if the bank is real.  
- **Student:** They become the judge. Portfolio gold.  
- **If it booms:** Golden-bank / gauge product other labs buy.  
- **Lab:** Pulse eval on a teaching tenant  
- **Pack:** A 30–50 item bilingual bank frozen with the team — plus 5 planted failures  
- **Applied:** Scorer + bank + planted bugs. CI-style report. No live model-shopping to buy a score.  
- **Systems:** Separate Chat bank from Agent bank. Worst-of dated runs. A stub never upgrades a miss.  
- **Forbidden:** Accuracy on a vibe rubric. Switching models to keep a signed score.

### GP-16 — Explainable forecasts that cannot invent drivers

**Cluster:** Energy · **Attacks:** P1 · P3 · **Size:** 1 student possible  

SHAP plus a story is still a lie if the story names a feature that was not there.

- **Claim:** Bilingual forecast narratives only mention features present in the attribution payload. A planted missing-feature probe is caught 100%.  
- **Meat:** XAI plus grounding. The pretty plot is not the thesis.  
- **Academic:** Faithful explanation. Easy to score.  
- **Student:** Charts and a gotcha test.  
- **If it booms:** Operator brief in Arabic/English, not raw SHAP.  
- **Lab:** Gigacast XAI + optional Pulse narration  
- **Pack:** Trained engine bundle + feature names locked in the pack  
- **Applied:** SHAP + template narrative. Drop a feature; story must not name it.  
- **Systems:** AR/EN narratives, same features. Consistent with GP-04 intervals.  
- **Forbidden:** LLM “explains” the forecast from a chart image. Unverified weather tales.

### GP-17 — Load-out demand with an actuals loop

**Cluster:** Factory · **Attacks:** P4 · P2 · **Size:** 1–2 students  

A weekly factory plan that never meets last week’s actuals is a slideshow.

- **Claim:** A returns/load-out model, served under a contract, is scored on next-week actuals. Drift or contract break un-promotes or retunes a DQ rule, with an audit row.  
- **Meat:** Closed loop — atlas P5 returned as a factory thesis.  
- **Academic:** Demand models + MLOps feedback.  
- **Student:** Trucks, SKUs, next week.  
- **If it booms:** Distributor / CPG wedge.  
- **Lab:** Healthy + TurnKey bridge  
- **Pack:** Invoice-line snapshot + weekly actuals (or constructed weeks from history)  
- **Applied:** One model, one week-ahead, score on held actuals.  
- **Systems:** Actuals → drift → DQ or un-promote. Show the loop on a calendar.  
- **Forbidden:** Train/test split presented as production. Writing to the ERP.

### GP-18 — Teaching-tenant data trust — Alamein as a living lab

**Cluster:** Campus · **Attacks:** P1 · P9 · P10 · **Size:** 2, or 1 plus supervisor seed work  

The college is not a case-study PDF. It is a governed instance students attack.

- **Claim:** An Alamein teaching tenant with org units, RBAC, evidence, and two data products is complete enough that GP-01, GP-12, and GP-14 can run without touching production brands.  
- **Meat:** Platform thinking. Isolation, capability-based access, seed honesty.  
- **Academic:** Weaker as a lone ML thesis; strong as systems/data-engineering or paired with GP-01.  
- **Student:** They built the lab others use. Risk: intern work — bind to two goldens.  
- **If it booms:** AASTMT Data Trust instance, reusable next year.  
- **Lab:** Carbon AASTMT brand · Alamein seeds  
- **Pack:** Alamein campus materials + AASTMT CSV catalog — sanitized users  
- **Applied:** Tenant, three org units, evidence on two sources, one calculation, one DQ fail.  
- **Systems:** RBAC tours: medical user cannot see finance procurement. Isolation vs other brands.  
- **Forbidden:** A theme. A slide campus. Production GOFSCO or student PII to “make it real.”

---

## 7. Medicine track (GP-09, GP-19–GP-24)

Alamein has a College of Medicine and an educational hospital in the same campus story. GradeVance already has draft profiles: abdominal OSCE, urinalysis OSPE, appendicitis CBL. The mentor can pair AI students with doctors. **Doctors own gold and pack meaning. AI students own the metric (citation, refusal, κ, span). Chat never writes a chart.**

Two pillars the faculty asked for, split so a team can finish in a year:

| Pillar | Cards | One-line |
|---|---|---|
| **Contraindications / safe prescribe** | GP-19, GP-23 | The pack says, or it stays silent. Completeness and dose/renal are a second score. |
| **Medical encoding** | GP-20, GP-21, GP-24 | The span must earn the code. Arabic is a first-class note, not a translation step. |
| **Already in tree** | GP-09, GP-22 | Hybrid OSCE rubrics. Finding-grounded differential on CBL. |

### GP-19 — Grounded contraindication checker

**Doctor:** Clinical pharmacology / internal medicine · **Size:** 2 students + pharmacologist  

The model does not get to invent an interaction.

- **Claim:** On a doctor-gold teaching prescription bank, every alert cites a versioned pack row (drug–drug, drug–disease, allergy, pregnancy). Recall on must-alert cases meets the declared bar. Invented interactions = 0.  
- **Meat:** CDS as data trust. Knowledge is a versioned pack, not a prompt. Alert fatigue is measured.  
- **Academic:** CDS evaluation: precision/recall, citation faithfulness, safety-critical NLP.  
- **Student:** They built the thing that stops a bad combination. Highest-status clinical AI card.  
- **If it booms:** Teaching-then-hospital prescribing safety. Every UG medicine/pharmacy school needs this.  
- **Lab:** Pulse + versioned drug-safety pack (config intelligence, not EHR write)  
- **Pack:** 40–60 UG-curriculum drugs (metformin, warfarin, ACEI, NSAID, methotrexate, …) encoded with doctors in two workshops. 80–120 labelled prescriptions: safe / caution / must-alert. Public labels may seed; doctors freeze the pack version.  
- **Applied:** Given meds + conditions + allergies, emit alerts with pack ids. Must-alert recall and 0 invented pairs.  
- **Systems:** Pack bump does not silently re-label last term’s cases (GP-08 pattern). Alert burden vs a chatty LLM baseline.  
- **Forbidden:** “Ask GPT, is this safe?” Live hospital lists. Writing to a chart. Real patient allergies.

### GP-20 — Clinical coding from teaching notes

**Doctor:** Medical records / HIM, or internist who codes · **Size:** 2 + coding clinician  

A discharge summary is not a billing code. The span must earn the ICD.

- **Claim:** Candidate ICD-10 (or ICD-11) codes from a teaching note are justified by an evidence span. Exact-code and parent-code scores are reported. HITL required before any “assigned” code. No silent billing.  
- **Meat:** Hierarchical classification, span grounding, human-accountable coding.  
- **Academic:** Clinical NLP + coding. Huge literature. Doctors recognise the job.  
- **Student:** Encoding feels like a profession. They can show a highlighted note.  
- **If it booms:** Hospital coding assistant with HITL. Coders are scarce.  
- **Lab:** Review queue (GradeVance-shaped) or Pulse propose + doctor accept  
- **Pack:** 80–120 **synthetic** discharges written by doctors from cases they already teach (appendicitis CBL first). Gold at 3-character and full. Not hospital EHR. Not student PII dumps.  
- **Applied:** Top-k codes + spans. Exact and parent-code F1. Review queue.  
- **Systems:** Refuse a code with no span. Versioned inclusion/exclusion notes.  
- **Forbidden:** Fine-tune on real discharges. A code list with no evidence. “Automated coding” for billing.

### GP-21 — OSPE finding encoding — urinalysis to structure

**Doctor:** Clinical pathology / lab medicine · **Size:** 1–2 + pathologist  

The station already exists. The finding must become a code, not a paragraph.

- **Claim:** Free-text or checklist OSPE urinalysis maps to a closed finding set (nitrite, leukocyte, blood, protein, microscopy, …) with units and qualifiers. Unstated findings are not invented.  
- **Meat:** Structured reporting. Smaller than ICD, so it finishes.  
- **Academic:** Information extraction + controlled vocabulary. Good first pairing if GP-20 feels large.  
- **Student:** A real OSPE. Pathologists will sit with them.  
- **If it booms:** Lab-report structuring for teaching labs, then hospital labs.  
- **Lab:** GradeVance `medicine_ospe_urinalysis_v1` + finding codebook  
- **Pack:** Existing OSPE profile + 40–60 doctor-written result slips. No patient LIS dumps.  
- **Applied:** Extract to codebook. Exact-slot accuracy. 0 invented cells.  
- **Systems:** Ranges and units as a contract. Out-of-range vs missing vs not-performed are different failures.  
- **Forbidden:** LLM fills a lab form from a vibe. Identifiable student OSPE scripts.

### GP-22 — Finding-grounded differential diagnosis

**Doctor:** Surgery, emergency, or Year-3 CBL lead · **Size:** 1–2 + CBL clinician  

No finding in the note, no place on the differential. Appendicitis is already in the tree.

- **Claim:** Ranked differentials only use findings present in the case. A planted extra-diagnosis that requires an absent finding is rejected. Doctor gold on a CBL bank.  
- **Meat:** Grounded clinical reasoning. The LLM disease-list is the cheap answer this card kills.  
- **Academic:** Diagnostic reasoning evaluation. Faculty-readable.  
- **Student:** The “AI doctor” project that is actually honest.  
- **If it booms:** CBL / ward-round copilot that teaches, not hallucinates.  
- **Lab:** GradeVance `medicine_cbl_appendicitis_v1` + Pulse citation  
- **Pack:** CBL brief + 30–50 doctor-written variants (ectopic, mesenteric adenitis, pyelo, …) with gold DDx and required findings.  
- **Applied:** DDx + cited findings. 0 diseases that need missing findings.  
- **Systems:** Must-not-miss list as a pack: refuse to drop them when findings allow; never invent them when they do not.  
- **Forbidden:** ChatGPT differential from the title “RIF pain.” Real ED notes. Advising treatment as if on the ward.

### GP-23 — Safe-prescription completeness and dose gates

**Doctor:** Clinical pharmacology / nephrology · **Size:** 1–2 + pharmacologist (may share GP-19)  

Contraindication is one failure. An incomplete or renal-blind script is another.

- **Claim:** A teaching prescription is scored on completeness (drug, dose, route, frequency, duration, indication) and on dose-range / renal / age gates from a versioned monograph pack. Failures name the missing slot or the pack row.  
- **Meat:** Prescribing as a contract. Completeness versus safety — two scores.  
- **Academic:** Undergraduate prescribing assessment (WHO-style rights). Very doable gold.  
- **Student:** Pairs with GP-19. A full “safe prescribe” studio if two teams share the pack.  
- **If it booms:** e-prescribing teaching OSCE, then CPOE checks that cite a pack.  
- **Lab:** Same safety-pack family as GP-19  
- **Pack:** Monographs for the same 40–60 UG drugs: usual dose, max, renal adjustment, paediatric flag. 60 incomplete-or-wrong-dose scripts gold-labelled.  
- **Applied:** Slot completeness + dose-gate pass/fail with pack citation.  
- **Systems:** eGFR as an input contract: if missing, refuse renal-risk drugs instead of guessing.  
- **Forbidden:** One “looks fine” score. Live e-prescriptions. Invented dose ranges.

### GP-24 — Arabic clinical encoding

**Doctor:** Bilingual clinician + coding lead · **Size:** 2 + bilingual clinician  

The note is Arabic. The code is international. The span must still be in the note.

- **Claim:** ICD (or problem-list) candidates from Arabic teaching notes cite Arabic evidence spans. Codes are not assigned from an English paraphrase the model invented.  
- **Meat:** MENA-specific clinical NLP. Encoding plus language fidelity.  
- **Academic:** Arabic medical NLP is under-served. Regional journals will care.  
- **Student:** Doctors write how they actually write.  
- **If it booms:** Arabic problem-list / coding helper. A GCC product, not a US MIMIC clone.  
- **Lab:** GP-20 pipeline with an Arabic note bank  
- **Pack:** 40–80 doctor-written Arabic teaching notes (same cases as GP-20, not hospital scans). Gold codes + span offsets. Course license only.  
- **Applied:** Top-k codes + Arabic spans. Parent-code credit. 0 English-only justification.  
- **Systems:** Mixed AR/EN notes (labs in English, history in Arabic). Same grounding rule.  
- **Forbidden:** Translate to English, code, throw the Arabic away. Real clinic notes. Identifiable student PBL.

### Doctor workshops (this is what makes medicine doable)

Do not wait for hospital ethics. Two afternoons with colleagues beats a year of EHR access. They write teaching gold. Students build the scorer.

| Workshop | Who | What they freeze | Feeds |
|---|---|---|---|
| 1 · Safety pack | Clinical pharmacology | 40–60 UG drugs + interaction / pregnancy / renal rows | GP-19 · GP-23 |
| 2 · Prescription gold | Same + internist | 80–120 scripts: safe / caution / must-alert / incomplete | GP-19 · GP-23 |
| 3 · Coding gold | HIM or internist who codes | 80–120 synthetic discharges + ICD + spans | GP-20 · GP-24 |
| 4 · Station / CBL | OSCE lead, pathologist, CBL tutor | Urinalysis slips + DDx variants on the appendicitis family | GP-09 · GP-21 · GP-22 |

**If only one doctor this month:** clinical pharmacology → GP-19. That is the seed that can boom.

---

## 8. What was added beyond the atlas (on purpose)

The eight kept failures are the spine. These cards are what a student can fall in love with without becoming an intern on a product backlog.

| Card | Why it exists |
|---|---|
| GP-04 | Uncertainty / refusal — academic gold, student magnet |
| GP-07 | AR/EN fidelity — regional realism |
| GP-09 | Medicine station — Alamein identity, packs already drafted |
| GP-10 | Arabic ERP semantic layer — the view-set goldmine as a thesis |
| GP-15 | Eval as product — measurement culture, teachable and sellable |
| GP-16 | Faithful XAI — pretty enough for students, strict enough for a viva |
| GP-17 | Closed loop as a factory thesis, not an atlas duplicate |
| GP-18 | Teaching tenant other cards sit on — only if bound to goldens |
| GP-19 | Contraindications — doctor-owned pack, 0 invented interactions |
| GP-20 | ICD encoding — spans, HITL, no billing |
| GP-21 | OSPE urinalysis → structure — smallest medicine card that still finishes |
| GP-22 | Finding-grounded DDx — CBL already in tree |
| GP-23 | Prescription completeness + dose/renal — sister of GP-19 |
| GP-24 | Arabic clinical encoding — MENA-specific |

---

## 9. What this bank refuses

- Campus ChatGPT / library bot  
- Fine-tune a base model on student or clinical prose  
- Rebuild Pulse or Gigacast as the title  
- Fruit-disease CNN and other old satellites  
- Live payroll, GOFSCO raw, `med/raw` student sheets  
- A pretty campus digital twin with invented totals  
- “ChatGPT, diagnose this / is this safe / auto-code this chart”  
- Hospital EHR, LIS, or identifiable student OSCE/PBL scripts  
- Six teams all doing agents (the viva looks like a club)

---

## 10. First cohort mix

If you start with six teams, mix the room so the viva panel sees a college.

| Team | Give them | Why |
|---|---|---|
| A | GP-03 | Flagship energy · hardest ML · boom path |
| B | GP-06 | Flagship agent · safety, not a toy |
| C | GP-19 + pharmacologist | Contraindications · highest clinical value |
| D | GP-20 or GP-24 + coder | Encoding · hospital-shaped, teaching text only |
| E | GP-09 or GP-22 | OSCE / CBL · skills and reasoning faculty |
| F | GP-01 or GP-12 or GP-04 | Campus trust or the theoretically loud energy card |

Pair two students on GP-06, GP-09, GP-10, GP-18, GP-19, GP-20, GP-24 when you can.

---

## 11. Supervision rules

1. The supervisor assigns the pack and the failing metric. Students do not shop a model to keep a signed score.  
2. Industrial systems stay the laboratory. A student repo may integrate; it must not become a silent product branch. The student keeps the claim.  
3. No GOFSCO raw, no `med/raw` student sheets, no live ERP writes, no hospital EHR/LIS, no identifiable OSCE/PBL on a public GitHub.  
4. Medicine: the doctor owns gold and pack meaning. The AI student owns citation, refusal, κ, and spans. Chat never writes a chart.  
5. A card without a claim that can fail is not assigned.  
6. Sanitize ministry load/weather before class use. Healthy is snapshot, read-only. Gold packs stay under course license.

---

## 12. Packs that can face students (intent)

| Pack | Role | Care |
|---|---|---|
| Kuwait load + weather | GP-03, GP-04, GP-05, GP-16 | Sanitize ministry series; license |
| AASTMT GHG CSVs + Alamein journey | GP-01, GP-12, GP-13, GP-14, GP-18 | Campus-real; still governed |
| NAA reflective gold | GP-08 | Student prose is sensitive; course license |
| Medicine OSCE/OSPE/CBL profiles | GP-09, GP-21, GP-22 | De-identify; doctor freeze |
| Doctor-written safety + coding gold | GP-19–GP-24 | Teaching cases only; no EHR |
| Healthy ERP snapshot | GP-10, GP-11, GP-17 | Read-only extract; anonymize accounts |
| GOFSCO raw / med student sheets | — | **Out.** Problem stories only |

Exact file binding (paths, strip list, license text) is the next operational step after this review — not required for Fable to judge the *shape* of the bank.

---

## 13. Journey status

| Phase | What | Status |
|---|---|---|
| 0 Audit | Systems, repos, datasets. Unit is failure, not repo. | Done |
| 1 Atlas freeze | Keep 8, kill 2. Four lines each. | Done |
| 2 Project bank | 24 cards, two depths, medicine track | This document |
| 3 Pack binding | Exact student files, strip, license | Next after review |
| 4 Teaching tenant + doctor workshops | Alamein instance; pharmacology/coding gold | After packs |
| 5 Supervise | Students attack a golden. Mentor keeps the product. They keep the claim. | Delivery year |

---

## 14. Review questions (for Fable)

Please review as a programme architect and as an examiner, not as a feature backlog.

1. **Doability.** Which cards are too large for one BSc year even with a doctor? Which are too small to defend?  
2. **Academic strength.** Which claims would survive a viva? Which still sound like intern work (especially GP-18)?  
3. **Student appeal vs meat.** Does the mix still teach grounding, leakage, consent, HITL — or will the room collapse into chatbots?  
4. **Medicine ethics.** Is “doctor-written teaching gold, no EHR” the right line, or should any card wait for IRB?  
5. **Overlap.** Should GP-19 and GP-23 be one team with two metrics? GP-20 and GP-24 one pipeline with two languages?  
6. **Gaps.** What valuable, doable failure is missing (imaging, vitals time-series, timetable/OSCE logistics, Arabic drug names, etc.) that still respects the refuse list?  
7. **First six.** Is the cohort mix in §10 the right opening, or should energy yield a seat to a second medicine team?  
8. **Boom vs college.** Where does “seed for a production system” start to steal the student’s thesis?

---

## 15. One-sentence law

**A number, a code, an alert, a mark, or a write is not allowed until a pack, a span, a consent, or an evidence id can carry it — and the student must be able to fail that test in public.**
