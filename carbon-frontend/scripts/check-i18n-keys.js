#!/usr/bin/env node
/* eslint-env node */
// I18N-2 gate: key-parity audit between the English and Arabic locale catalogs.
// Usage: node scripts/check-i18n-keys.js
// Exit 0 when every en key exists in ar (and vice versa) for all namespaces.
import { readdirSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const localesDir = join(__dirname, '..', 'src', 'i18n', 'locales');

function flattenKeys(obj, prefix = '') {
  const keys = [];
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      keys.push(...flattenKeys(value, path));
    } else {
      keys.push(path);
    }
  }
  return keys;
}

function load(lang) {
  const dir = join(localesDir, lang);
  const files = readdirSync(dir).filter((f) => f.endsWith('.json'));
  const catalog = {};
  for (const file of files) {
    const ns = file.replace(/\.json$/, '');
    const parsed = JSON.parse(readFileSync(join(dir, file), 'utf8'));
    for (const key of flattenKeys(parsed)) {
      catalog[`${ns}:${key}`] = true;
    }
  }
  return catalog;
}

const en = load('en');
const ar = load('ar');

const missingInAr = Object.keys(en).filter((k) => !ar[k]);
const missingInEn = Object.keys(ar).filter((k) => !en[k]);

if (missingInAr.length === 0 && missingInEn.length === 0) {
  console.log(`check-i18n-keys: OK — ${Object.keys(en).length} keys in parity (en === ar).`);
  process.exit(0);
}

if (missingInAr.length) {
  console.error(`Missing in ar: ${missingInAr.length}`);
  missingInAr.forEach((k) => console.error(`  - ${k}`));
}
if (missingInEn.length) {
  console.error(`Missing in en: ${missingInEn.length}`);
  missingInEn.forEach((k) => console.error(`  - ${k}`));
}
process.exit(1);
