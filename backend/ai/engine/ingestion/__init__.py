"""
Pulse ingestion package.

Host-agnostic CSV ingestion and the autonomous ops-workflow runtime.

The loader (:mod:`ingestion.csv_loader`) is a pure, dependency-free module: it
turns a raw timeseries CSV into validated ``{timestamp, values}`` records given a
*field schema* that is fetched live from the host (never hardcoded). The workflow
runtime (:mod:`ingestion.ops_workflow`) drives the full
``ingest → validate → infer → ops_output`` sequence as discrete, individually
callable steps, recording provenance to the ``ops_runs`` ledger.
"""
