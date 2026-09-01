// src/utils/logger.js
//
// Minimal structured logger for the Carbon frontend. Level is gated by
// `VITE_LOG_LEVEL` (`silent|error|warn|info|debug`, default `warn`). Every
// call is tagged with `[module]` and secrets (tokens, keys, passwords) are
// redacted before anything touches the console or the ring buffer.

const LEVELS = {
  silent: 0,
  error: 1,
  warn: 2,
  info: 3,
  debug: 4,
};

const DEFAULT_LEVEL = 'warn';
const RING_BUFFER_CAP = 100;

// Keys that always hold secrets — matched case-insensitively.
const SECRET_KEY_RE = /^(access|refresh|pulse_key|token|password|secret|authorization)$/i;
// Bearer `<jwt>` and OpenAI-style `sk-...` keys inside arbitrary strings.
const BEARER_RE = /(Bearer\s+)[A-Za-z0-9._~+/-]+=*/gi;
const SK_TOKEN_RE = /\bsk-[A-Za-z0-9_-]+/g;

function resolveLevel() {
  const raw = import.meta.env?.VITE_LOG_LEVEL || DEFAULT_LEVEL;
  return Object.prototype.hasOwnProperty.call(LEVELS, raw) ? raw : DEFAULT_LEVEL;
}

function redactString(value) {
  return value.replace(BEARER_RE, '$1[REDACTED]').replace(SK_TOKEN_RE, '[REDACTED]');
}

/**
 * Recursively redact secrets from any value before it is logged. Strings are
 * scanned for Bearer / sk- tokens, objects have their secret-named keys
 * replaced, and arrays are walked element-by-element.
 */
function redact(value, depth = 0) {
  if (depth > 6) return '[REDACTED]';
  if (typeof value === 'string') return redactString(value);
  if (value instanceof Error) return redactString(value.message || value.name);
  if (Array.isArray(value)) return value.map((item) => redact(item, depth + 1));
  if (value && typeof value === 'object') {
    const out = {};
    for (const [key, item] of Object.entries(value)) {
      out[key] = SECRET_KEY_RE.test(key) ? '[REDACTED]' : redact(item, depth + 1);
    }
    return out;
  }
  return value;
}

function stringifyArg(arg) {
  const value = redact(arg);
  if (value && typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

/**
 * Create a logger bound to a module name.
 * @param {string} module
 * @returns {{ debug: Function, info: Function, warn: Function, error: Function, getBuffer: Function }}
 */
export function createLogger(module) {
  const level = LEVELS[resolveLevel()];
  const ringBuffer = [];

  function record(levelName, args) {
    const message = [`[${module}]`, ...args.map(stringifyArg)].join(' ');
    ringBuffer.push({ ts: Date.now(), level: levelName, message });
    if (ringBuffer.length > RING_BUFFER_CAP) ringBuffer.shift();
    return message;
  }

  function log(levelName, minLevel, consoleMethod, args) {
    if (level < minLevel) return;
    const message = record(levelName, args);
    console[consoleMethod](message);
  }

  const logger = {
    debug: (...args) => log('debug', LEVELS.debug, 'debug', args),
    info: (...args) => log('info', LEVELS.info, 'info', args),
    warn: (...args) => log('warn', LEVELS.warn, 'warn', args),
    error: (...args) => log('error', LEVELS.error, 'error', args),
    getBuffer: () => ringBuffer.slice(),
  };

  return logger;
}

export default createLogger;
