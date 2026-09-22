// src/utils/graphEdgePath.js
// Orthogonal / staggered edge paths for EnterpriseGraph (ADR-0012).
// Prefer aligned channels + slight offsets over Holten-style bundling
// (bundling hurts path tracing on approval workflows).

/**
 * SVG path between anchors.
 * TB same-lane → vertical line; TB lane change → orthogonal elbows;
 * LR → horizontal elbows. Optional corridor offset staggers parallel links.
 *
 * @param {number} sx
 * @param {number} sy
 * @param {number} tx
 * @param {number} ty
 * @param {'lr'|'tb'} [direction]
 * @param {number} [laneOffset]
 * @returns {string}
 */
export function computeEdgePath(sx, sy, tx, ty, direction = 'lr', laneOffset = 0) {
  const ox = Number(laneOffset) || 0;
  if (direction === 'tb') {
    const sxx = sx + ox;
    const txx = tx + ox;
    if (Math.abs(sxx - txx) < 1.5) {
      return `M ${sxx} ${sy} L ${txx} ${ty}`;
    }
    const midY = sy + (ty - sy) * 0.5;
    return `M ${sxx} ${sy} L ${sxx} ${midY} L ${txx} ${midY} L ${txx} ${ty}`;
  }
  const syy = sy + ox;
  const tyy = ty + ox;
  if (Math.abs(syy - tyy) < 1.5) {
    return `M ${sx} ${syy} L ${tx} ${tyy}`;
  }
  const midX = sx + (tx - sx) * 0.5;
  return `M ${sx} ${syy} L ${midX} ${syy} L ${midX} ${tyy} L ${tx} ${tyy}`;
}

/**
 * Left-side return channel for back-edges (loops / catch → retry).
 * @param {number} sx
 * @param {number} sy
 * @param {number} tx
 * @param {number} ty
 * @param {number} [channelX] absolute x of the return gutter
 * @returns {string}
 */
export function computeBackEdgePath(sx, sy, tx, ty, channelX) {
  const cx = channelX != null ? channelX : Math.min(sx, tx) - 28;
  return `M ${sx} ${sy} L ${cx} ${sy} L ${cx} ${ty} L ${tx} ${ty}`;
}

/**
 * Assign ±lane offsets to edges that share a corridor (not ink-minimizing bundles).
 * @param {Array<object>} edges — must already have sourceX/Y targetX/Y
 * @param {'lr'|'tb'} direction
 * @param {number} [stepPx]
 * @returns {Array<object>} edges with laneOffset
 */
export function assignCorridorOffsets(edges, direction = 'tb', stepPx = 6) {
  if (!Array.isArray(edges) || edges.length < 2) {
    return (edges || []).map((e) => ({ ...e, laneOffset: e.laneOffset || 0 }));
  }
  const groups = new Map();
  edges.forEach((e, idx) => {
    let key;
    if (direction === 'tb') {
      const ax = Math.round(((e.sourceX + e.targetX) / 2) / 10) * 10;
      const sy = Math.round(e.sourceY / 24);
      const ty = Math.round(e.targetY / 24);
      key = `tb:${ax}:${sy}:${ty}`;
    } else {
      const ay = Math.round(((e.sourceY + e.targetY) / 2) / 10) * 10;
      const sx = Math.round(e.sourceX / 24);
      const tx = Math.round(e.targetX / 24);
      key = `lr:${ay}:${sx}:${tx}`;
    }
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(idx);
  });
  const out = edges.map((e) => ({ ...e, laneOffset: e.laneOffset || 0 }));
  groups.forEach((idxs) => {
    if (idxs.length < 2) return;
    idxs.forEach((idx, i) => {
      const centered = i - (idxs.length - 1) / 2;
      out[idx] = { ...out[idx], laneOffset: centered * stepPx };
    });
  });
  return out;
}

/**
 * Ancestors + descendants of a node id (inclusive) for focus-path dimming.
 * @param {Array<{source:*, target:*}>} edges
 * @param {*} focusId
 * @returns {Set<*>}
 */
export function focusPathIds(edges, focusId) {
  const ids = new Set();
  if (focusId == null || focusId === '') return ids;
  ids.add(focusId);
  const preds = new Map();
  const succs = new Map();
  (edges || []).forEach((e) => {
    if (!preds.has(e.target)) preds.set(e.target, []);
    if (!succs.has(e.source)) succs.set(e.source, []);
    preds.get(e.target).push(e.source);
    succs.get(e.source).push(e.target);
  });
  const walk = (start, adj) => {
    const stack = [start];
    while (stack.length) {
      const cur = stack.pop();
      (adj.get(cur) || []).forEach((n) => {
        if (ids.has(n)) return;
        ids.add(n);
        stack.push(n);
      });
    }
  };
  walk(focusId, preds);
  walk(focusId, succs);
  return ids;
}
