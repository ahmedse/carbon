"""Multi-turn coherence evaluation (Phase PV2-0B).

Offline runner that measures whether Pulse remembers conversations
(continuity, grounded recall, slot memory, language fidelity, etc.)
across 8–12 turn scripts with a scripted stub LLM.

This package DOES NOT change runtime code. It measures via real
dispatch_task("chat", ...) calls with an LLM stub and validates the
response + ledger against declarative expectations.

Paths the offline tier cannot exercise:
- fan-out (AGENT_ORCHESTRATOR_ENABLED=false)
- multi-step (KG_MULTI_STEP_ENABLED=false)
- live external tools
- async completion
"""

__all__ = ["run_script", "run_bank", "load_scripts", "ScriptResult", "BankReport"]
