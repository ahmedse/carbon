// Chairman Overview — strategic one-pager. Typography is theme variants (RULE 8).

import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  Box,
  Typography,
  Card,
  CardContent,
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
  Button,
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
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import useDocumentTitle from "../../hooks/useDocumentTitle";
import { fetchChairmanData } from "../../api/emissions-extended";
import PageContainer from "../../components/layout/PageContainer";
import PageHeader from "../../components/Page/PageHeader";
import LoadingSkeleton from "../../components/Page/LoadingSkeleton";
import { SPACING } from "../../theme/themeTokens";
import { MarketBasedAbsentAlert } from "./Scope2Labels";

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, ChartTooltip, Legend, Filler
);

function KpiCard({ label, value, unit, sub, icon, color, tooltip }) {
  return (
    <Card variant="outlined" sx={{ borderRadius: 1.5, height: "100%" }}>
      <CardContent sx={{ p: "10px 12px", "&:last-child": { pb: "10px" } }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 0.75 }}>
          <Box sx={{
            width: 26, height: 26, borderRadius: 0.75,
            display: "flex", alignItems: "center", justifyContent: "center",
            bgcolor: "action.hover", color, flexShrink: 0,
          }}
          >
            {icon}
          </Box>
          {tooltip && (
            <Tooltip title={tooltip} arrow placement="top">
              <InfoOutlined fontSize="small" color="disabled" />
            </Tooltip>
          )}
        </Box>
        <Typography variant="h3" component="p" color="text.primary">
          {value}
          {unit && (
            <Typography component="span" variant="caption" sx={{ ml: 0.5 }} color="text.secondary">
              {unit}
            </Typography>
          )}
        </Typography>
        <Typography variant="overline" color="text.secondary" display="block">
          {label}
        </Typography>
        {sub && (
          <Typography variant="caption" color="text.secondary" display="block">{sub}</Typography>
        )}
      </CardContent>
    </Card>
  );
}

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
        expandIcon={<ExpandMoreIcon fontSize="small" color="action" />}
        sx={{
          minHeight: 40, px: SPACING.lg,
          "& .MuiAccordionSummary-content": { my: 0.75, alignItems: "center", gap: 1 },
        }}
      >
        <Typography variant="overline" color="text.secondary">
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
  const theme = useTheme();
  const navigate = useNavigate();
  const { t } = useTranslation("emissions");
  useDocumentTitle(t("chairman.title"));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const token = localStorage.getItem("access");

  const load = useCallback(() => {
    let active = true;
    setLoading(true);
    setError(null);
    fetchChairmanData({}, token)
      .then((r) => { if (active) setData(r); })
      .catch((e) => { if (active) setError(e.message || t("chairman.loadFailed")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, t]);

  useEffect(() => load(), [load]);

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
    const labels = targets.map((row) => row.year);
    return {
      labels,
      datasets: [
        {
          label: t("chairman.sbtiTargetSeries"),
          data: labels.map((y) => targets.find((row) => row.year === y)?.target_co2e_tonnes ?? null),
          borderColor: theme.palette.text.secondary,
          backgroundColor: "transparent",
          borderDash: [6, 4],
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.15,
        },
        {
          label: t("chairman.actualSeries"),
          data: labels.map((y) => actualByYear[y] ?? null),
          borderColor: scopeColors[1],
          backgroundColor: theme.palette.action.hover,
          fill: true,
          borderWidth: 2.5,
          pointRadius: 3,
          pointHoverRadius: 5,
          tension: 0.15,
        },
      ],
    };
  }, [data, scopeColors, theme, t]);

  const donutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "60%",
    plugins: {
      legend: { position: "bottom", labels: { usePointStyle: true, padding: 10 } },
      tooltip: {
        callbacks: {
          label: (c) => {
            const total = c.dataset.data.reduce((a, b) => a + b, 0);
            const pct = total ? ((c.parsed / total) * 100).toFixed(1) : 0;
            return `${c.label}: ${c.parsed.toLocaleString()} t (${pct}%)`;
          },
        },
      },
    },
  };

  const lineOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { position: "top", labels: { usePointStyle: true, padding: 12 } },
      tooltip: {
        callbacks: {
          label: (c) => `${c.dataset.label}: ${c.parsed.y != null ? `${c.parsed.y.toLocaleString()} t CO₂e` : "—"}`,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: theme.palette.divider },
        ticks: { callback: (v) => `${v} t` },
      },
      x: { grid: { display: false } },
    },
  };

  if (loading) {
    return (
      <PageContainer>
        <LoadingSkeleton variant="console" />
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <Alert
          severity="error"
          action={(
            <Button color="inherit" size="small" onClick={load}>
              {t("common:retry")}
            </Button>
          )}
        >
          {error}
        </Alert>
      </PageContainer>
    );
  }

  const h = data?.headline || {};
  const period = data?.period;
  const campus = data?.coverage_by_campus || [];
  const actions = data?.actions || [];
  const sbti = data?.sbti || {};
  const coverage = data?.coverage || {};
  const footprint = typeof h.footprint_tonnes === "number" ? h.footprint_tonnes.toLocaleString() : "—";
  const coverageLabel = `${h.coverage_covered ?? 0} / ${h.coverage_total ?? 0}`;
  const periodLabel = period ? `${period.name} · ${period.status}` : t("chairman.noPeriod");
  const actionType = {
    collect_data: t("chairman.collectData"),
    improve_quality: t("chairman.improveQuality"),
    obtain_verification: t("chairman.obtainVerification"),
    formalize_exclusion: t("chairman.formalizeExclusion"),
  };
  const actionStatus = {
    open: { label: t("chairman.statusOpen"), color: "info" },
    in_progress: { label: t("chairman.statusInProgress"), color: "primary" },
    done: { label: t("chairman.statusDone"), color: "success" },
    blocked: { label: t("chairman.statusBlocked"), color: "error" },
  };

  const scope2Label = (method) => {
    const raw = String(method || "").toLowerCase().replace(/-/g, "_");
    if (raw === "market_based") return t("scope2MarketBased");
    if (raw === "location_based") return t("scope2LocationBased");
    return null;
  };

  return (
    <PageContainer sx={{ p: 0, overflow: "auto" }}>
      <Box sx={{ px: SPACING.lg, pt: 2 }}>
        <PageHeader
          title={t("chairman.title")}
          subtitle={t("chairman.description")}
          badge={{ label: periodLabel, color: "success" }}
        />
        <Typography variant="caption" color="text.secondary">
          {data?.as_of ? t("chairman.updated", { date: new Date(data.as_of).toLocaleDateString() }) : "—"}
        </Typography>
      </Box>

      <Alert
        severity="warning"
        sx={{ mx: SPACING.lg, mt: 1.5 }}
        action={(
          <Button color="inherit" size="small" onClick={() => navigate("/carbon/onboarding")}>
            {t("chairman.openOnboarding")}
          </Button>
        )}
      >
        {t("chairman.notO1Footprint")}
      </Alert>
      <Box sx={{ mx: SPACING.lg, mt: 1 }}>
        <MarketBasedAbsentAlert payload={data} />
      </Box>

      <Section title={t("chairman.headlineMetrics")} defaultExpanded>
        <Grid container spacing={1.25} sx={{ pt: 1 }}>
          {[
            {
              label: t("chairman.totalFootprint"),
              value: footprint,
              unit: t("chairman.unitTco2e"),
              sub: t("chairman.footprintSub"),
              icon: <Factory fontSize="small" />,
              color: theme.palette.primary.main,
              tooltip: t("chairman.footprintTip"),
            },
            {
              label: t("chairman.inventoryCoverage"),
              value: coverageLabel,
              unit: `${h.coverage_pct ?? 0}%`,
              sub: t("chairman.coverageSub"),
              icon: <TaskAlt fontSize="small" />,
              color: theme.palette.success.main,
              tooltip: t("chairman.coverageTip"),
            },
            {
              label: t("chairman.sbtiTargets"),
              value: sbti.count ?? 0,
              unit: sbti.draft ? t("chairman.draft") : t("chairman.active"),
              sub: t("chairman.committed", { count: sbti.committed ?? 0 }),
              icon: <Flag fontSize="small" />,
              color: theme.palette.warning.main,
              tooltip: t("chairman.sbtiTip"),
            },
            {
              label: t("chairman.dataQuality"),
              value: h.avg_quality_tier != null ? `T${h.avg_quality_tier}` : "—",
              unit: t("chairman.pcaf"),
              sub: t("chairman.dqScore", { score: h.data_quality_score ?? 0 }),
              icon: <Bolt fontSize="small" />,
              color: theme.palette.info.main,
              tooltip: t("chairman.dqTip"),
            },
            {
              label: t("chairman.openActions"),
              value: h.actions_open ?? 0,
              unit: t("chairman.toDo"),
              sub: t("chairman.inProgress", { count: h.actions_in_progress ?? 0 }),
              icon: <LocalShipping fontSize="small" />,
              color: theme.palette.error.main,
              tooltip: t("chairman.actionsTip"),
            },
            {
              label: t("chairman.calculations"),
              value: h.calculation_count ?? 0,
              unit: t("chairman.records"),
              sub: t("chairman.co2eRows"),
              icon: <Bolt fontSize="small" />,
              color: theme.palette.secondary.main,
              tooltip: t("chairman.calculationsTip"),
            },
          ].map((kpi) => (
            <Grid key={kpi.label} size={{ xs: 6, sm: 4, md: 2 }}>
              <KpiCard {...kpi} />
            </Grid>
          ))}
        </Grid>
      </Section>

      <Section
        title={t("chairman.scopeBreakdown")}
        badge={<Typography variant="caption" color="text.secondary">{t("chairman.footprintTotal", { value: footprint })}</Typography>}
        defaultExpanded
      >
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ pt: 0.5 }}>
          <Box sx={{ flex: "0 0 220px", height: 200 }}>
            {scopeDonut
              ? <Doughnut data={scopeDonut} options={donutOptions} />
              : <Typography variant="body2" color="text.secondary">{t("chairman.noMeasured")}</Typography>}
          </Box>
          <Box sx={{ flex: 1 }}>
            {(data?.scope_breakdown || []).map((s) => {
              const methodLabel = Number(s.scope) === 2 ? scope2Label(s.scope2_method) : null;
              return (
                <Box key={s.scope} sx={{ mb: 1.5 }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" mb={0.5}>
                    <Stack direction="row" gap={1} alignItems="center">
                      <Typography variant="subtitle2" color="text.primary">{s.scope_name}</Typography>
                      {Number(s.scope) === 2 && methodLabel && (
                        <Chip
                          size="small"
                          variant="outlined"
                          label={t("chairman.scope2Method", { method: methodLabel })}
                        />
                      )}
                      {Number(s.scope) === 2 && !methodLabel && (
                        <Chip size="small" variant="outlined" label={t("chairman.scope2Unlabelled")} />
                      )}
                    </Stack>
                    <Stack direction="row" gap={1.5} alignItems="baseline">
                      <Typography variant="h6" component="span" color="text.primary">
                        {parseFloat(s.co2e_tonnes).toLocaleString()}
                        <Typography component="span" variant="caption" sx={{ ml: 0.4 }} color="text.secondary">
                          {t("chairman.tonneUnit")}
                        </Typography>
                      </Typography>
                      <Typography variant="caption" color="text.secondary">{s.percentage}%</Typography>
                    </Stack>
                  </Stack>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(parseFloat(s.percentage), 100)}
                    sx={{
                      height: 5,
                      borderRadius: 1,
                      bgcolor: theme.palette.divider,
                      "& .MuiLinearProgress-bar": { bgcolor: scopeColors[s.scope], borderRadius: 1 },
                    }}
                  />
                </Box>
              );
            })}
          </Box>
        </Stack>
      </Section>

      <Section
        title={t("chairman.coverageByCampus")}
        badge={(
          <Chip
            size="small"
            variant="outlined"
            label={t("chairman.measured", { covered: coverage.covered ?? 0, total: coverage.total ?? 0 })}
          />
        )}
        defaultExpanded
      >
        <Stack spacing={1.5} sx={{ pt: 0.5 }}>
          {campus.length
            ? campus.map((c) => (
              <Box key={c.campus}>
                <Stack direction="row" justifyContent="space-between" alignItems="baseline" mb={0.5}>
                  <Typography variant="subtitle2" color="text.primary">{c.campus}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {t("chairman.sourcesLine", { covered: c.covered, total: c.total, pct: c.pct })}
                  </Typography>
                </Stack>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(c.pct, 100)}
                  sx={{
                    height: 7,
                    borderRadius: 1.5,
                    bgcolor: theme.palette.divider,
                    "& .MuiLinearProgress-bar": {
                      bgcolor: c.pct >= 60 ? theme.palette.success.main : c.pct >= 30 ? theme.palette.warning.main : theme.palette.error.main,
                      borderRadius: 1.5,
                    },
                  }}
                />
              </Box>
            ))
            : <Typography variant="body2" color="text.secondary">{t("chairman.noCoverage")}</Typography>}
          {campus.length > 0 && (
            <>
              <Divider sx={{ my: 0.25 }} />
              <Typography variant="caption" color="text.secondary">
                {t("chairman.coverageNote", { remaining: (coverage.total ?? 0) - (coverage.covered ?? 0) })}
              </Typography>
            </>
          )}
        </Stack>
      </Section>

      <Section
        title={t("chairman.trajectory")}
        badge={sbti.draft ? (
          <Chip size="small" label={t("chairman.draftTargets")} variant="outlined" color="warning" />
        ) : null}
        defaultExpanded={false}
      >
        {trajectoryChart
          ? <Box sx={{ height: 220, pt: 0.5 }}><Line data={trajectoryChart} options={lineOptions} /></Box>
          : <Typography variant="body2" color="text.secondary">{t("chairman.noTrajectory")}</Typography>}
      </Section>

      <Section
        title={t("chairman.priorityActions")}
        badge={h.actions_open > 0 ? (
          <Chip size="small" label={t("chairman.openCount", { count: h.actions_open })} color="error" />
        ) : null}
        defaultExpanded={!!actions.length}
      >
        {actions.length
          ? (
            <Stack spacing={0.75} sx={{ pt: 0.5 }}>
              {actions.slice(0, 8).map((a) => {
                const st = actionStatus[a.status] || { label: a.status, color: "default" };
                return (
                  <Stack
                    key={a.id}
                    direction="row"
                    alignItems="center"
                    gap={1}
                    sx={{ py: 0.75, px: 1, borderRadius: 1, bgcolor: "action.hover" }}
                  >
                    <Box sx={{ width: 7, height: 7, borderRadius: "50%", bgcolor: `${st.color}.main`, flexShrink: 0 }} />
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography variant="body2" color="text.primary" noWrap>
                        {actionType[a.action_type] || a.action_type}
                        {" — "}
                        {a.source_name || "—"}
                      </Typography>
                      {a.notes && (
                        <Typography variant="caption" color="text.secondary" noWrap>{a.notes}</Typography>
                      )}
                    </Box>
                    <Chip size="small" label={st.label} color={st.color} variant="outlined" />
                  </Stack>
                );
              })}
            </Stack>
          )
          : <Typography variant="body2" color="text.secondary">{t("chairman.noActions")}</Typography>}
      </Section>
    </PageContainer>
  );
}
