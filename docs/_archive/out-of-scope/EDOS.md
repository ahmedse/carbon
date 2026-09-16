# edOS: Hardened Air-Gapped Workstation Build Specification

**Scope:** the physical machine and operating system that hosts Moodle and presents the kiosk. "edOS" is a *configuration* of Ubuntu 24.04 LTS, not a fork — every control below is stock Ubuntu components plus ~15 config files and 4 scripts, so any Linux admin can maintain it after you. Version this document with the scripts.

---

## 0. Threat model (what we defend against, and don't)

| Threat | In scope | Control |
|--------|----------|---------|
| Student/visitor with minutes of physical access to a powered-off machine | ✔ | LUKS full-disk encryption, BIOS lock, no external boot |
| Same, machine powered on and locked | ✔ | Kiosk session, screen lock, DMA/Thunderbolt disabled, USB allow-list |
| Coordinator (authorised user) exfiltrating the bank | ✔ partial | No outbound network, export only to red stick with audit log, no USB storage except registered, role limits in Moodle. *Cannot* stop photographing the screen — policy + room layout. |
| Malware via imported files | ✔ | Read-only intake, ClamAV, macro strip, noexec mounts, browser isolation |
| Phone tethering / rogue USB Ethernet / Wi-Fi dongle to create a network path | ✔ | USBGuard class block, module blacklist, nftables default-drop, `modules_disabled` |
| Disk failure / ransomware / fat-finger | ✔ | Nightly encrypted restic to second disk, weekly offsite stick, restore drills |
| Lost/stolen sticks | ✔ | LUKS on red/release; intake sticks carry inbound files only and are wiped on return |
| Targeted attacker with firmware implants, TEMPEST, supply-chain | ✗ | Out of scope; disproportionate to the asset |

---

## 1. Hardware

- Small-form-factor desktop or mini-PC (business line: Lenovo ThinkCentre Tiny / HP Elite Mini / Dell OptiPlex Micro). **Requirements:** TPM 2.0, two internal drive bays or NVMe + SATA, **no Wi-Fi/BT module** (order without, or physically remove the M.2 card — removing is better than disabling), Kensington slot, chassis-intrusion switch if offered.
- 32 GB RAM (Postgres + Moodle + Firefox + LibreOffice comfortable), 2 × 1 TB NVMe/SSD (one system, one backup target).
- UPS (600–900 VA) with USB signalling → clean shutdown on power cut (protects Postgres).
- USB mono laser printer (not Wi-Fi). A **USB DVD writer** is optional but handy (write-once media).
- Monitor with **privacy filter**; position screen away from the door.
- 4 × identical USB 3 sticks (32 GB), coloured/labelled: `QBANK-IN-1`, `QBANK-IN-2` (blue), `QBANK-OUT` (red), `QBANK-RELEASE` (black).
- 1 × FIDO2 key per user if you take the WebAuthn route (MOODLE.md §3).

---

## 2. Firmware

Set and **write the BIOS supervisor password into the sealed envelope** (§14):

