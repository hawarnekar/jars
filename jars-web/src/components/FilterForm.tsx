/** The recommendation filter form — full parity with the CLI/TUI inputs. */

import { INDIAN_STATES, INSTITUTE_TYPES, SEAT_TYPES } from "../engine";
import type { Filters } from "../state/filters";

interface Props {
  filters: Filters;
  onChange: (next: Filters) => void;
  onSubmit: () => void;
  disabled?: boolean;
}

const labelCls = "block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1";
const inputCls =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 " +
  "shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 " +
  "dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";

export function FilterForm({ filters, onChange, onSubmit, disabled }: Props) {
  const set = <K extends keyof Filters>(key: K, value: Filters[K]) =>
    onChange({ ...filters, [key]: value });

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <div>
        <label className={labelCls} htmlFor="advRank">
          JEE Advanced rank <span className="text-slate-400">(for IITs)</span>
        </label>
        <input
          id="advRank"
          inputMode="numeric"
          className={inputCls}
          placeholder="e.g. 3000 — leave blank if N/A"
          value={filters.advRank}
          onChange={(e) => set("advRank", e.target.value)}
        />
      </div>

      <div>
        <label className={labelCls} htmlFor="mainsRank">
          JEE Mains rank / CRL <span className="text-slate-400">(for NITs/IIITs/GFTIs)</span>
        </label>
        <input
          id="mainsRank"
          inputMode="numeric"
          className={inputCls}
          placeholder="e.g. 25000 — leave blank if N/A"
          value={filters.mainsRank}
          onChange={(e) => set("mainsRank", e.target.value)}
        />
      </div>

      <div>
        <label className={labelCls} htmlFor="range">
          ± rank range
        </label>
        <input
          id="range"
          inputMode="numeric"
          className={inputCls}
          value={filters.range}
          onChange={(e) => set("range", e.target.value)}
        />
      </div>

      <div>
        <label className={labelCls} htmlFor="category">
          Category (seat type)
        </label>
        <select
          id="category"
          className={inputCls}
          value={filters.category}
          onChange={(e) => set("category", e.target.value)}
        >
          {SEAT_TYPES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          checked={filters.female}
          onChange={(e) => set("female", e.target.checked)}
        />
        Include female-only seats
      </label>

      <div>
        <label className={labelCls} htmlFor="homeState">
          Home state <span className="text-slate-400">(for HS/OS quota)</span>
        </label>
        <select
          id="homeState"
          className={inputCls}
          value={filters.homeState}
          onChange={(e) => set("homeState", e.target.value)}
        >
          <option value="">No home state — show both</option>
          {INDIAN_STATES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className={labelCls} htmlFor="instituteType">
          Institute types
        </label>
        <select
          id="instituteType"
          className={inputCls}
          value={filters.instituteType}
          onChange={(e) => set("instituteType", e.target.value)}
        >
          <option value="ALL">All</option>
          {INSTITUTE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <button
        type="submit"
        disabled={disabled}
        className="w-full rounded-md bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:focus:ring-offset-slate-900"
      >
        Recommend
      </button>
    </form>
  );
}
