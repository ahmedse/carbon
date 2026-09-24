"""Excellence Ledger (ADR-0051): one evidence store, many ladders.

Core app. Owns the schema, the evaluator, the collectors and the CLI. Owns no
ladder's content — tiers and tracks declare their own subjects and checks in
``assurance/<tier>/`` or ``domain_packs/<id>/assurance/``.
"""