- Supervisor password on; user power-on password **off** (LUKS does that job; two prompts annoys users into propping doors).
- Secure Boot **on** (Ubuntu signed shim). TPM 2.0 **on**.
- Boot order: internal disk only; disable USB/network/optical boot; disable "boot menu hotkey" if possible.
- Disable: Wi-Fi, Bluetooth, WWAN, **Thunderbolt/USB4 PCIe tunnelling** (DMA attack surface), Wake-on-LAN, Intel AMT/vPro (or unprovision), serial/parallel ports.
- Enable chassis intrusion detection, virtualisation (Docker doesn't need it, but future VM use might; harmless).
- After OS install: **disable Ethernet in BIOS too** unless you use the isolated-switch option. Physical absence beats firewall rules.

---

## 3. OS install & disk layout

Ubuntu **24.04 LTS Desktop (minimal install)**. Why desktop: you need GNOME for the kiosk anyway; Server + adding GNOME gives you the same thing with more work. Why 24.04: supported to 2029 (2034 with Pro), matches Moodle 5.3 LTS lifetime.

Use the installer's *Advanced → Encrypt with LUKS* or manual partitioning:

```
nvme0n1
├─ p1  1 GiB   EFI (vfat)                    /boot/efi
├─ p2  2 GiB   ext4                           /boot
└─ p3  rest    LUKS2 (argon2id) → LVM vg0
       ├─ root   60 GiB  ext4   /
       ├─ var    40 GiB  ext4   /var            (Docker, journald, apt cache)
       ├─ qbank  rest−16 ext4   /srv/qbank      (all data)
       └─ swap   16 GiB                          (encrypted by being inside LUKS)
nvme1n1 (backup disk)
└─ p1  LUKS2 → ext4 /mnt/backup   (separate key, opened by keyfile on root fs)
```

**LUKS unlock policy.** Passphrase at boot (long, held by `qbank-admin` and in the sealed envelope). Optionally add TPM2 + PIN so the machine boots to the kiosk with a 6-digit PIN typed by whoever arrives first:

```bash
systemd-cryptenroll --tpm2-device=auto --tpm2-with-pin=yes --tpm2-pcrs=0+7 /dev/nvme0n1p3
# /etc/crypttab:  luks-… UUID=… none tpm2-device=auto,tpm2-pin=yes
update-initramfs -u
```

PCR 0+7 bind to firmware + Secure Boot state, so a BIOS change or a tampered bootloader falls back to the passphrase. Don't bind PCR 4/8/9 or every kernel update breaks TPM unlock.

`/etc/fstab` hardening:

```
/srv/qbank       defaults,nodev,nosuid                 (Docker needs exec here)
/srv/qbank/in    bind,nodev,nosuid,noexec
/srv/qbank/out   bind,nodev,nosuid,noexec
/tmp             tmpfs,size=2G,nodev,nosuid,noexec
/var/tmp         bind to /tmp
```

---

## 4. Accounts

| Account | Purpose | Shell | sudo | Login |
|---------|---------|-------|------|-------|
| `root` | – | locked (`passwd -l`) | – | none |
| `qbank-admin` | you; all administration | bash | full, password required, `timestamp_timeout=0` | console/GUI switch-user; **no SSH** (sshd not installed) |
| `qbank` | kiosk session | bash (needed by GNOME) but with lockdown (§8) | none | GDM autologin |
| `qbank-svc` | owns `/srv/qbank`, runs compose & timers | nologin | none | none |

`/etc/sudoers.d/qbank`:

```
Defaults timestamp_timeout=0, logfile=/var/log/sudo.log, log_input, log_output
qbank-admin ALL=(ALL) ALL
qbank ALL=(qbank-svc) NOPASSWD: /usr/local/bin/qbank-export, /usr/local/bin/qbank-intake
```

The last line lets the kiosk user trigger the two media scripts (§9) without a password and without any other privilege.

Docker: `qbank-svc` is **not** in the `docker` group (that's root-equivalent). Compose runs from a systemd service as root with the project files owned by `qbank-svc`; humans never run `docker` directly except `qbank-admin` via sudo.

---

## 5. Network: none, enforced four ways

**Layer 0 — physical:** no Wi-Fi card; Ethernet disabled in BIOS unless the isolated switch is in use.

**Layer 1 — kernel modules:** `/etc/modprobe.d/qbank-deny.conf`

```
install cfg80211 /bin/false
install mac80211 /bin/false
install bluetooth /bin/false
install btusb /bin/false
install usbnet /bin/false
install cdc_ether /bin/false
install cdc_ncm /bin/false
install rndis_host /bin/false
install r8152 /bin/false
install ax88179_178a /bin/false
install thunderbolt_net /bin/false
install ipheth /bin/false
```

`install X /bin/false` (not `blacklist`) prevents loading even on explicit request. Rebuild initramfs.

**Layer 2 — nftables** `/etc/nftables.conf` (default-drop everywhere):

```
table inet qbank {
  chain input  { type filter hook input  priority 0; policy drop;
    iif lo accept
    ct state established,related accept
    # isolated switch only (delete this block if not used):
    iifname "enp*" ip saddr 10.66.0.0/24 tcp dport 443 accept
    iifname "enp*" ip saddr 10.66.0.0/24 udp dport { 53, 67 } accept
    iifname "enp*" ip saddr 10.66.0.0/24 tcp dport 445 accept   # write-only intake share
  }
  chain forward { type filter hook forward priority 0; policy drop; }
  chain output  { type filter hook output  priority 0; policy drop;
    oif lo accept
    oifname "enp*" ip daddr 10.66.0.0/24 accept
  }
}
```

**Docker:** `/etc/docker/daemon.json`

```json
{
  "iptables": false, "ip6tables": false, "userland-proxy": true,
  "no-new-privileges": true, "live-restore": true,
  "log-driver": "journald",
  "default-address-pools": [{"base": "172.31.0.0/16", "size": 24}]
}
```

With `iptables:false` Docker adds no NAT rules; containers have no route out (which is what we want) and published ports work via the userland proxy bound to `127.0.0.1:8080`. Host nginx terminates TLS on `127.0.0.1:443` (+ `10.66.0.1:443` if switch) and proxies to 8080. Sysctl `net.ipv4.ip_forward=0`.

**Layer 3 — USB class block** (§9): USB network adapters, phones in tethering mode, and Wi-Fi dongles are refused by USBGuard before a driver would even be asked for.

**Layer 4 (optional "hard mode")** — a late `systemd` unit runs `sysctl kernel.modules_disabled=1` after Docker is up. No module can load until reboot; combined with Secure Boot, the kernel's driver surface is frozen. Costs you: plugging in a new *class* of device (e.g., the DVD writer for the first time) requires a reboot with the unit masked. Worth it once the config is stable.

**Isolated-switch mode (if adopted):** netplan static `10.66.0.1/24` on `enp*`; `dnsmasq` serving DHCP `10.66.0.50–99` and answering `qbank.local` → `10.66.0.1`; Samba share `intake` with `read only = no`, `create mask = 0660`, `directory mask = 0770`, `hide dot files`, and the share directory `chmod 0330` (write+execute, no read) so drop-only works; `smb encrypt = required`, `server min protocol = SMB3`. **No** export share.

---

## 6. Storage layout

```
/srv/qbank/
├── compose/          compose.yml, Dockerfile, .env (600, qbank-svc), nginx.conf
├── moodledata/       bind-mounted into moodle container (uid 33)
├── pgdata/           bind-mounted into db container
├── tls/              qbank.local.crt/.key (key 600 root), qbank-ca.crt
├── in/               sanitised inbound files (noexec)            ← kiosk reads
├── out/              Firefox downloads, export-docx output (noexec) ← red stick source
├── quarantine/       ClamAV hits (root only)
├── backups/          restic repo staging
├── stats/            item stats sqlite (tools)
├── release/          last applied release manifest, CHANGELOG.md
└── logs/             intake/export/audit summaries (journald is primary)
```

Docker containers: `read_only: true` root fs with tmpfs for `/tmp` and `/run`; `cap_drop: [ALL]` + `cap_add: [CHOWN, SETUID, SETGID, NET_BIND_SERVICE]` for Apache; `security_opt: [no-new-privileges:true]`; pinned image **digests**, never tags. `docker compose config` output is committed so drift is visible.

---

## 7. TLS & the offline CA

One-time, on edOS as `qbank-admin` (the CA private key then leaves on the release stick and is deleted from the host):

```bash
# CA (10y)
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -days 3650 -nodes \
  -subj "/CN=QBANK Root CA" -keyout ca.key -out qbank-ca.crt

# Server (5y) with SAN
openssl req -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -subj "/CN=qbank.local" \
  -addext "subjectAltName=DNS:qbank.local,IP:10.66.0.1" -keyout qbank.local.key -out s.csr
openssl x509 -req -in s.csr -CA qbank-ca.crt -CAkey ca.key -CAcreateserial -days 1826 \
  -copy_extensions copy -out qbank.local.crt
```

Install `qbank-ca.crt` into `/usr/local/share/ca-certificates/` + `update-ca-certificates`, into Firefox via policy (§8), and hand it to laptop users if the switch is used. `/etc/hosts`: `127.0.0.1 qbank.local`. Put cert expiry (2031) in the calendar.

---

## 8. Kiosk session

**GDM autologin:** `/etc/gdm3/custom.conf` → `AutomaticLoginEnable=true`, `AutomaticLogin=qbank`. Keep `Switch user` available (admin needs it); the lock screen shows only "Unlock" + "Switch user".

**dconf lockdown** `/etc/dconf/profile/user` → `user-db:user` / `system-db:qbank`; `/etc/dconf/db/qbank.d/00-kiosk`:

```ini
[org/gnome/desktop/lockdown]
disable-command-line=true
disable-application-handlers=true
disable-log-out=true
disable-user-administration=true
[org/gnome/desktop/session]
idle-delay=uint32 600
[org/gnome/desktop/screensaver]
lock-enabled=true
lock-delay=uint32 0
[org/gnome/settings-daemon/plugins/power]
power-button-action='interactive'
sleep-inactive-ac-type='nothing'
[org/gnome/desktop/wm/keybindings]
panel-run-dialog=@as []
[org/gnome/settings-daemon/plugins/media-keys]
terminal=@as []
[org/gnome/shell]
favorite-apps=['firefox.desktop','libreoffice-writer.desktop']
[org/gnome/desktop/input-sources]
sources=[('xkb','us'),('xkb','ara')]
[org/gnome/desktop/interface]
enable-hot-corners=false
```

Lock every key above in `/etc/dconf/db/qbank.d/locks/kiosk`. `dconf update`. Autostart `~qbank/.config/autostart/qbank.desktop` → `firefox --kiosk https://qbank.local` (or without `--kiosk` if users want tabs; both are fine, the site allow-list below does the real containment).

**Firefox:** install the **.deb** from Mozilla's apt repository (mirrored to the release stick), **not the snap** — snaps expect the Snap Store and update in ways you can't control offline. `/etc/firefox/policies/policies.json`:

```json
{ "policies": {
  "DisableAppUpdate": true, "DisableTelemetry": true, "DisableFirefoxStudies": true,
  "DisablePocket": true, "DisableFirefoxAccounts": true, "DisableFormHistory": true,
  "DisablePrivateBrowsing": true, "DisableDeveloperTools": true, "BlockAboutConfig": true,
  "OfferToSaveLogins": false, "PasswordManagerEnabled": false,
  "ExtensionSettings": { "*": { "installation_mode": "blocked" } },
  "Homepage": { "URL": "https://qbank.local", "Locked": true, "StartPage": "homepage" },
  "WebsiteFilter": { "Block": ["<all_urls>"],
                     "Exceptions": ["https://qbank.local/*", "file:///srv/qbank/out/*", "file:///srv/qbank/in/*"] },
  "Certificates": { "Install": ["/usr/local/share/ca-certificates/qbank-ca.crt"] },
  "DefaultDownloadDirectory": "/srv/qbank/out", "PromptForDownloadLocation": false,
  "SanitizeOnShutdown": { "Cache": true, "Cookies": true, "History": true, "Sessions": true },
  "Preferences": { "browser.download.start_downloads_in_tmp_dir": { "Value": false, "Status": "locked" } }
} }
```

**LibreOffice** (apt, for DOCX/PDF), fonts `fonts-noto-core fonts-noto-naskh-arabic fonts-noto-color-emoji`, `hunspell-ar hunspell-en-gb`. Disable LibreOffice macros: `MacroSecurityLevel=3`.

**Printing:** CUPS, USB only. `/etc/cups/cupsd.conf`: `Browsing Off`, `Listen localhost:631`. `systemctl disable --now cups-browsed avahi-daemon`. Printer added once as default; kiosk user's print dialog shows just it.

**Plymouth/branding:** replace the Ubuntu logo with the college logo in the boot splash and GDM background; hide the GNOME top-bar app menu. Cosmetic, but it stops "why is this Linux" conversations.

---

## 9. Removable media

**USBGuard** `/etc/usbguard/rules.conf` (generated with sticks present, then edited):

```
allow with-interface equals { 09:00:*  }                        # hubs
allow with-interface equals { 03:*:*  }                         # keyboard/mouse (HID)
allow with-interface equals { 07:*:*  }                         # printer
allow id 04b8:xxxx                                              # scanner (if any)
allow id 0781:5583 serial "4C53000123121511222A" name "QBANK-IN-1"
allow id 0781:5583 serial "4C53000123121511222B" name "QBANK-IN-2"
allow id 0781:5583 serial "4C53000123121511222C" name "QBANK-OUT"
allow id 0781:5583 serial "4C53000123121511222D" name "QBANK-RELEASE"
allow id 1050:0407                                              # YubiKey (if WebAuthn)
allow id 051d:0002                                              # UPS
block with-interface one-of { 02:*:* 0e:*:* e0:*:* ef:*:* }   # network, video, wireless, misc
# implicit: block everything else
```

`ImplicitPolicyTarget=block`, `PresentDevicePolicy=apply-policy`, `InsertedDevicePolicy=apply-policy`. Blocked events go to journald; `qbank-status` shows the last 30 days of them — that's your "someone plugged their phone in" report.

**udev** forces intake sticks read-only at the block layer and labels roles:

```
ACTION=="add", SUBSYSTEM=="block", ENV{ID_SERIAL_SHORT}=="4C53000123121511222A", \
  RUN+="/sbin/blockdev --setro /dev/%k", ENV{QBANK_ROLE}="intake", TAG+="systemd", ENV{SYSTEMD_WANTS}="qbank-intake@%k.service"
ACTION=="add", SUBSYSTEM=="block", ENV{ID_SERIAL_SHORT}=="4C53000123121511222C", ENV{QBANK_ROLE}="export"
```

**`qbank-intake@.service`** (runs as `qbank-svc`, no shell for the user):

1. mount `ro,nodev,nosuid,noexec` at `/media/intake`
2. `clamscan -r --move=/srv/qbank/quarantine` (definitions refreshed from the release stick monthly — no `freshclam` network)
3. delete `*.docm *.xlsm *.pptm *.exe *.js *.vbs *.lnk *.hta *.scr *.iso *.img`; strip `vbaProject.bin` from any remaining OOXML (they're zips)
4. `rsync` only `*.docx *.pdf *.png *.jpg *.gif *.csv *.txt *.xml *.gift` → `/srv/qbank/in/YYYY-MM-DD/`
5. unmount, `logger -t qbank-intake "…N files…"`, desktop notification "Import ready"

**`qbank-export`** (sudo-allowed for `qbank`, prompts for a reason string):

1. Requires red stick present; unlocks LUKS with keyfile readable only by `qbank-svc`.
2. Copies **only** `/srv/qbank/out/<chosen folder>` (menu of folders; no free path).
3. Writes `EXPORT.log` on the stick and `logger -t qbank-export "$SUDO_USER exported <folder> reason=<…>"`.
4. Locks and ejects. auditd watches `/srv/qbank/out` (`-p rwa`) as a second record.

**Wipe-on-return** for blue sticks: `qbank-export wipe-intake` → `blkdiscard` + `mkfs.exfat`. Monthly.

---

## 10. Offline update mechanism (the "release bundle")

Everything that changes on edOS arrives on the **black stick** as a signed bundle; nothing is ever applied ad-hoc.

**On an online Ubuntu 24.04 build VM** (same package set — keep its `dpkg --get-selections` synced with edOS):

```
release/2026-11/
├── apt/            *.deb from `apt-offline get` against edOS's `apt-offline set` signature file
├── docker/         moodle-5.3.1.tar (docker save), postgres-16.x.tar, + digests
├── moodle/         moodle-5.3.1.tgz, ar.zip, plugins/*.zip
├── clamav/         main.cvd daily.cvd bytecode.cvd
├── firefox/        firefox_*.deb
├── scripts/        updated qbank-* scripts, dconf, policies.json, nftables (git tag)
├── MANIFEST.sha256
└── MANIFEST.sha256.sig   (GPG/minisign; public key baked into edOS at build)
```

**On edOS:** `qbank-release verify /media/release/2026-11` (signature + hashes, refuses on any mismatch) → `qbank-release apply` which: snapshots (MOODLE.md §10), `dpkg -i` in dependency order, `docker load`, copies configs, restarts services, runs the acceptance test (§16), logs to `CHANGELOG.md`. Rollback: `apt` via `/var/backups/dpkg.status`, containers via previous digest, configs via `etckeeper` (git in `/etc`, installed at build — commit on every apply).

Cadence: **quarterly** for the OS/ClamAV, on-demand for Moodle security advisories that matter. Ubuntu security updates for components you don't expose (no sshd, no network) are low urgency; kernel/LUKS/systemd/Firefox/LibreOffice updates are the ones to prioritise because they process untrusted input (files) or protect data at rest.

---

## 11. Logging, audit, monitoring

- `journald`: `Storage=persistent`, `SystemMaxUse=4G`, `Seal=yes` (forward secure sealing with a key kept on the release stick — tamper-evident logs).
- `auditd` `/etc/audit/rules.d/qbank.rules`:

```
-w /etc/sudoers -p wa -k sudoers
-w /etc/sudoers.d -p wa -k sudoers
-w /srv/qbank/out -p rwa -k qbank_export
-w /srv/qbank/tls -p rwa -k tls
-w /etc/usbguard -p wa -k usbguard
-w /etc/nftables.conf -p wa -k fw
-a always,exit -F arch=b64 -S mount,umount2 -k mounts
-a always,exit -F arch=b64 -S execve -F euid=0 -F auid>=1000 -k root_cmds
-e 2      # immutable until reboot
```

- Docker logs to journald (`daemon.json`). Moodle's own log store is the *content* audit (who edited what item); journald/auditd is the *system* audit (who exported, who plugged what in).
- `qbank-status` (weekly, prints one A4 the admin signs and files — auditors love this): disk %, SMART health both disks, last backup + restore-drill dates, clock vs. reference, cert expiry days, USBGuard blocks (30d), export events (30d), pending release, Moodle version, item counts per bank, failed logins (Moodle + PAM).
- UPS: `nut` or `apcupsd` → `upsmon` shuts down cleanly at 20% battery.

---

## 12. Backup (system layer)

- **Nightly 02:00** `restic backup` of `/srv/qbank/{moodledata,backups/nightly,in,out,stats,compose,tls}` + `/etc` → repo on `/mnt/backup` (second encrypted disk). Postgres dumped first (MOODLE.md §10) so DB is consistent; `pgdata/` itself is *excluded* (dumps are portable; raw pgdata isn't).
- **Weekly** `restic copy` to a second repo on the **red stick** (or a dedicated 5th "BACKUP" stick if you'd rather not mix roles) → stored in the exam-office safe. That's your offsite.
- `restic forget --keep-daily 14 --keep-weekly 8 --keep-monthly 24 --prune`.
- **Restic repo password** in the sealed envelope. Without it, backups are noise — this is the single most-forgotten secret in small deployments.
- **Quarterly drill**: restore to `/srv/qbank-restore-test`, bring up a second compose project on 8081, log in, count questions. 30 minutes. Calendar it.

---

## 13. Kernel & OS hardening baseline

`/etc/sysctl.d/90-qbank.conf`:

```
kernel.kptr_restrict=2        kernel.dmesg_restrict=1      kernel.yama.ptrace_scope=2
kernel.sysrq=0                kernel.unprivileged_bpf_disabled=1
fs.suid_dumpable=0            fs.protected_fifos=2         fs.protected_regular=2
fs.protected_hardlinks=1      fs.protected_symlinks=1
net.ipv4.ip_forward=0         net.ipv4.conf.all.accept_redirects=0
net.ipv6.conf.all.disable_ipv6=1
dev.tty.ldisc_autoload=0
```

Plus:
- AppArmor enforcing (default; add the Firefox and LibreOffice profiles from `apparmor-profiles`).
- `ulimit -c 0` + `Storage=none` in `coredump.conf`.
- `unattended-upgrades` **removed** (would silently fail forever offline — noise in logs).
- `snapd` removed (needs the store; nothing you use requires it).
- `whoopsie`, `apport`, `kerneloops`, `ubuntu-report` removed; `motd-news` disabled.
- `timesyncd` disabled (no NTP).
- GRUB password set, `GRUB_CMDLINE_LINUX="… intel_iommu=on iommu=force lockdown=confidentiality"` (or `amd_iommu`).
- `bolt` policy = no Thunderbolt authorisation.

Run **OpenSCAP** with the ComplianceAsCode Ubuntu 24.04 CIS Level 1 profile once at build (`oscap xccdf eval …` — the content ships offline as an XML file) to catch anything this document misses, then document accepted deviations (autologin and no NTP will be flagged; both are deliberate).

---

## 14. Physical & procedural controls

- Room lockable; key log. Machine on Kensington lock; case screws sealed with tamper-evident stickers (photograph them, keep photo in the release folder).
- **Sealed envelope in the exam-office safe** contains: LUKS passphrase, BIOS supervisor password, GRUB password, `qbank-admin` password, restic repo password, Moodle admin password + TOTP recovery codes, CA private key location (the release stick), release-signing private key passphrase. Opened only with two signatures; re-sealed with new date. Check quarterly it's still sealed.
- **Sign-in sheet** on the door (name, time in/out, purpose). Cheap, effective, and correlates with the audit log.
- **No phones on the desk** if you go WebAuthn; otherwise phones face-down, used for TOTP only. Camera use is the one threat technology can't address; make it explicit in the committee policy.
- Cleaners/maintenance never unaccompanied.

---

## 15. Incident playbook

| Event | Action |
|-------|--------|
| Unknown USB device blocked | `qbank-status` shows it; ask who was in the room per sign-in sheet; document. No further action unless repeated. |
| Blue stick missing | Low risk (inbound only, wiped monthly). Revoke its serial in USBGuard; issue replacement. |
| **Red stick missing** | It's LUKS; risk is low if passphrase secure. Rotate LUKS key on replacement; review `EXPORT.log` copy on host for what was on it; inform committee in writing. |
| Suspected leak of a paper | Freeze the quiz; export Moodle log of who viewed/previewed those items (Moodle → Reports → Logs, filter by course EXAMS); auditd export events; sign-in sheet. The three sources together usually identify the vector in an hour. |
| Disk failure (system) | Replace, reinstall from `edos-build.sh`, restore restic from `/mnt/backup`, redeploy compose. Target: half a day. |
| Disk failure (backup) | Replace, `restic init`, `restic copy` from red-stick repo, resume nightly. |
| Forgotten LUKS passphrase | Sealed envelope. If also lost: the data is gone; restore from the red-stick repo onto a rebuilt machine. This is why the envelope check is quarterly. |
| Clock wildly wrong (TOTP failing for all) | `qbank-admin` logs in locally (PAM doesn't need TOTP), `timedatectl set-time`, done. |
| Admin leaves the college | Hand-over: new admin sets new LUKS passphrase (`cryptsetup luksChangeKey`), new sudo password, new Moodle admin password, re-signs release key, new envelope. Half a day; scripted as `qbank-handover`. |

---

## 16. Build & acceptance

`scripts/edos-build.sh` applies §3–§13 idempotently on a fresh 24.04 minimal install and finishes by running `scripts/edos-accept.sh`, which must print all PASS:

```
[PASS] Secure Boot enabled, TPM present
[PASS] Root FS on LUKS2 (argon2id)
[PASS] No wireless interfaces; cfg80211 not loadable
[PASS] nftables policy drop on input/forward/output
[PASS] No route to default gateway; curl 1.1.1.1 fails (timeout <2s)
[PASS] Docker daemon iptables=false; containers have no default route
[PASS] https://qbank.local returns Moodle login (CA-validated, no warning)
[PASS] Moodle: guest off, self-reg off, MFA enforced for Manager, noemailever
[PASS] GDM autologin=qbank; dconf locks present; Firefox policies loaded
[PASS] USBGuard active; unknown mass-storage blocked (tested with spare stick)
[PASS] Intake stick mounts ro/noexec; clamscan available; DB age <90d
[PASS] auditd immutable; journald sealed; sudo logging
[PASS] restic repo reachable; last snapshot <24h (skip on first build)
[PASS] Cert expiry >365d; clock within 60s of operator reference
[PASS] sshd, snapd, avahi, cups-browsed, unattended-upgrades absent
[WARN] No NTP (by design)   [WARN] Autologin enabled (by design)
```

Paste that output into `CHANGELOG.md` at every release. If a future auditor asks "how do you know the controls are in place?", that file is the answer.

---

*Where the two documents meet:* Moodle trusts the host for *everything about the exit path* — export directory, red stick, audit — and the host trusts Moodle for *who did what to which item*. Neither alone is a security boundary; together they are, and every incident in §15 is resolved by reading both logs side by side.

**Next deliverables if you want them:** `edos-build.sh` + `edos-accept.sh` implementing this document verbatim, and the Moodle role XML/`config.php`/`compose.yml` set implementing `MOODLE.md` §2–§5 so setup is a single `make bootstrap`.
