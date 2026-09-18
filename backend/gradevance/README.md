# GradeVance (EduOS)

Multi-domain assessment + coaching app. Pack intelligence lives in
`domain_packs/eduos/`; this Django app is the typed SoR + runtime.

## Quick start (EduOS instance)

```bash
export DJANGO_BRAND=eduos
python manage.py migrate
python manage.py bootstrap_platform
python manage.py sync_eduos_packs
python manage.py register_gradevance_app
python manage.py gradevance_lti_readiness
```

## LTI soak

See `docs/eduos/LMS-SOAK.md`. Offline rehearsal:

```bash
pytest gradevance/tests/test_lti_soak_path.py -o addopts= -p no:_testbrand
```

Tectona (after EduOS LMS soak): set `TECTONA_GRADEVANCE=true` and re-bootstrap.

## API (`/api/v1/gradevance/`)

| Path | Purpose |
|------|---------|
| `GET summary/` | Counts |
| `GET profiles/` | YAML AssignmentProfiles on disk |
| `POST assignments/` | Create assignment pinned to a profile |
| `POST submissions/?analyze` | Submit + formative run |
| `GET runs/<id>/` | Segments, LCT codes, wave, rubric, coaching |
| `GET review-queue/` | HITL queue |
| `POST runs/<id>/edits/` | Append-only ExpertEdit (+ ProposalMiner) |
| `GET/POST proposals/` | Intelligence promotion queue + canary-gated accept |
| `POST proposals/<id>/decide|bump|repin/` | Accept/reject, pack bump, profile re-pin |
| `GET publish-gate/` | κ gate preview for summative publish |
| `GET runs/<id>/audit-export/` | Evidence package json_v2 |
| `GET/POST lti/*` | OIDC, JWKS, Deep Link, NRPS, status |
| `GET/POST runs/<id>/ags-*` | AGS preview / passback |
| `GET accessibility/` | WCAG checklist toward VPAT |
| `GET courses/` | Course list/create |

## Capabilities

`gradevance:view` · `manage` · `mark` · `submit` · `qa`  
Groups: `gradevance_lead`, `gradevance_markers`, `gradevance_students` (EduOS + Tectona brands)
