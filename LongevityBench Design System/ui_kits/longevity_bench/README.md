# LongevityBench — UI Kit

Interactive recreation of the LongevityBench evaluation dashboard. Inferred from the data model in `src/eval/longebench_runner.py` (records + summary JSON), Insilico Medicine's visual language, and the hackathon track spec.

Open [`index.html`](index.html) for the click-thru.

## Screens
1. **Runs list** — recent benchmark runs, status, scores at a glance
2. **Run detail** — metric cards, model comparison chart, full records table
3. **Record panel** — drill into a single prompt: messages, gold, response, `<think>` trace, verified entities
4. **New run** — modal for configuring an evaluation (task ID, model, concurrency, thinking mode)

## Components
- `TopBar` — search, run CTA, profile chip
- `Sidebar` — left nav with task ID hotkeys
- `MetricCard` — F1 / balanced acc / MAE / faithfulness tiles
- `RecordsTable` — sortable records table with status, gene symbols, latency
- `RunsTable` — list of past runs with sparkline + result chips
- `ModelBar` — comparison chart for L-LLM vs GPT-4o vs baselines
- `TracePanel` — model `<think>` trace with verified entity highlighting
- `Button`, `Badge`, `Pill`, `Input` — primitives
- `NewRunModal` — config form
