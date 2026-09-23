// HTML face of a graph node. SVG draws the shape; this draws the words.
// Placed in a foreignObject so it shares the canvas zoom transform.
import React from 'react';
import PropTypes from 'prop-types';
import { dominantDir, scriptRuns } from './graphText';

function Mixed({ text }) {
  const runs = scriptRuns(text);
  if (runs.length === 0) return null;
  return runs.map((run, i) => (
    <span key={`${run.dir}-${i}`} dir={run.dir} style={{ unicodeBidi: 'isolate' }}>
      {run.text}
    </span>
  ));
}

Mixed.propTypes = { text: PropTypes.string };

const clamp = {
  overflow: 'hidden',
  display: '-webkit-box',
  WebkitBoxOrient: 'vertical',
  wordBreak: 'break-word',
};

/**
 * Node words. No character slicing — the box ellipsizes at the end of a line.
 */
export function GraphNodeLabel({
  title = '',
  meta = '',
  status = '',
  statusColor,
  center = false,
  dir,
  fontFamily,
  color,
  tip = '',
}) {
  const textDir = dir || dominantDir(title || meta || status);
  return (
    <div
      xmlns="http://www.w3.org/1999/xhtml"
      dir={textDir}
      title={tip || undefined}
      style={{
        boxSizing: 'border-box',
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: center ? 'center' : 'stretch',
        textAlign: center ? 'center' : 'start',
        padding: '8px 12px',
        overflow: 'hidden',
        pointerEvents: 'none',
        fontFamily: fontFamily || 'inherit',
        color: color || 'inherit',
      }}
    >
      <div
        style={{
          ...clamp,
          WebkitLineClamp: 2,
          fontSize: 13,
          fontWeight: 600,
          lineHeight: '15px',
          width: '100%',
        }}
      >
        <Mixed text={String(title || '')} />
      </div>
      {meta ? (
        <div
          style={{
            ...clamp,
            WebkitLineClamp: 1,
            marginTop: 2,
            fontSize: 11,
            fontWeight: 400,
            lineHeight: '14px',
            opacity: 0.72,
            width: '100%',
          }}
        >
          <Mixed text={String(meta)} />
        </div>
      ) : null}
      {status ? (
        <div
          style={{
            ...clamp,
            WebkitLineClamp: 1,
            marginTop: 2,
            fontSize: 10,
            fontWeight: 650,
            lineHeight: '12px',
            width: '100%',
            color: statusColor || 'inherit',
          }}
        >
          <Mixed text={String(status)} />
        </div>
      ) : null}
    </div>
  );
}

GraphNodeLabel.propTypes = {
  title: PropTypes.string,
  meta: PropTypes.string,
  status: PropTypes.string,
  statusColor: PropTypes.string,
  center: PropTypes.bool,
  dir: PropTypes.oneOf(['rtl', 'ltr']),
  fontFamily: PropTypes.string,
  color: PropTypes.string,
  tip: PropTypes.string,
};

/** foreignObject wrapper so export can fall back to the data-* words. */
export function GraphNodeForeign({
  width,
  height,
  title,
  meta,
  status,
  statusColor,
  center,
  dir,
  fontFamily,
  color,
  tip,
}) {
  const textDir = dir || dominantDir(title || meta || status);
  return (
    <foreignObject
      x={0}
      y={0}
      width={width}
      height={height}
      data-title={title || ''}
      data-meta={meta || ''}
      data-status={status || ''}
      data-dir={textDir}
      style={{ overflow: 'visible', pointerEvents: 'none' }}
    >
      <GraphNodeLabel
        title={title}
        meta={meta}
        status={status}
        statusColor={statusColor}
        center={center}
        dir={textDir}
        fontFamily={fontFamily}
        color={color}
        tip={tip}
      />
    </foreignObject>
  );
}

GraphNodeForeign.propTypes = {
  width: PropTypes.number.isRequired,
  height: PropTypes.number.isRequired,
  title: PropTypes.string,
  meta: PropTypes.string,
  status: PropTypes.string,
  statusColor: PropTypes.string,
  center: PropTypes.bool,
  dir: PropTypes.oneOf(['rtl', 'ltr']),
  fontFamily: PropTypes.string,
  color: PropTypes.string,
  tip: PropTypes.string,
};
