import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Box } from '@mui/material';

import { splitMixed } from './mixedTextParts';

/**
 * MixedText — renders a sentence that may carry English domain terms inside an
 * Arabic (RTL) sentence without breaking bidi order.
 *
 * The pack declares a glossary of terms that stay English in every language.
 * Each term is wrapped in `<bdi dir="ltr">`, which isolates it from the
 * surrounding paragraph direction so an English phrase does not reorder the
 * Arabic around it. Nothing is translated here; the pack already chose the
 * wording. This component only isolates the allowlisted terms.
 */
export default function MixedText({ text, glossary, component = 'span', sx }) {
  const parts = useMemo(() => splitMixed(text, glossary), [text, glossary]);
  return (
    <Box component={component} sx={sx}>
      {parts.map((part, index) => (
        part.term
          ? <bdi key={`${index}-${part.text}`} dir="ltr">{part.text}</bdi>
          : <React.Fragment key={`${index}-${part.text}`}>{part.text}</React.Fragment>
      ))}
    </Box>
  );
}

MixedText.propTypes = {
  text: PropTypes.string,
  glossary: PropTypes.arrayOf(PropTypes.string),
  component: PropTypes.elementType,
  sx: PropTypes.oneOfType([PropTypes.object, PropTypes.array, PropTypes.func]),
};

MixedText.defaultProps = {
  text: '',
  glossary: [],
  component: 'span',
  sx: undefined,
};
