/** The recommendation engine — a TypeScript port of jars-cli/src/jars_lib/recommend.py and
 * the family-merge logic in jars_lib/engine.py:RecoEngine.recommend.
 *
 * Parity with the Python engine is verified by tests/engine.parity.test.ts, which replays
 * golden query outputs generated from jars_lib itself.
 */

import {
  GENDER_FEMALE,
  GENDER_NEUTRAL,
  IIT_TYPES,
  NON_IIT_TYPES,
  QUOTA_ALL_INDIA,
  QUOTA_HOME_STATE,
  QUOTA_OTHER_STATE,
} from "./constants";
import type { Dataset, ProgramGroup } from "./dataset";
import {
  assignScores,
  closingTrend,
  compareOrder,
  feasibility,
  recencyWeighted,
} from "./scoring";
import type { Cutoff, Recommendation, RecommendParams } from "./types";

/** recommend.py:_gender_pool — seat-pool genders a candidate may compete in. */
function genderPool(gender: string): Set<string> {
  if (gender === GENDER_FEMALE) return new Set([GENDER_NEUTRAL, GENDER_FEMALE]);
  return new Set([GENDER_NEUTRAL]);
}

const MAIN_QUOTAS = new Set([QUOTA_ALL_INDIA, QUOTA_HOME_STATE, QUOTA_OTHER_STATE]);

interface FamilyOpts {
  seatType: string;
  gender: string;
  homeState: string | null;
  instituteTypes: Set<string>;
  year: number | null;
}

/** True if a group survives the static (non-rank) filters — mirror of recommend.py:_filter. */
function passesFilter(g: ProgramGroup, opts: FamilyOpts): boolean {
  if (g.seatType !== opts.seatType) return false;
  if (!genderPool(opts.gender).has(g.gender)) return false;
  if (!opts.instituteTypes.has(g.instituteType)) return false;

  if (opts.homeState) {
    const inHome =
      (g.instituteState ?? "").trim().toLowerCase() === opts.homeState.trim().toLowerCase();
    const q = g.quota;
    // Keep: any non-main (special) quota; AI always; HS only in home state; OS only elsewhere.
    const keep =
      !MAIN_QUOTAS.has(q) ||
      q === QUOTA_ALL_INDIA ||
      (q === QUOTA_HOME_STATE && inHome) ||
      (q === QUOTA_OTHER_STATE && !inHome);
    if (!keep) return false;
  }
  return true;
}

/** Year-filtered per-year rows for a group (recommend.py applies the year filter pre-group). */
function yearsForGroup(
  g: ProgramGroup,
  year: number | null,
): Array<[number, number, number | null, number]> {
  if (year === null) return g.years;
  return g.years.filter((r) => r[0] === year);
}

