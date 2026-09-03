# User Stories, Journeys & Acceptance
# Read by: Product/UX Designer (authors these) + Master Architect (decomposes them).
# A feature is not ready to build until it has a story, a flow, and acceptance criteria.

---

## User Story Format

```
As a <specific user role>,
I want to <accomplish a goal>,
so that <the value / why it matters>.
```

Bad:  "As a user, I want a dashboard." (no goal, no value)
Good: "As an ML engineer, I want to see accuracy drift over 30 days, so that I can
       retrain before a model degrades in production."

### INVEST test (a good story is)
- **I**ndependent — buildable without waiting on another story
- **N**egotiable — describes intent, not implementation
- **V**aluable — a real user gains something
- **E**stimable — the team can size it
- **S**mall — fits in one delivery slice
- **T**estable — has clear acceptance criteria

---

## Acceptance Criteria (Given / When / Then)

```
Scenario: <name>
  Given <starting context/state>
  When  <the user does X>
  Then  <the observable outcome>
  And   <any additional guarantee>
```

Every story lists the happy path AND the key edge cases:
- Empty state (no data yet)
- Error state (operation fails)
- Permission/scope (user can only see their own data)
- Boundary (max/min, large inputs, slow network)

---

## User Journey / Workflow Map

For any multi-step feature, map the journey before designing screens:

```
Entry point → Step 1 → Step 2 → ... → Success
                 │         │
              (error?)  (drop-off risk?)
```

For each step capture: user goal, input needed, system response, failure/exit, next.
Flag friction points and drop-off risks — those are where UX effort pays off.

## Information Architecture (before screens)
- What are the core objects the user thinks in? (models, datasets, runs, reports…)
- How do they relate? (list → detail → sub-detail)
- Where does each task live in the nav? (map to ux-patterns.md navigation model)

---

## Definition of Ready (before a story enters a build phase)
- [ ] User role + goal + value stated (the story)
- [ ] Acceptance criteria written (happy path + edge cases)
- [ ] Journey/flow mapped if multi-step
- [ ] IA placement decided (where it lives in nav)
- [ ] Data & endpoints identified (hand-off to Master Architect / Backend)
- [ ] Design patterns identified (which ux-patterns.md + design-system primitives)

## Definition of Done (feature-level, UX view)
- [ ] All acceptance scenarios pass
- [ ] All 4 data states implemented (design-system RULE 4)
- [ ] Keyboard + a11y verified (WCAG AA)
- [ ] Consistent with ux-patterns.md (no reinvented interactions)
- [ ] Empty/error states give the user a next step

---

## Story Template (copy per feature)

```markdown
## Story: <short title>
**As a** <role> **I want** <goal> **so that** <value>.

### Acceptance
Scenario: happy path
  Given ... When ... Then ...
Scenario: empty
  Given no data ... Then show empty state with next action
Scenario: error
  Given the operation fails ... Then show actionable error + retry

### Journey (if multi-step)
Entry → ... → Success   (note friction/drop-off points)

### IA / placement
Lives under: <nav location>

### Hand-off
Data/endpoints: <...>   Patterns: <ux-patterns sections>   Primitives: <design-system>
```

---

*Source: ~/ai-toolkit/shared/user-stories.md — shared across all projects*
