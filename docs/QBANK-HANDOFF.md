# QBank / EdOS — Handoff Prompt (for Opus or any peer model)

Paste the block below verbatim to bring another model up to speed. It is written
to be self-contained and to stop re-litigating already-locked decisions.

---

```
You are joining as a technical peer on a next-generation medical-education
system for the College of Medicine at AASTMT. Here is the context so we can
pick up mid-design without re-explaining.

VISION
EdOS — an AI-native education operating system built app-by-app on an existing
"Data Trust Platform" (DTP) + an AI engine called "Pulse". The DTP already
provides: MDM (org-unit tree + reference taxonomies), Data Quality rules,
org-scoped RBAC, governance/audit events, dual-language (EN/AR + RTL), and a
domain-app extension seam. Pulse is a stateless AI engine (LLM routing, KG,
memory, six-witness pipeline) exposed per-app via declarative "domain manifests".

THE APP FAMILY (phased, not big-bang)
1. LAGNA (exists, will be rebuilt) = exam SEATING/logistics: distribute students
   into rooms, emit per-room "لجنة" sheets (DOCX/XLSX). No question content.
2. QBANK (current focus) = the question bank: a centralized, versioned, auditable
   store of medical questions + learning outcomes + standards. NO exams, NO
   student data.
3. MEDMENTOR (later) = mentorship (mentor/mentee, notes, goals, slots).
4. OSCE (later) = assessment circuits; consumes QBank questions + Lagna logistics.

LOCKED QBANK DECISIONS (do not re-litigate)
- Typed Django models (system-of-record), NOT JSON/dataschema rows.
- Learning outcomes = a hierarchical typed tree (OutcomeFramework → Outcome,
  parent self-FK), multi-framework (institutional PLO/ILO, NARS/NAQAAE, ACGME).
- Item-writing rules = DATA, split in two: scalar-field rules → DQ engine
  (ModelRuleAssignment); relational invariants (exactly one correct option,
  3-5 options, no "all/none of the above", unique stem-hash) → model clean()/service.
- Flaws are ENFORCED at write time, not suggested — and "flaws" includes the
  systemic failures of incumbent banks (vendor lock-in, QTI fragmentation,
  black-box psychometrics, closed taxonomies, no versioning, weak provenance,
  duplicate explosion, blueprint-as-afterthought, ungoverned AI, PII-entangled).
- Accreditation-grade audit: every lifecycle transition emits a GovernanceEvent;
  publish snapshots an immutable QuestionVersion.
- AI = LAST wave and it's Pulse: generate_item / generate_distractors /
  review_item / tag_suggest / blueprint_gap. AI drafts/flags only, never mutates.
- CONFIG-NOT-CODE: everything domain-specific (types, taxonomies, frameworks,
  flaws, rules, blueprints, lifecycle, RBAC, AI capabilities) is data/config;
  only the generic engine is code.
- INVARIANT-0: student data is FORBIDDEN in QBank (most protected class). It
  lives only in Lagna / future exam-delivery.

CURRENT STATE
Full design written in docs/DESIGN-QBANK.md. Next steps: write ADRs 0027/0028/0029,
then Phase 0 build plan (register the qbank app + seed taxonomies + outcome
frameworks). No implementation code has been written yet.

Please read the existing design before proposing changes, and flag anything that
contradicts the locked decisions above.
```
