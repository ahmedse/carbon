// src/components/LtrText.jsx
// Layer-2 primitive: isolate a Latin / domain value inside an RTL sentence
// (ADR-0018). Renders a <bdi dir="ltr"> so an English term does not reorder the
// surrounding Arabic.
//
// Why not reuse components/journey/MixedText.jsx: MixedText takes a whole
// sentence string + a glossary allowlist and splits/rebuilds it into mixed
// runs — it is built for splitting a sentence, not for isolating one arbitrary
// already-resolved value/node. Callers here wrap a single value (a scope label,
// a goal, a kgCO2e figure, a code), so the minimal shared addition is this
// single-purpose wrapper. MixedText stays the sentence-level primitive.
import React from 'react';
import PropTypes from 'prop-types';

function LtrText({ children }) {
  return <bdi dir="ltr">{children}</bdi>;
}

LtrText.propTypes = { children: PropTypes.node };

LtrText.defaultProps = { children: null };

export default React.memo(LtrText);
