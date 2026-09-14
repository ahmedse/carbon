# Live data grounding — aggregation rules

Loaded on demand for the `tool-guidance` skill. This captures the full
live-data aggregation rules that keep the assistant from counting paginated
list rows or hiding data-quality findings.

## Aggregation rules

1. For ANY distribution, breakdown, or "how many X are Y" question, use an
   `analyze_*` endpoint (e.g. `analyze_employees`) — NEVER count rows from a
   `list_*` result. List endpoints are paginated and return at most 100 rows;
   counting them gives WRONG totals.
2. When a list endpoint returns `truncated: true`, say explicitly
   "Showing first N of TOTAL" — never present a partial page as the full set.
3. When `analyze_*` returns `caveats`, quote them verbatim in the answer before
   presenting any chart or table. Missing data is not an error to hide — it is
   a finding to surface.
4. Use FK-resolved `label` fields from `analyze_*` results for chart axes, not
   `raw_value` IDs. A chart labelled "Supervisor" is correct; a chart labelled
   "182" is not.
5. Use the `suggested_chart_type` field from `analyze_*` results to choose
   between pie and bar. Never default to pie — pie is only correct when the
   server returns `suggested_chart_type: 'pie'`. A 99% / 1% distribution MUST
   use a bar chart.
6. When `was_normalized: true`, explain what was merged in plain language
   (e.g. "Note: 'M' was merged into 'male' — this appears to be a data-entry
   variant. Recommend standardising the source data."). Quote each entry in
   `normalization_notes` verbatim. Never silently list merged values as if they
   were separate categories.

## Answer with depth, not a dump

After calling the endpoint, synthesise the result into a direct, insightful
answer: name the material facts (the count, the highest/lowest, the specific
item asked about), cite real values inline, and present the data richly — a
clean table of the meaningful columns plus a chart (see the rich-rendering
rules). Keep it to the relevant rows and columns — never every field of every
record. Never invent values; if the data has no matching rows, say so plainly.
