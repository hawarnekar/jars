# jars-web

The static web UI for **jars** — the JEE Admission Recommendation System. Live at
**https://hawarnekar.github.io/jars/**.

It runs entirely in the browser: the recommendation engine is a TypeScript port of the
`jars_lib` Python engine, and the data is a compact file pre-built from the same library.
There is **no backend** and **no data-update feature** here — the site is read-only (see
[Refreshing the data](#refreshing-the-data)).

## Stack

- **React + TypeScript + Vite** (static build, `base: '/jars/'` for project Pages)
- **Tailwind CSS** (light/dark)
- **TanStack Table** for the sortable, expandable results
- **Vitest** for the engine parity tests

## How it works

```
jars-cli/data/cutoffs.parquet  (523k rows)
        │  tools/build_web_data.py  (reuses jars_lib._yearly_reps + NIRF lookup)
        ▼
jars-web/public/data/cutoffs.v1.json   (~88k rows, columnar + dictionary-encoded, ~0.5 MB gz)
        │  src/engine/  (TypeScript port of jars_lib/recommend.py + engine.py)
        ▼
            ranked recommendations, in the browser
```

The TS engine in `src/engine/` mirrors `jars_lib` function-for-function. Its correctness is
guaranteed by **golden parity tests** (`tests/engine.parity.test.ts`): the build step emits
`tests/golden/golden.json` containing query specs and the *Python* engine's output for each,
and the tests assert the TS engine reproduces them exactly. If the Python algorithm changes,
regenerate the data + goldens and the tests will flag any divergence.

## Develop

```bash
cd jars-web
npm install
npm run dev          # http://localhost:5173/jars/
```

Useful scripts:

| Script | What it does |
|---|---|
| `npm run dev` | Vite dev server |
| `npm test` | Vitest (engine + golden parity) |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run build` | Type-check + production build to `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run gen:data` | Regenerate the dataset + goldens from `jars-cli` |

## Refreshing the data

The dataset is committed to the repo and only changes when the maintainer republishes it:

```bash
# 1. Update the local dataset (in jars-cli) — requires the scraper extras
cd jars-cli && jars-lib update            # or a scoped slice, see jars-cli/README.md

# 2. Regenerate the web dataset + parity fixtures
cd ../jars-web && npm run gen:data

# 3. Commit and push — the deploy Action rebuilds and redeploys Pages
git add -A && git commit -m "data: refresh JoSAA/NIRF" && git push
```

## Deploy

`.github/workflows/deploy-web.yml` builds this app and deploys it to GitHub Pages on pushes
to the default branch that touch `jars-web/**`. One-time setup: in the GitHub repo, go to
**Settings → Pages → Build and deployment → Source: GitHub Actions**.

## Project layout

```
src/
  engine/        TypeScript port of the recommendation engine (+ parity-critical constants)
  components/    FilterForm, ResultsView, RowDetail, Notes
  hooks/         useDataset (loads + decodes the dataset), useDarkMode
  lib/           formatters, URL/query-string state
  content/       notes & disclaimers copy, column tooltips
  state/         filter model + validation
public/data/     committed, generated dataset (cutoffs.v1.json)
tests/           engine parity tests + golden fixtures
```
