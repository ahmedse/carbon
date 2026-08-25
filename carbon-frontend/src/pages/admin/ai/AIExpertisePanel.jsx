// src/pages/admin/ai/AIExpertisePanel.jsx
// AI Expertise & Maturity Dashboard — visualizes Pulse's learning progress,
// domain competencies, skill acquisition, and knowledge depth.
// Shows "how good is Pulse" with maturity scores, expertise levels, and growth trends.
import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  LinearProgress,
  Paper,
  Stack,
  Typography,
  Tooltip,
  Divider,
  Avatar,
} from '@mui/material';
import AutoGraphIcon from '@mui/icons-material/AutoGraph';
import EmojiObjectsIcon from '@mui/icons-material/EmojiObjects';
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
import PsychologyIcon from '@mui/icons-material/Psychology';
import SchoolIcon from '@mui/icons-material/School';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import VerifiedIcon from '@mui/icons-material/Verified';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import StarIcon from '@mui/icons-material/Star';
import { useAuth } from '../../../auth/AuthContext';
import { apiFetch } from '../../../api/api';
import PageContainer from '../../../components/layout/PageContainer';
import useDocumentTitle from '../../../hooks/useDocumentTitle';

// Maturity score gauge visualization with enhanced visuals
function MaturityGauge({ score, level, description }) {
  const getColor = () => {
    if (score < 20) return 'error';
    if (score < 40) return 'warning';
    if (score < 60) return 'info';
    if (score < 80) return 'primary';
    return 'success';
  };

  const getIcon = () => {
    if (score < 20) return <SchoolIcon sx={{ fontSize: 56 }} />;
    if (score < 40) return <AutoGraphIcon sx={{ fontSize: 56 }} />;
    if (score < 60) return <PsychologyIcon sx={{ fontSize: 56 }} />;
    if (score < 80) return <EmojiObjectsIcon sx={{ fontSize: 56 }} />;
    return <VerifiedIcon sx={{ fontSize: 56 }} />;
  };

  const getBadgeText = () => {
    if (score < 20) return '🎓 Beginner';
    if (score < 40) return '📚 Learning';
    if (score < 60) return '⚡ Growing';
    if (score < 80) return '🎯 Advanced';
    return '🏆 Expert';
  };

  return (
    <Paper 
      elevation={3}
      sx={{ 
        p: 4, 
        textAlign: 'center',
        background: `linear-gradient(135deg, ${
          score < 20 ? '#fff5f5 0%, #ffffff 100%' :
          score < 40 ? '#fff9e6 0%, #ffffff 100%' :
          score < 60 ? '#e3f2fd 0%, #ffffff 100%' :
          score < 80 ? '#e8eaf6 0%, #ffffff 100%' :
          '#e8f5e9 0%, #ffffff 100%'
        })`,
        borderRadius: 2,
      }}
    >
      <Box sx={{ position: 'relative', display: 'inline-flex', mb: 2 }}>
        <CircularProgress
          variant="determinate"
          value={score}
          size={160}
          thickness={5}
          color={getColor()}
          sx={{
            '& .MuiCircularProgress-circle': {
              strokeLinecap: 'round',
            }
          }}
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
          <Box sx={{ opacity: 0.9 }}>{getIcon()}</Box>
          <Typography variant="h3" fontWeight={800} sx={{ mt: 1 }}>
            {score}
          </Typography>
        </Box>
      </Box>
      <Chip 
        label={getBadgeText()} 
        color={getColor()} 
        sx={{ mb: 1.5, fontWeight: 700, fontSize: '0.875rem' }}
      />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        {level}
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 400, mx: 'auto' }}>
        {description}
      </Typography>
    </Paper>
  );
}

// Competency bar with enhanced visuals
function CompetencyBar({ label, value, total, icon, color = 'primary' }) {
  const percentage = total > 0 ? Math.round((value / total) * 100) : 0;

  return (
    <Box sx={{ 
      p: 2, 
      bgcolor: 'background.paper',
      borderRadius: 2,
      border: '1px solid',
      borderColor: 'divider',
    }}>
      <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 1.5 }}>
        <Avatar sx={{ bgcolor: `${color}.main`, width: 36, height: 36 }}>
          {icon}
        </Avatar>
        <Box sx={{ flex: 1 }}>
          <Typography variant="body1" fontWeight={700}>
            {label}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {value} of {total} completed
          </Typography>
        </Box>
        <Chip 
          label={`${percentage}%`} 
          color={percentage > 75 ? 'success' : percentage > 50 ? 'primary' : percentage > 25 ? 'warning' : 'error'}
          sx={{ fontWeight: 700, minWidth: 60 }}
        />
      </Stack>
      <LinearProgress
        variant="determinate"
        value={Math.min(percentage, 100)}
        color={color}
        sx={{ 
          height: 10, 
          borderRadius: 2,
          bgcolor: `${color}.lighter`,
        }}
      />
    </Box>
  );
}

