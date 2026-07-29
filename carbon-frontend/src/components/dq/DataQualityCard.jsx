// carbon-frontend/src/components/dq/DataQualityCard.jsx
import React, { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  CircularProgress,
  Alert,
  LinearProgress,
  Button,
  Grid,
  Chip,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  BarChart as BarChartIcon,
} from '@mui/icons-material';
import { useAuth } from '../../auth/AuthContext';
import { getOrgDQMetrics } from '../../api/dq';

/**
 * DataQualityCard
 * Displays org-level DQ metrics summary
 * Embedded in ModuleLandingPage
 */
function getQualityColor(percentage) {
  if (percentage >= 90) return 'success.main';
  if (percentage >= 70) return 'warning.main';
  return 'error.main';
}

function getQualityIcon(percentage) {
  if (percentage >= 90) return <CheckCircleIcon sx={{ color: 'success.main' }} />;
  if (percentage >= 70) return <WarningIcon sx={{ color: 'warning.main' }} />;
  return <ErrorIcon sx={{ color: 'error.main' }} />;
}

function getQualityLabel(percentage) {
  if (percentage >= 90) return 'Excellent';
  if (percentage >= 70) return 'Good';
  if (percentage >= 50) return 'Fair';
  return 'Poor';
}

function MetricRow({ label, value, color }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1.5 }}>
      <Typography variant="body2" sx={{ minWidth: 100 }}>
        {label}
      </Typography>
      <Box sx={{ flex: 1 }}>
        <LinearProgress
          variant="determinate"
          value={Math.min(value, 100)}
          sx={{
            height: 8,
            borderRadius: 4,
            backgroundColor: 'action.disabledBackground',
            '& .MuiLinearProgress-bar': {
              backgroundColor: color,
              borderRadius: 4,
            },
          }}
        />
      </Box>
      <Typography variant="body2" sx={{ minWidth: 50, textAlign: 'right', fontWeight: 600 }}>
        {value.toFixed(1)}%
      </Typography>
    </Box>
  );
}

export default function DataQualityCard({ onOpenMetrics }) {
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    if (!token) return;

    const fetchMetrics = async () => {
      try {
        setLoading(true);
        const response = await getOrgDQMetrics(token);
        setMetrics(response);
        setError(null);
      } catch (err) {
        console.error('Error fetching DQ metrics:', err);
        setError(err.message);
        setMetrics(null);
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
  }, [token]);

  if (loading) {
    return (
      <Card sx={{ mb: 2 }}>
        <CardHeader title="Data Quality Overview" />
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
            <CircularProgress size={40} />
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card sx={{ mb: 2 }}>
        <CardHeader title="Data Quality Overview" />
        <CardContent>
          <Alert severity="warning">
            Unable to load DQ metrics. Please try again.
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!metrics) {
    return null;
  }

  const avgQuality = (metrics.completeness_pct + metrics.uniqueness_pct + metrics.compliance_pct) / 3;
  const qualityColor = getQualityColor(avgQuality);

  return (
    <Card sx={{ mb: 2, borderLeft: `4px solid ${qualityColor}` }}>
      <CardHeader
        title="Data Quality Overview"
        subheader={`${metrics.table_count} tables, ${metrics.total_rows} total rows`}
        avatar={getQualityIcon(avgQuality)}
        action={
          <Button
            size="small"
            startIcon={<BarChartIcon />}
            onClick={onOpenMetrics}
            variant="outlined"
          >
            Details
          </Button>
        }
      />
      <CardContent>
        <Box sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Typography variant="h6">Overall Quality Score</Typography>
            <Chip
              label={getQualityLabel(avgQuality)}
              size="small"
              sx={{
                backgroundColor: qualityColor,
                color: 'white',
                fontWeight: 600,
              }}
            />
          </Box>
          <Box sx={{ position: 'relative', display: 'inline-block', width: 120 }}>
            <CircularProgress
              variant="determinate"
              value={Math.min(avgQuality, 100)}
              size={100}
              thickness={4}
              sx={{
                color: qualityColor,
              }}
            />
            <Box
              sx={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                {avgQuality.toFixed(0)}%
              </Typography>
            </Box>
          </Box>
        </Box>

        <Box sx={{ mt: 3 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 2 }}>
            Key Metrics
          </Typography>
          <MetricRow
            label="Completeness"
            value={metrics.completeness_pct}
            color="success.main"
          />
          <MetricRow
            label="Uniqueness"
            value={metrics.uniqueness_pct}
            color="info.main"
          />
          <MetricRow
            label="Compliance"
            value={metrics.compliance_pct}
            color="secondary.main"
          />
        </Box>
      </CardContent>
    </Card>
  );
}
