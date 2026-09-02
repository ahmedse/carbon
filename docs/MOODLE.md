# MOODLE: Question Bank Platform Configuration & Operations Manual

**Scope:** everything inside the container: Moodle version, site settings, information architecture, roles, item metadata, authoring workflow, import/export, exam assembly, post-exam analysis, backup, upgrade. Assumes the edOS host from `docs/EDOS.md` (`https://qbank.local`, `/srv/qbank/…`, `qbank-admin`).

> **Version note (Sept 2026):** Moodle 4.5 LTS is now security-only; Moodle 5.3 LTS ships 5 Oct 2026. The 5.x line has a redesigned question bank (banks are shareable modules, not locked inside courses), which is exactly the QBank use case. See §1.

---

## 0. Design principles (read these first; every decision below follows from them)

1. **Moodle is the database, not the exam engine.** Students never touch it. It exists to hold items with metadata, version history, review dialogue, and to assemble papers. Every Moodle feature not serving that is turned off.
2. **Structure = blueprint.** The category tree mirrors the assessment blueprint so that "Cardiovascular pharmacology, 8 items, ≥3 at Apply level" is a filter, not a hunt.
3. **Metadata that isn't enforced doesn't exist.** Controlled vocabularies, weekly audit query, no free-text classification.
4. **Reproducibility over cleverness.** High-stakes papers use fixed item lists pinned to a question *version*, never "random from category."
5. **No network → no email, no update checks, no remote anything.** Clock and TLS cert become your two silent failure modes (see §13).

---

## 1. Version decision

| Option | Status (Sept 2026) | Verdict |
|--------|--------------------|---------|
| 4.5 LTS | Security-only until 4 Oct 2027. Old per-course question bank model. | **No.** You'd be on a dying branch in 12 months and lack shared banks. |
| 5.2 | Current stable; general support to Apr 2027. New shared question-bank model (`mod_qbank`). PHP 8.2–8.4. | **Install now.** |
| 5.3 LTS | Releases 5 Oct 2026; security support to Oct 2029. | **Upgrade to 5.3.1 in Dec 2026**, then freeze. One upgrade in three years is the right cadence for an air-gapped box. |

**Why 5.x matters for you specifically:** in 5.x a question bank is a first-class object that lives in a course but is usable from any quiz on the site by anyone with `moodle/question:useall` on it. So "Pharmacology bank" is one thing, shared by every module exam that needs a pharm item, with one version history. In 4.x you'd be faking this with course-category contexts.

**Stack (pinned by digest in `compose.yml`):**

- Own image: `FROM moodlehq/moodle-php-apache:8.3` + Moodle 5.2.x tgz (sha256 verified). Don't use third-party "moodle" images — Bitnami's distribution model changed in 2025 and you can't rely on tags staying pullable; and you need offline reproducibility anyway.
- `postgres:16` (official). Postgres over MariaDB: better `pg_dump` consistency, saner collation for Arabic, and Moodle's own recommendation.
- No Redis, no Memcached — single-digit concurrent users; file cache on NVMe is fine.
- Container has **no outbound network** (edOS §5). Moodle will complain about not reaching moodle.org; the config below silences that.

---

## 2. `config.php` — the non-negotiables

```php
$CFG->wwwroot   = 'https://qbank.local';
$CFG->sslproxy  = true;                 // TLS terminated by host nginx
$CFG->dataroot  = '/var/www/moodledata';
$CFG->dbtype    = 'pgsql';
$CFG->prefix    = 'mdl_';
$CFG->dboptions = ['dbpersist' => 0, 'dbport' => 5432, 'dbcollation' => 'utf8mb4_unicode_ci'];

// Air-gap
$CFG->noemailever                 = true;   // never try to send mail
$CFG->disableupdatenotifications  = true;   // no calls to download.moodle.org
$CFG->disableupdateautodeploy     = true;
$CFG->curlsecurityblockedhosts    = "0.0.0.0/0\n::/0"; // belt and braces
$CFG->preventexecpath             = true;   // no admin-editable exec paths (ghostscript etc.)

// Security
$CFG->cookiesecure   = true;
$CFG->cookiehttponly = true;
$CFG->forcelogin     = true;   // nothing visible without login
$CFG->loglifetime    = 0;      // keep logs forever (audit trail is the point)
$CFG->passwordsaltmain = '<64 random chars>'; // set once, back up with the DB
$CFG->cronclionly    = true;   // cron only from CLI (host systemd timer)
$CFG->debugdisplay   = 0;

// Forced settings the UI can't undo
$CFG->forced_plugin_settings = [
  'tool_mfa' => ['enabled' => 1, 'lockout' => 5],
];
```

