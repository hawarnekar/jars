/** Loads the compact dataset once and builds the engine Dataset. */

import { useEffect, useState } from "react";
import { Dataset } from "../engine";
import type { RawDataset } from "../engine";

// Versioned filename so the browser can cache aggressively and bust on a new schema.
const DATA_URL = `${import.meta.env.BASE_URL}data/cutoffs.v1.json`;

export interface DatasetState {
  dataset: Dataset | null;
  loading: boolean;
  error: string | null;
}

export function useDataset(): DatasetState {
  const [state, setState] = useState<DatasetState>({
    dataset: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(DATA_URL);
        if (!res.ok) throw new Error(`Failed to load data (HTTP ${res.status}).`);
        const raw = (await res.json()) as RawDataset;
        const dataset = new Dataset(raw);
        if (!cancelled) setState({ dataset, loading: false, error: null });
      } catch (e) {
        if (!cancelled) {
          setState({
            dataset: null,
            loading: false,
            error: e instanceof Error ? e.message : "Could not load the dataset.",
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
