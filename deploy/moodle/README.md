# QBank Moodle Docker stack

Self-contained Moodle (5.2.x) + PostgreSQL (16) for air-gapped deployment.

- **Full runbook:** `docs/MOODLE-DOCKER.md`
- **What runs inside Moodle:** `docs/MOODLE.md`
- **The hardened host:** `docs/EDOS.md`

Quick reference:

```bash
# Dev (WSL2, online)
cp .env.example .env && sed -i 's|^QBANK_ROOT=.*|QBANK_ROOT=./data|' .env
./scripts/build-image.sh      # needs build/moodle-5.2.*.tgz + .sha256
./scripts/dev-up.sh

# Bundle for the workstation (online)
./scripts/bundle.sh ./release

# Deploy (air-gapped workstation)
./scripts/deploy.sh --cron
```

Generated at runtime (gitignored): `.env`, `config/config.php`, `tls/`, `data/`, `build/`, `release/`.
