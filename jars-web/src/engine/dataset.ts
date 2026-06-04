/** Decodes the columnar web dataset into program groups, ready for the engine.
 *
 * The browser dataset is already collapsed to one row per (program key, year) by the
 * Python build step (jars_lib.recommend._yearly_reps), so this module only has to group the
 * rows back by program key and decode the dictionary indices to strings.
 *
 * Group ordering matters: jars_lib's recommend() iterates programs in `_KEY_COLS`-sorted
 * order (a side effect of pandas' sorted groupby in `_yearly_reps`). We reproduce that exact
 * order here so that fully-tied results break ties identically to Python.
 */

import type { Cutoff, RawDataset } from "./types";

export interface ProgramGroup {
  instituteType: string;
  instituteName: string;
  instituteState: string | null;
  nirfRank: number | null;
  nirfScore: number | null;
  programName: string;
  quota: string;
  seatType: string;
  gender: string;
  /** Per-year rows sorted most-recent first: [year, round, openingRank, closingRank]. */
  years: Array<[number, number, number | null, number]>;
}

export class Dataset {
  readonly meta: RawDataset["meta"];
  readonly dict: RawDataset["dict"];
  readonly groups: ProgramGroup[];
  private readonly byIdentity: Map<string, ProgramGroup>;

  constructor(raw: RawDataset) {
    this.meta = raw.meta;
    this.dict = raw.dict;
    this.groups = buildGroups(raw);
    this.byIdentity = new Map(this.groups.map((g) => [identityOf(g), g]));
  }

  /** The full per-year history behind a recommendation, for the row-detail view. */
  yearsFor(cutoff: Cutoff): ProgramGroup["years"] {
    const g = this.byIdentity.get(
      `${cutoff.institute_type}|${cutoff.institute_name}|${cutoff.program_name}|${cutoff.quota}|${cutoff.seat_type}|${cutoff.gender}`,
    );
    return g ? g.years : [];
  }
}

function identityOf(g: ProgramGroup): string {
  return `${g.instituteType}|${g.instituteName}|${g.programName}|${g.quota}|${g.seatType}|${g.gender}`;
}

function buildGroups(raw: RawDataset): ProgramGroup[] {
  const { rows, dict, institutes } = raw;
  const n = rows.close.length;

  // Group rows by program key; keys index into the dictionaries (no string work yet).
  const byKey = new Map<string, ProgramGroup>();
  for (let i = 0; i < n; i++) {
    // Mirror jars_lib's _KEY_COLS: (institute_type, institute_name, program, quota, seat,
    // gender). institute_type is per row because some institutes change type across years.
    const key = `${rows.itype[i]}|${rows.inst[i]}|${rows.prog[i]}|${rows.quota[i]}|${rows.seat[i]}|${rows.gender[i]}`;
    let g = byKey.get(key);
    if (g === undefined) {
      const inst = institutes[rows.inst[i]];
      g = {
        instituteType: dict.institute_types[rows.itype[i]],
        instituteName: dict.institutes[rows.inst[i]],
        instituteState: inst.state >= 0 ? dict.states[inst.state] : null,
        nirfRank: inst.nirf_rank,
        nirfScore: inst.nirf_score,
        programName: dict.programs[rows.prog[i]],
        quota: dict.quotas[rows.quota[i]],
        seatType: dict.seat_types[rows.seat[i]],
        gender: dict.genders[rows.gender[i]],
        years: [],
      };
      byKey.set(key, g);
    }
    g.years.push([rows.year[i], rows.round[i], rows.open[i], rows.close[i]]);
  }

  const groups = [...byKey.values()];

  // Sort each group's years most-recent first (mirrors recommend.py `reverse=True`).
  for (const g of groups) g.years.sort((a, b) => b[0] - a[0]);

  // Sort groups by the engine key columns ascending, matching pandas' sorted groupby.
  groups.sort(
    (a, b) =>
      cmp(a.instituteType, b.instituteType) ||
      cmp(a.instituteName, b.instituteName) ||
      cmp(a.programName, b.programName) ||
      cmp(a.quota, b.quota) ||
      cmp(a.seatType, b.seatType) ||
      cmp(a.gender, b.gender),
  );
  return groups;
}

function cmp(a: string, b: string): number {
  // Code-unit comparison, matching pandas' default lexicographic string ordering for ASCII.
  return a < b ? -1 : a > b ? 1 : 0;
}
