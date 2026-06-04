import { useEffect, useMemo, useRef, useState } from "react";
import { recommend } from "./engine";
import type { Recommendation } from "./engine";
import { useDataset } from "./hooks/useDataset";
import { useDarkMode } from "./hooks/useDarkMode";
import { FilterForm } from "./components/FilterForm";
import { ResultsView } from "./components/ResultsView";
import { Notes } from "./components/Notes";
import { isValidationError, toRecommendParams, type Filters } from "./state/filters";
import {
  filtersFromSearch,
  filtersToSearch,
  searchHasRank,
  writeSearch,
} from "./lib/urlState";

export default function App() {
  const { dataset, loading, error } = useDataset();
  const [dark, toggleDark] = useDarkMode();
  const [filters, setFilters] = useState<Filters>(() =>
    filtersFromSearch(window.location.search),
  );
  const [results, setResults] = useState<Recommendation[] | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const autoRan = useRef(false);

  const runSearch = (f: Filters = filters) => {
    if (!dataset) return;
    const params = toRecommendParams(f);
    if (isValidationError(params)) {
      setFormError(params.message);
      setResults(null);
      return;
    }
    setFormError(null);
    setResults(recommend(dataset, params));
    writeSearch(filtersToSearch(f));
    setCopied(false);
  };

  // Auto-run once when arriving via a shared link that already carries a rank.
  useEffect(() => {
    if (dataset && !autoRan.current && searchHasRank(window.location.search)) {
      autoRan.current = true;
      runSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset]);

  const dataCurrency = useMemo(() => {
    const lu = dataset?.meta.last_updated;
    const ny = dataset?.meta.nirf_year;
    if (!lu) return null;
    const d = new Date(lu);
    const date = Number.isNaN(d.getTime()) ? String(lu) : d.toLocaleDateString();
    return `Data last updated ${date}${ny ? ` · NIRF ${ny}` : ""}.`;
  }, [dataset]);

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable — ignore */
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight">jars</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              JEE Admission Recommendation System
            </p>
          </div>
          <button
            onClick={toggleDark}
            aria-label="Toggle dark mode"
            className="rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {dark ? "☀ Light" : "☾ Dark"}
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6">
        <Notes dataCurrency={dataCurrency} />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[20rem_1fr]">
          <aside className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 lg:sticky lg:top-6 lg:self-start">
            <FilterForm
              filters={filters}
              onChange={setFilters}
              onSubmit={() => runSearch()}
              disabled={loading || !!error}
            />
            {formError && (
              <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-200">
                {formError}
              </p>
            )}
          </aside>

          <section>
            {loading && <p className="text-sm text-slate-500">Loading data…</p>}
            {error && (
              <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
                Could not load the dataset: {error}. Please refresh to try again.
              </p>
            )}
            {!loading && !error && results === null && (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Enter your rank and press <strong>Recommend</strong> to see matching programs.
              </p>
            )}
            {results !== null && dataset && (
              <>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-sm text-slate-600 dark:text-slate-300">
                    {results.length} matching {results.length === 1 ? "program" : "programs"}
                    {results.length > 0 && (
                      <span className="text-slate-400"> · click a row for detail</span>
                    )}
                  </p>
                  {results.length > 0 && (
                    <button
                      onClick={copyLink}
                      className="shrink-0 rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                    >
                      {copied ? "Link copied ✓" : "Copy shareable link"}
                    </button>
                  )}
                </div>
                {results.length === 0 ? (
                  <p className="rounded-md bg-slate-100 px-4 py-3 text-sm text-slate-600 dark:bg-slate-900 dark:text-slate-300">
                    No programs matched. Try widening the ± range, changing the category, or
                    checking that you entered the right rank (Advanced for IITs, Mains for the
                    rest).
                  </p>
                ) : (
                  <ResultsView results={results} dataset={dataset} />
                )}
              </>
            )}
          </section>
        </div>
      </main>

      <footer className="mx-auto max-w-7xl px-4 py-8 text-xs text-slate-400">
        jars is an unofficial guide. Verify everything on the official JoSAA portal.
        {" · "}
        <a
          className="underline underline-offset-2 hover:text-slate-600 dark:hover:text-slate-300"
          href="https://josaa.nic.in/"
          target="_blank"
          rel="noopener noreferrer"
        >
          josaa.nic.in
        </a>
      </footer>
    </div>
  );
}
