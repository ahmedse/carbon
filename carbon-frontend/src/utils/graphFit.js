// Smart auto-fit for enterprise / Plan DAGs.
// EnterpriseGraph sizes the SVG viewBox to at least the canvas (viewport) so
// preserveAspectRatio=meet cannot billboard a skinny DAG. That means zoom > 1
// on a deep TB layout overflows the viewBox and clips — Fit/Reset must not
// do that. Short plans still get a hard upscale cap so 2–3 steps stay card-sized.

export const FIT_ZOOM_FLOOR = 0.55;
export const FIT_ZOOM_CEIL = 1.75;

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/**
 * @param {object} opts
 * @param {number} opts.availW — canvas CSS width
 * @param {number} opts.availH — canvas CSS height
 * @param {number} opts.layoutW — laid-out graph width (px)
 * @param {number} opts.layoutH — laid-out graph height (px)
 * @param {'contain'|'width'|'none'|'smart'} [opts.fitMode='contain']
 * @param {number} [opts.fitZoomCeil]
 * @param {number} [opts.sampleNodeW=240] — typical step card width in layout space
 * @returns {{ scale: number, panX: number, panY: number }}
 */
export function computeFitScale({
  availW,
  availH,
  layoutW,
  layoutH,
  fitMode = 'contain',
  fitZoomCeil,
  sampleNodeW = 240,
}) {
  const lw = Math.max(Number(layoutW) || 1, 1);
  const lh = Math.max(Number(layoutH) || 1, 1);
  const aw = Math.max(Number(availW) || 1, 1);
  const ah = Math.max(Number(availH) || 1, 1);
  const nodeW = Math.max(Number(sampleNodeW) || 240, 1);

  if (fitMode === 'none') {
    return {
      scale: 1,
      panX: Math.max(0, (aw - lw) / 2),
      panY: Math.max(0, (ah - lh) / 2),
    };
  }

  const fitX = aw / lw;
  const fitY = ah / lh;
  const ceilCap = Number.isFinite(fitZoomCeil) ? fitZoomCeil : FIT_ZOOM_CEIL;

  // On-screen card caps (short plans only — deep plans may not upscale).
  const MAX_SHORT_NODE_W = 268;
  const shortNodeCeil = MAX_SHORT_NODE_W / nodeW;

  let fitted;
  let floor = FIT_ZOOM_FLOOR;
  let ceil = ceilCap;

  if (fitMode === 'smart') {
    // Tall / deep: viewBox already covers layoutH; zoom>1 clips the spine.
    // Stay at 1 and center horizontally — meet shows the full journey.
    // Shallow: contain + hard cap so 2–3 steps do not become giant boxes.
    const tall = lh / lw > 1.05 || lh > ah * 0.88 || lh / nodeW >= 3.5;
    if (tall) {
      floor = 1;
      ceil = 1;
      fitted = 1;
    } else {
      ceil = Math.min(ceilCap, shortNodeCeil, 1.08);
      fitted = Math.min(fitX, fitY, ceil);
    }
  } else if (fitMode === 'width') {
    fitted = fitX;
  } else {
    fitted = Math.min(fitX, fitY);
  }

  const scale = clamp(fitted, floor, ceil);
  const panX = Math.max(0, (aw - lw * scale) / 2);
  const scaledH = lh * scale;
  // Top-align when the journey fills/overflows the rail; else center.
  const panY = scaledH >= ah * 0.98 ? 0 : Math.max(0, (ah - scaledH) / 2);
  return { scale, panX, panY };
}
