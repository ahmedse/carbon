# Carbon Pulse Engine — vendored in-hand (INERT).
#
# Phase 1 vendors the full Pulse engine source verbatim. The package is
# intentionally NOT wired to Django, creates no migrations, and opens no DB
# connection on import. It is import-only until Phase 2 swaps the persistence
# seam (core/database.py) to a Django Store (see ADR-0009).
#
# Intra-package imports are rooted at `ai.engine.*`.