/** recommend.py:recommend — single rank scale / institute family. No limit applied here. */
function recommendFamily(
  ds: Dataset,
  rank: number,
  rankRange: number,
  opts: FamilyOpts,
): Recommendation[] {
  // Candidate groups with their (year-filtered) per-year rows.
  const candidates: Array<{ g: ProgramGroup; years: Array<[number, number, number | null, number]> }> = [];
  let refYear = -Infinity;
  for (const g of ds.groups) {
    if (!passesFilter(g, opts)) continue;
    const years = yearsForGroup(g, opts.year);
    if (years.length === 0) continue;
    for (const r of years) if (r[0] > refYear) refYear = r[0];
    candidates.push({ g, years });
  }
  if (candidates.length === 0) return [];

  const lo = rank - rankRange;
  const hi = rank + rankRange;
  const recs: Recommendation[] = [];

  for (const { g, years } of candidates) {
    // years is already sorted most-recent first.
    const inRange = years.filter(([, , o, c]) => rank <= c && (o === null || o <= rank));
    const inRangeYears = inRange.map(([y]) => y);

    const window = years.filter(([, , , c]) => lo <= c && c <= hi);
    if (window.length === 0) continue;
    const windowYears = window.map(([y]) => y);

    const band = inRange.length ? inRange : window;
    const opens = band.filter(([, , o]) => o !== null) as Array<[number, number, number, number]>;
    let openingRankMin: number | null = null;
    let openingMinYear: number | null = null;
    if (opens.length) {
      let best = opens[0];
      for (const r of opens) if (r[2] < best[2]) best = r;
      openingRankMin = best[2];
      openingMinYear = best[0];
    }
    let closingBest = band[0];
    for (const r of band) if (r[3] > closingBest[3]) closingBest = r;
    const closingRankMax = closingBest[3];
    const closingMaxYear = closingBest[0];

    const chance =
      recencyWeighted(
        years.map(([y, , , c]) => [y, feasibility(rank, c)] as [number, number]),
        refYear,
      ) ?? 0.0;

    const rankClosing = recencyWeighted(
      years.map(([y, , , c]) => [y, c] as [number, number]),
      refYear,
    );
    const openingPairs = years
      .filter(([, , o]) => o !== null)
      .map(([y, , o]) => [y, o as number] as [number, number]);
    const rankOpening = recencyWeighted(openingPairs, refYear);

    const trend = closingTrend(years);

    const [recentYear, recentRound, recentOpen, recentClose] = years[0];
    const cutoff: Cutoff = {
      year: recentYear,
      round: recentRound,
      institute_type: g.instituteType,
      institute_name: g.instituteName,
      program_name: g.programName,
      quota: g.quota,
      seat_type: g.seatType,
      gender: g.gender,
      opening_rank: recentOpen,
      closing_rank: recentClose,
    };

    recs.push({
      cutoff,
      nirf_rank: g.nirfRank,
      nirf_score: g.nirfScore,
      feasibility: chance,
      in_range_years: inRangeYears,
      window_years: windowYears,
      opening_rank_min: openingRankMin,
      opening_rank_min_year: openingMinYear,
      closing_rank_max: closingRankMax,
      closing_rank_max_year: closingMaxYear,
      rank_closing: rankClosing,
      rank_opening: rankOpening,
      score: 0.0,
      closing_rank_trend: trend,
    });
  }

  assignScores(recs);
  recs.sort(compareOrder); // Array.prototype.sort is stable (ES2019+).
  return recs;
}

function intersect(a: ReadonlySet<string>, b: Set<string>): Set<string> {
  const out = new Set<string>();
  for (const x of a) if (b.has(x)) out.add(x);
  return out;
}

/**
 * engine.py:RecoEngine.recommend — merge IIT (Advanced rank) and non-IIT (Mains rank)
 * families, each scored within its own rank scale, then re-sort by the ranking key.
 *
 * At least one of `jeeAdvRank` / `jeeMainsRank` must be provided.
 */
export function recommend(ds: Dataset, params: RecommendParams): Recommendation[] {
  const adv = params.jeeAdvRank ?? null;
  const mains = params.jeeMainsRank ?? null;
  if (adv === null && mains === null) {
    throw new Error("Provide at least one of jeeAdvRank or jeeMainsRank.");
  }

  const common = {
    seatType: params.seatType ?? "OPEN",
    gender: params.gender ?? GENDER_NEUTRAL,
    homeState: params.homeState ?? null,
    year: params.year ?? null,
  };
  const filter = params.instituteTypes ?? null;

  let recs: Recommendation[] = [];

  if (adv !== null) {
    const iit = filter ? intersect(IIT_TYPES, filter) : new Set(IIT_TYPES);
    if (iit.size) recs = recs.concat(recommendFamily(ds, adv, params.rankRange, { ...common, instituteTypes: iit }));
  }
  if (mains !== null) {
    const nonIit = filter ? intersect(NON_IIT_TYPES, filter) : new Set(NON_IIT_TYPES);
    if (nonIit.size)
      recs = recs.concat(recommendFamily(ds, mains, params.rankRange, { ...common, instituteTypes: nonIit }));
  }

  recs.sort(compareOrder);
  if (params.limit != null) recs = recs.slice(0, params.limit);
  return recs;
}
