// src/pages/Dashboard.jsx

import React from "react";
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Avatar,
  Chip,
  Divider,
  Stack,
  Paper,
  LinearProgress,
  Tooltip,
} from "@mui/material";
import InsertChartIcon from "@mui/icons-material/InsertChart";
import WaterDropIcon from "@mui/icons-material/WaterDrop";
import BoltIcon from "@mui/icons-material/Bolt";
import TrendingDownIcon from "@mui/icons-material/TrendingDown";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import EmojiNatureIcon from "@mui/icons-material/EmojiNature";
import EmojiEventsIcon from "@mui/icons-material/EmojiEvents";
import WbSunnyIcon from "@mui/icons-material/WbSunny";
import EmojiEmotionsIcon from "@mui/icons-material/EmojiEmotions";
import { Line, Bar, Pie, Doughnut } from "react-chartjs-2";
import { Chart, ArcElement, CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip as ChartTooltip, Legend } from "chart.js";

Chart.register(
  ArcElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ChartTooltip,
  Legend
);

// SVG Gauge for professional data completeness
function Gauge({ value, label, min = 0, max = 100, color = "#1976d2" }) {
  const radius = 46;
  const cx = 50, cy = 50;
  const circumference = 2 * Math.PI * radius;
  const percent = Math.min(1, Math.max(0, (value - min) / (max - min)));
  const offset = circumference * (1 - percent);
  return (
    <svg width={120} height={90} viewBox="0 0 120 90">
      <g>
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke="#eee"
          strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={0}
        />
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
        />
        <text x={cx} y={cy + 5} fontSize="28" fontWeight="bold" textAnchor="middle" fill="#222">{Math.round(value)}</text>
        <text x={cx} y={cy + 26} fontSize="13" textAnchor="middle" fill="#666">{label}</text>
      </g>
    </svg>
  );
}

