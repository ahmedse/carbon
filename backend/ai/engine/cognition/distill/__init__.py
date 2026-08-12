"""
Distillation cron — episodic → semantic memory conversion (PR-14).

Daily: distill recent turn_ledger rows into candidate facts.
Weekly: promote high-confidence candidates to confirmed.
Monthly: decay unused facts toward archival.
"""
