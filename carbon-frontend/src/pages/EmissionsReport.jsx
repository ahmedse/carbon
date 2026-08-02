// File: src/pages/EmissionsReport.jsx
// Professional Carbon Emissions Report with GHG Protocol structure

import React, { useState, useEffect, useRef } from "react";
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  Chip,
  Divider,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Stack,
  IconButton,
  Tooltip,
} from "@mui/material";
import {
  ExpandMore,
  Download,
  Print,
  Share,
  Nature,
  Factory,
  Bolt,
  LocalShipping,
  Description,
  CalendarMonth,
  Business,
  CheckCircle,
} from "@mui/icons-material";
import { Doughnut } from "react-chartjs-2";
import { useTheme } from "@mui/material/styles";
import { fetchEmissionsReport, fetchReportingPeriods } from "../api/emissions";
import useDocumentTitle from "../hooks/useDocumentTitle";

// ============ Styled Components ============

const ReportSection = ({ title, icon, children, sx = {} }) => (
  <Paper
    elevation={0}
    sx={{
      p: 4,
      mb: 3,
      border: "1px solid",
      borderColor: "divider",
      borderRadius: 2,
      ...sx,
    }}
  >
    <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 3 }}>
      {icon}
      <Typography variant="h5" sx={{ fontWeight: 700, color: "text.primary" }}>
        {title}
      </Typography>
    </Box>
    {children}
  </Paper>
);

const ScopeSummaryCard = ({ name, emissions, categories, color }) => (
  <Card
    elevation={0}
    sx={{
      border: "1px solid",
      borderColor: "divider",
      borderRadius: 2,
      borderLeft: `4px solid ${color}`,
      height: "100%",
    }}
  >
    <CardContent sx={{ p: 3 }}>
      <Typography variant="overline" sx={{ color: "text.secondary", fontWeight: 600 }}>
        {name}
      </Typography>
      <Typography variant="h3" sx={{ fontWeight: 700, color: "text.primary", my: 1 }}>
        {emissions.toLocaleString()}
        <Typography component="span" variant="h6" sx={{ ml: 1, fontWeight: 400, color: "text.secondary" }}>
          t CO₂e
        </Typography>
      </Typography>
      <Divider sx={{ my: 2 }} />
      <Typography variant="subtitle2" sx={{ color: "text.secondary", mb: 1 }}>
        Categories:
      </Typography>
      {categories?.map((cat, idx) => (
        <Box key={idx} sx={{ display: "flex", justifyContent: "space-between", mb: 0.5 }}>
          <Typography variant="body2" sx={{ color: "text.primary" }}>
            {cat.name}
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 600, color: "text.primary" }}>
            {cat.emissions_tonnes.toLocaleString()} t
          </Typography>
        </Box>
      ))}
    </CardContent>
  </Card>
);

// ============ Main Component ============

