# GradeVance — An Amazing Professor Journey

**Status:** Product vision + UX north star (implementation = Phase A→D in lifecycle plan)  
**Date:** 2026-09-18  
**Instance:** EduOS · App: GradeVance  
**Companion canvas:** *GradeVance Amazing Professor Journey* (beside chat)  
**Build plan:** [GRADEVANCE-PROFESSOR-LIFECYCLE.md](./GRADEVANCE-PROFESSOR-LIFECYCLE.md)  
**Parent design:** [GRADEVANCE-DESIGN.md](./GRADEVANCE-DESIGN.md) · ADR-0038  

---

## 0. North star (one line)

**Design the intention → prove the instrument → measure meaning → judge with humans → release with ceremony → improve the engine on purpose.**

Amazing is not “more AI.” Amazing is one continuous object graph, measurement before judgment, and HITL that compounds as versioned intelligence — without tool salad.

---

## 1. Enterprise research — steal / refuse

### Steal from the best

| System | Wisdom to keep |
|--------|----------------|
| **Gradescope** | Grade by criterion across the cohort; shared dynamic rubrics; parallel markers; **one workbench** |
| **Canvas SpeedGrader** | Submission + rubric + comments in one pane; block “done” if criteria incomplete |
| **Turnitin Feedback Studio** | Rich feedback studio — only if it is **the** grade of record (never a second SoR) |
| **Inspera** | Author → moderate → mark → **Confirm/release** as a known ceremony |
| **FeedbackFruits** | Staged paths; schedule when feedback appears; reward process, not one dump |
| **Avalon / Co-TA (research)** | Calibrate AI to the professor first; triage uncertainty; see cohort impact before live stakes |

**Winning pattern:** one object graph · one marking surface · explicit release · humans own stakes.

### Refuse (common enterprise flaws)

| Flaw | Where it shows | GradeVance stance |
|------|----------------|-------------------|
| Tool salad / dual gradebooks | Canvas score ≠ Turnitin score | GradeVance = SoR; LMS = passback only |
| Setup after submissions open | Late Gradescope link breaks the run | Stem + profile pin before publish; fail closed |
| Judgment without measurement | Rubric/LLM score with no theory of meaning | LCT SG/SD wave before band when theory applies |
| Silent AI drift | Model/prompt changes mid-cohort | Proposal → bump → re-pin; released cohorts immutable |
| Micro-HITL only | Fix one paper; never prove the instrument | Held-out κ + teaching pulse before summative |
| Death by settings | LMS option sprawl | One stem form; advanced = progressive disclosure |
| Feedback dump | Everything on due day | Formative trajectory; summative release deliberate |
| Admining from student playground | Thin demos conflate roles | Student desk ≠ professor hub |

---

## 2. The amazing week (narrative)

```
Compose intention → Prove instrument → Receive thinking → HITL seminar
        → Teach from the pulse → Release + govern
```

### 01 — Compose the assessment intention
Open **Courses & stems**. Name the course. Write the **stem students will see**. Pin a profile (`discipline × genre × level`). Mode = formative this week. Pipeline freezes at publish. No scavenger hunt for “where LCT lives.”

### 02 — Prove the instrument before stakes
**Calibration:** held-out gold vs engine SG/SD, κ on the wall. Weak κ → Proposals / pack fix — not silent threshold cheating. Summative publish **fails closed** until the gate says go.

### 03 — Receive thinking, not just files
**Assignment hub.** Analyze. **Run workbench:** semantic wave, SG/SD table, rubric draft, coaching. You *see* meaning before you touch a band.

### 04 — Mark like Gradescope, teach like a seminar
Queue by uncertainty. Edit a code with rationale (ExpertEdit). Shared criteria for markers. Coaching stays watermarked until you mean it.

### 05 — Teach from the pulse
Cohort pattern: flat waves, missing NOW WHAT. Five-minute teaching note. Students revise. Trajectory > single dump.

### 06 — Release with ceremony; learn on purpose
Explicit **Release**. Optional LMS passback — GradeVance remains SoR. Clustered edits → Proposal → Accept → bump → re-pin. Next cohort smarter; **this** cohort’s marks stay honest.

---

## 3. Signature moments only GradeVance can own

| Moment | Why competitors cannot copy it cheaply |
|--------|----------------------------------------|
| **The wave reveal** | Reflective SG/SD oscillation + coaching that names the missing SO WHAT — not a gradebook cell |
| **The κ wall** | Summative publish blocked on weak held-out agreement — trust through pain, once |
| **The governed promotion** | Marker corrections → Proposal → bump → re-pin — inspectable, versioned, no silent mid-term regrade |
| **Dual-mode honesty** | Formative coaching watermark vs summative release ceremony — same engines, different stakes |

---

## 4. Screen map (journey → UI)

| Journey beat | Primary surface | Primary CTA |
|--------------|-----------------|-------------|
| 01 Compose | Courses & stems | Publish assignment |
| 02 Prove | Calibration | Use profile in stem |
| 03 Receive | Assignment hub → Run workbench | Analyze / Open run |
| 04 Mark | Marking queue → Run workbench | Save ExpertEdit / Resolve |
| 05 Teach | Overview (cohort pulse) | Open Courses / Marking |
| 06 Release + learn | Run workbench → Proposals | Release · Accept → Bump → Re-pin |

**Invariant:** professors never administer a cohort from Student desk.

---

## 5. Implementation status

| Beat | Backend | UI |
|------|---------|-----|
| Courses & stems | ✅ | ✅ Phase A |
| Assignment hub | ✅ detail API | ✅ Phase A |
| Run workbench + HITL | ✅ edits/release | ✅ Phase A |
| Calibration κ | ✅ preview API | ✅ Phase A |
| Proposals loop | ✅ | ✅ linked |
| Cohort teaching pulse | partial | Phase B+ |
| File upload / KB CRUD | .txt upload + KB pin | Full KB chunks Phase D+ |
| Role-gated nav | ✅ ROUTE/MENU caps | Done Phase C |

See [GRADEVANCE-PROFESSOR-LIFECYCLE.md](./GRADEVANCE-PROFESSOR-LIFECYCLE.md) §10.

---

## 6. Related

- Lifecycle IA + screen contracts: [GRADEVANCE-PROFESSOR-LIFECYCLE.md](./GRADEVANCE-PROFESSOR-LIFECYCLE.md)
- Product thesis: [GRADEVANCE-DESIGN.md](./GRADEVANCE-DESIGN.md)
- LMS soak (deferred): [LMS-SOAK.md](./LMS-SOAK.md)
- ADR-0038 · RULE_31 · RULE_32 · RULE_33 (professor journey IA)
