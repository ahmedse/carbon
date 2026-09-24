// OutcomeReceipt — L0 deliverable for Result (and Chat plan-done parity).
// Title · state · facts · prose. Host figures only (ADR-0047 grounding).
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  Collapse,
  Stack,
  Typography,
} from '@mui/material';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useTranslation } from 'react-i18next';
import MarkdownMessage from './MarkdownMessage';
import { splitAnswerAppendix } from './splitAnswerAppendix';
import { receiptTitleFromAnswer } from './resultOutcome';

function TechnicalDetails({ appendix }) {
  const { t } = useTranslation('ai');
  const [open, setOpen] = useState(false);
  if (!appendix) return null;
  return (
    <Box>
      <Button
        size="small"
        color="inherit"
        onClick={() => setOpen((v) => !v)}
        endIcon={open ? <ExpandLessIcon sx={{ fontSize: 14 }} /> : <ExpandMoreIcon sx={{ fontSize: 14 }} />}
        sx={{ textTransform: 'none', px: 0, minWidth: 0, color: 'text.secondary' }}
        aria-expanded={open}
      >
        {t('resultTechnicalDetails')}
      </Button>
      <Collapse in={open} unmountOnExit>
        <Box sx={{ mt: 0.5, wordBreak: 'break-word' }}>
          <MarkdownMessage content={appendix} />
        </Box>
      </Collapse>
    </Box>
  );
}

TechnicalDetails.propTypes = { appendix: PropTypes.string };

/**
 * @param {object} props
 * @param {string} [props.title]
 * @param {string} [props.stateLabel]
 * @param {string} [props.stateColor] MUI Chip color
 * @param {string} [props.facts]
 * @param {string} [props.markdown] full answer (split into prose + appendix)
 * @param {string} [props.emptyCopy]
 */
export default function OutcomeReceipt({
  title = '',
  stateLabel = '',
  stateColor = 'default',
  facts = '',
  markdown = '',
  emptyCopy = '',
}) {
  const { t } = useTranslation('ai');
  const { prose, appendix, hasAppendix } = splitAnswerAppendix(markdown);
  const body = prose || markdown;
  const titleTrim = String(title || '').trim();
  const bodyFirst = receiptTitleFromAnswer(body, '');
  const showTitle = titleTrim && titleTrim !== bodyFirst && !body.startsWith(titleTrim);
  const showEmpty = !body && !titleTrim && !facts;

  return (
    <Stack spacing={0.75} data-testid="outcome-receipt">
      {(showTitle || stateLabel) && (
        <Stack direction="row" alignItems="center" spacing={0.75} useFlexGap flexWrap="wrap">
          {showTitle ? (
            <Typography variant="subtitle2" component="h3" sx={{ fontWeight: 600, m: 0 }}>
              {titleTrim}
            </Typography>
          ) : null}
          {stateLabel ? (
            <Chip
              size="small"
              label={stateLabel}
              color={stateColor}
              variant="outlined"
              sx={{ height: 20 }}
            />
          ) : null}
        </Stack>
      )}
      {facts ? (
        <Typography variant="caption" color="text.secondary" data-testid="outcome-receipt-facts">
          {facts}
        </Typography>
      ) : null}
      {body ? (
        <Box sx={{ wordBreak: 'break-word' }} data-testid="outcome-receipt-prose">
          <MarkdownMessage content={body} />
        </Box>
      ) : showEmpty ? (
        <Typography variant="body2" color="text.secondary">
          {emptyCopy || t('resultNoAnswer')}
        </Typography>
      ) : null}
      {hasAppendix ? <TechnicalDetails appendix={appendix} /> : null}
    </Stack>
  );
}

OutcomeReceipt.propTypes = {
  title: PropTypes.string,
  stateLabel: PropTypes.string,
  stateColor: PropTypes.string,
  facts: PropTypes.string,
  markdown: PropTypes.string,
  emptyCopy: PropTypes.string,
};