export default function EmissionsReport({ projectId }) {
  useDocumentTitle("Emissions Report");
  const theme = useTheme();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [report, setReport] = useState(null);
  const [periods, setPeriods] = useState([]);
  const [selectedPeriod, setSelectedPeriod] = useState("");
  const [selectedYear, setSelectedYear] = useState(2025); // Demo data year
  const reportRef = useRef(null);

  const token = localStorage.getItem("access");

  // Fetch reporting periods
  useEffect(() => {
    const loadPeriods = async () => {
      try {
        const result = await fetchReportingPeriods(token);
        setPeriods(result || []);
        if (result?.length > 0) {
          setSelectedPeriod(result[0].id);
        }
      } catch (err) {
        console.warn("Failed to load reporting periods:", err);
      }
    };
    loadPeriods();
  }, [token]);

  // Fetch report data
  useEffect(() => {
    const loadReport = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = { project_id: projectId };
        if (selectedPeriod) {
          params.reporting_period_id = selectedPeriod;
        } else {
          params.year = selectedYear;
        }
        const result = await fetchEmissionsReport(params, token);
        setReport(result);
      } catch (err) {
        console.error("Failed to load report:", err);
        setError(err.message || "Failed to load report");
      } finally {
        setLoading(false);
      }
    };

    loadReport();
  }, [projectId, selectedPeriod, selectedYear, token]);

  // Print report
  const handlePrint = () => {
    window.print();
  };

  // Download as JSON
  const handleDownload = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `emissions-report-${report.reporting_period?.name || selectedYear}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Scope colors — resolved from theme tokens (identical values)
  const scopeColors = {
    1: theme.palette.success.main,   // #10b981
    2: theme.palette.primary.light,  // #3b82f6
    3: theme.palette.warning.main,   // #f59e0b
  };

  const scopeIcons = {
    1: <Factory sx={{ color: scopeColors[1] }} />,
    2: <Bolt sx={{ color: scopeColors[2] }} />,
    3: <LocalShipping sx={{ color: scopeColors[3] }} />,
  };

  // Scope pie chart
  const scopePieData = report?.scope_details
    ? {
        labels: report.scope_details.map((s) => s.name),
        datasets: [
          {
            data: report.scope_details.map((s) => s.total_tonnes),
            backgroundColor: report.scope_details.map((s) => scopeColors[s.scope]),
            borderColor: "#fff",
            borderWidth: 3,
          },
        ],
      }
    : null;

  // Loading state
  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: 400 }}>
        <CircularProgress size={48} sx={{ color: "success.main" }} />
      </Box>
    );
  }

  // Error state
  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        {error}
      </Alert>
    );
  }

  // No data state
  if (!report) {
    return (
      <Alert severity="info" sx={{ m: 2 }}>
        No report data available
      </Alert>
    );
  }

  return (
    <Box
      ref={reportRef}
      sx={{
        maxWidth: 1200,
        mx: "auto",
        px: { xs: 2, md: 4 },
        py: 4,
        bgcolor: "background.default",
        "@media print": {
          px: 2,
          py: 1,
        },
      }}
    >
      {/* Report Header */}
      <Paper
        elevation={0}
        sx={{
          p: 4,
          mb: 4,
          background: `linear-gradient(135deg, ${theme.palette.success.main} 0%, ${theme.palette.success.dark} 100%)`,
          color: "common.white",
          borderRadius: 3,
          "@media print": {
            background: theme.palette.success.main,
            borderRadius: 0,
          },
        }}
      >
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <Box>
            <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 2 }}>
              <Nature sx={{ fontSize: 40 }} />
              <Typography variant="h4" sx={{ fontWeight: 800 }}>
                Carbon Emissions Report
              </Typography>
            </Box>
            <Typography variant="h6" sx={{ opacity: 0.9, mb: 1 }}>
              {report.title}
            </Typography>
            <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
              <Chip
                icon={<CalendarMonth />}
                label={
                  report.reporting_period?.name ||
                  `Year ${report.reporting_period?.year || selectedYear}`
                }
                sx={{ bgcolor: "rgba(255,255,255,0.2)", color: "white" }}
              />
              <Chip
                icon={<CheckCircle />}
                label={`Generated: ${new Date(report.generated_at).toLocaleDateString()}`}
                sx={{ bgcolor: "rgba(255,255,255,0.2)", color: "white" }}
              />
            </Stack>
          </Box>
          <Stack direction="row" spacing={1} sx={{ "@media print": { display: "none" } }}>
            <FormControl size="small" sx={{ minWidth: 120, bgcolor: "white", borderRadius: 1 }}>
              <Select
                value={selectedPeriod || selectedYear}
                onChange={(e) => {
                  const val = e.target.value;
                  if (typeof val === "number") {
                    setSelectedPeriod("");
                    setSelectedYear(val);
                  } else {
                    setSelectedPeriod(val);
                  }
                }}
                sx={{ bgcolor: "white" }}
              >
                {periods.map((p) => (
                  <MenuItem key={p.id} value={p.id}>
                    {p.name}
                  </MenuItem>
                ))}
                <Divider />
                {[2023, 2024, 2025, 2026].map((y) => (
                  <MenuItem key={y} value={y}>
                    Year {y}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Tooltip title="Print Report">
              <IconButton onClick={handlePrint} sx={{ bgcolor: "rgba(255,255,255,0.2)", color: "white" }}>
                <Print />
              </IconButton>
            </Tooltip>
            <Tooltip title="Download JSON">
              <IconButton onClick={handleDownload} sx={{ bgcolor: "rgba(255,255,255,0.2)", color: "white" }}>
                <Download />
              </IconButton>
            </Tooltip>
          </Stack>
        </Box>
      </Paper>

      {/* Executive Summary */}
      <ReportSection title="Executive Summary" icon={<Description sx={{ color: "success.main", fontSize: 28 }} />}>
        <Grid container spacing={4}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" sx={{ fontWeight: 600, color: "text.primary", mb: 2 }}>
                Total GHG Emissions
              </Typography>
              <Typography variant="h2" sx={{ fontWeight: 800, color: "text.primary" }}>
                {report.summary?.total_emissions_tonnes?.toLocaleString() || 0}
                <Typography component="span" variant="h5" sx={{ ml: 1, fontWeight: 400, color: "text.secondary" }}>
                  tonnes CO₂e
                </Typography>
              </Typography>
            </Box>
            <Typography variant="body1" sx={{ color: "text.secondary", lineHeight: 1.8 }}>
              This report presents the greenhouse gas (GHG) emissions inventory for the reporting period,
              calculated following the GHG Protocol Corporate Standard. Emissions are categorized into
              Scope 1 (direct), Scope 2 (indirect from energy), and Scope 3 (value chain) emissions.
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            {scopePieData && (
              <Box sx={{ height: 280 }}>
                <Doughnut
                  data={scopePieData}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "60%",
                    plugins: {
                      legend: {
                        position: "right",
                        labels: {
                          usePointStyle: true,
                          padding: 16,
                          font: { size: 12, weight: 500 },
                        },
                      },
                    },
                  }}
                />
              </Box>
            )}
          </Grid>
        </Grid>
      </ReportSection>

      {/* Scope Breakdown */}
      <ReportSection title="Emissions by Scope" icon={<Factory sx={{ color: "primary.light", fontSize: 28 }} />}>
        <Grid container spacing={3}>
          {report.scope_details?.map((scope) => (
            <Grid size={{ xs: 12, md: 4 }} key={scope.scope}>
              <ScopeSummaryCard
                scope={scope.scope}
                name={scope.name}
                emissions={scope.total_tonnes}
                categories={scope.categories}
                color={scopeColors[scope.scope]}
              />
            </Grid>
          ))}
        </Grid>
      </ReportSection>

      {/* Detailed Breakdown by Scope */}
      {report.scope_details?.map((scope) => (
        <ReportSection
          key={scope.scope}
          title={scope.name}
          icon={scopeIcons[scope.scope]}
          sx={{ borderLeft: `4px solid ${scopeColors[scope.scope]}` }}
        >
          <Typography variant="body1" sx={{ color: "text.secondary", mb: 3 }}>
            {scope.scope === 1 &&
              "Direct GHG emissions from sources owned or controlled by the organization."}
            {scope.scope === 2 &&
              "Indirect GHG emissions from the generation of purchased electricity, steam, heating, and cooling."}
            {scope.scope === 3 &&
              "All other indirect GHG emissions that occur in the organization's value chain."}
          </Typography>

          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: "background.paper" }}>
                  <TableCell sx={{ fontWeight: 600 }}>Category</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>
                    Emissions (t CO₂e)
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>
                    Data Points
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>
                    % of Scope
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {scope.categories?.map((cat, idx) => (
                  <TableRow key={idx}>
                    <TableCell>{cat.name}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>
                      {cat.emissions_tonnes.toLocaleString()}
                    </TableCell>
                    <TableCell align="right">{cat.count.toLocaleString()}</TableCell>
                    <TableCell align="right">
                      {scope.total_tonnes > 0
                        ? ((cat.emissions_tonnes / scope.total_tonnes) * 100).toFixed(1)
                        : 0}
                      %
                    </TableCell>
                  </TableRow>
                ))}
                <TableRow sx={{ bgcolor: "background.paper" }}>
                  <TableCell sx={{ fontWeight: 700 }}>Total</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    {scope.total_tonnes.toLocaleString()}
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    {scope.categories?.reduce((sum, c) => sum + c.count, 0).toLocaleString()}
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    100%
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        </ReportSection>
      ))}

      {/* Data Details (Expandable) */}
      <Accordion
        elevation={0}
        sx={{
          border: "1px solid",
          borderColor: "divider",
          borderRadius: "8px !important",
          "&:before": { display: "none" },
          mb: 3,
          "@media print": { display: "none" },
        }}
      >
        <AccordionSummary expandIcon={<ExpandMore />}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Detailed Calculation Data ({report.rows?.length || 0} records)
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          <TableContainer sx={{ maxHeight: 500 }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, bgcolor: "background.paper" }}>Module</TableCell>
                  <TableCell sx={{ fontWeight: 600, bgcolor: "background.paper" }}>Table</TableCell>
                  <TableCell sx={{ fontWeight: 600, bgcolor: "background.paper" }}>Category</TableCell>
                  <TableCell align="center" sx={{ fontWeight: 600, bgcolor: "background.paper" }}>Scope</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, bgcolor: "background.paper" }}>Activity</TableCell>
                  <TableCell sx={{ fontWeight: 600, bgcolor: "background.paper" }}>Factor</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, bgcolor: "background.paper" }}>CO₂e (t)</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {report.rows?.slice(0, 100).map((row, idx) => (
                  <TableRow key={idx} hover>
                    <TableCell sx={{ maxWidth: 150, overflow: "hidden", textOverflow: "ellipsis" }}>
                      {row.module}
                    </TableCell>
                    <TableCell sx={{ maxWidth: 150, overflow: "hidden", textOverflow: "ellipsis" }}>
                      {row.table}
                    </TableCell>
                    <TableCell>{row.category}</TableCell>
                    <TableCell align="center">
                      <Chip
                        label={row.scope}
                        size="small"
                        sx={{
                          bgcolor: `${scopeColors[row.scope]}20`,
                          color: scopeColors[row.scope],
                          fontWeight: 600,
                          minWidth: 32,
                        }}
                      />
                    </TableCell>
                    <TableCell align="right">
                      {parseFloat(row.activity_value).toLocaleString()} {row.activity_unit}
                    </TableCell>
                    <TableCell sx={{ fontSize: "0.75rem", color: "text.secondary" }}>{row.emission_factor}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>
                      {row.co2e_tonnes.toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          {(report.rows?.length || 0) > 100 && (
            <Typography variant="body2" sx={{ mt: 2, textAlign: "center", color: "text.secondary" }}>
              Showing first 100 of {report.rows.length.toLocaleString()} records
            </Typography>
          )}
        </AccordionDetails>
      </Accordion>

      {/* Methodology Note */}
      <ReportSection title="Methodology" icon={<Description sx={{ color: "secondary.main", fontSize: 28 }} />}>
        <Typography variant="body1" sx={{ color: "text.secondary", lineHeight: 1.8, mb: 2 }}>
          This emissions inventory was prepared in accordance with the Greenhouse Gas Protocol Corporate
          Standard developed by the World Resources Institute (WRI) and the World Business Council for
          Sustainable Development (WBCSD).
        </Typography>
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 4 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "text.primary", mb: 1 }}>
              Organizational Boundary
            </Typography>
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              Operational control approach
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "text.primary", mb: 1 }}>
              GWP Values
            </Typography>
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              IPCC AR6 100-year horizon
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "text.primary", mb: 1 }}>
              Emission Factors
            </Typography>
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              EPA, DEFRA, eGRID databases
            </Typography>
          </Grid>
        </Grid>
      </ReportSection>

      {/* Footer */}
      <Box sx={{ textAlign: "center", py: 3, color: "text.disabled", "@media print": { mt: 4 } }}>
        <Typography variant="body2">
          Generated by Carbon Management Platform • {new Date().toLocaleDateString()}
        </Typography>
      </Box>
    </Box>
  );
}
