// jwt.js
export function isJwtExpired(token) {
  if (!token) return true;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    // exp is in seconds since epoch
    return Date.now() / 1000 > payload.exp - 30; // 30s early to avoid race
  } catch {
    return true;
  }
}