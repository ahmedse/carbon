// src/config.js

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
export const API_ROUTES = {
  token: "/api/token/",
  tokenRefresh: "/api/token/refresh/",
  myRoles: "/api/my-roles/",
  projects: "/api/core/projects/",
  modules: "/api/core/modules/",
  tables: "/api/dataschema/tables/",
  fields: "/api/dataschema/fields/",
  rows: "/api/dataschema/rows/",
  schemaLogs: "/api/dataschema/schema-logs/",
  // Add other endpoints as needed
};