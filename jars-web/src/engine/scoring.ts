/** Scoring primitives — a direct port of the numeric helpers in
 * jars-cli/src/jars_lib/recommend.py. Constants are copied verbatim; the comments cite the
 * Python source so the two implementations stay auditable against each other.
 */

import type { Recommendation } from "./types";

// recommend.py:_FEASIBILITY_K — steepness of the feasibility logistic on (C - R) / C.
export const FEASIBILITY_K = 6.0;

// recommend.py:_RECENCY_DECAY — each year older contributes 0.6**n of the weight.
export const RECENCY_DECAY = 0.6;

// recommend.py:_W_NIRF / _W_CLOSING / _W_OPENING — ranking weights (sum to 1).
export const W_NIRF = 0.6;
export const W_CLOSING = 0.3;
export const W_OPENING = 0.1;

// recommend.py:_NIRF_RANK_SCALE — fixed scale mapping NIRF rank -> goodness.
export const NIRF_RANK_SCALE = 200.0;

// recommend.py:_closing_trend threshold — >=3% per-year relative change is easing/tighter.
const TREND_THRESHOLD = 0.03;

/** recommend.py:feasibility — admit likelihood in [0, 1] from rank and a closing rank. */
export function feasibility(rank: number, closingRank: number | null): number {
  if (closingRank === null || Number.isNaN(closingRank) || closingRank <= 0) return 0.0;
  const relativeMargin = (closingRank - rank) / closingRank;
  const x = Math.max(-60.0, Math.min(60.0, FEASIBILITY_K * relativeMargin));
  return 1.0 / (1.0 + Math.exp(-x));
}

/** recommend.py:_recency_weighted — blend per-year values, weighting recent years more. */
export function recencyWeighted(
  values: Array<[year: number, value: number]>,
  refYear: number,
): number | null {
  let num = 0.0;
  let den = 0.0;
  for (const [year, value] of values) {
    const w = RECENCY_DECAY ** (refYear - year);
    num += w * value;
    den += w;
  }
  return den ? num / den : null;
}

/** recommend.py:_nirf_goodness — NIRF rank -> goodness in [0, 1] (rank 1 -> 1.0). */
export function nirfGoodness(nirfRank: number | null): number {
  if (nirfRank === null) return 0.0;
  return Math.max(0.0, Math.min(1.0, 1.0 - (nirfRank - 1) / NIRF_RANK_SCALE));
}

/** recommend.py:_lower_is_better — min-max normalise so the smallest maps to 1.0. */
export function lowerIsBetter(value: number | null, lo: number, hi: number): number {
  if (value === null) return 0.0;
  if (hi <= lo) return 1.0;
  return Math.max(0.0, Math.min(1.0, (hi - value) / (hi - lo)));
}

/** recommend.py:_assign_scores — compute each rec's weighted score in place. */
export function assignScores(recs: Recommendation[]): void {
  const closings = recs.map((r) => r.rank_closing).filter((v): v is number => v !== null);
  const openings = recs.map((r) => r.rank_opening).filter((v): v is number => v !== null);
  const cLo = closings.length ? Math.min(...closings) : 0.0;
  const cHi = closings.length ? Math.max(...closings) : 0.0;
  const oLo = openings.length ? Math.min(...openings) : 0.0;
  const oHi = openings.length ? Math.max(...openings) : 0.0;

  for (const r of recs) {
    const gNirf = nirfGoodness(r.nirf_rank);
    const gClosing = lowerIsBetter(r.rank_closing, cLo, cHi);
    const gOpening =
      r.rank_opening !== null ? lowerIsBetter(r.rank_opening, oLo, oHi) : gClosing;
    r.score = W_NIRF * gNirf + W_CLOSING * gClosing + W_OPENING * gOpening;
  }
}

/** recommend.py:_order_key — sort comparator: score desc, then (nirf, closing, opening) asc. */
export function compareOrder(a: Recommendation, b: Recommendation): number {
  // Higher score first.
  if (a.score !== b.score) return b.score - a.score;
  const an = a.nirf_rank ?? Infinity;
  const bn = b.nirf_rank ?? Infinity;
  if (an !== bn) return an - bn;
  const ac = a.rank_closing ?? Infinity;
  const bc = b.rank_closing ?? Infinity;
  if (ac !== bc) return ac - bc;
  const ao = a.rank_opening ?? Infinity;
  const bo = b.rank_opening ?? Infinity;
  return ao - bo;
}

/** recommend.py:_closing_trend — OLS slope of (year, closing) over up to 5 recent years. */
export function closingTrend(
  yearsRows: Array<[year: number, round: number, open: number | null, close: number]>,
): string {
  const pts = yearsRows.slice(0, 5).map(([y, , , c]) => [y, c] as [number, number]);
  if (pts.length < 2) return "stable";
  const n = pts.length;
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const xMean = xs.reduce((a, b) => a + b, 0) / n;
  const yMean = ys.reduce((a, b) => a + b, 0) / n;
  const denom = xs.reduce((acc, x) => acc + (x - xMean) ** 2, 0);
  if (denom === 0) return "stable";
  let cov = 0;
  for (let i = 0; i < n; i++) cov += (xs[i] - xMean) * (ys[i] - yMean);
  const slope = cov / denom;
  const rel = slope / yMean;
  if (rel > TREND_THRESHOLD) return "easing";
  if (rel < -TREND_THRESHOLD) return "tighter";
  return "stable";
}
