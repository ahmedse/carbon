// ResponsiveList — under sm: stacked cards; md+: children table (ADR-0035 / MOB-C)

import React from 'react';
import PropTypes from 'prop-types';
import { Box, Stack, Typography, Chip } from '@mui/material';
import { useIsMobile } from '../../hooks/useIsMobile';
import { FONT } from '../../theme/themeTokens';

/**
 * @param {object} props
 * @param {Array} props.items
 * @param {function} props.getKey — (item) => key
 * @param {function} props.renderCard — (item) => { title, meta?, status?, statusColor?, onClick? }
 * @param {React.ReactNode} props.table — desktop table node
 * @param {string} [props.emptyLabel]
 */
export default function ResponsiveList({ items, getKey, renderCard, table, emptyLabel }) {
  const isMobile = useIsMobile();
  const list = Array.isArray(items) ? items : [];

  if (!isMobile) {
    return table;
  }

  if (list.length === 0) {
    return (
      <Typography sx={{ ...FONT.body2, color: 'text.secondary', py: 1 }}>
        {emptyLabel || '—'}
      </Typography>
    );
  }

  return (
    <Stack spacing={1} sx={{ width: '100%' }}>
      {list.map((item) => {
        const card = renderCard(item) || {};
        const {
          title,
          meta,
          status,
          statusColor = 'default',
          onClick,
        } = card;
        return (
          <Box
            key={getKey(item)}
            role={onClick ? 'button' : undefined}
            tabIndex={onClick ? 0 : undefined}
            onClick={onClick}
            onKeyDown={
              onClick
                ? (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onClick();
                    }
                  }
                : undefined
            }
            sx={{
              p: 1.5,
              border: 1,
              borderColor: 'divider',
              borderRadius: 1,
              bgcolor: 'background.paper',
              cursor: onClick ? 'pointer' : 'default',
              minHeight: 40,
              '&:hover': onClick ? { bgcolor: 'action.hover' } : undefined,
              '&:focus-visible': onClick
                ? { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: 2 }
                : undefined,
            }}
          >
            <Stack direction="row" spacing={1} alignItems="flex-start" justifyContent="space-between">
              <Box sx={{ minWidth: 0, flex: 1 }}>
                <Typography sx={{ ...FONT.body1, fontWeight: 600 }} noWrap>
                  {title}
                </Typography>
                {meta ? (
                  <Typography sx={{ ...FONT.caption, color: 'text.secondary', mt: 0.25 }} noWrap>
                    {meta}
                  </Typography>
                ) : null}
              </Box>
              {status ? (
                <Chip size="small" label={status} color={statusColor} sx={{ flexShrink: 0 }} />
              ) : null}
            </Stack>
          </Box>
        );
      })}
    </Stack>
  );
}

ResponsiveList.propTypes = {
  items: PropTypes.array,
  getKey: PropTypes.func.isRequired,
  renderCard: PropTypes.func.isRequired,
  table: PropTypes.node.isRequired,
  emptyLabel: PropTypes.string,
};
