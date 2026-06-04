/** Type mirrors of the Python dataclasses and the on-disk web dataset.
 *
 * The field names match jars_lib's `Cutoff` / `Recommendation` so the parity tests can
 * compare against the Python `to_dict()` output directly. See jars-cli/src/jars_lib/models.py.
 */

/** Per-institute metadata, keyed by institute name (1:1 with `dict.institutes`).
 *
 * Only fields the engine resolves by institute *name* live here (NIRF, state). Note that
 * `institute_type` is intentionally NOT here: a few institutes were reclassified across
 * years, and the engine keys on type per row, so it lives in `rows.itype`. */
export interface RawInstitute {
  /** Index into `dict.states`, or -1 when the institute's state is unknown. */
  state: number;
  nirf_rank: number | null;
  nirf_score: number | null;
}

/** The columnar, dictionary-encoded dataset emitted by tools/build_web_data.py. */
export interface RawDataset {
  meta: {
    last_updated?: string;
    nirf_year?: number;
    years?: number[];
    schema_version?: number;
    [k: string]: unknown;
  };
  dict: {
    institutes: string[];
    programs: string[];
    institute_types: string[];
    quotas: string[];
    seat_types: string[];
    genders: string[];
    states: string[];
    gender_neutral: string;
    gender_female: string;
  };
  institutes: RawInstitute[];
  rows: {
    inst: number[];
    itype: number[];
    prog: number[];
    quota: number[];
    seat: number[];
    gender: number[];
    year: number[];
    round: number[];
    open: (number | null)[];
    close: number[];
  };
}

/** One opening/closing-rank row (mirror of jars_lib.models.Cutoff). */
export interface Cutoff {
  year: number;
  round: number;
  institute_type: string;
  institute_name: string;
  program_name: string;
  quota: string;
  seat_type: string;
  gender: string;
  opening_rank: number | null;
  closing_rank: number | null;
}

/** A ranked suggestion (mirror of jars_lib.models.Recommendation). */
export interface Recommendation {
  cutoff: Cutoff;
  nirf_rank: number | null;
  nirf_score: number | null;
  feasibility: number;
  in_range_years: number[];
  window_years: number[];
  opening_rank_min: number | null;
  opening_rank_min_year: number | null;
  closing_rank_max: number | null;
  closing_rank_max_year: number | null;
  rank_closing: number | null;
  rank_opening: number | null;
  score: number;
  closing_rank_trend: string | null;
}

/** True when Open/Close/`bandYears` reflect in-range years; false for the reach fallback. */
export function bandInRange(r: Recommendation): boolean {
  return r.in_range_years.length > 0;
}

/** The years summarised by `opening_rank_min`/`closing_rank_max`. */
export function bandYears(r: Recommendation): number[] {
  return r.in_range_years.length ? r.in_range_years : r.window_years;
}

export interface RecommendParams {
  rankRange: number;
  jeeAdvRank?: number | null;
  jeeMainsRank?: number | null;
  seatType?: string;
  gender?: string;
  homeState?: string | null;
  instituteTypes?: Set<string> | null;
  year?: number | null;
  limit?: number | null;
}
