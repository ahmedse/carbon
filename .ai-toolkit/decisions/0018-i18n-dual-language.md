# ADR-0018 — Dual-Language i18n: English (default) + Arabic with RTL

**Date:** 2026-08-25
**Status:** Accepted
**Author:** Master Architect
**Supersedes:** None (new capability)
**Extends:** ADR-0015 (multi-instance), platform shell/theme conventions

---

## Context

The platform is English-only (326 JSX files / ~87.5K lines / ~1,000+ hardcoded strings).
Requirement: **dual-language UI — English is the default; Arabic is a full second
language, including RTL layout.** Explicit user constraint: the language switcher must
**never use a flag** (e.g., a Saudi flag) as a button or icon — language is not a country.

Scope boundary set by the user: i18n applies to **UI chrome and static platform copy
only**. AI/Pulse assistant replies and user-generated content are **not** translated —
the user chooses the language of those when writing (the assistant answers in the
language of the request). Translated static strings must still satisfy RULE_23 (copy
describes outcomes, never internals).

## Research Basis (top systems)

Compared: i18next/react-i18next, FormatJS/react-intl, LinguiJS, MUI v7 RTL guidance,
Google/Apple language-switcher patterns, and Arabic-specific RTL/i18n practice.

Wisdom adopted:
- Native-language text labels ("English" / "العربية"), no flags (Google/Apple pattern).
- Namespace-based catalogs, code-split and lazy-loaded (i18next namespaces).
- Full-sentence translations, never concatenated fragments (Arabic word order).
- Arabic plural rules = 6 CLDR forms (zero/one/two/few/many/other) via Intl.PluralRules.
- `Intl` + dayjs for dates/numbers — never the `t()` function.
- Logical CSS properties + RTL plugin; directional icon flips; `dir`/`lang` on `<html>`.

Flaws of top systems explicitly avoided (documented in TASKS.md I18N-1):
- English-as-key anti-pattern → **semantic namespaced keys** (`shell.sidebar.catalog`).
- Browser auto-detect overriding user choice → **default en, localStorage + server
  profile, never navigator detection**.
- Raw keys leaking in prod → `fallbackLng: 'en'` + dev-only diagnostics.
- `useSuspense` blank-screen pitfall → `useSuspense: false` + `ready` flag.
- Missing Arabic glyphs in Inter → **Arabic font added via @fontsource**.
- `ar` default Eastern-Arabic numerals in data → **Latin digits (`ar-EG-u-nu-latn`)**
  (user-approved; standard for Egyptian enterprise data views).
- Backend prose translated client-side → **error-code mapping on the frontend**
  (user-approved): backend returns codes; frontend renders localized text.

## Decision

1. **Library:** `i18next` + `react-i18next` (v24+/v15+). Semantic keys, one namespace
   per domain (`common`, `shell`, `auth`, `catalog`, `mdm`, `dq`, `dataschema`,
   `emissions`, `evidence`, `connections`, `ai`, `errors`). `fallbackLng: 'en'`,
   `useSuspense: false`, `interpolation.escapeValue: false` (React handles escaping).
2. **Locale switch:** `LanguageProvider` (`src/i18n/LanguageProvider.jsx`) persists
   choice to **localStorage AND server-side user profile** (new `accounts.User.language`
   field + `me/preferences/` GET/PATCH endpoint; also surfaced in `me/context/`).
   On switch: set `document.documentElement.dir/lang`, rebuild MUI theme with
   `direction`, swap Emotion cache.
3. **RTL:** dual Emotion caches (`stylis-plugin-rtl`, keys `muil`/`muirtl`), theme
   `direction` param in `createCarbonTheme(mode, direction)`, `dir="rtl"` + `lang="ar"`
   at runtime. Directional icons flipped via a small `DirIcon`/sx helper. DataGrid,
   Monaco, and charts get an explicit RTL audit (I18N-6).
4. **Fonts:** keep Inter for Latin; add `@fontsource/cairo` (Arabic) — swapped via
   `theme.typography.fontFamily` when `lang === 'ar'`; Arabic line-height bump.
5. **Switcher:** text-based `LanguageSwitcher` in `HeaderEnhanced` (top-right, near
   avatar menu): **"English" / "العربية"**, translate icon, no flags.
6. **Dates/numbers:** dayjs `ar` locale + `Intl.NumberFormat('ar-EG-u-nu-latn')` for
   Arabic data views; Gregorian calendar retained (Egypt official).
7. **AI/Pulse replies:** NOT translated (user scope). In-language responses only.
8. **Testing:** `__mocks__/react-i18next.js` in vitest; key-parity audit script
   (en/ar key sets must match) as a hard gate; RTL snapshot tests; dual-language
   Playwright E2E at the end.

## Consequences

- **Positive:** full Arabic surface incl. RTL; no flags; no navigator-surprise; stable
  keys; typed catalogs; error text localized without backend gettext overhaul.
- **Negative:** one-time migration cost across ~326 files; every future user-facing
  string MUST go through `t()` (enforced in I18N-6 + frontend role rules); Arabic
  translation quality depends on a review pass (I18N-6).
- **Never re-litigate:** library choice (i18next), keying (semantic namespaced),
  digits (Latin), flags (never), AI-reply scope (not translated), default (en).
