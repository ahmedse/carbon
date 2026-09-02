// src/config/branding.js
// Platform & instance identity — single source of truth for all branding.
//
// ONE SWITCH: set VITE_BRAND (aastmt | nibras | medos | tectona) and everything
// else (name, logo, favicon, palette, tagline, canonical URL, enabled apps)
// resolves from src/brands/*.js. Legacy VITE_* vars still work as an explicit
// override or fallback when VITE_BRAND is unset — nothing breaks.

import fallbackLogo from "../assets/logo.svg";
import { resolveBrand } from "../brands";

const brand = resolveBrand(import.meta.env.VITE_BRAND);

export const BRAND_ID = brand.id;

export const PLATFORM_NAME = import.meta.env.VITE_PLATFORM_NAME || brand.platformName;
export const PLATFORM_SHORT = import.meta.env.VITE_PLATFORM_SHORT || brand.platformShort;
export const INSTANCE_NAME = import.meta.env.VITE_INSTANCE_NAME || brand.instanceName;
export const INSTANCE_LOGO = import.meta.env.VITE_INSTANCE_LOGO || brand.logo || fallbackLogo;
export const INSTANCE_FAVICON = import.meta.env.VITE_INSTANCE_FAVICON || brand.favicon || "/favicon.svg";
export const CANONICAL_URL = import.meta.env.VITE_CANONICAL_URL || brand.canonicalUrl || "";

// Full brand title (header, browser tab, footer). Explicit env wins; then brand
// override; otherwise composed from INSTANCE_NAME + PLATFORM_NAME.
export const PLATFORM_TITLE =
  import.meta.env.VITE_PLATFORM_TITLE ||
  brand.title ||
  (INSTANCE_NAME ? `${INSTANCE_NAME} · ${PLATFORM_NAME}` : PLATFORM_NAME);

// Tagline + SEO description (meta tags).
export const PLATFORM_TAGLINE =
  import.meta.env.VITE_PLATFORM_TAGLINE || brand.tagline || "Trusted data platform hosting domain applications";
export const PLATFORM_DESCRIPTION =
  import.meta.env.VITE_PLATFORM_DESCRIPTION ||
  brand.description ||
  "A governed data platform for catalog, master data management, data quality, and emissions intelligence.";

// Per-brand theme palette (primary/secondary only; status colors stay platform-wide).
export const BRAND_PALETTE = brand.palette || {};

// Pulse instance id (mirrors backend PULSE_INSTANCE_ID).
export const PULSE_INSTANCE_ID = import.meta.env.VITE_PULSE_INSTANCE_ID || brand.pulseInstanceId || "carbon";

// Informational mirror of the backend app-enablement preset. Not enforced here —
// the real gate is PlatformAppConfig.is_enabled via useEnabledApps().
export const BRAND_ENABLED_APP_IDS = brand.enabledAppIds || [];