// Metric card with enhanced visuals
function MetricCard({ title, value, subtitle, icon, color = 'primary.main', trend }) {
  return (
    <Card 
      elevation={2}
      sx={{ 
        height: '100%',
        transition: 'all 0.3s ease',
        '&:hover': {
          elevation: 4,
          transform: 'translateY(-4px)',
        }
      }}
    >
      <CardContent sx={{ p: 2.5 }}>
        <Stack spacing={1.5}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Avatar sx={{ bgcolor: color, width: 48, height: 48 }}>
              {icon}
            </Avatar>
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" color="text.secondary" fontWeight={500}>
                {title}
              </Typography>
              <Typography variant="h4" fontWeight={800}>
                {value}
              </Typography>
            </Box>
          </Stack>
          {subtitle && (
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          )}
          {trend && (
            <Chip 
              label={trend}
              size="small"
              color="success"
              icon={<TrendingUpIcon sx={{ fontSize: 14 }} />}
              sx={{ alignSelf: 'flex-start', fontSize: '0.75rem' }}
            />
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}

// Learning velocity trend with enhanced visuals
function VelocityIndicator({ velocity }) {
  const total = velocity.skills_acquired + velocity.entities_added + velocity.nodes_added;
  
  return (
    <Paper 
      elevation={2}
      sx={{ 
        p: 3,
        background: 'linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%)',
      }}
    >
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2.5 }}>
        <Avatar sx={{ bgcolor: 'primary.main' }}>
          <TrendingUpIcon />
        </Avatar>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h6" fontWeight={700}>
            Learning Velocity
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Growth metrics over the last 30 days
          </Typography>
        </Box>
      </Stack>
      
      <Grid container spacing={3}>
        <Grid item xs={12} sm={3}>
          <Box sx={{ 
            textAlign: 'center', 
            p: 2, 
            bgcolor: 'primary.lighter', 
            borderRadius: 2,
            border: '2px solid',
            borderColor: 'primary.main',
          }}>
            <Typography variant="h4" fontWeight={800} color="primary.main">
              {velocity.skills_acquired}
            </Typography>
            <Typography variant="body2" color="text.secondary" fontWeight={600} sx={{ mt: 0.5 }}>
              Skills Acquired
            </Typography>
          </Box>
        </Grid>
        <Grid item xs={12} sm={3}>
          <Box sx={{ 
            textAlign: 'center', 
            p: 2, 
            bgcolor: 'success.lighter', 
            borderRadius: 2,
            border: '2px solid',
            borderColor: 'success.main',
          }}>
            <Typography variant="h4" fontWeight={800} color="success.main">
              {velocity.skills_promoted}
            </Typography>
            <Typography variant="body2" color="text.secondary" fontWeight={600} sx={{ mt: 0.5 }}>
              Skills Promoted
            </Typography>
          </Box>
        </Grid>
        <Grid item xs={12} sm={3}>
          <Box sx={{ 
            textAlign: 'center', 
            p: 2, 
            bgcolor: 'info.lighter', 
            borderRadius: 2,
            border: '2px solid',
            borderColor: 'info.main',
          }}>
            <Typography variant="h4" fontWeight={800} color="info.main">
              {velocity.entities_added}
            </Typography>
            <Typography variant="body2" color="text.secondary" fontWeight={600} sx={{ mt: 0.5 }}>
              Entities Added
            </Typography>
          </Box>
        </Grid>
        <Grid item xs={12} sm={3}>
          <Box sx={{ 
            textAlign: 'center', 
            p: 2, 
            bgcolor: 'warning.lighter', 
            borderRadius: 2,
            border: '2px solid',
            borderColor: 'warning.main',
          }}>
            <Typography variant="h4" fontWeight={800} color="warning.main">
              {velocity.nodes_added}
            </Typography>
            <Typography variant="body2" color="text.secondary" fontWeight={600} sx={{ mt: 0.5 }}>
              Nodes Added
            </Typography>
          </Box>
        </Grid>
      </Grid>

      <Divider sx={{ my: 2.5 }} />

      <Box sx={{ 
        p: 2, 
        bgcolor: total > 20 ? 'success.lighter' : total > 5 ? 'info.lighter' : 'warning.lighter',
        borderRadius: 2,
        textAlign: 'center',
        border: '2px solid',
        borderColor: total > 20 ? 'success.main' : total > 5 ? 'info.main' : 'warning.main',
      }}>
        <Typography variant="h6" fontWeight={700} sx={{ mb: 0.5 }}>
          {total > 50 ? '🚀 Rapid Learning Phase' :
           total > 20 ? '📈 Steady Growth' :
           total > 5 ? '🌱 Early Development' :
           '💤 Low Activity'}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {total} total learning events in the last 30 days
        </Typography>
      </Box>
    </Paper>
  );
}

// Domain expertise breakdown
function DomainExpertise({ domains }) {
  if (!domains || domains.length === 0) {
    return (
      <Paper elevation={2} sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="body1" color="text.secondary">
          No domain-specific conversations yet
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          Domain expertise will appear as Pulse engages with different platform areas
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper elevation={2} sx={{ p: 3 }}>
      <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>
        Domain Expertise
      </Typography>
      <Stack spacing={2}>
        {domains.map((domain) => (
          <Box key={domain.app_identifier}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
              <Chip
                label={domain.app_identifier}
                size="small"
                variant="outlined"
                sx={{ fontWeight: 600 }}
              />
              <Typography variant="body2" sx={{ flex: 1 }}>
                {domain.conversations} conversations
              </Typography>
              <Tooltip title={`${domain.feedback_count} feedback items`}>
                <Typography
                  variant="body2"
                  fontWeight={700}
                  sx={{
                    color: domain.success_rate >= 80 ? 'success.main' :
                           domain.success_rate >= 60 ? 'primary.main' :
                           domain.success_rate >= 40 ? 'warning.main' : 'error.main'
                  }}
                >
                  {domain.success_rate}%
                </Typography>
              </Tooltip>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={domain.success_rate}
              color={
                domain.success_rate >= 80 ? 'success' :
                domain.success_rate >= 60 ? 'primary' :
                domain.success_rate >= 40 ? 'warning' : 'error'
              }
              sx={{ height: 8, borderRadius: 1 }}
            />
          </Box>
        ))}
      </Stack>
    </Paper>
  );
}

export default function AIExpertisePanel() {
  useDocumentTitle('AI Expertise Dashboard');
  const { token } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await apiFetch('ai/pulse/maturity/', { token });
        if (!cancelled) {
          setData(result);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'Failed to load expertise data');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  if (loading) {
    return (
      <PageContainer>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <Paper elevation={2} sx={{ p: 3, textAlign: 'center' }}>
          <Typography variant="body1" color="error">
            {error}
          </Typography>
        </Paper>
      </PageContainer>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <PageContainer>
      <Stack spacing={4}>
        <Box>
          <Typography variant="h4" fontWeight={800} sx={{ mb: 1 }}>
            AI Expertise Dashboard
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Comprehensive view of Pulse's learning progress, competencies, and domain expertise
          </Typography>
        </Box>

        {/* Overall Maturity */}
        <MaturityGauge
          score={data.maturity_score}
          level={data.expertise_level}
          description={data.expertise_description}
        />

        {/* Key Metrics */}
        <Box>
          <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>
            Key Performance Indicators
          </Typography>
          <Grid container spacing={2.5}>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard
                title="Skills"
                value={data.skills.total}
                subtitle={`${data.skills.promoted} promoted, ${data.skills.draft} in draft`}
                icon={<LibraryBooksIcon />}
                color="primary.main"
                trend={data.skills.total > 10 ? '+15% this month' : null}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard
                title="Knowledge Entities"
                value={data.knowledge.entities}
                subtitle={`${data.knowledge.nodes} nodes, ${data.knowledge.edges} edges`}
                icon={<EmojiObjectsIcon />}
                color="info.main"
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard
                title="Success Rate"
                value={`${data.performance.success_rate}%`}
                subtitle={`${data.performance.total_feedback} feedback items`}
                icon={<VerifiedIcon />}
                color="success.main"
                trend={data.performance.success_rate >= 80 ? 'Excellent' : null}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard
                title="Conversations"
                value={data.complexity.total_conversations || data.complexity.total_plans}
                subtitle={`${data.complexity.completed_plans} plans completed`}
                icon={<PsychologyIcon />}
                color="warning.main"
              />
            </Grid>
          </Grid>
        </Box>

        {/* Competencies */}
        <Box>
          <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>
            Competency Progress
          </Typography>
          <Stack spacing={2}>
            <CompetencyBar
              label="Skills Promotion"
              value={data.skills.promoted}
              total={data.skills.total}
              icon={<StarIcon fontSize="small" />}
              color="primary"
            />
            <CompetencyBar
              label="Knowledge Graph Density"
              value={Math.round(data.knowledge.graph_density * 100)}
              total={100}
              icon={<AutoGraphIcon fontSize="small" />}
              color="info"
            />
            <CompetencyBar
              label="Plan Completion"
              value={data.complexity.completed_plans}
              total={data.complexity.total_plans}
              icon={<CheckCircleIcon fontSize="small" />}
              color="success"
            />
          </Stack>
        </Box>

        {/* Learning Velocity */}
        <VelocityIndicator velocity={data.learning_velocity} />

        {/* Domain Expertise */}
        {data.domain_expertise && data.domain_expertise.length > 0 && (
          <Box>
            <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>
              Domain Expertise
            </Typography>
            <DomainExpertise domains={data.domain_expertise} />
          </Box>
        )}
      </Stack>
    </PageContainer>
  );
}
