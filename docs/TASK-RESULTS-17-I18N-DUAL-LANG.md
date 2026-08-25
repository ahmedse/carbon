# Task Results — I18N Dual-Language UI (progress: I18N-1, I18N-2, I18N-5)

**Date:** 2026-08-24
**Authored by:** Master Architect
**Track:** Phase Set I18N (ADR-0018) — English (default) + Arabic RTL

## Scope of this report

This documents the I18N phases completed to date. I18N-3 (core apps), I18N-4
(hosted + tools), and I18N-6 (QA / RTL audit / E2E) remain open and are tracked
with accurate `READY` status in `TASKS.md`.

## Completed

### I18N-1 — Foundation (commit `80eb540`)
- `src/i18n/index.js` — i18next init: `lng` from `carbon.lang` (default `en`),
  `fallbackLng: 'en'`, `useSuspense: false`, `initImmediate: false`, namespaces
  `common`/`shell`/`auth`/`errors`/`ai`.
- `LanguageProvider` / `RtlProvider` / `useLanguage` / `languageContext`.
- Dual Emotion caches (`muil` / `muirtl` with `stylis-plugin-rtl`), Cairo font,
  direction-aware theme (`createCarbonTheme(mode, direction)`).
- `LanguageSwitcher` (text-only, no flags) mounted in `HeaderEnhanced`.

### I18N-2 — Shell + Auth (commit `80eb540`)
- `src/shell/*` (Shell, ShellSidebar, Breadcrumbs, ActivityBar, StatusBar,
  AIMessageBubble chrome), `src/auth/*` (Login, Forgot/Reset), shared components
  (ConfirmDialog, HeaderEnhanced, NotificationProvider, SystemDialog) → `t()`.
- `src/i18n/shellLabels.js` — studio label key map.
- en/ar catalogs: `shell` (195), `auth` (56), `common` (21), `errors` (12).
- `scripts/check-i18n-keys.js` — key-parity gate.

### I18N-5 backend — per-user language preference (commit `cdc0ceb`)
- `accounts.User.language` (choices `en`/`ar`, default `en`) + migration `0015`.
- `GET/PATCH /carbon-api/accounts/me/preferences/` + `language` surfaced in
  `me/context/`.
- 7 tests (`accounts/tests/test_language_preferences.py`) — all green.

### I18N-5 frontend — error mapping + core AI chrome (commit `ad6d7c1`)
- `src/utils/errorNormalizer.js` now emits `errorCode` + `messageKey` for every
  branch (timeout / network / auth / validation / not_found / server / unknown).
- `src/i18n/errorMessages.js` — complete code→key map wired into `normalizeError`.
- `ai` namespace (en/ar, 44 keys): workspace tabs, activity-bar labels, mode
  labels, safety contract (`ai.contract.*`), memory views, delete dialog.
- Migrated `AIWorkspace`, `AIWorkspaceHeader`, `AIStatusBar` chrome → `t('ai.*')`.
- 8 new `errorNormalizer` tests; `errors.validation` key added (en + ar).

## Verification evidence (this session)

| Gate | Result |
|------|--------|
| `npm run lint` | 0 errors (18 pre-existing warnings) |
| `npx vitest run` | **852 passed** (72 files) |
| `npm run build` | ✓ (21.57s) |
| `node scripts/check-i18n-keys.js` | **303 keys in parity (en === ar)** |
| `./.ai-toolkit/scripts/verify.sh frontend` | GATE PASSED |
| Frontend :5179 | HTTP 200 |
| Backend :8009 `/carbon-api/health/` | HTTP 200 |
| `me/context/` (unauthenticated) | HTTP 401 (protected, as expected) |

## Remaining (accurate, tracked in TASKS.md)

- **I18N-3** — migrate `src/pages/{catalog,dq,dataschema}` to `catalog`/`mdm`/`dq`/`dataschema`
  namespaces + Arabic catalogs. NOTE: actual pages live in `src/pages/*`, NOT the
  `src/apps/*` paths in the spec (stale naming). ~27 files / ~10k lines.
- **I18N-4** — migrate `src/pages/emissions/*`, `src/components/{evidence,import}/*`,
  connections UI, shared dialogs, root pages → `emissions`/`evidence`/`connections`/
  `importexport`/`common`/`shell`.
- **I18N-5 remaining** — deep per-panel AI chrome: 22 remaining `src/shell/AI*.jsx`
  files + 25 `src/pages/admin/ai/*` panels (tabs/panel headers/buttons/status labels);
  AIConversationView status-label flow (currently passed as resolved `label` prop).
- **I18N-6** — RTL sweep (DataGrid/Monaco/Chart.js/mermaid/katex), directional-icon
  audit, numerals audit, Arabic quality pass, Playwright E2E (EN + AR), deliverable
  `TASK-RESULTS-17-I18N-DUAL-LANG.md`.

## Migration pattern (for the remaining phases)

1. Add `{en,ar}/<ns>.json`, register in `src/i18n/index.js` + `__mocks__/react-i18next.js`.
2. In each component: `const { t } = useTranslation('<ns>')`; replace literal UI
   strings with `t('<semantic.key>')`; nested objects for grouped keys.
3. Run `node scripts/check-i18n-keys.js` (must stay zero-missing) + `npm run lint`
   + `npx vitest run` + `npm run build` + `verify.sh frontend` after each app.
4. Do NOT translate assistant replies, plan/artifact content, or rule/provenance
   text (content scope — ADR-0018). Numerals stay Latin (`ar-EG-u-nu-latn`).
