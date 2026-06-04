/** Serialise filter state to/from the URL query string for shareable result links.
 *
 * Only non-default values are written, keeping links short. The path (including the /jars/
 * base) is preserved — we only touch the search string.
 */

import { DEFAULT_FILTERS, type Filters } from "../state/filters";

const KEYS = {
  advRank: "adv",
  mainsRank: "mains",
  range: "range",
  category: "cat",
  female: "female",
  homeState: "hs",
  instituteType: "type",
} as const;

export function filtersToSearch(f: Filters): string {
  const sp = new URLSearchParams();
  if (f.advRank.trim()) sp.set(KEYS.advRank, f.advRank.trim());
  if (f.mainsRank.trim()) sp.set(KEYS.mainsRank, f.mainsRank.trim());
  if (f.range.trim() && f.range !== DEFAULT_FILTERS.range) sp.set(KEYS.range, f.range.trim());
  if (f.category !== DEFAULT_FILTERS.category) sp.set(KEYS.category, f.category);
  if (f.female) sp.set(KEYS.female, "1");
  if (f.homeState) sp.set(KEYS.homeState, f.homeState);
  if (f.instituteType !== DEFAULT_FILTERS.instituteType) sp.set(KEYS.instituteType, f.instituteType);
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export function filtersFromSearch(search: string): Filters {
  const sp = new URLSearchParams(search);
  return {
    advRank: sp.get(KEYS.advRank) ?? DEFAULT_FILTERS.advRank,
    mainsRank: sp.get(KEYS.mainsRank) ?? DEFAULT_FILTERS.mainsRank,
    range: sp.get(KEYS.range) ?? DEFAULT_FILTERS.range,
    category: sp.get(KEYS.category) ?? DEFAULT_FILTERS.category,
    female: sp.get(KEYS.female) === "1",
    homeState: sp.get(KEYS.homeState) ?? DEFAULT_FILTERS.homeState,
    instituteType: sp.get(KEYS.instituteType) ?? DEFAULT_FILTERS.instituteType,
  };
}

/** True if the URL carries at least one rank (so a shared link can auto-run). */
export function searchHasRank(search: string): boolean {
  const sp = new URLSearchParams(search);
  return !!(sp.get(KEYS.advRank) || sp.get(KEYS.mainsRank));
}

/** Update the address bar in place (no history entry), preserving path + base. */
export function writeSearch(search: string): void {
  const url = new URL(window.location.href);
  url.search = search;
  window.history.replaceState(null, "", url.toString());
}
