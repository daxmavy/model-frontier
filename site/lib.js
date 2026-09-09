// Pure helpers shared by the page and the tests.

/** Dollars, at a precision that suits the magnitude. */
export const money = v =>
  v >= 100 ? '$' + v.toFixed(0) :
  v >= 1 ? '$' + v.toFixed(2) :
  v >= 0.01 ? '$' + v.toFixed(3) : '$' + v.toPrecision(2);

/** Index scores read as numbers; benchmark scores read as percentages. */
export const fmtVal = (v, kind) =>
  kind === 'frac' ? (v * 100).toFixed(1) + '%' : v.toFixed(1);

export const fmtTokens = v =>
  v >= 1e12 ? (v / 1e12).toFixed(1) + 'T' :
  v >= 1e9 ? (v / 1e9).toFixed(1) + 'B' : (v / 1e6).toFixed(0) + 'M';

/**
 * Models that nothing else beats on both axes at once: no cheaper model scores
 * higher, and no higher-scoring model is cheaper. Where two models tie on cost,
 * only the better-scoring one survives. Returned in ascending cost order.
 */
export function paretoFrontier(rows, cost, cap) {
  const sorted = [...rows].sort((a, b) => cost(a) - cost(b) || cap(b) - cap(a));
  const keep = [];
  let best = -Infinity;
  for (const m of sorted) {
    if (cap(m) > best) { keep.push(m); best = cap(m); }
  }
  return keep;
}

/** Axis ticks: decade-anchored on a log axis, round numbers on a linear one. */
export function ticks(lo, hi, log) {
  const out = [];
  if (log) {
    for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) {
      for (const m of [1, 2, 5]) {
        const v = m * 10 ** e;
        if (v >= lo && v <= hi) out.push(v);
      }
    }
    return out.length > 9
      ? out.filter(v => Math.abs(Math.log10(v) - Math.round(Math.log10(v))) < 1e-9)
      : out;
  }
  const step = 10 ** Math.floor(Math.log10((hi - lo) / 5 || 1));
  for (const mul of [1, 2, 2.5, 5, 10]) {
    const s = step * mul;
    if ((hi - lo) / s <= 7) {
      for (let v = Math.ceil(lo / s) * s; v <= hi; v += s) out.push(+v.toFixed(10));
      return out;
    }
  }
  return out;
}
