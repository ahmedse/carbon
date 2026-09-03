# QBank Moodle — edOS Workstation Deployment Runbook

**Stack:** air-gapped Moodle 5.2.2 + PostgreSQL 16 (Docker Compose)
**Source:** `deploy/moodle/` in the Carbon repo
**Targets:** Ubuntu bare-metal edOS workstation (`/srv/qbank`) **and** Ubuntu WSL2 dev (`./data`)

---

## 0. The two artifacts you move

The whole `release/` directory is the transport unit (copy it to USB/SSD):

```
release/
├── images/moodle.tar.gz       538M   qbank/moodle:5.2.2
├── images/postgres.tar.gz     152M   postgres:16
├── moodle/moodle-5.2.2.tgz     86M   source-of-truth tarball (+ .sha256)
├── qbank-stack.tar.gz         8.5K   stack source
├── qbank.pub                        Ed25519 PUBLIC key (travels)
├── MANIFEST.sha256                  checksums of the 5 files above
└── MANIFEST.sha256.sig             Ed25519 signature over MANIFEST.sha256
```

> **Do NOT copy** `.sign/ed25519.key` (the secret signing key) — it stays on the
> online dev machine. The workstation only ever needs `qbank.pub` to verify.

---

## 1. On the workstation: verify the bundle (before trusting it)

```bash
cd /path/to/release
openssl pkeyutl -verify -pubin -inkey qbank.pub -rawin \
    -in MANIFEST.sha256 -sigfile MANIFEST.sha256.sig   # "Signature Verified Successfully"
sha256sum -c MANIFEST.sha256                            # all "OK"
```

Both must pass. If either fails, the USB copy is corrupt or tampered — do not deploy.

---

## 2. Prepare the stack directory + env

```bash
mkdir -p /srv/qbank && cd /srv/qbank          # edOS (bare-metal)
# or, on WSL dev: mkdir -p ~/aast/carbon/deploy/moodle  (already exists)

tar -xzf /path/to/release/qbank-stack.tar.gz -C .   # stack source (scripts, compose, Dockerfile)
mkdir -p release
cp /path/to/release/* release/                       # images + manifest + pub key + sig
```

Create `.env` (never committed — copy `.env.example` and fill in). The two fields
that differ between targets:

| Var | edOS (bare-metal) | WSL dev |
|---|---|---|
| `QBANK_ROOT` | `/srv/qbank` | `./data` |
| `MOODLE_DOMAIN` | your real hostname | `qbank.local` |
| `MOODLE_HTTPS_PORT` | `443` | `443` |

If you leave `POSTGRES_PASSWORD` / `MOODLE_ADMIN_PASS` / `PASSWORDSALTMAIN` at
their `__CHANGE_ME__` placeholders, `deploy.sh` generates and appends real values
on first run.

---

## 3. Deploy

```bash
cd /srv/qbank   # or the WSL stack dir
./scripts/deploy.sh --cron     # add --cron to install the host cron timer
```

`deploy.sh` does, in order:
1. verify manifest (+ Ed25519 signature) → `docker load` both images
2. generate a self-signed TLS cert if none exists (production: drop in your offline-CA cert first)
3. start `db`, wait healthy
4. run `admin/cli/install.php` in a one-off container (writes `config/config.php`)
5. inject air-gap hardening (MFA, session hardening) from `harden/config-extra.php`
6. fix permissions, `docker compose up -d`, verify schema, purge caches
7. re-hash the admin password if a salt was generated post-install
8. (with `--cron`) enable the `qbank-cron` systemd timer

---

## 4. First login — MFA is forced (expected, not a bug)

| | Value |
|---|---|
| URL | `https://<MOODLE_DOMAIN>/` (e.g. `https://qbank.local/`) |
| Admin user | `admin` |
| Admin password | from `.env` (`MOODLE_ADMIN_PASS`) |

1. Log in with `admin` + the `.env` password.
2. Moodle **immediately redirects to `/admin/tool/mfa/auth.php`** and forces you
   to configure a second factor (TOTP authenticator app). Complete it to reach
   the dashboard. This is the air-gap hardening, not a defect.
3. **Change the admin password after first login** (it's plaintext in `.env`):
   Site administration → Users → Accounts → Browse list of users → admin → Edit profile.

---

## 5. Post-deploy checks

```bash
cd /srv/qbank
docker compose ps                       # both services "Up (healthy)"
curl -sk -o /dev/null -w '%{http_code}\n' "https://$(grep ^MOODLE_DOMAIN .env | cut -d= -f2)/"   # 200/303
```

---

## 6. Backups (on the workstation)

```bash
./scripts/qbank        # pg_dump (custom format) + moodledata tar.gz → ./data/backup/
```

Backup both the DB dump **and** `PASSWORDSALTMAIN` from `.env` — the salt is
required to restore passwords, so it must live next to (not inside) the backup.

---

## 7. Re-bundling a new release (online dev machine, after changes)

```bash
cd deploy/moodle
./scripts/bundle.sh      # docker save images + tar source + MANIFEST.sha256
./scripts/sign.sh        # Ed25519-sign MANIFEST.sha256 (reuses .sign/ed25519.key)
./scripts/verify.sh      # round-trip check before you copy to USB
```

> Note: `bundle.sh` uses `docker save` only (read-only export). It is the one
> explicit docker step in the dev flow and does **not** build images or run
> compose — build/image work stays on the workstation or in CI.
