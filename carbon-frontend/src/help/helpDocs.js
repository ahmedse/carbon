// src/help/helpDocs.js
// Brand-aware platform help + per-app help documents.
//
// ONE SOURCE OF TRUTH for the Help section. The platform doc is resolved from
// the active brand (src/config/branding), and each domain app contributes its
// own help doc keyed by app id (matching src/apps/registry.js). Unknown apps
// get a doc auto-generated from their manifest, so future apps need zero edits.

import {
  PLATFORM_TITLE,
  PLATFORM_NAME,
  PLATFORM_DESCRIPTION,
  PLATFORM_TAGLINE,
} from "../config/branding";
import { APP_BY_ID } from "../apps/registry";

// ─────────────────────────────────────────────────────────────────────────
// Help doc shape:
//   {
//     kind:        'platform' | 'app',
//     title:       string,                     // H1 ("Welcome to …")
//     intro:       string,                     // bold one-line subtitle
//     description: string,                     // body paragraph
//     cards:       [{ icon, title, description }],   // icon = token (see renderer)
//     steps:       [{ label, icon, description }],   // workflow stepper
//     userStory:   { title, character, scenes: [{ time, text }] } | null,
//     faqs:        [{ q, a }],
//     contact:     { intro, email, version, lastUpdated } | null,
//   }
// ─────────────────────────────────────────────────────────────────────────

// ── Platform (Data Trust) help — brand-aware, never carbon-specific ──────
export function getPlatformHelpDoc() {
  return {
    kind: "platform",
    title: `Welcome to ${PLATFORM_NAME}`,
    intro: PLATFORM_TAGLINE,
    description: PLATFORM_DESCRIPTION,
    cards: [
      {
        icon: "workspace",
        title: "Unified Workspace",
        description:
          "All your Data Products (Modules), tables, and domain apps in one governed place. Switch between apps with a single click. Datasets (versioned contracts) are a separate Dataset Hub path.",
      },
      {
        icon: "data",
        title: "Governed Data",
        description:
          "Catalog, master data, and data-quality rules keep every domain app consistent, compliant, and trustworthy.",
      },
      {
        icon: "insights",
        title: "Instant Insights",
        description:
          "Use filters, dashboards, and export tools to turn governed data into actionable reports.",
      },
    ],
    steps: [
      {
        label: "Open a Domain App",
        icon: "app",
        description:
          "From the home portal or sidebar, open the domain application you work in (for example People, Carbon Footprint, or Healthy).",
      },
      {
        label: "Navigate Modules & Tables",
        icon: "navigate",
        description:
          "Use the sidebar to reach the modules and data tables inside each app. Every app declares its own structure.",
      },
      {
        label: "Add or Edit Data",
        icon: "add",
        description:
          "Within any table, use the 'Add Row' button to enter data. Click the edit icon to update rows, or the trash icon to delete.",
      },
      {
        label: "Analyze & Export",
        icon: "export",
        description:
          "Use filters and search to analyze records. Export data to CSV or rich formats for reporting and further analysis.",
      },
      {
        label: "Track Progress & Collaborate",
        icon: "collaborate",
        description:
          "Review data completeness, collaborate with your team, and provide feedback to continuously improve the platform.",
      },
    ],
    userStory: null,
    faqs: [
      {
        q: "How do I create a new table or module?",
        a: "If you have admin permissions, open a Data Product (Module) in Catalog Studio to add tables. Define fields, types, and access controls so your team can start entering data. Versioned Dataset Hub contracts are separate from Data Products.",
      },
      {
        q: "Can I edit or delete data after saving?",
        a: "Yes. Click the edit (✎) icon next to a row to update it, or the trash (🗑️) icon to delete it. All changes are tracked for data integrity.",
      },
      {
        q: "How do I export my data?",
        a: "Inside any table, use the 'Export CSV' option (usually in the table toolbar or via the bulk actions menu) to download your data for reporting.",
      },
      {
        q: "How is access controlled?",
        a: "Access is managed by your administrator. Roles such as admin, data owner, or auditor determine what you can view or edit in each app and data product.",
      },
      {
        q: "Which apps can I see?",
        a: "Each instance enables its own set of domain apps. You only see the apps enabled for your organization and the ones you have access to.",
      },
    ],
    contact: {
      intro: "Need help or want to suggest an improvement?",
      email: "ahmed.saied@aast.edu",
      version: "1.0.0",
      lastUpdated: "September 2026",
    },
  };
}

