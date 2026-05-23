# Integration guide — wiring LongevityBench Design System into L-LLMBenchmarking

This guide lands the dashboard in your repo **without overlapping anything Inspect AI already does.**

## The clean separation

```
Inspect AI                            Dashboard (this design system)
─────────────                         ─────────────────────────────
runs the eval                         renders the eval
scores the samples                    visualises the scores
writes .eval log files                reads them (read-only)
ships `inspect view`                  ships a richer per-team viewer
```

The dashboard is a **static React app** that loads a single `data.json` file. The JSON is produced by `tools/export_inspect_logs.py` — a thin adapter that uses Inspect AI's public log-reading API (`inspect_ai.log.read_eval_log`). No re-running, no re-scoring, no duplicated logic.

## Setup (one time)

```bash
# 1. From the L-LLMBenchmarking repo root, drop the design system in:
cd L-LLMBenchmarking
unzip ~/Downloads/longevitybench-design-system.zip -d design-system

# 2. Copy the Inspect log bridge into your repo:
cp design-system/tools/export_inspect_logs.py tools/export_inspect_logs.py

# 3. Make sure inspect-ai is installed (it already is, since you use it):
.venv/bin/pip install inspect-ai pyyaml

# 4. Add to your repo's CLAUDE.md (snippet at the bottom of this file).
```

## Day-to-day loop

```bash
# Step 1 — run evals with Inspect AI (you already do this)
.venv/bin/python -m src.eval.run_inspect \
  --lb-id LB-0038 --limit 50 \
  --models longevity_llm,gemini_flash,deepseek_chat,claude_sonnet

# Step 2 — export the logs to dashboard JSON
.venv/bin/python -m tools.export_inspect_logs \
  --log-dir outputs/inspect \
  --out design-system/ui_kits/longevity_bench/public/data.json

# Step 3 — serve the static dashboard
cd design-system/ui_kits/longevity_bench
python -m http.server 8765
# open http://localhost:8765
```

For a tighter loop, alias step 2+3 in a Makefile:

```makefile
dashboard:
	python -m tools.export_inspect_logs \
	  --log-dir outputs/inspect \
	  --out design-system/ui_kits/longevity_bench/public/data.json
	cd design-system/ui_kits/longevity_bench && python -m http.server 8765
```

## Wire `data.json` into the dashboard

The current `data.jsx` in the kit uses seed data so the views render without a backend. To consume real Inspect logs, change the top of `data.jsx` to:

```jsx
// data.jsx — replace seed constants with a fetch on load.

const useDashboardData = () => {
  const [data, setData] = React.useState(null);
  React.useEffect(() => {
    fetch('./public/data.json')
      .then(r => r.ok ? r.json() : null)
      .then(setData)
      .catch(() => setData(null));
  }, []);
  return data;
};

// Fall back to seed mock if the fetch fails (e.g. first run, no eval yet).
const dataOrSeed = (data) => data || {
  models: SEED_MODELS, samples: SEED_SAMPLES, runs: SEED_RUNS, ...
};

Object.assign(window, { useDashboardData, dataOrSeed });
```

Then in `index.html` wrap `App` to read it:

```jsx
function App() {
  const live = useDashboardData();
  const data = dataOrSeed(live);
  // ...pass data.samples to <ResultsMatrix>, data.runs to <LiveRunsView>, etc.
}
```

## What does NOT belong in the dashboard

Anything Inspect AI already does. Specifically:

| Concern                        | Where it lives                       |
|--------------------------------|--------------------------------------|
| Provider abstraction           | `litellm_client.py` (existing)       |
| Task / solver / scorer         | `inspect_tasks/`, `inspect_scorers.py`, `inspect_solvers.py` |
| Concurrency / retries          | Inspect AI internals                 |
| Sample-level pass/fail logic   | `longebench_scorer()` in your code   |
| Log format                     | Inspect's `.eval` files (canonical)  |
| Single-run drilldown viewer    | `inspect view <log-dir>`             |

The dashboard's job is **aggregation, comparison, and trust-signals across multiple Inspect runs**. If you ever want a raw single-log viewer, just `inspect view outputs/inspect/longevity_llm/<run-id>.eval` — don't rebuild it here.

## The 4 dashboard views, mapped to your data

| Dashboard view     | Reads from Inspect log                                   |
|--------------------|----------------------------------------------------------|
| **Trust & reasoning** | `samples[*].cells[<model>].trace` + a future trace-scoring step writing `trace_scores[<model>]` |
| **Eval matrix**       | `samples` + `models` (Promptfoo-style row × col)        |
| **Compare models**    | `runs[*].scores` aggregated per `lb_id` × `model`       |
| **Live runs**         | `runs` filtered by `status == "running"` (you'd write status from a wrapper around `run_inspect.py`) |

## Trace scoring (extra credit per CLAUDE.md)

The dashboard reserves `trace_scores[<model>]` in the JSON schema for the bio-fact-checker pipeline described in your CLAUDE.md (NCBI / KEGG / WormBase / MGI / STRING-DB verifiers). When you build that, write its output as a second adapter:

```python
# tools/score_traces.py — runs after the eval, fills trace_scores
# Reads outputs/inspect/<model>/*.eval, extracts reasoning_content,
# calls NCBI/KEGG/etc., writes back into data.json under trace_scores.
```

The `TrustView` component already expects this shape and will light up automatically when it's populated.

## CLAUDE.md snippet to drop into your repo

Add this block near the top of `L-LLMBenchmarking/CLAUDE.md`:

````md
## Design system

For any UI work, slide deck, paper figure, or eval-site page, ground in
`design-system/` and follow it precisely. Specifically:

1. Read `design-system/README.md` for tone, voice, and visual rules
2. Link `design-system/colors_and_type.css` for tokens
3. Reuse components from `design-system/ui_kits/longevity_bench/`:
   - Layout: `Sidebar`, `TopBar`
   - Views: `TrustView`, `ResultsMatrix`, `CompareView`, `LiveRunsView`,
     `RunDetail`, `RecordDrawer`
   - Primitives: `Icon`, `Button`, `Badge`, `Pill`, `MetricCard`
4. Icons: brand glyphs in `design-system/assets/`, science icons in
   `design-system/assets/scicons/`. Never invent SVG illustrations.
5. Voice: scientific, terse, sentence-case, tabular numbers, green only
   for primary action / success / brand. No emoji, no marketing intensifiers.

## Dashboard pipeline (do NOT overlap with Inspect AI)

The dashboard is a static viewer on top of Inspect AI logs:

  run_inspect.py → outputs/inspect/<model>/*.eval
                 → tools/export_inspect_logs.py
                 → design-system/ui_kits/longevity_bench/public/data.json
                 → static React dashboard (just open index.html)

When extending evals, always write through Inspect AI's task/solver/scorer
APIs — never reimplement runners, scoring, or log parsing in the dashboard.
The dashboard reads, never executes.
````

## Caveats

- `tools/export_inspect_logs.py` calls `inspect_ai.log.read_eval_log` which is part of Inspect AI's public Python API — stable across patch versions but check release notes on major version bumps.
- The `.eval` log format is a SQLite-backed binary; we never read it directly, only through Inspect's reader.
- `data.json` can get large (several MB at 200 samples × 5 models with full traces). Consider sharding (`data.<lb_id>.json`) if it exceeds ~10 MB.
- The dashboard's seed mock data is intentionally similar to your real schema so the views work before your first export. Once you wire `useDashboardData`, delete the seed constants from `data.jsx`.
