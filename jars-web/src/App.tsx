import { useMemo, useState } from "react";
import { recommend } from "./engine";
import type { Recommendation } from "./engine";
import { useDataset } from "./hooks/useDataset";
import { FilterForm } from "./components/FilterForm";
import { ResultsView } from "./components/ResultsView";
import {
  DEFAULT_FILTERS,
  isValidationError,
  toRecommendParams,
  type Filters,
} from "./state/filters";

export default function App() {
  const { dataset, loading, error } = useDataset();
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [results, setResults] = useState<Recommendation[] | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const lastUpdated = dataset?.meta.last_updated;
  const nirfYear = dataset?.meta.nirf_year;

  const runSearch = () => {
    if (!dataset) return;
    const params = toRecommendParams(filters);
    if (isValidationError(params)) {
      setFormError(params.message);
      setResults(null);
      return;
    }
    setFormError(null);
    setResults(recommend(dataset, params));
  };

  const freshness = useMemo(() => {
    if (!lastUpdated) return null;
    const d = new Date(lastUpdated);
    return Number.isNaN(d.getTime()) ? String(lastUpdated) : d.toLocaleDateString();
  }, [lastUpdated]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto max-w-7xl px-4 py-4">
          <h1 className="text-xl font-bold tracking-tight">jars</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            JEE Admission Recommendation System
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[20rem_1fr]">
          <aside className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <FilterForm
              filters={filters}
              onChange={setFilters}
              onSubmit={runSearch}
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
                Could not load the dataset: {error}
              </p>
            )}
            {!loading && !error && results === null && (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Enter your rank and press <strong>Recommend</strong> to see matching programs.
              </p>
            )}
            {results !== null && dataset && (
              <>
                <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">
                  {results.length} matching {results.length === 1 ? "program" : "programs"}
                  {results.length > 0 && (
                    <span className="text-slate-400"> · click a row for year-by-year detail</span>
                  )}
                </p>
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

      <footer className="mx-auto max-w-7xl px-4 py-6 text-xs text-slate-400">
        {freshness && (
          <span>
            Data last updated {freshness}
            {nirfYear ? ` · NIRF ${nirfYear}` : ""} · An unofficial guide, not a guarantee.
          </span>
        )}
      </footer>
    </div>
  );
}
