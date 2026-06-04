/** Filter form state and its mapping to engine RecommendParams. */

import { GENDER_FEMALE, GENDER_NEUTRAL } from "../engine";
import type { RecommendParams } from "../engine";

/** UI filter state. Ranks/range are kept as strings so the inputs can be empty/partial. */
export interface Filters {
  advRank: string;
  mainsRank: string;
  range: string;
  /** Seat type / category, e.g. "OPEN", "OBC-NCL". */
  category: string;
  female: boolean;
  /** Home state name, or "" for "no home state (show both HS and OS)". */
  homeState: string;
  /** "ALL" or one of INSTITUTE_TYPES. */
  instituteType: string;
}

export const DEFAULT_FILTERS: Filters = {
  advRank: "",
  mainsRank: "",
  range: "2000",
  category: "OPEN",
  female: false,
  homeState: "",
  instituteType: "ALL",
};

/** Max results to compute — matches the TUI's cap. */
export const RESULT_LIMIT = 300;

export interface ValidationError {
  message: string;
}

function parseOptInt(value: string): number | null {
  const v = value.trim();
  if (v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : NaN;
}

/**
 * Convert UI filters to engine params, or return a validation error.
 * Mirrors the CLI/TUI rules: at least one rank, ranks/range must be valid integers.
 */
export function toRecommendParams(f: Filters): RecommendParams | ValidationError {
  const adv = parseOptInt(f.advRank);
  const mains = parseOptInt(f.mainsRank);
  const range = parseOptInt(f.range);

  if (Number.isNaN(adv) || Number.isNaN(mains) || Number.isNaN(range)) {
    return { message: "Ranks and range must be whole numbers." };
  }
  if (adv === null && mains === null) {
    return {
      message:
        "Enter at least one rank: JEE Advanced (for IITs) or JEE Mains (for NITs/IIITs/GFTIs).",
    };
  }
  if (adv !== null && adv <= 0) return { message: "JEE Advanced rank must be positive." };
  if (mains !== null && mains <= 0) return { message: "JEE Mains rank must be positive." };
  if (range === null || range < 0) return { message: "± range must be zero or more." };

  return {
    rankRange: range,
    jeeAdvRank: adv,
    jeeMainsRank: mains,
    seatType: f.category,
    gender: f.female ? GENDER_FEMALE : GENDER_NEUTRAL,
    homeState: f.homeState || null,
    instituteTypes: f.instituteType === "ALL" ? null : new Set([f.instituteType]),
    year: null,
    limit: RESULT_LIMIT,
  };
}

export function isValidationError(x: RecommendParams | ValidationError): x is ValidationError {
  return (x as ValidationError).message !== undefined;
}
