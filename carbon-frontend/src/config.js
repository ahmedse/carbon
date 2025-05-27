export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
export const API_ROUTES = {
  token: "/api/token/",
  tokenRefresh: "/api/token/refresh/",
  myRoles: "/api/my-roles/",
  projects: "/api/core/projects/",
  modules: "/api/core/modules/",
  entries: "/api/datacollection/entries/",
  templates: "/api/datacollection/templates/",
  items: "/api/datacollection/item-definitions/",
};