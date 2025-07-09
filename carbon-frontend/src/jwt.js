// src/jwt.js
// JWT expiry checking logic.

import { jwtDecode } from "jwt-decode";

/**
 * Checks if a JWT token is expired or invalid.
 * @param {string} token 
 * @returns {boolean} - true if expired or invalid.
 */
export function isJwtExpired(token) {
  if (!token) return true;
  try {
    const { exp } = jwtDecode(token);
    if (!exp) return true;
    return Date.now() >= exp * 1000;
  } catch (error) {
    // Debug log for decoding issues
    console.warn("JWT decoding failed:", error);
    return true;
  }
}