---
name: rich-content-rendering
description: How to format replies with tables, code, mermaid diagrams, KaTeX math, and figures
allowed-tools: []
---
Format replies as rich Markdown — use the right construct instead of prose.

- **Tables** — one data row per line; leave a blank line before the table; put the header, the `|---|---|` delimiter, and every data row each on its OWN line.
- **Code** — fenced blocks (```python, ```sql, ```json) render with syntax highlighting and a copy button; indent JSON with 2 spaces per level.
- **Diagrams** — a ```mermaid fenced block renders as a live diagram (flowchart, sequenceDiagram, stateDiagram-v2, classDiagram, pie, gantt). You CAN draw diagrams; when a process or structure is clearer as a picture, emit one.
- **Mermaid line rules** — the opening ```mermaid fence starts on its OWN line preceded by a blank line; the closing fence is on its own line; each directive on its own line.
- **Data charts** — for 3+ comparable numeric records, emit a Mermaid chart IN ADDITION to a table: ```mermaid pie for parts-of-a-whole; ```mermaid xychart-beta with `bar` for magnitudes or `line` for trends.
- **Math** — $inline$ and $$block$$ render with KaTeX.
- **Figures** — images with a title render with a caption below.
- **Links** — internal platform routes (starting with /) render as in-app links.

Complete worked examples (tables, pie, xychart-beta, flowchart) are in `references/formatting-examples.md`.
