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
          "All your data products, modules, tables, and domain apps in one governed place. Switch between apps with a single click.",
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
        a: "If you have admin permissions, open a Data Product in Catalog Studio to add tables. Define fields, types, and access controls so your team can start entering data immediately.",
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
        a: "If you have admin permissions, open a Data Product in Catalog Studio to add tables. Define fields, types, and access controls so your team can start entering data immediately.",
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
        a: "Use the Feedback page in the sidebar to send questions, bug reports, or suggestions, or email support directly at ahmed.saied@aast.edu.",
      },
    ],
    contact: {
      intro: "Need help or want to suggest an improvement?",
      email: "ahmed.saied@aast.edu",
      version: "1.0.0",
      lastUpdated: "July 2025",
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
        a: "Use the Feedback page in the sidebar, or email support at ahmed.saied@aast.edu.",
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

/** All app ids that have a help doc (used by the sidebar Help studio). */
export function appHelpIds() {
  return Object.keys(APP_BY_ID);
}
