// File: src/components/dq/DQMetricsPanel.jsx
import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Box,
  CircularProgress,
  Alert,
  Grid,
  Typography,
  Chip,
  LinearProgress,
} from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import { getOrgDQMetrics } from '../../api/dq';

function getQualityColor(score) {
  if (score >= 90) return '#4caf50'; // Green
  if (score >= 70) return '#ff9800'; // Orange
  return '#f44336'; // Red
}

function getQualityLabel(score) {
  if (score >= 90) return 'Excellent';
  if (score >= 70) return 'Good';
  return 'Needs Attention';
}

export default function DQMetricsPanel({ token }) {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (token) {
      fetchMetrics();
    }
  }, [token]);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getOrgDQMetrics(token);
      setMetrics(data);
    } catch (err) {
      setError(`Failed to load metrics: ${err.message}`);
      console.error('DQ Metrics Panel error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader title="Data Quality Overview" />
        <CardContent sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader title="Data Quality Overview" />
        <CardContent>
          <Alert severity="warning">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  if (!metrics) {
    return (
      <Card>
        <CardHeader title="Data Quality Overview" />
        <CardContent>
          <Typography color="text.secondary">No data quality metrics available</Typography>
        </CardContent>
      </Card>
    );
  }

  const overallScore = metrics.overall_score || 0;
  const qualityColor = getQualityColor(overallScore);
  const qualityLabel = getQualityLabel(overallScore);

  return (
    <Card sx={{ height: '100%' }}>
      <CardHeader
        title="Data Quality Overview"
        subheader={`Organization-level metrics`}
        avatar={<TrendingUpIcon sx={{ color: qualityColor }} />}
      />
      <CardContent>
        <Grid container spacing={2}>
          {/* Overall Score */}
          <Grid item xs={12} sm={6}>
            <Box sx={{ textAlign: 'center', mb: 2 }}>
              <Box
                sx={{
                  position: 'relative',
                  width: 120,
                  height: 120,
                  margin: '0 auto',
                  mb: 1,
                }}
              >
                <CircularProgress
                  variant="determinate"
                  value={overallScore}
                  size={120}
                  sx={{ color: qualityColor }}
                />
                <Box
                  sx={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    bottom: 0,
                    right: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexDirection: 'column',
                  }}
                >
                  <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
                    {overallScore.toFixed(1)}%
                  </Typography>
                  <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>
                    Overall
                  </Typography>
                </Box>
              </Box>
              <Chip
                label={qualityLabel}
                size="small"
                sx={{
                  backgroundColor: qualityColor,
                  color: 'white',
                  fontWeight: 'bold',
                }}
              />
            </Box>
          </Grid>

          {/* Key Metrics */}
          <Grid item xs={12} sm={6}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              {/* Completeness */}
              <Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    Completeness
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#4caf50', fontWeight: 'bold' }}>
                    {(metrics.completeness_score || 0).toFixed(1)}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={metrics.completeness_score || 0}
                  sx={{ backgroundColor: '#e0e0e0', '& .MuiLinearProgress-bar': { backgroundColor: '#4caf50' } }}
                />
              </Box>

              {/* Uniqueness */}
              <Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    Uniqueness
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#2196f3', fontWeight: 'bold' }}>
                    {(metrics.uniqueness_score || 0).toFixed(1)}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={metrics.uniqueness_score || 0}
                  sx={{ backgroundColor: '#e0e0e0', '& .MuiLinearProgress-bar': { backgroundColor: '#2196f3' } }}
                />
              </Box>

              {/* Compliance */}
              <Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    Compliance
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#ff9800', fontWeight: 'bold' }}>
                    {(metrics.compliance_score || 0).toFixed(1)}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={metrics.compliance_score || 0}
                  sx={{ backgroundColor: '#e0e0e0', '& .MuiLinearProgress-bar': { backgroundColor: '#ff9800' } }}
                />
              </Box>
            </Box>
          </Grid>

          {/* Statistics */}
          <Grid item xs={12}>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 1, mt: 1 }}>
              <Box sx={{ textAlign: 'center', p: 1, backgroundColor: '#f5f5f5', borderRadius: 1 }}>
                <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
                  Tables Monitored
                </Typography>
                <Typography variant="h6">{metrics.table_count || 0}</Typography>
              </Box>
              <Box sx={{ textAlign: 'center', p: 1, backgroundColor: '#f5f5f5', borderRadius: 1 }}>
                <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
                  Rules Active
                </Typography>
                <Typography variant="h6">{metrics.rule_count || 0}</Typography>
              </Box>
              <Box sx={{ textAlign: 'center', p: 1, backgroundColor: '#f5f5f5', borderRadius: 1 }}>
                <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
                  Last Checked
                </Typography>
                <Typography variant="caption">
                  {metrics.last_run ? new Date(metrics.last_run).toLocaleDateString() : 'Never'}
                </Typography>
              </Box>
            </Box>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
}
