# People partner slice

Permanent way to share **People / My / Team** source without shipping **Pulse** or the **Data Trust product**.

This is a **review package**, not a second product repo. It will not boot as Carbon. People still calls org-units, reference values, DQ gates, and catalog audit helpers in the full tree; those **apps and consoles stay out of the zip**.

## Ship it

From the Carbon root (does not start or kill the stack):

```bash
./manage.sh export-people-slice
```

Or:

```bash
./scripts/export_people_slice.sh
```

Default output:

- Folder: `dist/people-slice/`
- Archive: `dist/people-slice-YYYYMMDD.tar.gz`

Optional:

```bash
./scripts/export_people_slice.sh --out /path/to/dir --archive /path/to/people-slice.tar.gz
```

Send only the `.tar.gz`. Do not add the partner as a collaborator on this monorepo.

## What is in

| Include | Why |
|---|---|
| `backend/people/` | HR / payroll / ESS API |
| `backend/correspondence/` | Leave / loan / attendance request spine |
| `backend/regulations/` + `regulation_packs/` | Compliance evaluators People registers |
| `backend/accounts/`, `backend/core/` | Login, RBAC, audit middleware (not Catalog/DQ/MDM product) |
| `carbon-frontend/src/apps/{people,my,team}/` | Staff + ESS + manager UI |
| `carbon-frontend/src/api/{people,my,team}.js` | People HTTP clients |
| Shared UI pieces: `auth/`, `hooks/`, `theme/`, `i18n/`, `components/` (after Pulse/Catalog/DQ prune) | So the People screens are readable |
| `docs/nibras/`, People QA manual | Product docs for this slice |

## What is never in

Pulse: `backend/ai/`, `docs/pulse/`, `assurance/pulse/`, AI/Pulse shell and admin UI, `api/ai*`.

Data Trust product: `backend/{catalog,dq,mdm,dataschema,connections,importexport,inbound,evidence}/`, Catalog/DQ/MDM pages, `assurance/datatrust/`, Data Trust QA.

Other brands/apps: GradeVance, Healthy, emissions/Carbon, EduOS, `.ai-toolkit/`, domain packs (Pulse processes), secrets (`.env`, dumps, keys).

The exporter **fails** if any leak path is present in the destination.

## How to talk about it

> This archive is People (HR) source for review. Pulse (AI) and Data Trust (catalog / DQ / MDM platform) are separate products and are not included. The zip is not a runnable Carbon instance.

## Changing the boundary

Edit `shipping/people-slice/include.txt` and `shipping/people-slice/exclude-globs.txt`, then re-run the exporter. Do not ad-hoc zip the monorepo.
