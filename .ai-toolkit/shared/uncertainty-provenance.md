# Uncertainty Provenance — The Confidence-Conservation Contract

**How every AI system carries, degrades, and never fabricates certainty across its
own boundaries.** Governs every seam where a value crosses a stage: tool calls,
retrieval, memory reads, context assembly, sub-agent handoffs, intent routing.

This is the contract behind `ai-tools.md` and intent routing — the layer *underneath*
"which tool / which zone". It is about what happens to **not-knowing** as data flows.

---

## The defect it prevents (state it exactly)

> A value whose epistemic status is **absent / low-confidence / assumed** gets silently
> re-typed as **known**, and a downstream stage narrates it with full confidence.

This is the single root cause of agent hallucination. The model is not "lying" — it is
faithfully rendering a value whose *uncertainty was erased upstream*. Python sees
`dict → dict → str`; the epistemic collapse is invisible to the type checker and to the
model. Examples of the same defect wearing different clothes:

- Geocoder returns `{}` → treated as "no data" → fall through → answer about something else.
- DB lookup on a synonym returns `[]` → "nothing found" instead of "I didn't understand the term".
- Retrieval returns 0 hits → model synthesizes from memory instead of "I searched, found nothing".
- `try/except` swallows an error → pipeline continues on a fabricated default.
- Truncated context → model "fills in" the missing middle.
- A default parameter masks a *missing* required one.

---

## The law (non-negotiable)

**1. Conservation of confidence.**
> No stage may emit confidence higher than the **minimum** confidence of the inputs it
> consumed. Certainty can be *lost* downstream, never *manufactured*.

Every hallucination is a violation of this law — a **confidence-amplifying junction**
where a low-certainty input produced a high-certainty output. If you instrument one
thing, instrument this: does `confidence_out > min(confidence_in)`? A "yes" is the bug.

**2. Absence is a value, not a gap.**
> `no_match`, `empty`, `timeout`, `truncated`, `unauthorized` are **distinct first-class
> results**, each routed to a *different* handler. Collapsing any of them into a falsy
> value (`None`, `[]`, `{}`, `""`) is the original sin. In particular:
> **`empty` (resolver did not understand the entity) ≠ `none` (understood, genuinely
> zero results).** They are opposite signals and must never share a branch.

**3. The unknown routes up; the known routes down.**
> Open-vocabulary decisions (entity resolution, intent, disambiguation) **escalate** to a
> layer that can reason — the LLM, then the human. Closed-vocabulary decisions **descend**
> to deterministic code. The bug is always motion in the wrong direction: an unknown that
> went *down* into a deterministic actor, which then guessed.

**4. On no-match, decide — never act.**
> When a resolver returns `no_match`, the LLM may only **normalize / ask / declare
> unknown**. It may NEVER **act** on the gap (invent coordinates, fabricate a row,
> hallucinate a reading). Deciding is safe; acting on a gap is fabrication.

---

## The required shape: tri-state results at every boundary

Every deterministic primitive returns **three states, never two**:

| State | Meaning | Handler |
|---|---|---|
| `resolved(data)` | understood + found | proceed downstream |
| `no_match(reason, hint?)` | did NOT understand the entity/intent | **escalate up** — LLM normalizes or asks |
| `error(cause)` | understood, but the fetch/compute failed | **report** the failure; never substitute |

`no_match` is a *type*, not a control-flow branch — it must be impossible to implicitly
coerce into `resolved`. A truthiness check (`if result:`) that lumps `no_match` with
`error` and `empty` is the anti-pattern.

---

## Why the tempting fix is always wrong

The bug lives at the **meta level** (how the system handles its own not-knowing). The
tempting fixes live at the **object level** (add a tool, add an alias, add a synonym).
Object-level fixes scale linearly with an infinite world; meta-level fixes are constant —
*one* rule for "what happens when a resolver doesn't resolve" covers regions, typos,
synonyms, ambiguous terms, and every entity you haven't imagined.

**Tell that you're about to make the mistake:** you're *enumerating instances of the
unknown* (a second alias, a third special case). The moment you write the second entry,
you've conceded the vocabulary is open — and an open vocabulary is met by a *procedure for
not-knowing*, never a *bigger list*.

---

## Architectural properties this demands

- **Provenance is conserved.** Every value crossing a boundary carries *where it came
  from* and *how sure it is*. Degrade it freely; never upgrade it silently.
- **Absence is first-class.** Distinct results for no-match / empty / timeout / truncated /
  unauthorized, each with its own handler.
- **Escalation is mandatory, not optional.** A "no match" that falls through to a plausible
  answer is how an agent hallucinates *without ever being detectably wrong*.

One line:

> **Hallucination is a conservation-of-confidence violation caused by erasing the
> epistemic type of a value at a boundary — so the cure is not more capability, it is
> making "I don't know" impossible to silently discard.**

---

## Detectable (review + grep signatures)

- A resolver / tool returning bare `None`/`[]`/`{}` for "didn't understand" AND for
  "genuinely empty" — same falsy value, two opposite meanings.
- A fall-through comment like *"fall back so the user still gets something"* after an
  empty result (that "something" is an answer to a different question).
- A confidence/score attached to inputs but **absent** from the emitted answer.
- `try/except` that continues the pipeline on a default instead of surfacing `error`.
- Any junction where a low-confidence input yields a high-confidence output.

---

*Source: ~/ai-toolkit/shared/uncertainty-provenance.md (mirrored into carbon/.ai-toolkit/shared/)*
