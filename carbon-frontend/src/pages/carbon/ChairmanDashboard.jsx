// src/pages/carbon/ChairmanDashboard.jsx
// Chairman Overview — strategic one-pager for board presentations.
// Accordion sections let leadership expand only what they need.

import React, { useState, useEffect, useMemo } from "react";
import {
  Box,
  Typography,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  Chip,
  LinearProgress,
  Stack,
  Divider,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Grid,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useTheme } from "@mui/material/styles";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Tooltip as ChartTooltip,
  Legend,
  Filler,
} from "chart.js";
import { Doughnut, Line } from "react-chartjs-2";
import {
  Factory,
  Bolt,
  LocalShipping,
  Flag,
  TaskAlt,
  InfoOutlined,
} from "@mui/icons-material";
import useDocumentTitle from "../../hooks/useDocumentTitle";
import { fetchChairmanData } from "../../api/emissions-extended";
import PageContainer from "../../components/layout/PageContainer";
import { FONT, SPACING } from "../../theme/themeTokens";

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, ChartTooltip, Legend, Filler
);

const ACTION_TYPE_LABEL = {
  collect_data: "Collect Data",
  improve_quality: "Improve Quality",
  obtain_verification: "Obtain Verification",
  formalize_exclusion: "Formalize Exclusion",
};

const ACTION_STATUS_META = {
  open:        { label: "Open",        color: "info" },
  in_progress: { label: "In Progress", color: "primary" },
  done:        { label: "Done",        color: "success" },
  blocked:     { label: "Blocked",     color: "error" },
};

// ── Compact KPI card ─────────────────────────────────────────────────────────
function KpiCard({ label, value, unit, sub, icon, color, tooltip }) {
  return (
    <Card variant="outlined" sx={{ borderRadius: 1.5, height: "100%" }}>
      <CardContent sx={{ p: "10px 12px", "&:last-child": { pb: "10px" } }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 0.75 }}>
          <Box sx={{
            width: 26, height: 26, borderRadius: 0.75,
            display: "flex", alignItems: "center", justifyContent: "center",
            bgcolor: `${color}18`, color, flexShrink: 0,
          }}>
            {React.cloneElement(icon, { sx: { fontSize: 15 } })}
          </Box>
          {tooltip && (
            <Tooltip title={tooltip} arrow placement="top">
              <InfoOutlined sx={{ fontSize: 13, color: "text.disabled", cursor: "help" }} />
            </Tooltip>
          )}
        </Box>
        <Typography sx={{ fontSize: "1.3rem", fontWeight: 700, color: "text.primary", lineHeight: 1.1 }}>
          {value}
          {unit && (
            <Typography component="span" sx={{ ml: 0.5, fontSize: "0.7rem", fontWeight: 500, color: "text.secondary" }}>
              {unit}
            </Typography>
          )}
        </Typography>
        <Typography sx={{ fontSize: "0.65rem", fontWeight: 600, color: "text.secondary", textTransform: "uppercase", letterSpacing: "0.04em", mt: 0.25 }}>
          {label}
        </Typography>
        {sub && (
          <Typography sx={{ fontSize: "0.6rem", color: "text.disabled", mt: 0.125 }}>{sub}</Typography>
        )}
      </CardContent>
    </Card>
  );
}

