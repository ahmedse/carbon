#!/usr/bin/env python3
"""Test Carbon login and create demo users if needed."""
import requests
import json

BASE = "http://localhost:8009/carbon-api"

# Demo users from populate_demo_users.py
DEMO_USERS = [
    ("admin1", "adminpass", "admin"),
    ("admin2", "adminpass", "admin"),
    ("auditor1", "auditorpass", "auditor"),
    ("auditor2", "auditorpass", "auditor"),
    ("owner1", "ownerpass", "data-owner"),
    ("owner2", "ownerpass", "data-owner"),
]

print("=== Carbon Login Test ===")
for username, password, role in DEMO_USERS:
    resp = requests.post(f"{BASE}/token/", json={"username": username, "password": password})
    if resp.status_code == 200:
        data = resp.json()
        access = data.get("access", "")[:40]
        print(f"  ✅ {username} ({role}) — token: {access}...")
    else:
        print(f"  ❌ {username} ({role}) — HTTP {resp.status_code}: {resp.text[:100]}")
