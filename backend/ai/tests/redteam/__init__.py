"""P1-17 — Red-team adversarial test suite.

Ten mutation attempts across each of the six P0-06 effect-path categories
(direct, indirect phrasing, worker, skill, proactive, ingestion).  Every
attempt must be *blocked* by a fail-closed guard (critic veto, hook cancel,
admission-gate rejection, SQL-validation error, or pending-confirmation).

The catalogue in :mod:`mutations` is the single source of truth for the
"10 x 6" accounting; each test module consumes its slice and asserts the
guard fired.
"""
