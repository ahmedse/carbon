// src/pages/admin/ai/SkillLearningPanel.jsx
// Route /admin/ai/skill-learning — the "Skill Learning" progression view
// (Pulse 0.2 #3 — "Real Learning"). Backed by GET /ai/pulse/skills/
// (getPulseSkills). Renders the drafted → promoted → reused arc as a LEGIBLE
// three-stage flow (NOT a raw table). All counts derive from the API array.
// RULE_8 tokens only; RULE_10 apiFetch only (via src/api/aiPulse.js); RULE_16
// grounded states: loading spinner, offline paper, honest empty/zero-reused.
import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Typography,
  useTheme,
} from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import { useAuth } from '../../../auth/AuthContext';
import { getPulseSkills } from '../../../api/aiPulse';

/** Format an integer counter defensively. */
function formatInt(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString();
}

/** Format an ISO timestamp defensively. */
function formatDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

/** "85%" style formatting for success_rate (0..1). */
function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${Math.round(value * 100)}%`;
}

export default function SkillLearningPanel() {
  useDocumentTitle('Skill Learning');
  const theme = useTheme();
  const { token } = useAuth();

  const [skills, setSkills] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const payload = await getPulseSkills(token);
        if (!cancelled) {
          setSkills(Array.isArray(payload) ? payload : []);
          setOffline(false);
        }
      } catch {
        if (!cancelled) {
          setSkills([]);
          setOffline(true);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  // Stage mapping (all derived from the API array — never UI-invented):
  //   Drafted = draft | user_approved (drafted but not yet promoted)
  //   Promoted = instance_promoted
  //   Reused  = usage_count > 0 (a promoted skill that ran on the hot path)
  const { draftedCount, promotedCount, reusedCount, reusedSkills } = useMemo(() => {
    const list = skills ?? [];
    const drafted = list.filter((s) => s.status === 'draft' || s.status === 'user_approved');
    const promoted = list.filter((s) => s.status === 'instance_promoted');
    const reused = list
      .filter((s) => Number(s.usage_count) > 0)
      .slice()
      .sort((a, b) => Number(b.usage_count) - Number(a.usage_count));
    return {
      draftedCount: drafted.length,
      promotedCount: promoted.length,
      reusedCount: reused.length,
      reusedSkills: reused,
    };
  }, [skills]);

  const stages = useMemo(
    () => [
      { key: 'drafted', label: 'Drafted', caption: 'Drafted but not yet promoted', count: draftedCount },
      { key: 'promoted', label: 'Promoted', caption: 'Promoted to instance', count: promotedCount },
      { key: 'reused', label: 'Reused', caption: 'Invoked on the hot path', count: reusedCount },
    ],
    [draftedCount, promotedCount, reusedCount]
  );

  return (
    <PageContainer>
      <Stack spacing={1.5} sx={{ flex: 1, minHeight: 0, width: '100%', maxWidth: 1000 }}>
        <Typography variant="h5" fontWeight={700}>Skill Learning</Typography>
        <Typography variant="body2" color="text.secondary">
          The drafted → promoted → reused arc. Shows how many skills progressed through the
          admission gate and actually ran on the hot path — backed by real backend counts.
        </Typography>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={24} />
          </Box>
        ) : offline ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <CloudOffIcon fontSize="large" sx={{ color: 'text.secondary' }} />
            <Typography variant="subtitle1" sx={{ mt: 1 }} fontWeight={600}>Data unavailable</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Data unavailable — the skill learning API is offline
            </Typography>
          </Paper>
        ) : (skills?.length ?? 0) === 0 ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="subtitle1" fontWeight={600}>No skills yet</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              No skills yet — draft a skill from the AI workspace to start the learning flywheel.
            </Typography>
          </Paper>
        ) : (
          <>
            {/* ── Three-stage progression ── */}
            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              spacing={1}
              alignItems={{ xs: 'stretch', sm: 'center' }}
            >
              {stages.map((stage, i) => {
                const active = stage.count > 0;
                return (
                  <React.Fragment key={stage.key}>
                    {i > 0 && (
                      <ArrowForwardIcon
                        sx={{ color: 'text.disabled', alignSelf: { xs: 'center', sm: 'auto' } }}
                        aria-hidden
                      />
                    )}
                    <Paper
                      variant={active ? 'elevation' : 'outlined'}
                      sx={{
                        flex: 1,
                        p: 2,
                        textAlign: 'center',
                        borderColor: active ? theme.palette.primary.main : undefined,
                        borderLeft: active
                          ? `3px solid ${theme.palette.primary.main}`
                          : undefined,
                      }}
                    >
                      <Typography
                        variant="h4"
                        fontWeight={700}
                        sx={{ color: active ? theme.palette.primary.main : theme.palette.text.disabled }}
                      >
                        {formatInt(stage.count)}
                      </Typography>
                      <Typography
                        variant="subtitle2"
                        fontWeight={600}
                        sx={{ color: active ? theme.palette.text.primary : theme.palette.text.secondary }}
                      >
                        {stage.label}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {stage.caption}
                      </Typography>
                    </Paper>
                  </React.Fragment>
                );
              })}
            </Stack>

            {/* ── Reused skills list ── */}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="overline" color="text.secondary">Reused skills</Typography>
              {reusedSkills.length === 0 ? (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  No skills have been reused yet — promote a skill and let the agent invoke it on
                  a matching request.
                </Typography>
              ) : (
                <Stack spacing={1} sx={{ mt: 1 }}>
                  {reusedSkills.map((skill, i) => (
                    <Paper
                      key={`${skill.name}-${i}`}
                      variant="outlined"
                      sx={{ p: 1.5, bgcolor: theme.palette.background.default }}
                    >
                      <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                        <Box sx={{ flex: 1, minWidth: 160 }}>
                          <Typography variant="subtitle2" fontWeight={700}>{skill.name}</Typography>
                          <Chip size="small" variant="outlined" label={skill.kind} />
                        </Box>
                        <Typography variant="body2" color="text.secondary">
                          {formatInt(skill.usage_count)} use{Number(skill.usage_count) === 1 ? '' : 's'}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {pct(skill.success_rate)} success
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Last run: {formatDate(skill.last_executed_at)}
                        </Typography>
                      </Stack>
                    </Paper>
                  ))}
                </Stack>
              )}
            </Paper>
          </>
        )}
      </Stack>
    </PageContainer>
  );
}
