/** Expanded per-program detail: full year-by-year opening/closing history + metrics. */

import type { Dataset, Recommendation } from "../engine";

interface Props {
  rec: Recommendation;
  dataset: Dataset;
}

export function RowDetail({ rec, dataset }: Props) {
  const years = dataset.yearsFor(rec.cutoff); // most-recent first: [year, round, open, close]

  return (
    <div className="bg-slate-50 px-4 py-3 text-sm dark:bg-slate-900/60">
      <div className="grid gap-4 md:grid-cols-[1fr_auto]">
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Year-by-year cutoffs (final round)
          </h4>
          <div className="overflow-x-auto">
            <table className="text-xs">
              <thead>
                <tr className="text-slate-500 dark:text-slate-400">
                  <th className="px-2 py-1 text-left font-medium">Year</th>
                  {years.map(([y]) => (
                    <th key={y} className="px-2 py-1 text-right font-medium">
                      {y}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="px-2 py-1 text-left text-slate-500 dark:text-slate-400">Open</td>
                  {years.map(([y, , open]) => (
                    <td key={y} className="px-2 py-1 text-right tabular-nums">
                      {open === null ? "—" : open.toLocaleString("en-IN")}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="px-2 py-1 text-left text-slate-500 dark:text-slate-400">Close</td>
                  {years.map(([y, , , close]) => (
                    <td key={y} className="px-2 py-1 text-right tabular-nums font-medium">
                      {close.toLocaleString("en-IN")}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <dl className="space-y-1 text-xs">
          <Metric label="Match score" value={(rec.score * 100).toFixed(1)} />
          <Metric label="Chance" value={`${Math.round(rec.feasibility * 100)}%`} />
          <Metric
            label="Wtd. closing"
            value={rec.rank_closing !== null ? Math.round(rec.rank_closing).toLocaleString("en-IN") : "—"}
          />
          <Metric
            label="Wtd. opening"
            value={rec.rank_opening !== null ? Math.round(rec.rank_opening).toLocaleString("en-IN") : "—"}
          />
          <Metric label="NIRF rank" value={rec.nirf_rank ?? "—"} />
          <Metric label="NIRF score" value={rec.nirf_score ?? "—"} />
        </dl>
      </div>
      <p className="mt-2 text-xs text-slate-400">
        “Match score” is jars' weighted ranking key (NIRF » closing » opening). “Chance” is a
        recency-weighted admit likelihood and does not affect ordering.
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between gap-6 md:w-48">
      <dt className="text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="font-medium tabular-nums">{value}</dd>
    </div>
  );
}
