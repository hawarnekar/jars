/** Notes & disclaimers: an always-visible essentials strip + a collapsible full panel. */

import { useState } from "react";
import { ALL_NOTES, ESSENTIAL_NOTES } from "../content/notes";

interface Props {
  /** Optional data-currency line, e.g. "Data last updated 3 Jun 2026 · NIRF 2025". */
  dataCurrency?: string | null;
}

export function Notes({ dataCurrency }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <section className="space-y-3">
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-900/60 dark:bg-amber-950/40">
        <ul className="space-y-1.5">
          {ESSENTIAL_NOTES.map((n) => (
            <li key={n.title} className="text-amber-900 dark:text-amber-200">
              <span className="font-semibold">{n.title}.</span>{" "}
              <span className="text-amber-800/90 dark:text-amber-200/80">{n.body}</span>
            </li>
          ))}
        </ul>
        <button
          className="mt-2 text-xs font-medium text-amber-900 underline underline-offset-2 hover:text-amber-700 dark:text-amber-200"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
        >
          {open ? "Hide details" : "How this works & important notes"}
        </button>
      </div>

      {open && (
        <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm shadow-sm dark:border-slate-800 dark:bg-slate-900">
          {dataCurrency && (
            <p className="mb-3 text-xs font-medium text-slate-500 dark:text-slate-400">
              {dataCurrency}
            </p>
          )}
          <dl className="grid gap-3 sm:grid-cols-2">
            {ALL_NOTES.map((n) => (
              <div key={n.title}>
                <dt className="font-semibold text-slate-800 dark:text-slate-200">{n.title}</dt>
                <dd className="mt-0.5 text-slate-600 dark:text-slate-400">{n.body}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </section>
  );
}
