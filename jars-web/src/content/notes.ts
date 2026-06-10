/** User-facing notes & disclaimers. Edit copy here without touching components.
 *
 * ESSENTIAL_NOTES surface in an always-visible strip; ALL_NOTES populate the collapsible
 * "How this works / Important notes" panel. The data-currency line is rendered separately
 * from dataset meta (see App).
 */

export interface Note {
  title: string;
  body: string;
}

/** Shown prominently at all times. */
export const ESSENTIAL_NOTES: Note[] = [
  {
    title: "A guide, not a guarantee",
    body:
      "Past cutoffs do not predict future ones. Actual closing ranks shift every year with the number of applicants, seat-matrix changes, and counselling dynamics. Use these results to shortlist and explore — never as a promise of admission.",
  },
  {
    title: "Unofficial tool",
    body:
      "jars is not affiliated with JoSAA, NIRF, the IITs/NITs/IIITs/GFTIs, or any government body. Always verify against the official JoSAA portal and institute websites before making any decision.",
  },
];

/** The full set, shown in the collapsible panel (includes the essentials first). */
export const ALL_NOTES: Note[] = [
  ...ESSENTIAL_NOTES,
  {
    title: "How recommendations are made",
    body:
      "Suggestions are based only on historical JoSAA opening and closing ranks and each institute's NIRF Engineering ranking. No other factors — placements, fees, location, faculty, or personal preferences — are considered.",
  },
  {
    title: "Newly introduced courses aren't shown",
    body:
      "Programs launched recently have no past cutoff data, so they cannot be ranked or recommended here, even if they may be a good fit. Check the official JoSAA seat matrix for the latest list of programs.",
  },
  {
    title: '"Chance" is an estimate, not a probability',
    body:
      "The Chance figure is a recency-weighted indication of how comfortably your rank cleared past closing ranks. It does not model round-by-round movement, withdrawals, or seat upgrades during counselling.",
  },
  {
    title: "Enter the correct rank",
    body:
      "IIT seats use your JEE Advanced rank; NIT/IIIT/GFTI seats use your JEE Mains (CRL) rank. These are different scales — entering one in place of the other will give misleading results.",
  },
  {
    title: "How results are ordered",
    body:
      "Results are ranked by a weighted score: NIRF rank (highest weight), then recency-weighted closing rank, then opening rank. This is jars' own heuristic, not an official ranking.",
  },
  {
    title: "Institutes without a NIRF rank appear lower",
    body:
      "NIRF covers only the Engineering list, and it's the primary sort key — so an institute absent from NIRF (shown as “Unranked” in the NIRF column) sorts below NIRF-listed ones, even when its cutoffs are competitive. A missing NIRF rank does not mean the institute is poor.",
  },
  {
    title: "Home-state quota depends on your domicile",
    body:
      "When you set a home state, HS quota is shown for institutes in that state and OS quota elsewhere. Confirm your actual domicile eligibility on the official portal — quota rules can be nuanced.",
  },
];

/** Short tooltips for result columns whose meaning isn't obvious from the header. */
export const COLUMN_TOOLTIPS: Record<string, string> = {
  open: "Smallest opening rank across the shown years (with the year it occurred).",
  close: "Largest closing rank across the shown years (with the year it occurred).",
  years:
    "Years your rank fell within that program's opening–closing band. A ~ prefix marks near-window reach years your rank did not clear.",
  nirf: "NIRF Engineering rank (1 = best). “Unranked” means the institute is not in the NIRF list — it gets no NIRF credit in the ranking score, so it sorts lower even with competitive cutoffs.",
  chance:
    "Recency-weighted admit likelihood — how comfortably your rank cleared past closing ranks. Display only; does not affect ordering.",
  trend:
    "Direction of the closing rank over recent years: Easing (more accessible), Tighter (more competitive), or Stable.",
};
