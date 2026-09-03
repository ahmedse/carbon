# Compact UI Constitution — Carbon Data Trust Platform
# Read by: Frontend Worker (every session), Master Architect (when reviewing UI).
# This is the authoritative density specification for Carbon's enterprise look.
# It CONCRETIZES the generic design-system.md rules into specific MUI theme values.
#
# PHILOSOPHY:
# Enterprise UIs pack information. Consumer whitespace ≠ enterprise.
# Palantir Foundry, Ataccama, Linear, VS Code — all use tight, scannable layouts.
# This file ensures EVERY worker produces identically dense output.

---

## The Compact Density Contract

| Axis | Value | Where |
|------|-------|-------|
| Base font | `fontSize: 10, htmlFontSize: 14` | theme.typography |
| Body text | `body1: 0.75rem, body2: 0.6875rem` | theme.typography |
| Headings | `h1: 1.4rem` → `h6: 0.8125rem` | theme.typography |
| Caption | `0.625rem` | theme.typography |
| Border radius | `shape.borderRadius: 8` (use `borderRadius: 1` for 8px) | theme.shape |
| Spacing unit | `spacing: 8` (use `p:1` for 8px, `p:0.75` for 6px) | theme.spacing |

---

## Component Density Spec

### Buttons
```
padding: '3px 8px'
fontSize: '0.6875rem'
minHeight: '24px'
borderRadius: 3
textTransform: 'none'
sizeSmall: padding '2px 6px', fontSize '0.7rem'
sizeLarge: padding '6px 14px', fontSize '0.8125rem', minHeight '30px'
```
- NEVER create custom-sized buttons — use `size="small"` or theme defaults.
- NEVER increase button padding for "emphasis" — use variant (contained/outlined).

### DataGrid
```
fontSize: '0.65rem'
rowHeight: 36 (theme defaultProps)
columnHeaderHeight: 32 (theme defaultProps)
columnHeaders: bg background.dark, borderBottom 2px solid divider
cell: borderBottom 1px solid divider, padding '4px 8px', lineHeight 1.3
row hover: primary 4% opacity
```
- Use `density="compact"` on all DataGrids.
- Column headers are 0.625rem uppercase (theme columnHeaderTitle).
- Pagination text is body2 size.
- **ROW CLICK = HIGHLIGHT ONLY.** Never navigate on row click. The user must deliberately click an action button (eye icon, etc.) to navigate. Set `highlightRow` and `onRowClick` for selection state.

### Chips / Badges
```
borderRadius: 3
fontSize: '0.65rem'
height: '18px'
fontWeight: 500
```
- Semantic colors: success/error/warning/info/primary use the theme chip overrides.
- NEVER inline chip styling — use `color="success"` / `color="error"` etc.
- Scope badges: `success.main`=Scope1 green, `warning.main`=Scope2 amber, `primary.main`=Scope3 blue.

### Table (MuiTable)
```
TableHead: padding '6px 8px', fontSize '0.625rem', uppercase, letterSpacing '0.05em'
TableCell: padding '4px 8px', fontSize '0.6875rem'
TableRow: hover primary 4%, last-child no border
```

### Tabs
```
MuiTabs: minHeight 36
MuiTab: minHeight 36, padding '6px 12px', fontSize '0.8125rem', fontWeight 500
indicator: height 2
```

### Text Inputs & Selects
```
MuiTextField: size="small" (default prop)
MuiSelect: size="small" (default prop)
borderRadius: 4
```
- ALWAYS use `size="small"` — it's set as the theme defaultProp.
- NEVER override input size inline.
- Form labels inherit body2/caption sizing.

### Dialogs
```
DialogTitle: fontSize '1rem', fontWeight 600, padding '12px 16px'
DialogContent: padding '12px 16px'
DialogActions: padding '8px 16px'
```
- NEVER add extra padding to dialog sections.
- Dialog maxWidth should be constrained — prefer 'sm' or 'md'.