// ── Per-app help docs ────────────────────────────────────────────────────
const APP_HELP_DOCS = {
  carbon: {
    kind: "app",
    title: "Welcome to Carbon Footprint",
    intro: "Your collaborative tool for carbon data collection, organization, and analysis.",
    description:
      "This guide walks you through the essential steps to manage your environmental data, from entering information to analyzing and exporting results.",
    cards: [
      {
        icon: "workspace",
        title: "Unified Workspace",
        description: "All your modules, tables, and data in one place. Switch projects with a single click.",
      },
      {
        icon: "data",
        title: "Smart Data Entry",
        description: "Flexible forms, field validation, and attachments let you capture the data that matters.",
      },
      {
        icon: "insights",
        title: "Instant Insights",
        description: "Use filters and export tools to turn your data into actionable reports.",
      },
    ],
    steps: [
      {
        label: "Select a Project",
        icon: "project",
        description:
          "After logging in, choose your working project from the project list. All your data and modules are organized by project.",
      },
      {
        label: "Navigate Modules & Tables",
        icon: "navigate",
        description:
          "Use the sidebar to access modules (such as Water, Transportation). Each module contains data tables tailored to your organization's process.",
      },
      {
        label: "Add or Edit Data",
        icon: "add",
        description:
          "Within any table, use the 'Add Row' button to enter new data. Click the edit icon to change existing rows, or the trash icon to delete.",
      },
      {
        label: "Analyze & Export",
        icon: "export",
        description:
          "Use filters and search to analyze your records. Export data to CSV for reporting or further analysis.",
      },
      {
        label: "Track Progress & Collaborate",
        icon: "collaborate",
        description:
          "Review data completeness, collaborate with your team, and provide feedback to continuously improve the platform.",
      },
    ],
    userStory: {
      title: "User Story: A Day in the Carbon Platform",
      character: "Meet Omar, a sustainability officer:",
      scenes: [
        { time: "Morning", text: "Omar logs in, selects his project, and checks for any pending data entries." },
        { time: "Midday", text: "He navigates to the Waste Water module and enters new data from the latest facility report." },
        { time: "Afternoon", text: "Omar reviews the Water Consumption data, applies filters to spot anomalies, and exports a summary for his manager." },
        { time: "End of Day", text: "He uses the Feedback page to suggest an improvement to the team." },
      ],
    },
    faqs: [
      {
        q: "How do I create a new table or module?",
        a: "If you have admin permissions, open a Data Product (Module) in Catalog Studio to add tables. Define fields, types, and access controls so your team can start entering data. Versioned Dataset Hub contracts are separate from Data Products.",
      },
      {
        q: "Can I edit or delete data after saving?",
        a: "Yes. Click the edit (✎) icon next to a row to update its data. Use the trash (🗑️) icon to delete a row. All changes are tracked for data integrity.",
      },
      {
        q: "How do I export my data?",
        a: "Inside any table, use the 'Export CSV' option (usually in the table toolbar or via the bulk actions menu) to download your data for reporting.",
      },
      {
        q: "How is access controlled?",
        a: "Access is managed by your project administrator. Roles such as admin, data owner, or analyst determine what you can view or edit in each project/module.",
      },
      {
        q: "Who do I contact for support?",
        a: "Use the Feedback page in the sidebar to send questions, bug reports, or suggestions.",
      },
    ],
    contact: {
      intro: "Need help or want to suggest an improvement?",
      email: "ahmed.saied@aast.edu",
      version: "1.0.0",
      lastUpdated: "July 2025",
    },
  },

  // ── Carbon Lead guide — the full detail behind the Journey's "lead" seat ──
  "carbon-lead": {
    kind: "app",
    title: "Carbon Lead guide",
    intro: "Run the inventory: one open period, declared sources, a calculation you can defend, and a number you can quote.",
    description:
      "The Journey teaches by doing — seven camps, each finished by a real action in the app. This is the full written guide behind the Carbon Lead seat: what each camp is for, the decision it owns, and the field notes a lead is expected to know. The camps are always open and nothing is locked; a camp is complete only when the app proves the outcome.",
    cards: [
      {
        icon: "period",
        title: "Own the window",
        description:
          "The whole inventory points at exactly one open reporting period. With none, nobody can enter data; with two, every total and lock becomes ambiguous.",
      },
      {
        icon: "boundary",
        title: "Own the boundary",
        description:
          "The boundary decides which entities count and how they are consolidated — equity share, financial control, or operational control. Sources, factors and totals all sit inside it.",
      },
      {
        icon: "calc",
        title: "Own the number",
        description:
          "A calculation turns activity rows into emissions and writes an audit row naming who ran it. Read created, skipped and error counts before you run it again.",
      },
    ],
    steps: [
      {
        label: "1 · Setup and policy",
        icon: "period",
        description:
          "Keep exactly one reporting period open. Declare each source with its scope, and make sure each one has an active emission factor of the same scope and unit. Two open periods means every total has two meanings.",
      },
      {
        label: "2 · Coverage targets",
        icon: "check",
        description:
          "Every declared source ends up covered by data or excluded with a stated reason — not material, insufficient data, outside the boundary, or other. An exclusion is a decision; an omission is a mistake.",
      },
      {
        label: "3 · Data products",
        icon: "book",
        description:
          "Reusable data products will bring many rows in one shape. This path is not wired to the app yet, so no work is owed here today.",
      },
      {
        label: "4 · Data entry",
        icon: "add",
        description:
          "Your owners enter this period's activity rows in the unit the factor expects, from real meter or invoice readings. You own the hand-off: their rows in and clean, your coverage decision next.",
      },
      {
        label: "5 · Calculation and quality",
        icon: "calc",
        description:
          "Run the calculation for the open period and read its counts. Quality tiers run from 1 (audited) to 5 (proxy); a figure resting on a weak tier is shown and labelled, never dressed as assured.",
      },
      {
        label: "6 · Lock and close",
        icon: "lock",
        description:
          "A period moves open, locked, submitted, then verified or rejected. Open goes to locked — never straight to closed. A rejected period goes back for a fix and a new submission.",
      },
      {
        label: "7 · Report and disclosure",
        icon: "quote",
        description:
          "Before you quote a total, say in words what it sums: which sources and which boundary. A period in a header is a label, not a filter.",
      },
    ],
    userStory: {
      title: "A day in the lead's seat",
      character: "Meet Ali, the carbon lead:",
      scenes: [
        { time: "Morning", text: "He confirms exactly one period is open on Reporting Periods, then declares a generator on Inventory Coverage and binds it to an active factor of the same scope." },
        { time: "Midday", text: "A data owner reports their rows are in. Ali checks the coverage row, marks one source covered and excludes another with a stated reason." },
        { time: "Afternoon", text: "He runs the calculation, reads the created, skipped and error counts, and fixes a failing row before touching a warning." },
        { time: "End of day", text: "He locks the period, submits it for verification, and prepares a one-line scope note for any total he quotes." },
      ],
    },
    faqs: [
      {
        q: "How many reporting periods should be open?",
        a: "Exactly one. With none, data entry has no window. With two, every total and every lock points at two records. Open one if none is, and lock the extras if several are.",
      },
      {
        q: "What must match between an activity row and its emission factor?",
        a: "The unit — litres, kWh, and so on — and the scope. A factor multiplies an amount in a specific unit; a mismatch gives a wrong figure or no figure at all.",
      },
      {
        q: "What does excluding a source require?",
        a: "A stated reason: not material, insufficient data, outside the boundary, or other. The reason is what makes an exclusion a decision instead of a silent gap.",
      },
      {
        q: "What does the boundary decide?",
        a: "Which entities count in the inventory and how they are consolidated. Choose the approach before data is entered — changing it afterwards silently changes what every figure means.",
      },
      {
        q: "Who can see that a calculation was run?",
        a: "Anyone with audit access. Every run writes an audit row with the user, the time and the counts. Run it once, read the counts, then decide whether a re-run is needed.",
      },
      {
        q: "What is the next legal transition when data entry is done?",
        a: "Lock it — open goes to locked. Verification and closing come after submission, and closing straight from open is refused.",
      },
      {
        q: "How is a Tier 4 or 5 figure treated?",
        a: "It is shown and labelled 'not assured'. A proxy is a useful estimate, not proof, so it is improved over time rather than presented as audited.",
      },
      {
        q: "The dashboard shows a total under a period name. What does it sum?",
        a: "The Chairman page adds every calculation across all periods; the period in the header is a label, not a filter. State in words what a number covers before quoting it.",
      },
      {
        q: "The period is locked and an owner needs to fix a row. What now?",
        a: "A lock protects what was submitted. Only a lead can move the period back to open; owners should never archive and re-enter rows to get around it.",
      },
    ],
    contact: {
      intro: "Need help or want to suggest an improvement?",
      email: "ahmed.saied@aast.edu",
      version: "1.0.0",
      lastUpdated: "October 2026",
    },
  },

  // ── Carbon Field guide — the full detail behind the Journey's "owner" seat ──
  "carbon-field": {
    kind: "app",
    title: "Carbon Field guide",
    intro: "Enter this period's activity rows for your own sources — from real readings, in the unit the factor expects.",
    description:
      "This is the full written guide behind the Data Owner seat in the Journey. It covers the whole gathering job: finding the sources you owe, saving one honest activity row, reading the quality flags, and handing clean rows to the lead who owns coverage. Nothing here is invented — every figure comes from a meter, an invoice, or the app itself.",
    cards: [
      {
        icon: "add",
        title: "Enter what the meter says",
        description:
          "A row is one activity — litres of fuel, or kilowatt-hours — written in the unit the factor expects. Rounding or converting to look tidy is a silent edit to the record.",
      },
      {
        icon: "tier",
        title: "Read the flags, not the vibes",
        description:
          "Quality checks mark a row as passing, warning or failing. Fix a failing row first: it breaks a rule. A warning is a doubt worth a second look.",
      },
      {
        icon: "handoff",
        title: "Hand off, don't decide coverage",
        description:
          "You supply the data. The lead decides whether a source is covered or excluded with a reason. Your job ends when the rows are in and clean.",
      },
    ],
    steps: [
      {
        label: "1 · Find what you owe",
        icon: "navigate",
        description:
          "Data Entry lists the data products you own for the open period. Pick the source with the fewest rows — that gap is what you owe first.",
      },
      {
        label: "2 · Save one honest row",
        icon: "add",
        description:
          "Open your source, add one row with the amount and unit exactly as the meter or invoice states, and save it. The saved row is the proof the lesson is done.",
      },
      {
        label: "3 · Bring many rows at once",
        icon: "book",
        description:
          "For a whole file of readings, import: upload one file of up to 10 MB, map each column, then validate — in that order. Keep one file per import.",
      },
      {
        label: "4 · Why the total didn't move",
        icon: "calc",
        description:
          "Saving a row records activity; it does not calculate emissions. A calculation is run by someone with the calculate permission, usually the lead. Never re-enter the row.",
      },
      {
        label: "5 · Read your quality status",
        icon: "check",
        description:
          "Open a flagged row and read the reason. Failing rows break a rule and can block the period; warnings can wait until the failures are gone.",
      },
      {
        label: "6 · Locked or rejected",
        icon: "lock",
        description:
          "When a period is locked, its rows are read-only. When it is rejected, read the verifier's note and prepare the corrected row — the lead moves the period, not you.",
      },
      {
        label: "7 · Hand the rows off",
        icon: "handoff",
        description:
          "Confirm your source shows the rows are in and clean, then tell the lead they are ready. Coverage and exclusion are the lead's decision, with its own permission.",
      },
    ],
    userStory: {
      title: "A day in the field seat",
      character: "Meet Bilagot, a data owner:",
      scenes: [
        { time: "Morning", text: "She opens Data Entry, finds the source with the fewest rows, and reads the meter reading off the log sheet." },
        { time: "Midday", text: "She adds one row in the unit the factor expects, saves it, and does not round the figure to look tidy." },
        { time: "Afternoon", text: "She imports a month of readings — upload, map columns, validate — and checks one flagged row's reason." },
        { time: "End of day", text: "She tells the lead the rows are in and clean, and stops there: coverage is the lead's call." },
      ],
    },
    faqs: [
      {
        q: "Which page lists the data I own this period?",
        a: "Data Entry (My Data) is scoped to your org units. The Chairman page shows the whole picture and Emission Factors is configuration, so neither is your list.",
      },
      {
        q: "The meter reads 1,027,668 kWh. Should I round it?",
        a: "No. Enter exactly what the meter or invoice says, in the unit the factor expects. Tidy is not evidence, and rounding is a silent edit to the record.",
      },
      {
        q: "My row is saved but the total didn't move. Did I do it wrong?",
        a: "No. Entering data and calculating are separate steps with separate permissions. Ask the lead to run the calculation — and never enter the row a second time, or the activity doubles.",
      },
      {
        q: "What are the import wizard's steps, in order?",
        a: "Upload, map columns, validate. You upload first so the wizard can read your columns, then map them, then it validates before anything is saved.",
      },
      {
        q: "One row is failing and another is warning. Which do I fix first?",
        a: "The failing row. Failing rows break a rule and can block the period; warnings can wait until the failures are gone.",
      },
      {
        q: "Can I edit a row when the period is locked?",
        a: "No — a lock makes its rows read-only. Ask the lead to move the period; do not archive and re-enter rows to get around a lock.",
      },
      {
        q: "Who decides that a source is covered or excluded?",
        a: "The carbon lead. You supply rows, the lead decides coverage. Never mark a source excluded because it is hard to collect — that decision needs a stated reason.",
      },
      {
        q: "A source has no real row this period. What do I enter?",
        a: "Nothing. A stream with no real row stays missing — nothing is invented. Tell the lead the gap is real so they can chase the meter or exclude it with a reason.",
      },
      {
        q: "How do I know a source is mine?",
        a: "Your org unit decides it. A source you do not own will not appear in your list, and entering data for it is not your job.",
      },
    ],
    contact: {
      intro: "Need help or want to suggest an improvement?",
      email: "ahmed.saied@aast.edu",
      version: "1.0.0",
      lastUpdated: "October 2026",
    },
  },

  people: {
    kind: "app",
    title: "Welcome to People",
    intro: "Nibras HR & payroll — employees, compliance, and payroll runs.",
    description:
      "This guide walks you through managing your workforce: organization structure, employees, attendance, leave, payroll, and compliance.",
    cards: [
      {
        icon: "workspace",
        title: "Organization",
        description: "Positions and organization structure keep every employee anchored in the right team.",
      },
      {
        icon: "data",
        title: "Workforce",
        description: "Employees, attendance, leave, certifications, and rotation in one governed place.",
      },
      {
        icon: "insights",
        title: "Payroll & Benefits",
        description: "Run payroll, generate payslips, and manage loans with full auditability.",
      },
    ],
    steps: [
      {
        label: "Set Up Organization",
        icon: "project",
        description:
          "Define positions and reporting lines in Organization so every employee record has the right context.",
      },
      {
        label: "Onboard Employees",
        icon: "add",
        description:
          "Add employees and assign them to positions. Attach certifications and rotation schedules as they change.",
      },
      {
        label: "Track Attendance & Leave",
        icon: "navigate",
        description:
          "Record attendance and leave to keep workforce availability current and compliant.",
      },
      {
        label: "Run Payroll",
        icon: "export",
        description:
          "Create payroll runs, review payslips, and manage loans and benefits.",
      },
      {
        label: "Stay Compliant",
        icon: "collaborate",
        description:
          "Manage compliance rules so HR practices remain auditable and aligned with policy.",
      },
    ],
    userStory: {
      title: "User Story: A Day in People",
      character: "Meet Sara, an HR officer:",
      scenes: [
        { time: "Morning", text: "Sara opens People and checks the onboarding queue for new hires." },
        { time: "Midday", text: "She approves leave requests and updates attendance records." },
        { time: "Afternoon", text: "Sara runs payroll for the month and reviews payslips before release." },
        { time: "End of Day", text: "She updates a compliance rule and shares feedback with the team." },
      ],
    },
    faqs: [
      {
        q: "How do I add an employee?",
        a: "Open People → Employees and use 'Add'. Assign a position and fill in the required fields before saving.",
      },
      {
        q: "How do I run payroll?",
        a: "Go to People → Payroll, create a payroll run for a period, review the computed payslips, and confirm.",
      },
      {
        q: "How is employee data protected?",
        a: "Access is role-based: People Admin manages records, Data Owners edit their assigned org units, and Analysts get read-only visibility.",
      },
      {
        q: "Who do I contact for support?",
        a: "Use the Feedback page in the sidebar.",
      },
    ],
    contact: {
      intro: "Need help or want to suggest an improvement?",
      email: "ahmed.saied@aast.edu",
      version: "1.0.0",
      lastUpdated: "September 2026",
    },
  },

  healthy: {
    kind: "app",
    title: "Welcome to Healthy",
    intro: "Healthy Foods Factory — demand forecasting, rep health, inventory, and AR collections.",
    description:
      "This guide walks you through managing factory operations: loadout sheets, rep health, accounts receivable, and slow-moving inventory.",
    cards: [
      {
        icon: "workspace",
        title: "Dashboard",
        description: "A single view of factory performance and key operational metrics.",
      },
      {
        icon: "data",
        title: "Loadout & Rep Health",
        description: "Track daily loadout sheets and monitor rep performance.",
      },
      {
        icon: "insights",
        title: "AR & Inventory",
        description: "Manage collections and spot slow-moving inventory before it costs you.",
      },
    ],
    steps: [
      {
        label: "Open the Dashboard",
        icon: "project",
        description:
          "Start at the Healthy Dashboard for an overview of today's factory operations.",
      },
      {
        label: "Review Loadout Sheets",
        icon: "navigate",
        description:
          "Open Loadout Sheet to record and review daily dispatch and product loadouts.",
      },
      {
        label: "Monitor Rep Health",
        icon: "collaborate",
        description:
          "Check Rep Health to track field performance and follow up on underperforming areas.",
      },
      {
        label: "Manage AR Collections",
        icon: "export",
        description:
          "Use AR Queue to prioritize and follow up on outstanding collections.",
      },
      {
        label: "Spot Slow Movers",
        icon: "insights",
        description:
          "Review Slow Movers inventory to make data-driven replenishment and clearance decisions.",
      },
    ],
    userStory: null,
    faqs: [
      {
        q: "Where do I see today's factory overview?",
        a: "Open the Healthy Dashboard from the app, or the Healthy entry in the sidebar.",
      },
      {
        q: "How do I follow up on outstanding collections?",
        a: "Use AR Queue to list outstanding invoices and prioritize your follow-up calls.",
      },
      {
        q: "How do I find slow-moving inventory?",
        a: "Open Slow Movers to see items that are not turning over, so you can plan promotions or clearance.",
      },
    ],
    contact: {
      intro: "Need help or want to suggest an improvement?",
      email: "ahmed.saied@aast.edu",
      version: "1.0.0",
      lastUpdated: "September 2026",
    },
  },

  stub: {
    kind: "app",
    title: "Welcome to Stub App",
    intro: "Minimal isolation proof for the platform manifest registry.",
    description:
      "Stub App demonstrates that a new domain application can register with the platform with zero changes to the shell.",
    cards: [
      {
        icon: "workspace",
        title: "Manifest-Driven",
        description: "Declared entirely through its app manifest — identity, routes, roles, and navigation.",
      },
    ],
    steps: [
      {
        label: "Open Stub Home",
        icon: "project",
        description:
          "Navigate to the Stub entry in the sidebar to open its single landing page.",
      },
    ],
    userStory: null,
    faqs: [
      {
        q: "What is Stub App?",
        a: "It is a minimal reference app used to prove the platform's manifest-driven registration contract.",
      },
    ],
    contact: null,
  },
};

