// src/config/branding.js
// Platform & instance identity — single source of truth for all branding
// All values driven by .env for multi-customer deployability

import fallbackLogo from "../assets/aast_carbon_logo_.jpg";

export const PLATFORM_NAME = import.meta.env.VITE_PLATFORM_NAME || "Carbon Data Trust";
export const PLATFORM_SHORT = import.meta.env.VITE_PLATFORM_SHORT || "Carbon";
export const INSTANCE_NAME = import.meta.env.VITE_INSTANCE_NAME || "";
export const INSTANCE_LOGO = import.meta.env.VITE_INSTANCE_LOGO || fallbackLogo;
export const INSTANCE_FAVICON = import.meta.env.VITE_INSTANCE_FAVICON || "/logo.svg";