### Cards / Paper
```
Card: boxShadow 'none', border 1px solid divider, borderRadius 8
Paper: borderRadius 8, no backgroundImage, no default boxShadow
```
- Use `variant="outlined"` on Paper for subtle borders instead of elevation.

### Accordion
```
Accordion: boxShadow none, border 1px solid divider, borderRadius 4, marginBottom 8
AccordionSummary: padding '0 12px', minHeight 40
AccordionDetails: padding 12px
```

### Icon Buttons
```
borderRadius: 4
padding: 6
sizeSmall: padding 4, fontSize '1.125rem'
```

### Alerts
```
borderRadius: 4
padding: '6px 12px'
fontSize: '0.8125rem'
border: 1px solid semantic-color
```

### Tooltips
```
fontSize: '0.75rem'
padding: '4px 8px'
borderRadius: 4
```

---

## Sidebar Navigation Pattern (VS Code / Linear Style)

This is Carbon's signature navigation pattern. Every sidebar MUST follow this.

```
Container: full height, flex column, bg background.paper, overflow hidden
List: disablePadding, flex 1, overflow auto, py 0.5, px 0.75
Nav row: height 28px, px 0.75, gap 0.75, borderRadius 5px, cursor pointer
Icon: fontSize 14, opacity 0.6 (1.0 when active)
Label: fontSize '0.65rem', fontWeight 400 (600 when active), lineHeight 1
Group header: fontSize '0.575rem', fontWeight 500, color text.disabled
              LETTER-SPACING 0.04em, px 0.75, pt 0.75, pb 0.25
              NEVER uppercase, NEVER bold, NEVER colored
Dividers: REPLACED with 6px spacing gaps (Box height:6)
Active indicator: &::before pseudo-element — 2.5px primary.main bar,
                  left 0, top 6, bottom 6, borderRadius '0 3px 3px 0'
Active bg: light mode rgba(14,165,233,0.07), dark mode rgba(56,189,248,0.1)
Default width: 200px

NO header chrome (no title, no collapse button)
NO context info block mid-sidebar
NO dividers (use spacing gaps)
NO uppercase text
```

**Bottom context pill** (org unit):
- Only visible for org-scoped users (data-owner/steward).
- Hidden for superusers and global admins (`!(user?.is_superuser || isGlobalAdminFlag)`).
- Compact: px 0.75, py 0.375, borderRadius 5, bg primary 5-8% opacity.
- Icon: LocationOnIcon fontSize 10, label fontSize 0.575rem.

---

## Page Layout Spec

### PageContainer (wrapper for all page content)
```
px: 1, py: 0.75
```
- NEVER add ad-hoc Box sx={{ p:3 }} — use PageContainer.

### PageHeader
```
Icon: 1rem
Title: 0.875rem (h5 variant)
Subtitle: 0.6875rem (subtitle2)
Description: body2 variant
Badge: Chip height 16px
Actions: gap 0.75
Bottom border: pb 0.5, mb 1, borderBottom 1px solid divider
```
- NEVER render inline Breadcrumbs in PageHeader — the shell owns breadcrumbs.

---

## Font Scale Reference

| Variant | Size | Weight | Use |
|---------|------|--------|-----|
| h1 | 1.4rem | 700 | Page hero (rarely used) |
| h2 | 1.25rem | 700 | Section title |
| h3 | 1.1rem | 600 | Card title |
| h4 | 0.95rem | 600 | Dialog title alternative |
| h5 | 0.875rem | 600 | Panel header, PageHeader title |
| h6 | 0.8125rem | 600 | Widget title, small header |
| subtitle1 | 0.75rem | 500 | Secondary headings |
| subtitle2 | 0.6875rem | 500 | Compact subhead |
| body1 | 0.75rem | 400 | Primary body text |
| body2 | 0.6875rem | 400 | Secondary body, metadata |
| caption | 0.625rem | 400 | Fine print, timestamps |
| button | 0.6875rem | 500 | Button labels |

