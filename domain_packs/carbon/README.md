# Carbon Domain Pack

Brand-specific domain knowledge for the Carbon instance of the Pulse engine:
the domain vocabulary, tool/API catalog, trigger config, process definitions,
skills, and prompt templates. Loaded by
`backend/ai/engine/ports/domain.py::load_domain_pack` (the host resolves
brand → directory and passes the path in).
