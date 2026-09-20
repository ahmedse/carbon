# Pulse UX — Non-admin re-shoot (2026-09-20)

**Brand:** EduOS (`VITE_BRAND=eduos`, FE `:5179`, BE `:8009`)  
**User:** `gv_student` (non-admin)  
**Note:** Nibras `emp_1001` is not valid on this EduOS stack.

## Screenshots

| File | What |
|------|------|
| `ux-audit-shots/ux-na-01-home-after-login.png` | Student home after login |
| `ux-audit-shots/ux-na-02-pulse-chat-dock.png` | Pulse Chat dock open |
| `ux-audit-shots/ux-na-03-agent-mode-autonomy.png` | Agent + Autonomy dial (**Balanced**) |
| `ux-audit-shots/ux-na-07-chat-deixis-clarify.png` | **PASS** — “Did you mean **GradeVance**?” after “check that one for me” |
| `ux-audit-shots/ux-na-10-agent-leave-scope-route.png` | Agent leave attempt (earlier partial) |

## Live deixis (closed)

| Method | Latency | Result |
|--------|---------|--------|
| In-process `CarbonIntelligence.send_message` | **0.19s** | `Did you mean **GradeVance**?` |
| HTTP `POST …/messages/` | **0.27s** | same |
| UI Playwright | — | `UX-NA-DEIXIS-UI-2026-09-20.json` → `has_did_you_mean: true` |

Prior hang was cold LLM + stuck `runserver --noreload` worker — not deixis. Seeded history → gate fires before tools.

## Other fixes this pass

- `resolve_navigation` restored (was ImportError → always fell through nav fast-path)
- Entity annotation ORM call wrapped in `sync_to_async` (was `SynchronousOnlyOperation` spam)
- Agent task picker label: “New / pick one” (no “Task task” overlap)

## Verdicts

| Check | Result |
|-------|--------|
| Autonomy dial (non-admin) | **PASS** |
| Deixis live Chat | **PASS** |
| Leave ≠ DQ (unit) | **PASS** |
| Telemetry `chat.deixis_gate` | **PASS** (logged) |