/** Auto-generate a help doc from an app manifest (for future apps). */
function autoGenerateAppHelpDoc(manifest) {
  return {
    kind: "app",
    title: `Welcome to ${manifest.name}`,
    intro: manifest.description || "",
    description: `This guide introduces ${manifest.name}, a domain application registered on the platform.`,
    cards: [
      {
        icon: "workspace",
        title: "Domain App",
        description: manifest.description || "A platform-registered domain application.",
      },
    ],
    steps: (manifest.navigation?.items || [])
      .filter((i) => i.path && i.type !== "divider" && i.type !== "group")
      .slice(0, 6)
      .map((i) => ({ label: i.label, icon: "navigate", description: `Open ${i.label} to get started.` })),
    userStory: null,
    faqs: [],
    contact: null,
  };
}

/** Resolve a help doc for an app id, or null if the app is unknown. */
export function getAppHelpDoc(appId) {
  if (!appId) return null;
  if (APP_HELP_DOCS[appId]) return APP_HELP_DOCS[appId];
  const manifest = APP_BY_ID[appId];
  return manifest ? autoGenerateAppHelpDoc(manifest) : null;
}

// ── Multi-guide apps ─────────────────────────────────────────────────────
// An app can offer more than one guide (an overview plus role guides). The
// order below is the tab order; `docKey` points back into APP_HELP_DOCS so the
// documents themselves stay in ONE place.
const APP_GUIDES = {
  carbon: [
    { id: "overview", label: "Overview", docKey: "carbon" },
    { id: "lead", label: "Lead guide", docKey: "carbon-lead" },
    { id: "field", label: "Field guide", docKey: "carbon-field" },
  ],
};

/** The guides an app offers, in tab order. Empty when the app has only one. */
export function getAppGuides(appId) {
  if (!appId) return [];
  const rows = APP_GUIDES[appId];
  if (!rows) return [];
  return rows
    .map((row) => ({ id: row.id, label: row.label, doc: APP_HELP_DOCS[row.docKey] }))
    .filter((row) => Boolean(row.doc));
}

/** All app ids that have a help doc (used by the sidebar Help studio). */
export function appHelpIds() {
  return Object.keys(APP_BY_ID);
}