// ── Accordion section wrapper ─────────────────────────────────────────────────
function Section({ title, badge, defaultExpanded = true, children }) {
  const theme = useTheme();
  return (
    <Accordion
      defaultExpanded={defaultExpanded}
      disableGutters
      elevation={0}
      square
      sx={{
        "&:before": { display: "none" },
        borderBottom: `1px solid ${theme.palette.divider}`,
        bgcolor: "background.paper",
      }}
    >
      <AccordionSummary
        expandIcon={<ExpandMoreIcon sx={{ fontSize: 18, color: "text.secondary" }} />}
        sx={{
          minHeight: 40, px: SPACING.lg,
          "& .MuiAccordionSummary-content": { my: 0.75, alignItems: "center", gap: 1 },
        }}
      >
        <Typography sx={{ fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em", color: "text.secondary" }}>
          {title}
        </Typography>
        {badge}
      </AccordionSummary>
      <AccordionDetails sx={{ px: SPACING.lg, pb: SPACING.md, pt: 0 }}>
        {children}
      </AccordionDetails>
    </Accordion>
  );
}

export default function ChairmanDashboard() {
  useDocumentTitle("Chairman Overview");
  const theme = useTheme();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const token = localStorage.getItem("access");

  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    fetchChairmanData({}, token)
      .then((r) => { if (active) setData(r); })
      .catch((e) => { if (active) setError(e.message || "Failed to load"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token]);

  const scopeColors = useMemo(() => ({
    1: theme.palette.success.main,
    2: theme.palette.primary.main,
    3: theme.palette.warning.main,
  }), [theme]);

  const scopeDonut = useMemo(() => {
    if (!data?.scope_breakdown?.length) return null;
    return {
      labels: data.scope_breakdown.map((s) => s.scope_name),
      datasets: [{
        data: data.scope_breakdown.map((s) => s.co2e_tonnes),
        backgroundColor: data.scope_breakdown.map((s) => scopeColors[s.scope] || theme.palette.grey[400]),
        borderColor: theme.palette.background.paper,
        borderWidth: 3,
        hoverOffset: 6,
      }],
    };
  }, [data, scopeColors, theme]);

  const trajectoryChart = useMemo(() => {
    const targets = data?.trajectory?.targets;
    if (!targets?.length) return null;
    const actualByYear = {};
    (data?.trajectory?.yearly_comparison || []).forEach((y) => { actualByYear[y.year] = y.total_co2e_tonnes; });
    const labels = targets.map((t) => t.year);
    return {
      labels,
      datasets: [
        {
          label: "SBTi target", data: labels.map((y) => targets.find((t) => t.year === y)?.target_co2e_tonnes ?? null),
          borderColor: theme.palette.text.secondary, backgroundColor: "transparent",
          borderDash: [6, 4], borderWidth: 2, pointRadius: 0, tension: 0.15,
        },
        {
          label: "Actual", data: labels.map((y) => actualByYear[y] ?? null),
          borderColor: scopeColors[1], backgroundColor: `${scopeColors[1]}20`,
          fill: true, borderWidth: 2.5, pointRadius: 3, pointHoverRadius: 5, tension: 0.15,
        },
      ],
    };
  }, [data, scopeColors, theme]);

  const donutOptions = {
    responsive: true, maintainAspectRatio: false, cutout: "60%",
    plugins: {
      legend: { position: "bottom", labels: { usePointStyle: true, padding: 10, font: { size: 10, weight: 500 } } },
      tooltip: {
        backgroundColor: theme.palette.grey[900], bodyFont: { size: 11 }, padding: 8, cornerRadius: 6,
        callbacks: { label: (c) => { const t = c.dataset.data.reduce((a, b) => a + b, 0); const pct = t ? ((c.parsed / t) * 100).toFixed(1) : 0; return `${c.label}: ${c.parsed.toLocaleString()} t (${pct}%)`; } },
      },
    },
  };

  const lineOptions = {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { position: "top", labels: { usePointStyle: true, padding: 12, font: { size: 10, weight: 500 } } },
      tooltip: { backgroundColor: theme.palette.grey[900], titleFont: { size: 11, weight: 600 }, bodyFont: { size: 10 }, padding: 8, cornerRadius: 6, callbacks: { label: (c) => `${c.dataset.label}: ${c.parsed.y != null ? c.parsed.y.toLocaleString() + " t CO₂e" : "—"}` } },
    },
    scales: {
      y: { beginAtZero: true, grid: { color: theme.palette.divider }, ticks: { font: { size: 10 }, callback: (v) => `${v} t` } },
      x: { grid: { display: false }, ticks: { font: { size: 10 } } },
    },
  };

  if (loading) return (
    <PageContainer sx={{ alignItems: "center", justifyContent: "center" }}>
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: 300 }}>
        <CircularProgress size={40} />
      </Box>
    </PageContainer>
  );

  if (error) return <PageContainer><Alert severity="error" sx={{ m: 2 }}>{error}</Alert></PageContainer>;

  const h = data?.headline || {};
  const period = data?.period;
  const campus = data?.coverage_by_campus || [];
  const actions = data?.actions || [];
  const sbti = data?.sbti || {};
  const coverage = data?.coverage || {};
  const footprint = typeof h.footprint_tonnes === "number" ? h.footprint_tonnes.toLocaleString() : "—";
  const coverageLabel = `${h.coverage_covered ?? 0} / ${h.coverage_total ?? 0}`;
  const periodLabel = period ? `${period.name} · ${period.status}` : "No active period";

  return (
    <PageContainer sx={{ p: 0, overflow: "auto" }}>

      {/* ── Page header ─────────────────────────────────────────────────── */}
      <Box sx={{ px: SPACING.lg, pt: 2, pb: 1.5, borderBottom: `1px solid ${theme.palette.divider}` }}>
        <Stack direction="row" alignItems="flex-start" justifyContent="space-between" flexWrap="wrap" gap={1}>
          <Box>
            <Typography sx={{ fontSize: "1.15rem", fontWeight: 700, color: "text.primary" }}>
              Chairman Dashboard
            </Typography>
            <Typography sx={{ fontSize: "0.78rem", color: "text.secondary", mt: 0.25, maxWidth: 620, lineHeight: 1.5 }}>
              Platform-wide strategic overview — footprint, coverage, SBTi alignment, and open actions.
              Audience: board &amp; leadership. For day-to-day tracking use <em>Emissions Breakdown</em>.
            </Typography>
          </Box>
          <Stack direction="row" alignItems="center" gap={1} flexShrink={0}>
            <Chip size="small" label={periodLabel} color="success" sx={{ fontSize: "0.65rem" }} />
            <Typography sx={{ fontSize: "0.65rem", color: "text.disabled" }}>
              {data?.as_of ? `Updated ${new Date(data.as_of).toLocaleDateString()}` : "—"}
            </Typography>
          </Stack>
        </Stack>
      </Box>

      {/* ── Section 1: Headline metrics (6 KPIs) ─────────────────────── */}
      <Section title="Headline Metrics" defaultExpanded>
        <Grid container spacing={1.25} sx={{ pt: 1 }}>
          {[
            { label: "Total Footprint", value: footprint, unit: "t CO₂e", sub: "all periods, all campuses",
              icon: <Factory />, color: theme.palette.primary.main,
              tooltip: "Total CO₂e across ALL reporting periods and campuses (Scope 1+2+3). Platform-wide, not period-filtered." },
            { label: "Inventory Coverage", value: coverageLabel, unit: `${h.coverage_pct ?? 0}%`, sub: "of declared universe",
              icon: <TaskAlt />, color: theme.palette.success.main,
              tooltip: "Sources with at least one calculation ÷ total declared sources. Goal: 100% Scope 1+2, 80% Scope 3." },
            { label: "SBTi Targets", value: sbti.count ?? 0, unit: sbti.draft ? "draft" : "active", sub: `${sbti.committed ?? 0} committed`,
              icon: <Flag />, color: theme.palette.warning.main,
              tooltip: "Science-Based Targets. Draft = pending board ratification. SBTi 1.5°C pathway requires 42% reduction by 2030." },
            { label: "Data Quality", value: h.avg_quality_tier != null ? `T${h.avg_quality_tier}` : "—", unit: "PCAF", sub: `DQ score ${h.data_quality_score ?? 0}/100`,
              icon: <Bolt />, color: theme.palette.info.main,
              tooltip: "PCAF tier (1=audited, 3=calculated, 5=proxy). DQ score = data completeness 0–100. T3 is the minimum credible standard." },
            { label: "Open Actions", value: h.actions_open ?? 0, unit: "to do", sub: `${h.actions_in_progress ?? 0} in progress`,
              icon: <LocalShipping />, color: theme.palette.error.main,
              tooltip: "Work items for closing coverage gaps: collect missing data, improve quality, obtain verification, formalize exclusions." },
            { label: "Calculations", value: h.calculation_count ?? 0, unit: "records", sub: "CO₂e rows",
              icon: <Bolt />, color: theme.palette.secondary.main,
              tooltip: "Total CO₂e calculation records (activity rows × emission factors). Each represents one measured emission event." },
          ].map((kpi) => (
            <Grid key={kpi.label} size={{ xs: 6, sm: 4, md: 2 }}>
              <KpiCard {...kpi} />
            </Grid>
          ))}
        </Grid>
      </Section>

      {/* ── Section 2: Scope breakdown ────────────────────────────────── */}
      <Section
        title="Scope Breakdown"
        badge={<Typography sx={{ fontSize: "0.65rem", color: "text.disabled" }}>{footprint} t CO₂e total</Typography>}
        defaultExpanded
      >
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ pt: 0.5 }}>
          <Box sx={{ flex: "0 0 220px", height: 200 }}>
            {scopeDonut
              ? <Doughnut data={scopeDonut} options={donutOptions} />
              : <Typography sx={{ fontSize: "0.8rem", color: "text.disabled", mt: 2 }}>No measured emissions yet.</Typography>
            }
          </Box>
          <Box sx={{ flex: 1 }}>
            {(data?.scope_breakdown || []).map((s) => (
              <Box key={s.scope} sx={{ mb: 1.5 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="baseline" mb={0.5}>
                  <Typography sx={{ fontSize: "0.78rem", fontWeight: 600, color: "text.primary" }}>{s.scope_name}</Typography>
                  <Stack direction="row" gap={1.5} alignItems="baseline">
                    <Typography sx={{ fontSize: "0.95rem", fontWeight: 700, color: "text.primary" }}>
                      {parseFloat(s.co2e_tonnes).toLocaleString()}
                      <Typography component="span" sx={{ fontSize: "0.65rem", ml: 0.4, color: "text.secondary" }}>t</Typography>
                    </Typography>
                    <Typography sx={{ fontSize: "0.65rem", color: "text.disabled", width: 38, textAlign: "right" }}>{s.percentage}%</Typography>
                  </Stack>
                </Stack>
                <LinearProgress variant="determinate" value={Math.min(parseFloat(s.percentage), 100)}
                  sx={{ height: 5, borderRadius: 1, bgcolor: theme.palette.divider,
                    "& .MuiLinearProgress-bar": { bgcolor: scopeColors[s.scope], borderRadius: 1 } }} />
              </Box>
            ))}
          </Box>
        </Stack>
      </Section>

      {/* ── Section 3: Coverage by campus ─────────────────────────────── */}
      <Section
        title="Coverage by Campus"
        badge={
          <Chip size="small" variant="outlined"
            label={`${coverage.covered ?? 0} / ${coverage.total ?? 0} measured`}
            sx={{ fontSize: "0.6rem", height: 18 }} />
        }
        defaultExpanded
      >
        <Stack spacing={1.5} sx={{ pt: 0.5 }}>
          {campus.length
            ? campus.map((c) => (
              <Box key={c.campus}>
                <Stack direction="row" justifyContent="space-between" alignItems="baseline" mb={0.5}>
                  <Typography sx={{ fontSize: "0.8rem", fontWeight: 600, color: "text.primary" }}>{c.campus}</Typography>
                  <Typography sx={{ fontSize: "0.7rem", color: "text.secondary" }}>
                    {c.covered} / {c.total} sources · {c.pct}%
                  </Typography>
                </Stack>
                <LinearProgress variant="determinate" value={Math.min(c.pct, 100)}
                  sx={{ height: 7, borderRadius: 1.5, bgcolor: theme.palette.divider,
                    "& .MuiLinearProgress-bar": {
                      bgcolor: c.pct >= 60 ? theme.palette.success.main : c.pct >= 30 ? theme.palette.warning.main : theme.palette.error.main,
                      borderRadius: 1.5 } }} />
              </Box>
            ))
            : <Typography sx={{ fontSize: "0.8rem", color: "text.disabled" }}>No coverage data.</Typography>
          }
          {campus.length > 0 && (
            <>
              <Divider sx={{ my: 0.25 }} />
              <Typography sx={{ fontSize: "0.65rem", color: "text.disabled" }}>
                Coverage is a plan, not a grade — {(coverage.total ?? 0) - (coverage.covered ?? 0)} sources remain declared (to be measured).
              </Typography>
            </>
          )}
        </Stack>
      </Section>

      {/* ── Section 4: SBTi Trajectory (collapsed by default) ─────────── */}
      <Section
        title="Emissions Trajectory"
        badge={sbti.draft ? <Chip size="small" label="illustrative · draft targets" variant="outlined" sx={{ fontSize: "0.6rem", height: 18, color: "warning.main", borderColor: "warning.main" }} /> : null}
        defaultExpanded={false}
      >
        {trajectoryChart
          ? <Box sx={{ height: 220, pt: 0.5 }}><Line data={trajectoryChart} options={lineOptions} /></Box>
          : <Typography sx={{ fontSize: "0.8rem", color: "text.disabled", py: 1 }}>No trajectory data. SBTi targets are required.</Typography>
        }
      </Section>

      {/* ── Section 5: Priority actions ───────────────────────────────── */}
      <Section
        title="Priority Actions"
        badge={h.actions_open > 0 ? <Chip size="small" label={`${h.actions_open} open`} color="error" sx={{ fontSize: "0.6rem", height: 18 }} /> : null}
        defaultExpanded={!!actions.length}
      >
        {actions.length
          ? (
            <Stack spacing={0.75} sx={{ pt: 0.5 }}>
              {actions.slice(0, 8).map((a) => {
                const st = ACTION_STATUS_META[a.status] || { label: a.status, color: "default" };
                return (
                  <Stack key={a.id} direction="row" alignItems="center" gap={1}
                    sx={{ py: 0.75, px: 1, borderRadius: 1, bgcolor: "action.hover" }}>
                    <Box sx={{ width: 7, height: 7, borderRadius: "50%", bgcolor: `${st.color}.main`, flexShrink: 0 }} />
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography sx={{ fontSize: "0.78rem", color: "text.primary", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        <strong>{ACTION_TYPE_LABEL[a.action_type] || a.action_type}</strong> — {a.source_name || "—"}
                      </Typography>
                      {a.notes && (
                        <Typography sx={{ fontSize: "0.65rem", color: "text.disabled", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {a.notes}
                        </Typography>
                      )}
                    </Box>
                    <Chip size="small" label={st.label} color={st.color} variant="outlined" sx={{ fontSize: "0.6rem", height: 18, flexShrink: 0 }} />
                  </Stack>
                );
              })}
            </Stack>
          )
          : <Typography sx={{ fontSize: "0.8rem", color: "text.disabled", py: 1 }}>No open actions — all gaps addressed.</Typography>
        }
      </Section>

    </PageContainer>
  );
}

