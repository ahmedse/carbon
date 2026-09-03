# Product & UX Design Principles
# Read by: Product/UX Designer (every session), Master Architect (when scoping features),
#          Frontend Worker (when composing UI). The "why" above the design-system's "how".
#
# design-system.md governs how the UI LOOKS and is BUILT (tokens, primitives, states).
# THIS file governs how the product should FEEL and BEHAVE for the user.

---

## The North Star

**Every feature exists to help a real user accomplish a real goal with the least friction.**
If a change doesn't make a user's job faster, clearer, or safer, question why it's being built.

---

## The 10 Principles

1. **User goal first, feature second.** Start from the job-to-be-done, not the screen. Name the user and their goal before designing anything.

2. **Clarity over cleverness.** The obvious path beats the elegant one. If it needs explaining, redesign it. No novelty that forces relearning.

3. **Progressive disclosure.** Show what's needed now; reveal complexity on demand. Defaults handle the 80% case; power is one click deeper, never in the way.

4. **Immediate, honest feedback.** Every action gets a visible response within 100ms (optimistic UI or spinner). Never leave the user wondering if it worked.

5. **Prevent errors, then recover gracefully.** Disable the impossible, confirm the destructive, validate inline. When something fails, say what happened and the next step — never a dead end.

6. **Consistency is a feature.** The same action looks and behaves the same everywhere. Predictability lowers cognitive load more than any single delight.

7. **Sensible defaults, minimal input.** Pre-fill, remember, infer. Every field the user must fill is a tax — justify it. The best form is no form.

8. **Perceived performance matters as much as real.** Skeletons over spinners, optimistic updates, instant local feedback. Never block the whole screen for a partial load.

9. **Accessible by default (WCAG AA).** Keyboard-complete, screen-reader-sane, contrast-safe, status never by color alone. Accessibility is baseline, not a feature.

10. **Trust through transparency.** Show system state, data freshness, and what will happen before it happens. Enterprise users trust software that never surprises them.

11. **Deliberate actions only.** In enterprise software, no side-effect should trigger from an ambiguous gesture. <strong>Row clicks highlight only</strong> — the user must deliberately click a specific action (icon button, context menu, or CTA) to navigate, edit, or delete. Accidental clicks on dense data grids are frequent and costly. This applies to all DataGrid, Table, and List components.

---

## Applying the principles (decision heuristics)

- **Adding a field?** → Can we infer or default it instead? (Principle 7)
- **Adding a step?** → Can it be progressive-disclosed or removed? (Principle 3)
- **A destructive action?** → Confirm + make it undoable if possible. (Principle 5)
- **A slow operation?** → Optimistic UI or skeleton + progress. (Principle 8)
- **A new interaction?** → Does a consistent pattern already exist? Reuse it. (Principle 6, ux-patterns.md)
- **A new screen?** → Who is the user, what's their goal, what are the 4 data states? (Principles 1, design-system RULE 4)

---

## The hand-off chain (who owns what)

```
Product/UX Designer  → user story, journey, flow, acceptance criteria, IA   (THIS file + user-stories.md)
Master Architect     → decomposes into technical phases, names contracts
Backend Worker       → data + endpoints per api-contract.md
Frontend Worker      → composes UI per design-system.md + ux-patterns.md
Debugger / Curator   → preserve + promote learnings
```

A feature is not "designed" until the user, their goal, the flow, and acceptance criteria exist.

---

*Source: ~/ai-toolkit/shared/design-principles.md — shared across all projects*
