// Shared mobile breakpoint hook (ADR-0035 / compact-ui §Mobile).
// Phone portrait = theme.breakpoints.down('sm') (<600).
// Landscape phones are often ≥600 wide but short — keep the mobile shell so
// Pulse/nav do not flip to desktop mid-rotation.

import { useTheme, useMediaQuery } from '@mui/material';

export function useIsMobile() {
  const theme = useTheme();
  const narrow = useMediaQuery(theme.breakpoints.down('sm'));
  // Short landscape (typical phone rotate): width up to md, height ≤500.
  const shortLandscape = useMediaQuery(
    '(max-height: 500px) and (max-width: 960px) and (orientation: landscape)'
  );
  return narrow || shortLandscape;
}

export default useIsMobile;
