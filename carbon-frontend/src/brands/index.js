// src/brands/index.js
// Brand registry — the single source of truth for per-instance identity.
// ONE SWITCH: VITE_BRAND (aastmt | nibras | medos | tectona).
// Adding a new brand = add a file here + an entry in BRANDS. No shell edits.

import aastmt from './aastmt';
import nibras from './nibras';
import medos from './medos';
import tectona from './tectona';

export const BRANDS = {
  aastmt,
  nibras,
  medos,
  tectona,
};

export const BRAND_IDS = Object.keys(BRANDS);

/**
 * Resolve a brand id to its config object. Unknown/missing id falls back to
 * aastmt (the default platform brand).
 */
export function resolveBrand(brandId) {
  return BRANDS[brandId] || BRANDS.aastmt;
}

export default BRANDS;