**Host-side cron** (edOS, not container): systemd timer every minute → `docker compose exec -T moodle php admin/cli/cron.php`. Moodle's question-version cleanup, log rotation, and stats tasks depend on it.

---

## 3. Site administration settings (one pass, ~40 min)

### Users → Authentication

- Manual accounts only. Disable: email-based self-registration, guest login (`guestloginbutton = Hide`), "Allow log in via email" off.
- **MFA (`tool_mfa`, core since 4.3):** enable factor `totp` (weight 100) and configure as: `totp` = 100; `role` factor with Manager/Administrator selected so admins *cannot* skip; `grace` = 100 with 7-day period for onboarding. Required points: 100. Result: everyone gets 7 days from first login to enrol a phone; after that TOTP is mandatory.
- **Phones-not-allowed alternative:** factor `webauthn` (core in 4.5+). A £25 FIDO2 key per coordinator works with zero network. If your exam-room policy bans phones, this is the answer, and it's arguably better (can't be photographed).
- Password policy: min 12, 1 digit, 1 non-alphanumeric, rotation *off* (rotation is counterproductive; MFA carries the load). Lockout threshold 5, duration 30 min.
- Session timeout 30 min (Security → Site policies). Kiosk lock is at 10 min anyway.

### Security → Site policies

- Force users to log in ✔; Open to Google ✗; Maximum uploaded file size 64 MB (Word files with images); Allow EMBED/OBJECT ✗; Enable trusted content ✗ (nobody needs raw JS in questions); `allowobjectembed` off.
- **Protect usernames** ✔; **Log out on browser close** via kiosk anyway.

### Advanced features

Turn **off**: Blogs, Badges, Portfolios, Competencies (unless you'll map ILOs there — see §6), Analytics, MoodleNet, Web services, Mobile web service, Global search (unless you want it — it's useful for question text search; enable with the *simple DB* engine, no Solr), Messaging, Notes, Comments *(keep — used by qbank review)*, Course request, RSS.

### Plugins

- Question bank sub-plugins: keep `qbank_comment`, `qbank_history`, `qbank_tagquestion`, `qbank_usage`, `qbank_statistics`, `qbank_viewcreator`, `qbank_editquestion`, `qbank_columnsortorder`, `qbank_bulkmove`, `qbank_importquestions`, `qbank_exportquestions`, `qbank_previewquestion`, `qbank_deletequestion`. Disable nothing yet; decide `qbank_exportquestions` in §5.
- Question types: **disable** `calculated*`, `randomsamatch`, `truefalse` (T/F is banned in most medical assessment standards), `gapselect` unless used, `ddwtos`. Keep `multichoice`, `match`, `description`, `essay`, `shortanswer`, `numerical`, `ddmarker`, `ddimageortext`, `multianswer` (cloze), `ordering` (core in 4.5+; useful for key-features items).
- Text editor: TinyMCE (default). Add Arabic to `Site administration → Language → Language packs` by unzipping `ar.zip` (from `download.moodle.org/langpack/5.2/`) into `moodledata/lang/ar/` offline; purge caches. Set `langlist = en,ar`.

### Appearance → Manage tags

Create tag collection **"Item metadata"**, area = Questions, and pre-create the *standard* tags from §6. Tick "Show standard tags". Core does **not** hard-block ad-hoc tags, so the weekly audit query in §6 is what enforces the vocabulary.

### Front page

Set to a single Page block with three links: *Question banks*, *Exams*, *Exports (/srv/qbank/out)*, and the laminated-sheet text. Nothing else.

---

## 4. Information architecture

```
Site
└── Course category: "QBANK"                     (hidden from nobody; it's the whole site)
    ├── Course: BANK-ANAT   "Anatomy"            ← one course per academic module
    │   └── Question bank: "Anatomy – Master"     ← exactly ONE bank per module course
    │       ├── Category: 01 Upper limb
    │       │   ├── 01.1 Shoulder
    │       │   └── 01.2 Brachial plexus
    │       ├── 02 Thorax
    │       └── ZZ Retired                         ← never delete; move here
    ├── Course: BANK-PHARM  "Pharmacology"
    ├── …one per module…
    ├── Course: EXAMS-2026-27  "Exam papers 2026/27"   ← quizzes live here (§8)
    └── Course: SANDBOX "Training & import staging"    ← authors practise; imports land here first
```

