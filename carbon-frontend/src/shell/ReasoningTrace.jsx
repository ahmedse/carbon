// src/shell/ReasoningTrace.jsx
// Wave D3 — AI output transparency: an on-click (NOT hover) "why this answer"
// affordance that expands a compact panel of provenance, in OUTCOME language
// only (RULE_23 — never engine_turn_id, raw guard_results, S2/S4, token
// counts, or latency). Theme tokens only (RULE_8). Keyboard-complete via a
// real <button> (Enter/Space toggle), aria-expanded on the trigger.
import { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Chip, IconButton, Link, Paper, Stack, Typography } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import PublicOutlinedIcon from '@mui/icons-material/PublicOutlined';
import { useTranslation } from 'react-i18next';
import { useLanguage } from '../i18n/useLanguage';

// RULE_23 — drop any line that leaks engine internals before rendering.
// Covers engine_turn_id ("Turn: …"), raw guard_results ("Guards: …"),
// S2/S4 labels, token counts ("… tok"/"token(s)"), and latency.
const LEAK_PATTERN = /(engine_turn|^\s*turn\s*:|\bguards?\b|\btok\b|\btokens?\b|latency|\bS[24]\b)/i;

function isOutcomeLine(line) {
  if (typeof line !== 'string') return false;
  const trimmed = line.trim();
  return trimmed !== '' && !LEAK_PATTERN.test(trimmed);
}

// Tools are surfaced in outcome language: the action's human label/summary, or
// the pending action's confirmation message / proposed rule name.
function actionLabel(action) {
  return action?.label || action?.summary || null;
}

function pendingLabel(pending) {
  return pending?.confirmation_message || pending?.proposed_rule?.name || null;
}

// Data freshness from a serialized timestamp; guard invalid/empty input.
function formatFreshness(createdAt) {
  if (!createdAt) return null;
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

// RULE_29 — external web citations: map a provider tag to its localized label.
const PROVIDER_LABEL_KEYS = {
  wikipedia: 'source_wikipedia',
  duckduckgo: 'source_duckduckgo',
  external_web: 'source_external_web',
};

function providerLabel(source, t) {
  return t(PROVIDER_LABEL_KEYS[source] || 'source_external_web');
}

function ReasoningTrace({ lines = [], actions = [], pendingActions = [], createdAt = null, externalSources = [] }) {
  const { isRtl } = useLanguage();
  const { t } = useTranslation('ai');
  const [open, setOpen] = useState(false);

  const sources = (Array.isArray(lines) ? lines : []).filter(isOutcomeLine);
  const tools = [
    ...(Array.isArray(actions) ? actions : []).map(actionLabel),
    ...(Array.isArray(pendingActions) ? pendingActions : []).map(pendingLabel),
  ].filter(Boolean);
  const freshness = formatFreshness(createdAt);

  // External sources are already provenance-safe; validate defensively and
  // build the localized badge label + link text once (keyed on the prop).
  const externalSourceItems = useMemo(() => {
    const list = Array.isArray(externalSources) ? externalSources : [];
    const items = [];
    for (const item of list) {
      if (!item || typeof item !== 'object') continue;
      const title = typeof item.title === 'string' ? item.title.trim() : '';
      const url = typeof item.url === 'string' ? item.url.trim() : '';
      if (!title && !url) continue; // malformed — nothing to render
      if (!url) continue; // no URL to link to — cannot render a citation
      const label = providerLabel(item.source, t);
      const date = formatFreshness(item.retrieved_at);
      const badgeLabel = `${t('external')} · ${label}${date ? ` · ${date}` : ''}`;
      items.push({
        key: `${url}::${title || url}`,
        linkText: title || url,
        url,
        badgeLabel,
      });
    }
    return items;
  }, [externalSources, t]);

  return (
    <Box
      sx={{
        position: 'absolute',
        top: 4,
        ...(isRtl ? { left: 2 } : { right: 2 }),
        zIndex: 10,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
      }}
    >
      <IconButton
        size="small"
        aria-label="Why this answer"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        sx={{
          p: 0.25,
          color: 'text.disabled',
          opacity: open ? 1 : 0.45,
          '&:hover': { opacity: 1 },
        }}
      >
        <InfoOutlinedIcon sx={{ fontSize: 11 }} />
      </IconButton>

      {open && (
        <Paper
          variant="outlined"
          sx={{
            mt: 0.5,
            p: 1.25,
            minWidth: 240,
            maxWidth: 360,
            bgcolor: 'background.paper',
            boxShadow: 2,
          }}
        >
          <Stack spacing={1}>
            {(sources.length > 0 || externalSourceItems.length > 0) && (
              <Box>
                <Typography
                  variant="caption"
                  sx={{ display: 'block', fontWeight: 600, color: 'text.secondary', mb: 0.25 }}
                >
                  Sources
                </Typography>
                {sources.map((line) => (
                  <Typography key={line} variant="caption" sx={{ display: 'block' }}>
                    {line}
                  </Typography>
                ))}
                {externalSourceItems.length > 0 && (
                  <Box dir="ltr">
                    {externalSourceItems.map((item) => (
                      <Stack
                        key={item.key}
                        direction="row"
                        spacing={0.75}
                        alignItems="center"
                        sx={{ mt: 0.25 }}
                      >
                        <Link
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          component="a"
                          variant="caption"
                          sx={{ display: 'block', wordBreak: 'break-word', flexGrow: 1 }}
                        >
                          {item.linkText}
                        </Link>
                        <Chip
                          size="small"
                          variant="outlined"
                          color="default"
                          icon={
                            <PublicOutlinedIcon
                              sx={{ fontSize: 14, color: 'text.secondary' }}
                              aria-hidden="true"
                            />
                          }
                          label={item.badgeLabel}
                          aria-label={item.badgeLabel}
                        />
                      </Stack>
                    ))}
                  </Box>
                )}
              </Box>
            )}

            {tools.length > 0 && (
              <Box>
                <Typography
                  variant="caption"
                  sx={{ display: 'block', fontWeight: 600, color: 'text.secondary', mb: 0.25 }}
                >
                  Tools used
                </Typography>
                {tools.map((tool) => (
                  <Typography key={tool} variant="caption" sx={{ display: 'block' }}>
                    {tool}
                  </Typography>
                ))}
              </Box>
            )}

            {freshness && (
              <Box>
                <Typography
                  variant="caption"
                  sx={{ display: 'block', fontWeight: 600, color: 'text.secondary', mb: 0.25 }}
                >
                  Data freshness
                </Typography>
                <Typography variant="caption" sx={{ display: 'block' }}>
                  {freshness}
                </Typography>
              </Box>
            )}
          </Stack>
        </Paper>
      )}
    </Box>
  );
}

ReasoningTrace.propTypes = {
  lines: PropTypes.arrayOf(PropTypes.string),
  actions: PropTypes.array,
  pendingActions: PropTypes.array,
  createdAt: PropTypes.string,
  externalSources: PropTypes.array,
};

export default ReasoningTrace;