export default function Dashboard() {
  // IMAGINARY DEMO DATA for AASTMT (2025), one year cycle
  const summary = {
    emissions: 5340, // last month
    emissionsStart: 6200, // Jan start
    emissionsTarget: 5000, // reduction goal
    emissionsChange: -13, // overall improvement %
    water: 80000,
    waterChange: -5.6,
    energy: 178000,
    energyChange: -4.8,
    energyGoal: 170000,
    topCampus: "Abu Qir",
    dataCompleteness: 97,
    auditWarnings: 0,
    lastUpdate: "2025-12-31",
  };

  // 1 year monthly data
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const emissionsByMonth = [6200, 6100, 6000, 5920, 5860, 5780, 5700, 5620, 5550, 5450, 5400, 5340];
  const emissionsTargetArray = Array(12).fill(summary.emissionsTarget);

  const emissionsTrend = {
    labels: months,
    datasets: [
      {
        label: "CO₂ Emissions (t)",
        data: emissionsByMonth,
        borderColor: "#1976d2",
        backgroundColor: "rgba(25,118,210,0.09)",
        tension: 0.4,
        pointRadius: 3,
        fill: true
      },
      {
        label: "Target",
        data: emissionsTargetArray,
        borderColor: "#43a047",
        borderDash: [8, 4],
        pointRadius: 0,
        fill: false,
        borderWidth: 2
      }
    ],
  };

  const waterTrend = {
    labels: months,
    datasets: [
      {
        label: "Water (m³)",
        data: [9400, 9200, 9100, 8900, 8700, 8600, 8500, 8400, 8300, 8200, 8100, 8000],
        backgroundColor: "#43a047",
        borderRadius: 6,
        maxBarThickness: 24,
      },
    ],
  };

  const energyTrend = {
    labels: months,
    datasets: [
      {
        label: "Energy (kWh)",
        data: [187000, 185000, 184000, 183000, 182000, 180000, 179000, 178000, 177000, 175000, 172000, 170000],
        borderColor: "#fbc02d",
        backgroundColor: "rgba(251,192,45,0.12)",
        tension: 0.4,
        pointRadius: 3,
        fill: true,
      },
      {
        label: "Goal",
        data: Array(12).fill(summary.energyGoal),
        borderColor: "#43a047",
        borderDash: [8, 4],
        pointRadius: 0,
        fill: false,
        borderWidth: 2
      }
    ],
  };

  const energyMix = {
    labels: ["Grid", "Solar", "Backup Diesel"],
    datasets: [
      {
        data: [77, 20, 3],
        backgroundColor: ["#1976d2", "#fbc02d", "#8e24aa"],
        borderWidth: 2,
      },
    ],
  };

  const scopePie = {
    labels: ["Scope 1", "Scope 2", "Scope 3"],
    datasets: [
      {
        data: [15, 50, 35],
        backgroundColor: ["#43a047", "#1e88e5", "#ff7043"],
        borderWidth: 2,
      },
    ],
  };

  const completenessTrend = {
    labels: months,
    datasets: [
      {
        label: "Data Completeness (%)",
        data: [83, 89, 93, 92, 94, 96, 98, 99, 98, 97, 97, 97],
        borderColor: "#8e24aa",
        backgroundColor: "rgba(142,36,170,0.07)",
        tension: 0.3,
        fill: true,
        pointRadius: 3,
      },
    ],
  };

  const campuses = [
    { name: "Abu Qir", emissions: 2110, happiness: 92 },
    { name: "Alexandria", emissions: 1190, happiness: 89 },
    { name: "Smart Village", emissions: 940, happiness: 95 },
    { name: "Cairo", emissions: 610, happiness: 90 },
    { name: "Port Said", emissions: 490, happiness: 93 },
  ];

  const cardStyle = { borderRadius: 4, boxShadow: 4 };

  return (
    <Box sx={{ maxWidth: 1350, mx: "auto", mt: 4, mb: 10, px: { xs: 1, sm: 3 } }}>
      {/* Executive Banner */}
      <Paper elevation={0} sx={{
        mb: 5,
        p: { xs: 2, md: 4 },
        borderRadius: 4,
        bgcolor: "#e3f2fd",
        border: "1px solid #bbdefb",
        display: "flex",
        flexDirection: { xs: "column", md: "row" },
        alignItems: { md: "center" },
        gap: 3
      }}>
        <Avatar sx={{ bgcolor: "#1976d2", width: 64, height: 64, mr: 3 }}>
          <EmojiEventsIcon sx={{ fontSize: 40 }} />
        </Avatar>
        <Box>
          <Typography variant="h4" fontWeight={900} color="primary.dark" letterSpacing={-1}>
            AASTMT Sustainability Dashboard <span style={{ color: "#43a047" }}>2025</span>
          </Typography>
          <Typography color="text.secondary" fontSize={18} fontWeight={500}>
            <b>For Demo Purposes &amp; Work In Progress</b>
          </Typography>
          <Typography color="text.secondary" fontSize={15} mt={1}>
            All metrics and visualizations below use <u>imaginary</u> data for demonstration purposes only.
          </Typography>
        </Box>
        <Chip label="Demo / WIP" color="warning" variant="filled" sx={{ height: 36, fontWeight: 700, ml: "auto" }} />
      </Paper>

      {/* KPI and Progress Cards */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card sx={cardStyle}>
            <CardContent>
              <Stack direction="row" alignItems="center" spacing={2} mb={2}>
                <Avatar sx={{ bgcolor: "#1976d2" }}><EmojiNatureIcon /></Avatar>
                <Box flexGrow={1}>
                  <Typography color="text.secondary" fontWeight={500}>CO₂ Emissions</Typography>
                  <Stack direction="row" alignItems="baseline" spacing={1}>
                    <Typography variant="h6" fontWeight={900}>{summary.emissions.toLocaleString()} t</Typography>
                    <Typography color="success.main" fontSize={16} fontWeight={700}>Target: {summary.emissionsTarget.toLocaleString()} t</Typography>
                  </Stack>
                  <Box mt={1}>
                    <LinearProgress
                      variant="determinate"
                      value={Math.min(100, ((summary.emissionsStart - summary.emissions) / (summary.emissionsStart - summary.emissionsTarget)) * 100)}
                      sx={{ height: 12, borderRadius: 6, bgcolor: "#d7ffd9", "& .MuiLinearProgress-bar": { bgcolor: "#43a047" } }}
                    />
                  </Box>
                </Box>
                <Chip label={`${summary.emissionsChange}% ↓`}
                  color="success"
                  size="small"
                  icon={<TrendingDownIcon />}
                  sx={{ fontWeight: 700 }}
                />
              </Stack>
              <Typography color="success.main" fontWeight={700} fontSize={14}>
                Significant progress! Emissions reduced by 13% this year.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card sx={cardStyle}>
            <CardContent>
              <Stack direction="row" alignItems="center" spacing={2} mb={2}>
                <Avatar sx={{ bgcolor: "#fbc02d" }}><BoltIcon /></Avatar>
                <Box flexGrow={1}>
                  <Typography color="text.secondary" fontWeight={500}>Energy Consumption</Typography>
                  <Stack direction="row" alignItems="baseline" spacing={1}>
                    <Typography variant="h6" fontWeight={900}>{summary.energy.toLocaleString()} kWh</Typography>
                    <Typography color="success.main" fontSize={16} fontWeight={700}>Goal: {summary.energyGoal.toLocaleString()} kWh</Typography>
                  </Stack>
                  <Box mt={1}>
                    <LinearProgress
                      variant="determinate"
                      value={Math.min(100, ((187000 - summary.energy) / (187000 - summary.energyGoal)) * 100)}
                      sx={{ height: 12, borderRadius: 6, bgcolor: "#fff9c4", "& .MuiLinearProgress-bar": { bgcolor: "#fbc02d" } }}
                    />
                  </Box>
                </Box>
                <Chip label={`${summary.energyChange}% ↓`}
                  color="success"
                  size="small"
                  icon={<TrendingDownIcon />}
                  sx={{ fontWeight: 700 }}
                />
              </Stack>
              <Typography color="success.main" fontWeight={700} fontSize={14}>
                Energy reduction on track, approaching yearly goal.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Trends and Mix */}
      <Grid container spacing={3} sx={{ mt: 1 }}>
        <Grid item xs={12} md={7}>
          <Card sx={{ ...cardStyle, minHeight: 325 }}>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>
                CO₂ Emissions Trend (Jan–Dec 2025)
              </Typography>
              <Box sx={{ height: 220 }}>
                <Line data={emissionsTrend} options={{
                  plugins: {
                    legend: { display: true, labels: { font: { size: 13 } } },
                  },
                  scales: { y: { beginAtZero: false } },
                  responsive: true,
                  maintainAspectRatio: false,
                }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={5}>
          <Card sx={{ ...cardStyle, minHeight: 325 }}>
            <CardContent>
              <Typography fontWeight={700} mb={1}>Energy Mix</Typography>
              <Box sx={{ height: 160, mb: 2 }}>
                <Doughnut data={energyMix} options={{
                  plugins: { legend: { position: "bottom" } },
                  cutout: "70%",
                  responsive: true,
                  maintainAspectRatio: false
                }} />
              </Box>
              <Typography color="success.main" fontWeight={700} fontSize={15}>
                Solar share up 5% vs previous year.
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={7}>
          <Card sx={{ ...cardStyle, minHeight: 220 }}>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>
                Water Usage Trend (Jan–Dec 2025)
              </Typography>
              <Box sx={{ height: 140 }}>
                <Bar data={waterTrend} options={{
                  plugins: { legend: { display: false } },
                  scales: { y: { beginAtZero: true } },
                  responsive: true,
                  maintainAspectRatio: false
                }} />
              </Box>
              <Typography color="success.main" fontWeight={700} fontSize={14} mt={1}>
                Water usage steadily declining; conservation programs effective.
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={5}>
          <Card sx={cardStyle}>
            <CardContent>
              <Typography fontWeight={700} mb={1}>Scope Breakdown</Typography>
              <Box sx={{ height: 120 }}>
                <Pie data={scopePie} options={{
                  plugins: { legend: { position: "bottom" } },
                  responsive: true,
                  maintainAspectRatio: false
                }} />
              </Box>
              <Typography color="text.secondary" fontSize={13}>Scopes 1/2/3</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Data Quality, Happiness, Emissions By Campus */}
      <Grid container spacing={3} sx={{ mt: 1 }}>
        <Grid item xs={12} md={4}>
          <Card sx={{ ...cardStyle, textAlign: "center", minHeight: 220 }}>
            <CardContent>
              <Typography fontWeight={700} mb={1}>Data Completeness</Typography>
              <Gauge value={summary.dataCompleteness} label="%" color="#8e24aa" />
              <Typography color="success.main" fontWeight={700} fontSize={14} mt={1}>
                Data quality exceptional.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card sx={{ ...cardStyle, textAlign: "center", minHeight: 220 }}>
            <CardContent>
              <Typography fontWeight={700} mb={1}>Audit Status</Typography>
              <Avatar sx={{ bgcolor: "#43a047", mx: "auto", width: 56, height: 56 }}>
                <EmojiEmotionsIcon sx={{ fontSize: 36 }} />
              </Avatar>
              <Typography variant="h4" fontWeight={900} color="#43a047" mt={1}>
                {summary.auditWarnings}
              </Typography>
              <Typography color="success.main" fontWeight={700} fontSize={14} mt={1}>
                No warnings; audit-ready.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card sx={{ ...cardStyle, textAlign: "center", minHeight: 220 }}>
            <CardContent>
              <Typography fontWeight={700} mb={1}>Campus Happiness</Typography>
              <Box display="flex" justifyContent="center" gap={2} mb={2}>
                {campuses.map(c => (
                  <Stack key={c.name} alignItems="center" spacing={0.5}>
                    <Avatar sx={{ bgcolor: "#1976d2", mb: 0.5, width: 32, height: 32 }}>{c.name[0]}</Avatar>
                    <Typography fontSize={12}>{c.name}</Typography>
                    <Tooltip title={`Happiness Score: ${c.happiness}%`}>
                      <EmojiEmotionsIcon sx={{ color: "#43a047", fontSize: 22, mb: -0.5 }} />
                    </Tooltip>
                    <Typography color="success.main" fontWeight={800} fontSize={16}>{c.happiness}%</Typography>
                  </Stack>
                ))}
              </Box>
              <Typography color="success.main" fontWeight={700} fontSize={14}>
                High engagement across all campuses.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Data Completeness Trend & Emissions by Campus */}
      <Grid container spacing={3} sx={{ mt: 1 }}>
        <Grid item xs={12} md={6}>
          <Card sx={cardStyle}>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>Data Completeness Trend</Typography>
              <Box sx={{ height: 120 }}>
                <Line data={completenessTrend} options={{
                  plugins: { legend: { display: false } },
                  scales: { y: { beginAtZero: true, max: 100 } },
                  responsive: true,
                  maintainAspectRatio: false
                }} />
              </Box>
              <Typography color="success.main" fontWeight={700} fontSize={14} mt={1}>
                Consistent improvement all year.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card sx={cardStyle}>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={700} mb={2}>
                Emissions by Campus (t CO₂)
              </Typography>
              <Box sx={{ height: 120 }}>
                <Bar data={{
                  labels: campuses.map(c => c.name),
                  datasets: [{
                    label: "Emissions (t CO₂)",
                    data: campuses.map(c => c.emissions),
                    backgroundColor: [
                      "#1976d2", "#43a047", "#fbc02d", "#8e24aa", "#ff7043"
                    ],
                    borderRadius: 8,
                  }]
                }} options={{
                  plugins: { legend: { display: false } },
                  scales: { y: { beginAtZero: true } },
                  responsive: true,
                  maintainAspectRatio: false
                }} />
              </Box>
              <Typography color="success.main" fontWeight={700} fontSize={14} mt={1}>
                All campuses contributed to progress.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Divider sx={{ my: 6 }} />

      {/* Footer / Meta Info */}
      <Stack direction={{ xs: "column", md: "row" }} alignItems="center" justifyContent="space-between" spacing={2} mt={5}>
        <Typography color="text.secondary" fontSize={16}>
          <b>Disclaimer:</b> This dashboard is for **demonstration** and **work-in-progress review** only.<br />
          All metrics and trends shown here are based on <u>imaginary</u> data for AASTMT.
        </Typography>
        <Stack direction="row" alignItems="center" spacing={2}>
          <Chip label={`Last update: ${summary.lastUpdate}`} color="default" variant="outlined" />
          <Chip label="© 2025 AASTMT Sustainability Demo" color="primary" variant="outlined" />
        </Stack>
      </Stack>
    </Box>
  );
}