/** Display formatters, mirroring the TUI's cell rendering (tui/jars_tui/app.py). */

import { bandInRange, bandYears } from "../engine";
import type { Recommendation } from "../engine";

/** Render a rank with the year it occurred, e.g. "1 (2024)". TUI: _fmt_rank_year. */
export function fmtRankYear(value: number | null, year: number | null): string {
  if (value === null) return "—";
  return year !== null ? `${value.toLocaleString("en-IN")} (${year})` : value.toLocaleString("en-IN");
}

/** Render a band of years, prefixing "~" for reach (near-window) years. TUI: _fmt_years. */
export function fmtYears(years: number[], reach: boolean): string {
  if (years.length === 0) return "—";
  const body = years.length === 1 ? String(years[0]) : `(${years.join(", ")})`;
  return reach ? `~${body}` : body;
}

export function fmtBandYears(r: Recommendation): string {
  return fmtYears(bandYears(r), !bandInRange(r));
}

export function fmtChance(feasibility: number): string {
  return `${Math.round(feasibility * 100)}%`;
}

/** A coarse colour band for the admit chance, for subtle visual cueing. */
export function chanceTone(feasibility: number): string {
  if (feasibility >= 0.66) return "text-emerald-600 dark:text-emerald-400";
  if (feasibility >= 0.33) return "text-amber-600 dark:text-amber-400";
  return "text-rose-600 dark:text-rose-400";
}

export const TREND_LABEL: Record<string, string> = {
  easing: "Easing",
  tighter: "Tighter",
  stable: "Stable",
};

export function trendTone(trend: string | null): string {
  if (trend === "easing") return "text-emerald-600 dark:text-emerald-400";
  if (trend === "tighter") return "text-rose-600 dark:text-rose-400";
  return "text-slate-500 dark:text-slate-400";
}