**Rules:**

- **Category depth ≤ 3** and categories are *content* (system/topic), never process ("Dr Ahmed's questions", "2025 exam"). Process is tags.
- **Category names are numbered** so they sort like the blueprint document.
- **One bank per module**, named `<Module> – Master`. Quizzes get their own auto-bank in 5.x; you never author into those.
- **Question `ID number`** is mandatory and follows `MOD-CAT-NNNN` e.g. `PHARM-CVS-0042`. It's the stable handle across versions, exports, and the item-stats spreadsheet. Moodle enforces uniqueness only within a bank; the prefix keeps it globally unique. Question *name* = first 8 words of the stem (auto via import tool).
- **Never delete a question.** Move to `ZZ Retired`, tag `status:retired`, comment why. Deleting breaks the audit trail and any historical paper that referenced it.

---

## 5. Roles

Create five site-level custom roles (Users → Permissions → Define roles), all based on *no archetype*, assigned in the **course** context of the relevant BANK-* course (which flows down to the bank). Prohibit everything not listed.

| Capability (`moodle/question:*` unless noted) | Author | Reviewer | Coordinator | Exam Officer | Bank Admin |
|-----------------------------------------------|--------|----------|-------------|--------------|------------|
| `viewmine` / `viewall` | ✔ / – | ✔ / ✔ | ✔ / ✔ | ✔ / ✔ | ✔ / ✔ |
| `add` | ✔ | – | ✔ | – | ✔ |
| `editmine` / `editall` | ✔ / – | – / ✔¹ | ✔ / ✔ | – / – | ✔ / ✔ |
| `usemine` / `useall` (put in a quiz) | – | – | ✔ | ✔ | ✔ |
| `movemine` / `moveall` | – | – | ✔ | – | ✔ |
| `managecategory` | – | – | ✔ | – | ✔ |
| `tagmine` / `tagall` | ✔ / – | – / ✔ | ✔ / ✔ | – | ✔ |
| `commentmine` / `commentall` | ✔ | ✔ | ✔ | ✔ | ✔ |
| `mod/quiz:manage`, `mod/quiz:preview` in EXAMS course | – | – | ✔ (own module's quiz) | ✔ | ✔ |
| `moodle/course:view` EXAMS course | – | – | ✔ | ✔ | ✔ |
| `qbank/importquestions:*`² | – | – | – | – | ✔ |
| Site administration | – | – | – | – | ✔ (= `qbank-admin` Moodle account) |

¹ Reviewers edit *all* so they can fix typos and flip status to Ready; the version history records it as their edit.

² Import/Export capabilities live under the sub-plugins in 5.x; check exact names in *Define roles* search for "export"/"import".

**Export decision.** The clean approach: authors and reviewers *cannot* export. Coordinators can export their own bank (they need it for the DOCX pipeline). Export is a *download in Firefox*, and Firefox's download directory is pinned to `/srv/qbank/out/` (edOS §8), which only leaves the room on the red stick. So the technical control on export is the *host*, not Moodle; Moodle's role just reduces the number of people who can trigger it.

**Accounts:** one real person per account, username = college ID, `Department` field = module code. No shared "reviewer" logins — the audit log is worthless if people share accounts. Create with *Upload users* (CSV) from `/srv/qbank/in/users.csv`.

---

## 6. Item metadata schema (tags)

Format `key:value`, lowercase, no spaces. Pre-create all as standard tags.

| Key | Values | Set by | Required |
|-----|--------|--------|----------|
| `status` | `draft` `review` `approved` `retired` | workflow (§7) | ✔ (in addition to Moodle's Draft/Ready flag — Moodle's flag is binary; you need four states) |
| `bloom` | `recall` `understand` `apply` `analyse` | author, confirmed by reviewer | ✔ |
| `diff` | `easy` `moderate` `hard` (a priori) | author | ✔ |
| `type` | `sba` (single best answer) `emq` `sa` `kf` (key features) `meq` `image` | author | ✔ |
| `ilo` | `PHARM-3.2` (ILO code from module spec) | author | ✔ |
| `sys` | `cvs` `resp` `gi` `renal` `neuro` `msk` `endo` `haem` `repro` `derm` `id` `psych` | author | ✔ for integrated modules |
| `used` | `2025-s1-pharm` (paper ID) | **automated** by `tools mark-used` after each exam | – |
| `src` | `lecture` `textbook` `clinical` `external` | author | – |
| `flag` | `stats-review` `flawed` `duplicate-of:PHARM-CVS-0017` | post-exam / reviewer | – |

**Why not Moodle Competencies for ILOs?** They work, but they're heavier than you need and don't surface in the question bank filter. Tags do. If accreditation later needs a competency framework, export the `ilo:` tags to one.

**Weekly vocabulary audit** (run by `tools audit-tags`, or this SQL via `docker compose exec db psql`):

```sql
SELECT t.name, COUNT(*) FROM mdl_tag t
JOIN mdl_tag_instance ti ON ti.tagid=t.id AND ti.itemtype='question'
WHERE t.isstandard=0 GROUP BY t.name ORDER BY 2 DESC;
```

Anything listed is a typo or a new value someone wants; either fix or promote to standard.

**Missing-metadata report:** questions with `status:approved` lacking any of the required keys → shown to coordinator on Monday. (`tools audit-meta`.)

---

## 7. Authoring & review workflow

```
 Author writes → status:draft  (Moodle flag: Draft)
      │  self-check against item-writing checklist (below)
      ▼
 Author tags status:review, comments "@reviewer ready"
      │
      ▼
 Reviewer (different person, same module) reads item + answer + rationale
      ├─ FAIL → comment with specific flaw code, status:draft, back to author
      └─ PASS → fixes trivia, sets Moodle flag Ready, tag status:approved,
                confirms bloom/diff/ilo tags
      │
      ▼
 Available to Coordinator for assembly (filter: status:approved, used: ∉ last 2 papers)
      │
      ▼
 After exam: tools mark-used + item stats → flag:stats-review if outside thresholds (§9)
      │
      ├─ revise → new version (history keeps old), reviewer re-approves
      └─ retire → move to ZZ Retired, status:retired
```

**Moodle mechanics that make this work:**

- Every save = new **version**; the History column shows who/when. Assembly (§8) references a specific version; if an author later edits, the quiz shows "newer version available" and the Exam Officer *chooses* whether to update. Nothing changes under a frozen paper.
- **Comments** (`qbank_comment`) are the review dialogue. Rule: every status change has a comment. No email exists, so reviewers check the *Comments* column filter `> 0` and the `status:review` tag filter on their Monday slot.
- **Draft/Ready flag** is what quizzes honour: Draft items cannot be added to a quiz. Reviewer is the only role that flips it.

**Item-writing checklist (SBA) — laminate this next to the user sheet:**

1. Stem is a clinical vignette: age, sex, presentation, relevant findings, *then* the lead-in.
2. Lead-in is a focused question answerable with options covered ("cover-the-options" test).
3. Exactly one best answer; distractors are plausible *and homogeneous* (all drugs, all diagnoses).
4. No "all/none of the above", no "except", no negatives in the lead-in, no absolutes (always/never).
5. Options alphabetical or logical order; similar length; no grammatical cue to the key.
6. No verbatim textbook phrase in the key; no item that gives away another item's answer.
7. Rationale in *General feedback* explains why the key is correct **and** why each distractor is wrong (this is what makes the bank a teaching asset later).
8. Tags complete; ID number set; image has alt text; Arabic text has `dir="rtl"` span if mixed.

---

## 8. Import & export

**Canonical format: Moodle XML.** It round-trips everything (images base64-embedded, tags, ID number, general feedback, version-agnostic). GIFT and Aiken are for *authoring speed*, never for archive.

**Authoring in Word → Moodle.** Give authors this template (one item; `tools convert-docx` parses it into Moodle XML with tags and images):

```
ID: PHARM-CVS-0042
Tags: bloom:apply diff:moderate type:sba ilo:PHARM-3.2 sys:cvs
A 64-year-old man with heart failure (LVEF 30%) on ramipril and bisoprolol
develops bilateral ankle oedema and a serum K⁺ of 5.9 mmol/L after a new drug
was started two weeks ago. Which drug is most likely responsible?
A. Amlodipine
B. Digoxin
*C. Spironolactone
D. Furosemide
E. Ivabradine
Explanation: Aldosterone antagonists cause hyperkalaemia, especially with ACE
inhibitors... Amlodipine causes oedema but not hyperkalaemia; ...
---
```

Rules for the template: asterisk marks the key; `---` separates items; images pasted inline are extracted and embedded. The converter rejects items failing checks 4 and 5 above (mechanical checks: option count 4–5, "all of the above", negative lead-in words) and writes a rejection list — cheap enforcement of the checklist.

**GIFT** (for coordinators who prefer typing straight into Moodle's importer):

```gift
// question: PHARM-CVS-0042
::PHARM-CVS-0042::[html]<p>A 64-year-old man ... most likely responsible?</p>{
  ~Amlodipine
  ~Digoxin
  =Spironolactone
  ~Furosemide
  ~Ivabradine
  ####<p>Aldosterone antagonists cause hyperkalaemia ...</p>
}
```

GIFT can't carry tags or ID numbers reliably — fine for staging into SANDBOX, then bulk-tag.

**Import procedure:**

1. File arrives in `/srv/qbank/in/` (blue stick pipeline or laptop drop-share; edOS §9). Already ClamAV-scanned and macro-stripped.
2. Bank Admin: `tools convert-docx in/PHARM-batch-07.docx → in/PHARM-batch-07.xml` (+ `.rejects.txt`).
3. Moodle → SANDBOX course → its bank → *Import* → Moodle XML → into category `Staging/<module>/<date>`. Match grades: *Nearest grade*; Stop on error: **Yes**.
4. Eyeball 3 items (images, Arabic direction). Bulk-move to the module bank's correct category (`qbank_bulkmove`).
5. Delete the staging category. Log line via `logger -t qbank-import`.

**Export:**

- Whole-bank archival: monthly, Bank Admin exports each bank as Moodle XML to `/srv/qbank/out/archive/YYYY-MM/` — this is your **format-independent escrow**. If Moodle ever dies, this restores into any Moodle or converts to QTI.
- Paper export: §8b below.

---

## 8b. Exam assembly

1. **Blueprint first.** A spreadsheet/CSV per paper: rows = category × bloom level × count. `tools blueprint-check PHARM-2026-S1.csv` reports which cells the bank can satisfy from `status:approved` items not `used:` in the last two sittings. Fix shortfalls *before* assembly day.
2. In `EXAMS-2026-27`, create quiz `PHARM-2026-S1-FINAL`. Settings: *Shuffle within questions* ✔ (option order randomised per print variant), *Shuffle questions* ✗ (order is designed), layout *every page*, no time limit, no grade display — it's a container.
3. Add questions from the module bank **by explicit selection** using the filter panel (category + tags). Not random. Random-from-category is for formative/practice only: you cannot reproduce it, defend it to an appeals panel, or compute item stats against a stable list.
4. Coordinator + Exam Officer both preview (`mod/quiz:preview`) — the standard "second pair of eyes" on the *assembled* paper (cueing between items, duplicate concepts).
5. `tools export-docx --quiz PHARM-2026-S1-FINAL --variants 2 --out /srv/qbank/out/PHARM-2026-S1/` produces: Paper A/B (DOCX + PDF, Noto Naskh Arabic embedded for RTL items), answer keys, item-ID map for stats, blueprint coverage sheet. Version-pinned: the tool records question version IDs into `manifest.json` in the same folder.
6. Print via LibreOffice → CUPS. Copy folder to red stick. **Nothing else leaves.**

**If you deliver on paper with OMR sheets:** evaluate `mod_offlinequiz` (Academic Moodle Cooperation, Vienna). It generates the question paper PDF + answer sheets, and scans the filled sheets back in with a USB scanner to give per-item statistics inside Moodle. It's mature and widely used in European med schools. **Check its supported-version list against 5.2/5.3 before committing**; if it lags, run analysis via `tools` (§9) instead.

---

## 9. Post-exam item analysis

Input: per-student response matrix (from OMR software, or the exam office spreadsheet) as CSV keyed by item ID from `manifest.json`. `tools item-stats` computes per item:

| Metric | Keep | Review (`flag:stats-review`) | Notes |
|--------|------|------------------------------|-------|
| Difficulty *p* | 0.30–0.85 | <0.30 or >0.85 | >0.90 may still be fine for must-know safety items — reviewer decides |
| Discrimination (point-biserial) | ≥0.20 | 0.10–0.20 | <0.10 with *p* in range → likely keying error; **check the key first** |
| Negative discrimination | – | **always** | Almost always a mis-key or ambiguous item |
| Distractor functioning | each distractor chosen by ≥5% | any distractor <5% | Replace the dead distractor; item stays |
| Paper KR-20 | ≥0.80 for a 100-item final | | Report to committee |

The tool writes a **comment** on each flagged question (`"2026-S1: p=0.91 rpb=0.04 — review key"`), adds `flag:stats-review`, and adds `used:2026-s1-pharm` to every item on the paper. Stats never go into question text or feedback; comments are the right place because they're versioned, attributable, and filterable.

Cumulative stats across sittings live in `/srv/qbank/stats/items.sqlite` (tool-owned), keyed by ID number — Moodle isn't a good home for longitudinal psychometrics.

---

## 10. Backup & restore (Moodle layer)

- **Nightly (host timer, 02:00):** `pg_dump -Fc` + `tar` of `moodledata` (excluding `cache/`, `localcache/`, `sessions/`, `temp/`, `trashdir/`) → `/srv/qbank/backups/nightly/`. Encrypted and deduplicated by `restic` (edOS §12).
- **Monthly:** Moodle XML export of every bank (§8) — logical, format-independent.
- **Before every upgrade or bulk import:** manual snapshot, `tools snapshot "pre-upgrade-5.3"`.
- **Quarterly restore drill** into `SANDBOX` on the same host: `tools restore-test` restores the latest dump into a throwaway compose project on port 8081, runs `php admin/cli/check_database_schema.php`, counts questions per bank vs. production, and prints a pass/fail. Unrehearsed backups aren't backups.

Retention: 14 nightly, 12 monthly, all pre-upgrade snapshots.

---

## 11. Offline upgrade procedure

Do this at most twice a year; **minor** point releases (5.2.x) only when a security advisory affects components you actually use (most Moodle CVEs are in features you've disabled — read the advisory, don't reflexively patch a machine with no network).

1. On an internet machine: download `moodle-5.3.1.tgz` + `.sha256`, any plugin zips (offlinequiz), `ar.zip` langpack. Verify. Put on release stick with `manifest.json` signed (edOS §10).
2. On edOS: `qbank-release verify /media/release` → `tools snapshot pre-5.3.1`.
3. `docker compose exec moodle php admin/cli/maintenance.php --enable`
4. Build new image (`Dockerfile` ARG `MOODLE_TGZ`), `docker compose up -d moodle`.
5. `docker compose exec moodle php admin/cli/upgrade.php --non-interactive`
6. `php admin/cli/purge_caches.php`; log in; check *Notifications*, question bank opens, one export works, MFA still prompts.
7. `maintenance.php --disable`. Log the release in `CHANGELOG.md`.

Rollback = `docker compose down`, restore snapshot, `up` with the previous image tag. Rehearse once in SANDBOX before doing it on the real site.

---

## 12. Users' day-to-day (for the laminated sheet, Moodle side)

- Login → your name top-right → **Question banks** (in the module course) → filter by tag. Bookmarking a filtered URL is fine; the filter is in the URL.
- New item: *Create a new question* → SBA = "Multiple choice", one answer only, shuffle ✔, numbering `A.`. Fill *General feedback* with the rationale. Set ID number. Tags. Save → it's a Draft.
- Review: filter `status:review`, open, read, comment, change tags, set *Ready*.
- **Log out** when leaving the seat. The kiosk locks in 10 min anyway, but the audit log is only accurate if you do.

---

## 13. The two silent failures

1. **Clock drift → TOTP fails for everyone.** No NTP on an air-gapped box; the RTC drifts seconds per month. TOTP tolerates ±30 s (one step). `qbank-status` prints the clock; Bank Admin compares with a phone monthly and corrects with `timedatectl set-time`. Also keep two **TOTP recovery codes per user** printed and sealed in the exam-office safe, and the `admin` account's codes separately. (WebAuthn keys don't depend on the clock — one more argument for them.)
2. **TLS certificate expiry → browser refuses `qbank.local`.** Issue the server cert for **5 years** from your offline CA (edOS §7); put the expiry date in the maintenance calendar with a 90-day reminder. Firefox policy pins the CA, so there's no "click through" for the kiosk user — expiry is a hard stop.

---

*Where the two documents meet:* Moodle trusts the host for *everything about the exit path* — export directory, red stick, audit — and the host trusts Moodle for *who did what to which item*. Neither alone is a security boundary; together they are, and every incident (edOS §15) is resolved by reading both logs side by side.
