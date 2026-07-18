// src/config.js
// Central API config and endpoint management.
// ALWAYS uses environment variables - NEVER hardcode URLs or ports

// API Base URL - read from environment variable
// Fallback is for development only - should always be set in .env
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1/";

// API timeout (milliseconds)
export const API_TIMEOUT = parseInt(import.meta.env.VITE_API_TIMEOUT || "30000", 10);

// Validate configuration on load
if (!import.meta.env.VITE_API_BASE_URL) {
  console.error("❌ CRITICAL: VITE_API_BASE_URL not set in .env - using fallback URL");
  console.error("📝 Please create .env file with: VITE_API_BASE_URL=http://localhost:8000/api/v1/");
}

// Health check on app load - robust and non-fatal
const validateApiConfig = async () => {
  try {
    // Prefer a health endpoint if available, otherwise hit the API base URL.
    const healthUrlCandidates = [
      `${API_BASE_URL.replace(/\/$/, '')}/health/`,
      API_BASE_URL,
    ];

    let reachable = false;
    for (const url of healthUrlCandidates) {
      try {
        const res = await fetch(url, { method: 'GET' });
        // Any HTTP response (200-499/500) shows the host is reachable; only network errors/aborts are fatal.
        console.log(`API reach check: ${url} -> ${res.status}`);
        reachable = true;
        break;
      } catch (err) {
        // Try next candidate
      }
    }

    if (reachable) {
      console.log("✅ API Base URL appears reachable:", API_BASE_URL);
    } else {
      console.error("❌ API Base URL is NOT reachable:", API_BASE_URL);
      console.error("🔧 Check that backend is running and VITE_API_BASE_URL is correct");
    }

  } catch (error) {
    console.error("❌ API Base URL validation failed:", error);
  }
};

// Run validation in development mode
if (import.meta.env.DEV) {
  validateApiConfig();
}

console.log("🔧 API Configuration:", {
  baseUrl: API_BASE_URL,
  timeout: API_TIMEOUT,
  mode: import.meta.env.MODE,
  envCheck: import.meta.env.VITE_API_BASE_URL ? '✅ Set' : '❌ Using fallback',
});

// All backend API routes (relative to API_BASE_URL)
export const API_ROUTES = {
  // Authentication
  token: "token/",
  tokenRefresh: "token/refresh/",
  logout: "accounts/logout/",
  myRoles: "accounts/my-roles/",
  
  // Core
  modules: "core/modules/",
  feedback: "core/feedback/",

  // Accounts / access control
  users: "accounts/users/",
  groups: "accounts/roles/",
  scopedRoles: "accounts/scoped-roles/",

  // Organisation (MDM)
  orgUnits: "mdm/org-units/",
  
  // Data Schema
  tables: "dataschema/tables/",
  fields: "dataschema/fields/",
  rows: "dataschema/rows/",
  schemaLogs: "dataschema/schema-logs/",
  
  // AI Copilot
  aiChat: "ai/chat/send_message/",
  aiChatHistory: "ai/chat/history/",
  aiChatClear: "ai/chat/clear_history/",
  aiChatReact: "ai/chat/{id}/react/",
  aiInsights: "ai/insights/",
  aiInsightAck: "ai/insights/{id}/acknowledge/",
  aiPreferences: "ai/preferences/me/",
  aiPreferencesUpdate: "ai/preferences/update_me/",
  aiQaRun: "ai/qa/run/",
  
  // Emissions Calculator
  emissionsDashboard: "emissions/dashboard/",
  emissionsYearlyComparison: "emissions/yearly-comparison/",
  emissionsReport: "emissions/report/",
  emissionsCalculate: "emissions/calculate/",
  emissionsPeriods: "emissions/periods/",
  emissionsFactors: "emissions/factors/",
  emissionsCalculations: "emissions/calculations/",
  emissionsRules: "emissions/rules/",
  emissionsGWP: "emissions/gwp/",
};

// Pulse AI Configuration
// Pulse AI is an external AI assistant service that integrates with Carbon
export const PULSE_HOST = import.meta.env.VITE_PULSE_HOST || "http://127.0.0.1:9100";

console.log("🔧 Pulse AI Configuration:", {
  host: PULSE_HOST,
  envCheck: import.meta.env.VITE_PULSE_HOST ? '✅ Set' : '❌ Using default',
});