- NEVER set fontSize/lineHeight as raw sx inline — use `variant="body1"` etc.
- Hierarchy comes from variant, not random sizes.

---

## Spacing Scale

| Token | Pixels | Use |
|-------|--------|-----|
| 0.25 | 2px | Micro gap (icon-to-label) |
| 0.5 | 4px | Tight internal padding |
| 0.75 | 6px | Compact container padding |
| 1 | 8px | Standard padding (PageContainer) |
| 1.5 | 12px | Section spacing |
| 2 | 16px | Card padding |
| 3 | 24px | Major section break |

- ALL spacing via theme `spacing()` or sx shorthand (`p`, `m`, `gap`, `py`, `px`).
- NEVER raw px values in sx padding/margin.
- Exception: height/width constraints use raw px (e.g., `height: 28` for sidebar rows).

---

## Color Token Map (NEVER inline hex)

| Hex | Token |
|-----|-------|
| `#2563eb` | `primary.main` |
| `#3b82f6` | `primary.light` |
| `#1d4ed8` | `primary.dark` |
| `#10b981` | `success.main` |
| `#059669` | `success.dark` |
| `#ef4444` | `error.main` |
| `#dc2626` | `error.dark` |
| `#f59e0b` | `warning.main` |
| `#0ea5e9` | `info.main` |
| `#18181b` | `text.primary` |
| `#71717a` | `text.secondary` |
| `#a1a1aa` | `text.disabled` |
| `#e4e4e7` | `divider` |
| `#ffffff` | `background.default` |
| `#fafafa` | `background.paper` |
| `#f4f4f5` | `background.dark` |

- chartPalette export from carbonTheme.js for Recharts colors.
- Scope colors: `scope1=error.main`, `scope2=warning.main`, `scope3=primary.main`.

---

## The Hard Rules (enforceable)

1. **NEVER hardcode hex colors, rgb(), or raw px spacing in sx.** Use theme tokens.
2. **NEVER override font sizes inline.** Use `variant` — if you need a different size, use a DIFFERENT variant.
3. **NEVER add padding to dialogs/cards beyond theme defaults.** Compact is intentional.
4. **NEVER build a custom sidebar item.** Use the ShellSidebar pattern (28px rows, left-bar active indicator).
5. **NEVER uppercase group headers.** 0.575rem muted, sentence case.
6. **NEVER show org unit context to superusers/global admins.** It's meaningless noise.
7. **ALWAYS use `size="small"`** on inputs — it's the theme default.
8. **ALWAYS wrap pages in PageContainer** (px:1, py:0.75) — no ad-hoc Box padding.
9. **PageHeader owns page chrome** — title, subtitle, badge, actions. One per page.
10. **Breadcrumbs live in the shell** (Breadcrumbs.jsx). Never inline them in pages.

---

## Frontend Worker Compact Pre-Flight

```
[ ] No raw hex colors in my new code
[ ] No raw font sizes — all via variant or theme component overrides
[ ] No ad-hoc padding on pages — using PageContainer
[ ] Nav items follow 28px row / 0.65rem label pattern
[ ] Group labels are 0.575rem sentence case, not uppercase
[ ] Dialogs use theme defaults (no extra padding)
[ ] DataGrid uses density="compact"
```

## Anti-Patterns (instant reject)

- `sx={{ color: '#...' }}` — use `color: 'primary.main'`
- `sx={{ fontSize: '0.95rem' }}` — use `variant="h5"` or similar
- `sx={{ padding: '16px' }}` — use `p: 2`
- `sx={{ textTransform: 'uppercase' }}` on group labels
- Raw `<Breadcrumbs>` in a page header
- `<TextField>` without `size="small"` (already default, but don't override with `size="medium"`)
- Org unit info visible to admin/superuser accounts
