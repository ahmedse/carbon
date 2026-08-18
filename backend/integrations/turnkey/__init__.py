"""TurnKey Bridge (Phase P2).

Bidirectional HTTP connector between Carbon's trusted data and TurnKey's ML
serving tier:

* Outbound: push trained artifacts, register models, promote versions.
* Inbound: receive signed prediction results + drift alerts, store them as
  evidence and trigger DQ re-evaluation.

Design contract: docs/DESIGN-PLATFORM.md §6. HTTP bridge only — NO shared DB,
NO direct import of TurnKey serving code.
"""
