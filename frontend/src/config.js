// frontend/src/config.js
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
export const API_ROUTES = {
  token: "/api/token/",
  tokenRefresh: "/api/token/refresh/",
  myRoles: "/api/my-roles/",
  dataItemDefs: "/api/datacollection/item-definitions/",
  templates: "/api/datacollection/templates/",
};