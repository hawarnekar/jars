# jars — JEE Admission Recommendation System

**jars** recommends engineering colleges and programs from your JEE rank, using historical
JoSAA opening/closing ranks (IITs, NITs, IIITs, GFTIs) and NIRF Engineering rankings.

This repository is a monorepo with two front-ends over the same recommendation logic:

| Directory | What it is |
|---|---|
| [`jars-cli/`](jars-cli/) | The Python library (`jars_lib`), the Textual TUI (`jars`), the JoSAA/NIRF scraper, and the local dataset. This is the source of truth for the data and the recommendation algorithm. |
| [`jars-web/`](jars-web/) | A static web UI hosted on GitHub Pages. The recommendation engine is ported to TypeScript and runs entirely in the browser against a compact dataset pre-built from `jars-cli`. |

## Web app

Live site: **https://hawarnekar.github.io/jars/**

The web app is **read-only**: it has no scraper or "update" action. Its dataset is generated
offline from `jars-cli` and committed to the repo. To refresh the published data:

```bash
# 1. Update the local dataset (in jars-cli)
cd jars-cli && jars-lib update            # or a scoped slice, see jars-cli/README.md

# 2. Regenerate the web dataset + parity fixtures
cd ../jars-web && npm run gen:data        # wraps jars-cli/tools/build_web_data.py

# 3. Commit and push — GitHub Actions rebuilds and redeploys Pages
git add -A && git commit -m "data: refresh JoSAA/NIRF" && git push
```

See [`jars-cli/README.md`](jars-cli/README.md) and [`jars-web/README.md`](jars-web/README.md)
for details.

## Disclaimer

jars is an **unofficial** tool, not affiliated with JoSAA, NIRF, or any institute. Its
recommendations are based only on historical cutoff ranks and NIRF rankings — a guide for
shortlisting, **not** a guarantee of admission. Always verify against the official JoSAA
portal before making decisions.
