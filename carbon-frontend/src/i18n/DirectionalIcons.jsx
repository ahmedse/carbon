// src/i18n/DirectionalIcons.jsx
// RTL-aware chevron/back helpers — Emotion mirrors sx left/right, not icons.
import React from 'react';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { useLanguage } from './useLanguage';

/**
 * Chevron pointing toward the start edge (collapse / previous / back into rail).
 * LTR → left; RTL → right.
 */
export function ChevronStart(props) {
  const { isRtl } = useLanguage();
  const Icon = isRtl ? ChevronRightIcon : ChevronLeftIcon;
  return <Icon data-chevron="start" data-mirrored={isRtl ? '1' : '0'} {...props} />;
}

/**
 * Chevron pointing toward the end edge (expand / next / open rail).
 * LTR → right; RTL → left.
 */
export function ChevronEnd(props) {
  const { isRtl } = useLanguage();
  const Icon = isRtl ? ChevronLeftIcon : ChevronRightIcon;
  return <Icon data-chevron="end" data-mirrored={isRtl ? '1' : '0'} {...props} />;
}

/** Navigation "back" — flips in RTL. */
export function BackArrow({ sx, ...rest }) {
  const { isRtl } = useLanguage();
  return (
    <ArrowBackIcon
      {...rest}
      sx={[isRtl ? { transform: 'scaleX(-1)' } : null, ...(Array.isArray(sx) ? sx : sx ? [sx] : [])]}
    />
  );
}

/** Navigation "forward" — flips in RTL. */
export function ForwardArrow({ sx, ...rest }) {
  const { isRtl } = useLanguage();
  return (
    <ArrowForwardIcon
      {...rest}
      sx={[isRtl ? { transform: 'scaleX(-1)' } : null, ...(Array.isArray(sx) ? sx : sx ? [sx] : [])]}
    />
  );
}

/** Tooltip / drawer placement on the end side of a start rail. */
export function useEndPlacement() {
  const { isRtl } = useLanguage();
  return isRtl ? 'left' : 'right';
}

/** Tooltip / drawer placement on the start side of an end rail. */
export function useStartPlacement() {
  const { isRtl } = useLanguage();
  return isRtl ? 'right' : 'left';
}
