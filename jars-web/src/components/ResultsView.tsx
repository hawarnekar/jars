/** Sortable, expandable results — a table on wider screens, cards on mobile. */

import { Fragment, useState } from "react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getExpandedRowModel,
  getSortedRowModel,
  useReactTable,
  type ExpandedState,
  type SortingState,
} from "@tanstack/react-table";
import type { Dataset, Recommendation } from "../engine";
import {
  chanceTone,
  fmtBandYears,
  fmtChance,
  fmtRankYear,
  TREND_LABEL,
  trendTone,
} from "../lib/format";
import { RowDetail } from "./RowDetail";

const col = createColumnHelper<Recommendation>();

const columns = [
  col.accessor((r) => r.cutoff.institute_name, {
    id: "institute",
    header: "Institute",
    cell: (c) => <span className="font-medium">{c.getValue()}</span>,
  }),
  col.accessor((r) => r.cutoff.program_name, { id: "program", header: "Program" }),
  col.accessor((r) => r.cutoff.seat_type, { id: "category", header: "Category" }),
  col.accessor((r) => r.cutoff.quota, { id: "quota", header: "Quota" }),
  col.accessor((r) => r.opening_rank_min ?? undefined, {
    id: "open",
    header: "Open",
    sortUndefined: "last",
    cell: (c) => fmtRankYear(c.row.original.opening_rank_min, c.row.original.opening_rank_min_year),
  }),
  col.accessor((r) => r.closing_rank_max ?? undefined, {
    id: "close",
    header: "Close",
    sortUndefined: "last",
    cell: (c) => fmtRankYear(c.row.original.closing_rank_max, c.row.original.closing_rank_max_year),
  }),
  col.accessor((r) => (r.in_range_years[0] ?? r.window_years[0]) ?? undefined, {
    id: "years",
    header: "Years",
    sortUndefined: "last",
    cell: (c) => fmtBandYears(c.row.original),
  }),
  col.accessor((r) => r.nirf_rank ?? undefined, {
    id: "nirf",
    header: "NIRF",
    sortUndefined: "last",
    cell: (c) => c.row.original.nirf_rank ?? "—",
  }),
  col.accessor((r) => r.feasibility, {
    id: "chance",
    header: "Chance",
    cell: (c) => (
      <span className={chanceTone(c.getValue())}>{fmtChance(c.getValue())}</span>
    ),
  }),
  col.accessor((r) => r.closing_rank_trend ?? undefined, {
    id: "trend",
    header: "Trend",
    sortUndefined: "last",
    cell: (c) => {
      const t = c.row.original.closing_rank_trend;
      return <span className={trendTone(t)}>{t ? TREND_LABEL[t] ?? t : "—"}</span>;
    },
  }),
];

interface Props {
  results: Recommendation[];
  dataset: Dataset;
}

export function ResultsView({ results, dataset }: Props) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [expanded, setExpanded] = useState<ExpandedState>({});

  const table = useReactTable({
    data: results,
    columns,
    state: { sorting, expanded },
    onSortingChange: setSorting,
    onExpandedChange: setExpanded,
    getRowCanExpand: () => true,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
  });

  const rows = table.getRowModel().rows;

  return (
    <div>
      {/* Desktop / tablet: table */}
      <div className="hidden overflow-x-auto rounded-lg border border-slate-200 md:block dark:border-slate-800">
        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
          <thead className="bg-slate-50 dark:bg-slate-900">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                <th className="w-8" />
                {hg.headers.map((h) => (
                  <th
                    key={h.id}
                    onClick={h.column.getToggleSortingHandler()}
                    className="cursor-pointer select-none px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                  >
                    {flexRender(h.column.columnDef.header, h.getContext())}
                    {{ asc: " ▲", desc: " ▼" }[h.column.getIsSorted() as string] ?? ""}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800/70">
            {rows.map((row) => (
              <Fragment key={row.id}>
                <tr
                  className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-900/50"
                  onClick={row.getToggleExpandedHandler()}
                >
                  <td className="px-2 text-center text-slate-400">
                    {row.getIsExpanded() ? "▾" : "▸"}
                  </td>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-2 align-top tabular-nums">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
                {row.getIsExpanded() && (
                  <tr>
                    <td colSpan={row.getVisibleCells().length + 1} className="p-0">
                      <RowDetail rec={row.original} dataset={dataset} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile: cards */}
      <ul className="space-y-3 md:hidden">
        {rows.map((row) => {
          const r = row.original;
          return (
            <li
              key={row.id}
              className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900"
            >
              <button
                className="w-full text-left"
                onClick={row.getToggleExpandedHandler()}
              >
                <div className="font-medium">{r.cutoff.institute_name}</div>
                <div className="text-sm text-slate-600 dark:text-slate-300">
                  {r.cutoff.program_name}
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
                  <span>{r.cutoff.seat_type} · {r.cutoff.quota}</span>
                  <span>Close {fmtRankYear(r.closing_rank_max, r.closing_rank_max_year)}</span>
                  <span>NIRF {r.nirf_rank ?? "—"}</span>
                  <span className={chanceTone(r.feasibility)}>{fmtChance(r.feasibility)}</span>
                  <span className={trendTone(r.closing_rank_trend)}>
                    {r.closing_rank_trend ? TREND_LABEL[r.closing_rank_trend] : "—"}
                  </span>
                </div>
              </button>
              {row.getIsExpanded() && (
                <div className="mt-3 -mx-3 -mb-3 overflow-hidden rounded-b-lg">
                  <RowDetail rec={r} dataset={dataset} />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
