#!/usr/bin/env python
"""P12 G2 — Profile 15 key API endpoints with django-silk instrumentation.

Usage (from backend/, venv activated):
    python profile_endpoints.py

Flow:
    1. Login as admin/admin123 to obtain a JWT.
    2. Hit each endpoint N times (2 warmup + 8 measured) with the JWT.
    3. Print avg / p95 / min / max per endpoint.
    4. Afterwards, query silk DB via `manage.py shell` to attach query counts.

CLI script — print() output is intentional.
"""
import math
import time
import requests

BASE = "http://localhost:8009/carbon-api"
USERNAME = "admin"
PASSWORD = "admin123"
HITS = 8
WARMUP = 2

# (label, method, path) — paths verified against registered URL config.
ENDPOINTS = [
    ("emissions dashboard",   "GET", "/carbon/dashboard/"),
    ("emissions calculations", "GET", "/carbon/calculations/"),
    ("catalog assets",        "GET", "/catalog/assets/"),
    ("accounts users",        "GET", "/accounts/users/"),
    ("accounts scoped-roles", "GET", "/accounts/scoped-roles/"),
    ("accounts me/context",   "GET", "/accounts/me/context/"),
    ("dq rules",              "GET", "/dq/rules/"),
    ("dq results",            "GET", "/dq/results/"),
    ("mdm org-units",         "GET", "/mdm/org-units/"),
    ("mdm reference-sets",    "GET", "/mdm/reference-sets/"),
    ("dataschema tables",     "GET", "/dataschema/tables/"),
    ("dataschema fields",     "GET", "/dataschema/fields/"),
    ("emissions targets",     "GET", "/carbon/targets/"),
    ("catalog governance-policies", "GET", "/catalog/governance-policies/"),
    ("accounts audit-log",    "GET", "/accounts/audit-log/"),
]


def p95(values):
    if not values:
        return 0.0
    s = sorted(values)
    idx = max(0, min(len(s) - 1, math.ceil(0.95 * len(s)) - 1))
    return s[idx]


def main():
    # 1. Login
    r = requests.post(f"{BASE}/token/", json={"username": USERNAME, "password": PASSWORD}, timeout=15)
    r.raise_for_status()
    token = r.json()["access"]
    headers = {"Authorization": f"Bearer {token}"}

    print(f"{'Endpoint':<28} {'avg ms':>8} {'p95 ms':>8} {'min ms':>8} {'max ms':>8}  status")
    print("-" * 78)

    results = []
    for label, method, path in ENDPOINTS:
        url = f"{BASE}{path}"
        status = None
        times = []
        for i in range(WARMUP + HITS):
            t0 = time.perf_counter()
            resp = requests.get(url, headers=headers, timeout=30)
            dt = (time.perf_counter() - t0) * 1000.0
            status = resp.status_code
            if i >= WARMUP:
                times.append(dt)
        avg = sum(times) / len(times)
        results.append((label, path, avg, p95(times), min(times), max(times), status))
        print(f"{label:<28} {avg:>8.1f} {p95(times):>8.1f} {min(times):>8.1f} {max(times):>8.1f}  {status}")

    print("\nDone. Query counts per request are in the silk DB; fetch with:")
    print("  python manage.py shell -c \"from silk.models import Request; ...\"")


if __name__ == "__main__":
    main()
