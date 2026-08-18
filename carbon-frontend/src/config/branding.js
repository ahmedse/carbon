// src/config/branding.js
// Platform & instance identity — single source of truth for all branding.
// Everything here is driven by .env (VITE_*) for multi-entity reuse.
//
// To rebrand for another entity, edit these values in .env:
//   VITE_INSTANCE_NAME=YourEntity          # e.g. "AASTMT"
//   VITE_PLATFORM_NAME=Data Trust Platform
//   VITE_PLATFORM_TITLE=YourEntity · Data Trust Platform   # (optional override)
//
// Composed title = "<INSTANCE_NAME> · <PLATFORM_NAME>" (or PLATFORM_NAME when no instance).

import fallbackLogo from "../assets/logo.svg";

export const PLATFORM_NAME = import.meta.env.VITE_PLATFORM_NAME || "Data Trust Platform";
export const PLATFORM_SHORT = import.meta.env.VITE_PLATFORM_SHORT || "Data Trust";
export const INSTANCE_NAME = import.meta.env.VITE_INSTANCE_NAME || "";
export const INSTANCE_LOGO = import.meta.env.VITE_INSTANCE_LOGO || fallbackLogo;
export const INSTANCE_FAVICON = import.meta.env.VITE_INSTANCE_FAVICON || "/favicon.svg";

// Full brand title (header, browser tab, footer). Explicit env var wins;
// otherwise composed from INSTANCE_NAME + PLATFORM_NAME.
export const PLATFORM_TITLE =
  import.meta.env.VITE_PLATFORM_TITLE ||
  (INSTANCE_NAME ? `${INSTANCE_NAME} · ${PLATFORM_NAME}` : PLATFORM_NAME);

// Tagline + SEO description (meta tags).
export const PLATFORM_TAGLINE =
  import.meta.env.VITE_PLATFORM_TAGLINE || "Trusted data platform hosting domain applications";
export const PLATFORM_DESCRIPTION =
  import.meta.env.VITE_PLATFORM_DESCRIPTION ||
  "A governed data platform for catalog, master data management, data quality, and emissions intelligence.";
