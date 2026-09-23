# Screen Spec — Account Settings (`/settings`)

**Owner:** Pulse · **IA:** Shell bottom Settings · **Route:** `/settings?tab=`  
**Track:** Shell identity follow-on (Account module remake)  
**Status:** READY for FE (2026-09-23)

## 1. User story + acceptance

As a signed-in user I open **Account Settings** to manage login identity, password, UI preferences, and keyboard shortcuts — not my HR profile (that is **My**) and not Pulse provisioning (auto-connect via `pulseAuth.js`).

Acceptance:
- [ ] Four tabs only: **Account** · **Security** · **Preferences** · **Shortcuts**
- [ ] No **Pulse AI** tab (keys provisioned by `ensurePulseKey`, not Settings)
- [ ] First tab labeled **Account** (not Profile); `?tab=profile` and `?tab=pulse` redirect to `account`
- [ ] Header **Account** → `/settings?tab=account`; sidebar matches the four tabs
- [ ] Linked employee (when present) is read-only + **Open in My**
- [ ] Preferences: language + theme (no “coming soon” stub)
- [ ] Password change uses `NotificationProvider`, not raw Snackbar
- [ ] EN/AR i18n parity for all new/changed strings

## 2. Journey

Header Account / Sidebar Account → Account tab → optional Open in My  
Security → change password → success toast  
Preferences → language or theme → immediate effect (+ language PATCH to `me/preferences/`)  
Shortcuts → read-only list

## 3. IA

| Surface | Path |
|---|---|
| Shell rail | Settings (bottom) |
| Settings subnav | Account, Security, Preferences, Shortcuts |
| Header menu | Account → `?tab=account`; Preferences → `?tab=preferences`; Shortcuts → `?tab=shortcuts` |

## 4. Composition

```
PageContainer
 └─ PageHeader (title Account Settings, subtitle signed-in-as)
 └─ MUI Tabs (Account | Security | Preferences | Shortcuts)
 └─ tab panels (maxWidth ~600)
      ├─ Account: Identity section + Linked employee (optional) + Roles
      ├─ Security: change-password form
      ├─ Preferences: language select + theme toggle
      └─ Shortcuts: key list
```

Reuse: `PageContainer`, `PageHeader`, `NotificationProvider`, `useLanguage`, `useThemeMode`, auth `employee`. No new Layer-2 primitives.

## 5. State matrix

| Surface | States |
|---|---|
| Account / roles fetch | loading (LinearProgress) · loaded · error (silent fallback to auth user) · empty roles (hide Roles card) |
| Linked employee | present · absent (hide card) |
| Security form | idle · submitting · error · success |
| Preferences | always local-available; language PATCH best-effort |

## 6. Data contract

| Call | Use |
|---|---|
| `GET accounts/my-roles/` | username + roles (Account tab) |
| AuthContext `employee` from `me/context` | Linked employee (no `people/me` from Settings) |
| `POST accounts/change-password/` | Security |
| `PATCH accounts/me/preferences/` | language |

## 7. a11y

Tabs are real `Tabs`/`Tab` with keyboard focus; password fields have autocomplete; buttons disabled while submitting.

## 8. Performance

No grid. Single roles fetch on mount. No Pulse host calls from this page.

## 9. i18n / RTL

`common` + `shell` keys; AR parity required. Direction follows existing `useLanguage`.

## Non-goals

Dedicated `/my/profile`, Pulse key UI, editing employee fields, photo upload.
