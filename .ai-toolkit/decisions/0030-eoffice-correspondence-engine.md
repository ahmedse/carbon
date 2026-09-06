# ADR-0030 — e-Office Correspondence & Approval Engine (shared workflow spine)

- **Status:** Accepted
- **Date:** 2026-09-06
- **Deciders:** Master Architect
- **Area:** backend + frontend — new `correspondence` app; `people` self-service;
  new `my` / `team` frontend surfaces (cross-cutting platform capability)

## Context

Nibras (People & Payroll instance) needs employee self-service: request leave,
view payslip, update profile, track loans. But "self-service" is not an HR
feature — the same primitive (a form that is created, routed for approval,
tracked, edited, rejected, and archived, leaving an immutable trail) recurs
across every future domain app (Finance expense claims, Procurement requests,
official internal memos). Building it inside `people` would hard-wire a
cross-cutting capability into one domain and force every future app to
re-implement routing and approval.

The gold-standard framings are **Workday's Business Process Framework** (every
action is a routed Business Process = Definition + Steps + role Routing +
Condition Rules + Approval Chain + Delegation + immutable Process History) and,
for the Gulf/Kuwait government+enterprise context, the **e-Office /
e-Correspondence** model (official reference numbers, memo types, for-action vs
for-info routing, delegation/تفويض, e-signature/توقيع إلكتروني, Arabic RTL).

The Trust Platform already exposes the right seams for a *trust-native* engine:
`mdm.ReferenceSet`/`ReferenceValue` (governed enums, ADR-0027), `dq` typed gate
(`ModelRuleAssignment`, ADR-0025), `catalog.emit_governance_event` (decoupled
audit half, ADR-0025), and `mdm.OrgUnit` scoping (RULE_12). The `people` app
already uses all four.

## Decision

Build a **single shared `correspondence` engine app** — the e-Office
Correspondence & Approval spine — that any domain app plugs into. It is
**trust-native by construction** and **config-as-data** (workflows are DB rows,
not code).

1. **One engine, many domain request types.** Domain apps own the *definition*
   (their form fields + which policy applies); the `correspondence` app owns the
   *runtime, routing, approvals, delegation, reference numbering, and audit*.

2. **The routed thing is `Correspondence`** — one typed entity presented by
   `CorrespondenceType` (ReferenceSet-backed) as a **Request (طلب)** for
   self-service asks or a **Memo/مذكرة** for official correspondence. Both share
   one runtime and one audit trail (ServiceNow's single-`task`-base pattern).

3. **No `GenericForeignKey`.** The link from a `Correspondence` to its domain
   subject uses `subject_type` (`"app.Model"` label) + `subject_id` (int),
   resolved via `apps.get_model` — mirroring `people.PersonnelEvent` and
   `dq.ModelRuleAssignment` (ADR-0025 forbids generic FKs).

4. **Governed enums are FK to `ReferenceValue`** (ADR-0027): `correspondence_type`,
   `leave_type`, `memo_type` become reference sets carrying policy metadata, not
   `CharField` codes.

5. **Config-as-data workflows.** `WorkflowPolicy` + `WorkflowPolicyStep` rows
   define states, ordered steps, role-based routing (manager | hr | specific
   role), skip/condition rules, cancel window, and visibility. HR edits flow
   without a deploy. Policy version is frozen onto each `Correspondence` at
   submit time (in-flight items keep their rules).

6. **Trust-native seams (reuse, don't reinvent):** submit is gated by the `dq`
   typed gate; every action emits `emit_governance_event` (the immutable Process
   History); governed enums bind `mdm.ReferenceSet`; org scope via `mdm.OrgUnit`.

7. **e-Signature is a designed seam, not v1 code.** Models carry a nullable
   `signature` linkage and the API/UI reserve the affordance, clearly marked
   "PKI e-signature — future phase." Reference numbers, memo types, delegation,
   and for-action/for-info routing ARE in the design from day one.

8. **Three peer surfaces over one engine.** `my` (ESS, "About me"), `team` (MSS,
   "About my reports": Approvals Inbox + team views), and existing domain-admin
   apps ("About everyone"). `my`/`team` are new frontend manifest apps; their
   backend reads are self/hierarchy-scoped endpoints on `people` + the generic
   `correspondence` API.

## Alternatives Considered

- **Build self-service inside `people`** — rejected: hard-wires a cross-cutting
  capability into one domain; every future app re-implements routing/approval.
- **Adopt a BPMN engine (Camunda/Flowable)** — rejected: heavyweight, external
  runtime, no trust-core integration, poor Arabic/e-office fit.
- **`GenericForeignKey` for the subject link** — rejected: ADR-0025 (repo avoids
  generic FKs); use `model_label` + `id`.
- **Store request payloads in `dataschema.DataRow`** — rejected for owned request
  state (ADR-0025): typed `Correspondence` with a validated JSON `payload` +
  reference-set FKs gives referential integrity and org-scope. `dataschema` stays
  for inbound governed *measurements*, not request forms.

## Consequences

- **Positive:** one audited, governed, config-driven spine reused by every domain
  app; Gulf/e-office vocabulary and expectations met; e-signature ready as a seam;
  no new audit/governance infrastructure (reuses `catalog`/`dq`/`mdm`).
- **Negative / trade-off:** a new core app + a schema migration to move
  `leave_type` (and siblings) to `ReferenceValue` FKs; domain apps must register a
  `WorkflowPolicy` + form schema to participate.

## Related

- Canonical spec + phased plan: `docs/DESIGN-EOFFICE-CORRESPONDENCE.md`
- Builds on: ADR-0025 (typed vs dataschema), ADR-0027 (governed lookup FK),
  ADR-0015 (multi-instance), ADR-0016 (domain-app manifest contract),
  ADR-0018 (dual-language i18n + RTL), ADR-0029 (compensation ledger).
