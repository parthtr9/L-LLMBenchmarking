# CLAUDE.md — LongevityBench-X

Collaborative coding guide for the Caltech Longevity Hackathon, Track 01 · LongevityLLM Benchmarking.
Sponsored by Insilico Medicine. Prize: $1,000 + co-authorship on a peer-reviewed publication.

---

## Design system

For any UI work, slide deck, paper figure, or eval-site page, ground in
`LongevityBench Design System/` and follow it precisely. Specifically:

1. Read `LongevityBench Design System/README.md` for tone, voice, and visual rules
2. Link `LongevityBench Design System/colors_and_type.css` for tokens
3. Reuse components from `LongevityBench Design System/ui_kits/longevity_bench/`:
   - Layout: `Sidebar`, `TopBar`
   - Views: `TrustView`, `ResultsMatrix`, `CompareView`, `LiveRunsView`, `RunDetail`, `RecordDrawer`
   - Primitives: `Icon`, `Button`, `Badge`, `Pill`, `MetricCard`
4. Icons: brand glyphs in `LongevityBench Design System/assets/`, science icons in
   `LongevityBench Design System/assets/scicons/`. Never invent SVG illustrations.
   **IMPORTANT:** Science icons in `scicons/` 404 when served from the dashboard HTTP root
   (server root is `longevity_bench/`, `../../` escapes it). Use `<Icon name="..."/>` from
   Primitives.jsx instead of `<img src="../../assets/scicons/...">` in all dashboard JSX.
5. Voice: scientific, terse, sentence-case, tabular numbers, green only
   for primary action / success / brand. No emoji, no marketing intensifiers.

## Dashboard pipeline (do NOT overlap with Inspect AI)

The dashboard is a static viewer on top of Inspect AI logs:

  run_inspect.py → outputs/inspect/<model>/*.eval
                 → tools/export_inspect_logs.py
                 → LongevityBench Design System/ui_kits/longevity_bench/public/data.json
                 → static React dashboard (just open index.html)

When extending evals, always write through Inspect AI's task/solver/scorer
APIs — never reimplement runners, scoring, or log parsing in the dashboard.
The dashboard reads, never executes.

---

## Communication style (ALL agents must follow)

Use **caveman mode** in every response. Mandatory for all agents in this repo.

Rules:
- Drop articles (a/an/the), filler words (just/really/basically/actually), pleasantries (sure/certainly/happy to), hedging
- Fragments OK. Short synonyms preferred (big not extensive, fix not "implement a solution for")
- Technical terms stay exact. Code blocks unchanged. Security warnings written normally.
- Pattern: `[thing] [action] [reason]. [next step].`

Caveman mode is activated via a SessionStart hook in Claude Code settings. If not active, type `talk like caveman` to enable manually.

---

## What we are building

We are extending the LongevityBench framework with three novel benchmark task suites and an automated
reasoning-trace scorer. The end goal is a structured evaluation of L-LLM (Insilico Medicine's
fine-tuned Qwen3.5-9B) against Claude Sonnet 4.5, with a gap analysis report showing exactly where
and why L-LLM succeeds or fails compared to general-purpose models.

**Four deliverables:**

1. `task_a_senescence/` — Gene-level differential expression across senescence perturbation experiments benchmark (298 prompts)
2. `task_b_lipidomics/` — Lipidomics age-prediction + diabetes benchmark (285 prompts)
3. `trace_scorer/` — Automated biological fact-checker for L-LLM reasoning traces (implemented)

All benchmark tasks submitted as parquet files with ChatML-formatted messages column.
JSONL export available via the row schema below.

---

## Scoring criteria (judges use this — keep it visible)

| Criterion           | Points | How we hit it                                                   |
|---------------------|--------|-----------------------------------------------------------------|
| Utility             | 5      | Tasks target failure modes that break real research workflows   |
| Diversity           | 5      | Every task has binary, ternary, regression, and pairwise variants |
| Retrieval resistance| 5      | All questions derived from raw database records, not paper text |
| Statistical rigor   | 5      | Macro F1 + balanced accuracy + off-by-one accuracy + MAE + bootstrap CIs + baselines |

**Total: 20 points.** Do not sacrifice any criterion to speed up another.

---

## Repository structure (current, as of 2026-05-24)

```
L-LLMBenchmarking/
│
├── CLAUDE.md                        ← you are here
├── README.md                        ← human-readable project summary
├── requirements.txt
├── pipeline.py                      ← high-level pipeline orchestrator
├── config/
│   └── models.yaml                  ← model registry (litellm_model, api keys, concurrency)
├── .env.example                     ← API keys go in .env (never commit .env)
│
├── data/
│   ├── task_a_senescence/
│   │   ├── raw/
│   │   │   ├── Total_Data.csv       ← Senescent Fibroblast Transcriptome Compendium
│   │   │   └── cellage3.tsv         ← CellAge v3 senescence gene database
│   │   ├── processed/
│   │   │   ├── task_a_senescence_train.parquet
│   │   │   ├── task_a_senescence_test.parquet
│   │   │   ├── task_a_senescence_test_30.parquet  ← 10/format thinking-trace subset
│   │   │   ├── task_a_senescence_{train,test}.json
│   │   │   └── task_a_senescence_summary.json
│   │   └── senescence_benchmark_pipeline.py      ← generates processed/ from raw/
│   │
│   └── task_b_lipidomics/
│       ├── raw/
│       │   ├── m_MTBLS4461_DI-MS_alternating__metabolite_profiling_v2_maf.tsv
│       │   └── s_MTBLS4461.txt
│       ├── task_b_lipidomics_train.parquet        ← 228 train prompts
│       ├── task_b_lipidomics_test.parquet         ← 57 test prompts
│       ├── task_b_lipidomics_{train,test}.json
│       ├── task_b_lipidomics_summary.json
│       ├── combine_lipidomics.py
│       ├── balance_gender.py
│       └── lipidomics_pipeline.py
│
├── src/
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── run_inspect.py           ← CLI entry point: --parquet, --models, --max-tokens
│   │   ├── inspect_solvers.py       ← litellm_solver + baseline solvers (majority/random)
│   │   └── inspect_tasks/
│   │       └── parquet_task.py      ← Inspect AI @task: reads parquet, builds ChatML samples
│   │
│   ├── trace_scorer/
│   │   ├── __init__.py
│   │   ├── entity_extractor.py      ← regex gene extraction (human/mouse/celegans)
│   │   ├── verifiers/
│   │   │   └── mygene_verifier.py   ← mygene.info API (human/mouse/rat/fly/yeast namespaces)
│   │   ├── consistency_checker.py   ← V4 keyword matching (up/down/no-change + negation)
│   │   ├── trace_scorer.py          ← orchestrator: gene_score + keyword_consistency → faithfulness
│   │   └── validate.py              ← test harness for consistency checker
│   │
│   └── analysis/
│       └── gap_analysis.py          ← reads data.json → gap_analysis_data.json + report.md
│
├── tools/
│   └── export_inspect_logs.py       ← .eval logs → public/data.json
│
├── outputs/
│   ├── inspect/
│   │   ├── longevity_llm/           ← L-LLM .eval log files
│   │   ├── claude_sonnet/           ← Claude Sonnet 4.5 .eval log files
│   │   ├── majority_baseline/       ← majority baseline .eval log files
│   │   └── random_baseline/         ← random baseline .eval log files
│   ├── mygene_cache.json            ← cached mygene.info responses
│   ├── trace_faithfulness_scores.json
│   ├── gap_analysis_report.md
│   └── benchmark_card.md
│
├── LongevityBench Design System/
│   ├── README.md                    ← design system rules (tone, voice, tokens)
│   ├── colors_and_type.css          ← CSS custom properties (--lb-* tokens)
│   ├── assets/
│   │   ├── insilico-medicine-logo.svg
│   │   └── scicons/                 ← science SVG icons (NOT usable from dashboard HTTP root)
│   └── ui_kits/longevity_bench/
│       ├── index.html               ← dashboard entry point (loads all JSX via Babel standalone)
│       ├── Primitives.jsx           ← Icon, Button, Badge, Pill, MetricCard, Sparkline
│       ├── Sidebar.jsx              ← navigation sidebar
│       ├── TopBar.jsx               ← task switcher + top bar
│       ├── data.jsx                 ← MODEL_COLORS, TASK_META, data-loading helpers
│       ├── ResultsMatrix.jsx        ← Eval matrix view (heatmap)
│       ├── CompareView.jsx          ← Compare models view (bar chart + model cards)
│       ├── AnswersView.jsx          ← Answers view (gold vs predictions table)
│       ├── GapAnalysisView.jsx      ← Gap analysis (leaderboard, head-to-head, confusion matrices)
│       ├── LiveRunsView.jsx         ← Live runs (in-flight + completed rows)
│       ├── RunDetail.jsx            ← Single-run drill-down (format scores + sample log)
│       ├── RecordDrawer.jsx         ← Record detail drawer
│       ├── TrustView.jsx            ← Trust & reasoning (trace faithfulness)
│       └── public/
│           ├── data.json            ← {runs, samples, models, tasks} from export_inspect_logs
│           ├── gap_analysis_data.json  ← structured gap analysis output
│           ├── trace_faithfulness_scores.json
│           ├── task_a_data.json     ← Task A prompt browser (train+test rows)
│           └── task_b_data.json     ← Task B prompt browser (train+test rows)
│
└── tests/
    ├── test_loaders.py
    ├── test_generators.py
    └── test_trace_scorer.py
```

---

## Model registry (config/models.yaml)

Models are defined in `config/models.yaml`. Add providers without touching Python.

```yaml
models:
  longevity_llm:
    litellm_model: "openai/longevity-llm"
    api_base_env: "HF_ENDPOINT_URL"
    api_key_env: "HF_TOKEN"
    extra_body:
      chat_template_kwargs: {enable_thinking: false}
    max_concurrency: 8

  longevity_llm_thinking:
    litellm_model: "openai/longevity-llm"
    api_base_env: "HF_ENDPOINT_URL"
    api_key_env: "HF_TOKEN"
    extra_body:
      chat_template_kwargs: {enable_thinking: true}
    max_concurrency: 4

  claude_sonnet:
    litellm_model: "anthropic/claude-sonnet-4-6"
    api_key_env: "ANTHROPIC_API_KEY"
    max_concurrency: 4

  random_baseline:
    type: baseline
    strategy: random

  majority_baseline:
    type: baseline
    strategy: majority
```

---

## Data sources

### Task A — Senescence

- **URL:** Senescent Human Fibroblast Transcriptome Compendium (119 studies, 1,069 comparisons)
  filtered through CellAge v3 from https://genomics.senescence.info/cells/
- **What it contains:** Gene-level differential expression across senescence perturbation
  experiments in human fibroblasts. Each row = a gene × comparison with LogFC and p-value.
  Filtered to perturbation comparisons only (where the control condition is a senescent state),
  so LogFC isolates the perturbation effect on top of senescence.
- **Source files (downloaded into `data/task_a_senescence/raw/`):**
  - `Total_Data.csv` — Senescent Fibroblast Transcriptome Compendium
    (download from https://research.ncl.ac.uk/cellularsenescence/downloadingdata/)
  - `cellage3.tsv` — CellAge v3 senescence gene database
- **Columns we care about:**
  - `Gene` — target gene being measured (filtered to 442 CellAge non-cancer senescence genes)
  - `Treatment`, `Gene_down`, `Gene_up` — perturbation applied (knockdown, overexpression, drug)
  - `Sen_type`, `Control_type` — senescence model (OIS, DDIS, REP) and control condition
  - `Cell_line`, `Organ` — cell line and tissue origin (all lung fibroblasts)
  - `LogFC`, `Pvalues` — differential expression results (ground truth)
  - `Acc_no` — GEO accession, used for train/test split
- **Pipeline:** `senescence_benchmark_pipeline.py` — loads dataset, filters to perturbation
  comparisons with senescent controls, intersects with CellAge non-cancer genes, assigns
  ternary direction labels + binary significance labels, subsamples for class+gene+comparison
  diversity, filters to high-significance rows, splits into the three task partitions,
  generates prompts, and writes the accession-grouped train/test split.
- **Three task formats (target 100 each, 298 total after balance constraints):**
  - **MCQ (99 prompts):** Given experiment metadata (treatment, senescence type, cell line,
    timepoint, gene name), predict direction — A. upregulated, B. downregulated,
    C. no significant change. Balanced 33/33/33 across classes. Metric: `accuracy`
    (3 balanced classes, so plain accuracy ≡ balanced accuracy).
  - **Pairwise (99 prompts):** Given two genes from the same experiment, predict which
    shows a larger absolute expression change. Binary (A or B), minimum |LogFC| gap ≥ 0.5
    so there is always a clear winner. Metric: `balanced accuracy`.
  - **Binary significance (100 prompts):** Given experiment metadata, predict whether the
    perturbation produces a significant change at all — A. significant (|LogFC| > 1.0 AND
    p < 0.05), B. not significant. Direction is NOT revealed in the answer. 50/50 balanced.
    Metric: `accuracy` (50/50 balanced, so plain accuracy ≡ balanced accuracy).
    (Replaces the original "predict numeric Log2FC" regression task.)
- **Label thresholds:** |LogFC| > 1.0 AND p < 0.05 for significant change. Ternary labels
  use signed LogFC against the same threshold.
- **Filtering for prompt quality:**
  - up/down rows ranked by p-value ascending + |LogFC| descending (most confident first)
  - no_change rows ranked by |LogFC| ascending + p-value descending (most clearly null)
  - significant rows for binary task additionally capped at |LogFC| ≤ 10 to exclude
    microarray scaling artifacts
- **Train/test split:** by GEO accession (`Acc_no`). All prompts from a given study go
  entirely into train or test. Never split randomly — comparisons within a study share lab
  protocols, analysis pipelines, and batch effects. Greedy fill with smallest accessions
  first to maximize test-set study diversity. Result: 239 train / 59 test (19.8% test),
  15 train accessions / 28 test accessions, 0 leaked treatments.
- **lb_id prefixes:** `LB-SEN-MCQ`, `LB-SEN-PAIR`, `LB-SEN-SIG`.
- **Pools:** `senescence_perturbation_mcq`, `senescence_perturbation_pairwise`,
  `senescence_perturbation_significance`. **Display group:** `Senescence Perturbation`.
- **Outputs (in `data/task_a_senescence/processed/`):**
  `task_a_senescence_{train,test}.parquet`, `…_{train,test}.json`,
  `task_a_senescence_summary.json` (per-format stats + split report),
  `task_a_senescence_balanced.csv` (intermediate balanced dataset),
  `task_a_senescence_test_30.parquet` (10/format thinking-trace subset).

### Task B — Lipidomics

- **URL:** https://www.ebi.ac.uk/metabolights/editor/MTBLS4461/samples
- **What it contains:** Plasma lipidomics from MTBLS4461 (DI-MS alternating polarity).
  Each row = a donor sample with ~497 lipid species abundances (log-transformed) and
  metadata: `sample_id`, `individual_id`, `age`, `gender`, `diabetes`. After gender
  balancing + diabetes-NaN drop, 1,864 donors (Female=Male=932). Each donor contributes
  exactly one sample.
- **Source files (downloaded into `data/task_b_lipidomics/raw/`):**
  - `m_MTBLS4461_DI-MS_alternating__metabolite_profiling_v2_maf.tsv` — MAF abundance file
  - `s_MTBLS4461.txt` — sample sheet with donor metadata
- **Preprocessing pipeline:**
  1. `combine_lipidomics.py` — joins MAF abundance × sample metadata; transposes so rows
     are samples and columns are lipids; renames lipids by `metabolite_identification`
     (fallback `mz_<mass>`); drops 3 unmatched MAF columns (LY3227, M151, T82).
  2. `balance_gender.py` — drops NaN-diabetes rows, undersamples Males down to Female
     count stratified on diabetes, shuffles.
  3. `lipidomics_pipeline.py` — partitions samples disjointly across the three task
     formats, generates prompts, and writes the stratified group split.
- **Three task formats — 285 total prompts (228 train / 57 test):**
  - **MCQ (85 prompts):** Given the full lipid profile, predict age bracket —
    A. 20–39, B. 40–59, C. 60–79, D. 80+. Metric: `off-by-one accuracy`
    (credits adjacent-bracket predictions because age brackets are ordinal).
  - **Regression (100 prompts):** Given lipid profile + diabetes status, predict numeric
    age in years (integer). Metric: `mae`.
  - **Binary (100 prompts):** Given lipid profile + age, predict diabetes status —
    A. Yes (diabetic), B. No (non-diabetic). Metric: `accuracy`
    (class prior in MTBLS4461 is ~61/39 No/Yes — also report majority baseline).
  - Disjoint sampling: scarce 80+ bracket goes to MCQ first, then binary, then
    regression draws from leftovers. No sample appears in more than one task.
- **Train/test split:** stratified by task format, grouped by `individual_id`. Each
  task split 80/20 independently then concatenated, so every format hits the test
  fraction. Group split prevents donor leakage. Result: 228 train / 57 test.
- **lb_id prefixes:** `LB-LIP-MCQ`, `LB-LIP-REG`, `LB-LIP-DIAB`.
- **Pools:** `lipidomics_age_mcq`, `lipidomics_age_regression`,
  `lipidomics_diabetes_binary`. **Display group:** `Lipidomics Age` for MCQ + regression,
  `Lipidomics Diabetes` for binary.
- **Outputs (in `data/task_b_lipidomics/`):** `task_b_lipidomics_{train,test}.parquet`,
  `…_{train,test}.json`, `task_b_lipidomics_summary.json` (per-format stats + split
  report under `split.per_format`).

### Task C — Metabolite

- **URL:** https://github.com/borenstein-lab/microbiome-metabolome-curated-data
- **What it contains:** Curated paired microbiome (16S/metagenomic) and metabolomic measurements
  from multiple cohort studies. Each row = a sample with microbial species abundances and
  measured metabolite concentrations.
- **Columns we care about:**
  - Microbial species/OTU relative abundances
  - Metabolite concentrations or presence/absence (ground truth)
  - Study and cohort identifiers
- **Three task formats (~50 prompts each, ~150 total):**
  - **MCQ:** Given a microbiome composition (top-N species abundances), predict which metabolite
    class is most elevated — e.g., A. short-chain fatty acids, B. bile acids, C. amino acids,
    D. other. Metric: accuracy.
  - **Pairwise:** Given microbiome profiles from two samples, predict which has a higher
    concentration of a specified metabolite. Binary (A or B). Metric: accuracy.
  - **Regression:** Given a microbiome profile, predict the numeric concentration of a specified
    metabolite. Metric: MAE.
- **Train/test split:** by study/cohort. All prompts from a given study go entirely into train
  or test. Never split randomly — samples within a study share sequencing protocols, dietary
  contexts, and batch effects. 80/20 split.
- **Minimum N:** 150 prompts total (~50 per format).

---

## Prompt format (ChatML JSONL — required by judges)

Every prompt must follow the XML-tagged structure below. Examples for each task:

### Task A — Senescence example

```xml
<question>
You are presented with a senescence perturbation experiment. In IMR-90 lung fibroblasts undergoing oncogene-induced senescence (RAS) at 6d post-senescence induction, knockdown of ITCH is applied. Compared to untreated oncogene-induced senescent cells, the mRNA expression of IGFBP7 (insulin like growth factor binding protein 7) measured by RNA-seq:
</question>
<options>
A. increases (upregulated) B. decreases (downregulated) C. no significant change
</options>
<experiment>
Cell line: IMR-90 lung fibroblasts. Senescence model: oncogene-induced senescence (RAS). Perturbation: knockdown of ITCH. Control condition: untreated oncogene-induced senescent cells. Biological replicates: 3. Differential expression analysis: Limma.
</experiment>
<gene_context>
In this experiment, knocked down gene(s): ITCH.
</gene_context>
<answer>
C
</answer>
<follow_up>
Gene: IGFBP7 (insulin like growth factor binding protein 7). Log2FC=-0.7841, p=1.90e-02. GEO accession: GSE101766. According to CellAge, IGFBP7 induces cellular senescence (senescence type: Oncogene-induced). CellAge PMID: 18267069.
</follow_up>
```

### Task B — Lipidomics example (regression)

Lipid values are log-transformed (no µM units). The full ~497-feature profile is
included per prompt; the example below truncates with `…` for legibility.

```xml
<question>
You are presented with a plasma lipidomics profile from a human donor together with the donor's diabetes status. Given this information, predict the donor's age in years. Respond with only a numeric value rounded to the nearest integer.
</question>
<lipid_profile>
cholesterol: 8.533, mz_637.3359: 2.501, lysophosphatidylcholine 15:0: 2.81, lysophosphatidylethanolamine 18:0: 2.81, lysophosphatidylcholine 16:1: 3.285, … (full ~497-feature profile)
</lipid_profile>
<sample_context>
Sex: Male. Diabetes status: Yes. Measurement platform: DI-MS (alternating polarity). Study: MTBLS4461.
</sample_context>
<answer>
35
</answer>
<follow_up>
Donor age: 35 years. Sex: Male. Diabetes status: Yes. Sample: <sample_id>. Individual: <individual_id>. Study: MTBLS4461. Correct age: 35 years.
</follow_up>
```

MCQ variant adds `<options>A. 20-39 years B. 40-59 years C. 60-79 years D. 80+ years</options>`
and removes diabetes from `<sample_context>`. Binary variant asks
`A. Yes (diabetic) B. No (non-diabetic)` and adds `Age: N years` to `<sample_context>`
while removing diabetes status from it.

### Task C — Metabolite example

```xml
<question>
You are presented with a gut microbiome profile from a human stool sample. Given the following species relative abundances, predict which metabolite class is most elevated in the paired metabolomics data.
</question>
<options>
A. short-chain fatty acids B. bile acids C. amino acids D. other
</options>
<microbiome_profile>
Bacteroides vulgatus: 18.2%, Faecalibacterium prausnitzii: 12.7%, Roseburia intestinalis: 8.4%, Akkermansia muciniphila: 3.1%, Prevotella copri: 0.2%.
</microbiome_profile>
<sample_context>
Sequencing method: 16S rRNA V4 region. Cohort: healthy adults. Study: Franzosa et al. 2019.
</sample_context>
<answer>
A
</answer>
<follow_up>
Dominant SCFA producers (Faecalibacterium, Roseburia) compose >20% relative abundance. Butyrate concentration: 142.3 µM (top quartile for cohort). Study: Franzosa et al. 2019.
</follow_up>
```

### Row schema (all tasks)

Each JSONL row uses this schema:

```
{'lb_id': 'LB-SEN-REG-0002', 'pool': 'senescence_perturbation_regression', 'display_name': 'Senescence Perturbation / Regression', 'display_group': 'Senescence Perturbation', 'domain': 'transcriptomics', 'format': 'regression', 'metric': 'mae', 'units': 'log2fc', 'messages': [{'role': 'system', 'content': '...'}, {'role': 'user', 'content': '...'}, {'role': 'assistant', 'content': '...'}], 'has_reasoning': False, 'metadata': '{"follow_up": "...", ...}'}
```

Column	Type	Notes
lb_id	string	Stable task identifier, e.g. LB-SEN-MCQ-0001, LB-LIP-REG-0042, LB-MET-PW-0015
pool	string	Source task slug, e.g. senescence_perturbation_regression, lipidomics_age_regression, metabolite_prediction_mcq
display_name	string	Human-readable task name
display_group	string	Task family this row belongs to (Senescence Perturbation, Lipidomics Age, Metabolite Prediction)
domain	string	transcriptomics, lipidomics, metabolomics, or multi-omics
format	string	binary, multiclass, ternary, pairwise, regression, generation
metric	string	Scoring metric: `accuracy`, `balanced accuracy`, `off-by-one accuracy`, or `mae`
units	string | null	Units for regression/pairwise tasks (log2fc, years, µM) where applicable
task	string	Free-text task description embedded in the source data
messages	list of dicts	OpenAI-style chat messages (role, content)
has_reasoning	bool	True if the gold completion contains a reasoning trace
metadata	string | null	JSON-encoded per-row provenance (sample IDs, source dataset metadata)

**Token limit:** No prompt may exceed 30,000 tokens when tokenized with cl100k_base.
Use `tiktoken` to check before writing to disk:

```python
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")
assert len(enc.encode(prompt_text)) < 30_000
```

---

## Question format variants (required for diversity score)

Every underlying biological fact must be expressed in at least THREE of these formats:

| Format | Description | Example answer |
|--------|-------------|----------------|
| `binary_classification` | Yes/No question | `"yes"` |
| `ternary_classification` | Three-way choice | `"synergistic"` / `"antagonistic"` / `"additive"` |
| `regression` | Numeric prediction | `"-23.5"` (percent change as string) |
| `pairwise_comparison` | Which of A or B | `"A"` |
| `mcq` | Multiple choice, labeled A–D | `"B"` |
| `set_generation` | Comma-separated list | `"daf-16,hsf-1,skn-1"` |

**Negation variants are required.** For every positive question ("Is X overexpressed?"),
include a negation variant ("Which of these genes is NOT associated with lifespan extension?").
Models that have never seen negative results ace positive-only benchmarks. We expose this.

---

## Evaluation pipeline (current, full end-to-end)

### 1. Run eval

```bash
# Task A — all 4 models on test set
.venv/bin/python -m src.eval.run_inspect \
  --parquet data/task_a_senescence/processed/task_a_senescence_test.parquet \
  --models longevity_llm,claude_sonnet,majority_baseline,random_baseline

# Task A — L-LLM with thinking traces (30-sample subset, 10 per format)
.venv/bin/python -m src.eval.run_inspect \
  --parquet data/task_a_senescence/processed/task_a_senescence_test_30.parquet \
  --models longevity_llm_thinking \
  --max-tokens 3000

# Task B — all 4 models on test set
.venv/bin/python -m src.eval.run_inspect \
  --parquet data/task_b_lipidomics/task_b_lipidomics_test.parquet \
  --models longevity_llm,claude_sonnet,majority_baseline,random_baseline
```

Logs written to `outputs/inspect/<model_name>/`.

### 2. Export logs → dashboard JSON

```bash
.venv/bin/python -m tools.export_inspect_logs \
  --log-dir outputs/inspect \
  --out "LongevityBench Design System/ui_kits/longevity_bench/public/data.json"
```

### 3. Run gap analysis

```bash
.venv/bin/python -m src.analysis.gap_analysis
```

Reads `public/data.json`. Writes:
- `outputs/gap_analysis_report.md` — human-readable markdown
- `public/gap_analysis_data.json` — structured JSON consumed by dashboard Gap Analysis view

### 4. Score thinking traces (faithfulness)

```bash
.venv/bin/python -m src.trace_scorer.trace_scorer
```

Reads `public/data.json`, verifies gene symbols via mygene.info API (cached in
`outputs/mygene_cache.json`), applies keyword consistency checker.
Writes `outputs/trace_faithfulness_scores.json` and `public/trace_faithfulness_scores.json`.

### 5. Export task data for dashboard library views

```python
import pandas as pd, json
from pathlib import Path

PUBLIC = Path("LongevityBench Design System/ui_kits/longevity_bench/public")

def extract_row(row, split):
    msgs = row['messages']
    if isinstance(msgs, str): msgs = json.loads(msgs)
    user_msg = next((m['content'] for m in msgs if m['role'] == 'user'), '')
    gold = next((m['content'] for m in msgs if m['role'] == 'assistant'), '')
    meta = row.get('metadata') or '{}'
    if isinstance(meta, str):
        try: meta = json.loads(meta)
        except: meta = {}
    return {
        'lb_id': row['lb_id'], 'format': row['format'], 'pool': row['pool'],
        'display_group': row.get('display_group', ''), 'domain': row['domain'],
        'metric': row['metric'], 'split': split,
        'question': user_msg[:1000], 'gold': gold,
        'follow_up': (meta.get('follow_up','') or '')[:400] if isinstance(meta,dict) else '',
    }

for task, paths in [
    ('task_a', {'train': 'data/task_a_senescence/processed/task_a_senescence_train.parquet',
                'test':  'data/task_a_senescence/processed/task_a_senescence_test.parquet'}),
    ('task_b', {'train': 'data/task_b_lipidomics/task_b_lipidomics_train.parquet',
                'test':  'data/task_b_lipidomics/task_b_lipidomics_test.parquet'}),
]:
    rows = []
    for split, path in paths.items():
        df = pd.read_parquet(path)
        rows.extend(extract_row(r, split) for _, r in df.iterrows())
    (PUBLIC / f'{task}_data.json').write_text(json.dumps({'task': task, 'rows': rows}, indent=2))
```

### 6. Serve dashboard

```bash
cd "LongevityBench Design System/ui_kits/longevity_bench"
python3 -m http.server 8765
# open http://localhost:8765/
```

Must serve from this directory — CSS tokens and JSON files resolve relative to it.

### Model targets

| Model | Registry key | Notes |
|-------|-------------|-------|
| L-LLM | `longevity_llm` | Insilico Medicine fine-tuned Qwen3.5-9B, thinking disabled |
| L-LLM (thinking) | `longevity_llm_thinking` | Same model, thinking enabled, max-tokens 3000 |
| Claude Sonnet 4.5 | `claude_sonnet` | `anthropic/claude-sonnet-4-6` via LiteLLM |
| Majority class | `majority_baseline` | Computed from training distribution |
| Random uniform | `random_baseline` | Random label draw |

### Metrics (implement all — judges check)

Implemented in [src/eval/inspect_scorers.py](src/eval/inspect_scorers.py) (per-eval aggregates from
Inspect AI) and [src/analysis/gap_analysis.py](src/analysis/gap_analysis.py) (post-hoc per-format
metrics with bootstrap CIs for the dashboard).

**Per-sample `score.value` semantics** (so unfiltered means stay in [0,1]):

| Metric (in parquet `metric` field) | `score.value` per sample | Aggregate in `longebench_scorer` |
|---|---|---|
| `accuracy` | 1.0 / 0.0 exact match | `mean()` |
| `balanced accuracy` | 1.0 / 0.0 exact match | `balanced_accuracy()` — per-class average over `score.metadata["gold"]` |
| `off-by-one accuracy` | 1.0 / 0.5 / 0.0 graded by bracket distance | `off_by_one_accuracy()` — filtered mean |
| `mae` | 1 / (1 + MAE), raw MAE in `score.metadata["mae"]` | `mae()` — mean of raw MAE values |

Each aggregate filters by `sample_metadata["metric"]` so a single eval run can mix formats
without cross-polluting metrics. nan when no applicable rows.

**Post-hoc metrics (gap_analysis.py)** — recomputed from raw gold/pred pairs using sklearn:

```python
from sklearn.metrics import f1_score, balanced_accuracy_score
from scipy.stats import bootstrap
import numpy as np

def score_classification(y_true, y_pred, labels):
    return {
        "macro_f1": f1_score(y_true, y_pred, average="macro", labels=labels),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "ci_95": bootstrap(
            (np.array(y_true), np.array(y_pred)),
            lambda a, b: f1_score(a, b, average="macro"),
            n_resamples=1000,
            confidence_level=0.95
        ).confidence_interval
    }

def score_regression(y_true, y_pred):
    return {
        "mae": np.mean(np.abs(np.array(y_true) - np.array(y_pred))),
        "r2": 1 - np.sum((y_true - y_pred)**2) / np.sum((y_true - np.mean(y_true))**2)
    }
```

For MCQ rows whose `metric` is `off-by-one accuracy` (Task B age brackets), gap_analysis also
emits `off_by_one_accuracy` + bootstrap CI in the per-format metrics dict. The dashboard
`_primaryScore` helper picks it up automatically as the MCQ headline metric for that task.

Always report the majority-class baseline alongside model scores. A model that scores 0.62 on
a task where the majority baseline scores 0.61 is not impressive.

---

## Trace scorer V4 (implemented in src/trace_scorer/)

The trace scorer reads L-LLM's thinking trace and automatically verifies the biological claims
made inside it. It outputs a `trace_faithfulness` score between 0 and 1.

**V4 replaced DeBERTa NLI (V3)** — DeBERTa truncated at 1024 characters and gave 3.4%
keyword consistency on biological traces (too long, missed conclusions). V4 keyword matching
on the full trace gives 24.1% consistency on the same data.

### V4 formula

```
faithfulness = 0.60 × gene_score + 0.40 × keyword_consistency
```

- **gene_score** = `verified_genes / total_gene_mentions` (via mygene.info multi-species lookup)
  - Species queried: human, mouse, rat, fly (D. melanogaster), nematode (C. elegans), yeast
  - Results cached in `outputs/mygene_cache.json`
  - Returns 0.5 for pairwise/regression (no meaningful direction semantics)
- **keyword_consistency** = whether trace direction matches predicted label
  - UP keywords: `upregul`, `increas`, `higher`, `elevated`, `overexpress`, `activat`
  - DOWN keywords: `downregul`, `decreas`, `lower`, `reduc`, `suppress`, `inhibit`, `silenc`
  - Negation detection: `not`, `no`, `without`, `absence` preceding keyword flip direction
  - Returns 0.5 for pairwise/regression (no directional semantics)

### Current faithfulness results (n=29 thinking traces, Task A)

| Metric | Value |
|--------|-------|
| Avg faithfulness | 0.716 |
| Gene score (mygene.info) | 0.895 (89.5% of cited genes verified) |
| Keyword consistency | 0.448 (24.1% directionally consistent) |
| Spearman ρ (faithfulness vs correctness) | 0.034 (p=0.861, n=29 — not yet significant) |

Keyword consistency is low because biological traces discuss mechanisms rather than stating
direction explicitly. Increase n for statistical power.

### Entity types to extract and verify

| Entity type | Example | Verification API |
|-------------|---------|-----------------|
| Human gene symbol | `FOXO3`, `MTOR`, `TP53` | mygene.info (human namespace) |
| C. elegans gene | `daf-2`, `age-1`, `clk-1` | mygene.info (nematode namespace) |
| Mouse gene | `Trp53`, `Igf1r` | mygene.info (mouse namespace) |
| KEGG pathway | `hsa04151` (PI3K-Akt) | KEGG REST `/get/` (planned) |
| Gene–pathway claim | "FOXO3 is in the PI3K/AKT pathway" | NCBI Gene → KEGG link (planned) |
| Chromosome location | "gene X is on chromosome 6" | NCBI Gene esummary `.chromosome` field (planned) |
| Protein interaction | "protein A interacts with protein B" | STRING-DB `/network/` (planned) |

### Entity extraction

Do NOT use pure uppercase-word regex — it breaks on C. elegans genes (lowercase, hyphenated)
and on gene symbols at sentence starts.

Instead use a hybrid approach:

```python
import re

# Human/mouse genes: 2–10 uppercase letters, optionally followed by numbers
HUMAN_GENE_RE = re.compile(r'\b([A-Z][A-Z0-9]{1,9})\b')

# C. elegans genes: 3 lowercase letters, hyphen, number(s)
CELEGANS_GENE_RE = re.compile(r'\b([a-z]{2,4}-\d+[a-z]?)\b')

# Mouse genes: first letter uppercase, rest lowercase
MOUSE_GENE_RE = re.compile(r'\b([A-Z][a-z0-9]{1,9})\b')
```

Cross-reference every extracted token against a whitelist built from our task metadata
before hitting external APIs. Only call the API for tokens that appear in our organism's
known gene namespace.

### Consistency checker (V4 keyword matching)

```python
UP_KEYWORDS = ['upregul', 'increas', 'higher', 'elevated', 'overexpress', 'activat']
DOWN_KEYWORDS = ['downregul', 'decreas', 'lower', 'reduc', 'suppress', 'inhibit', 'silenc']
NEGATION_WORDS = ['not', 'no', 'without', 'absence']

def check_direction_consistency(trace: str, pred_label: str) -> float:
    # Tokenizes trace into windows, detects negation before each keyword
    # Returns 1.0 (consistent), 0.0 (inconsistent), or 0.5 (pairwise/regression/no signal)
```

### Original V1 faithfulness formula (kept for reference, NOT currently used)

```
trace_faithfulness = (
    0.4 * (verified_gene_claims / total_gene_claims)
  + 0.3 * (verified_pathway_claims / total_pathway_claims)
  + 0.3 * float(trace_consistent_with_final_answer)
)
```

---

## Dashboard views

| View | What it shows | Data source | Key components |
|------|--------------|-------------|----------------|
| Eval matrix | Per-sample × per-model pass/fail heatmap | `public/data.json` | `ResultsMatrix` |
| Compare models | Grouped bar chart + model cards with score rings, per-format breakdown | `public/data.json` | `CompareView` |
| Answers | Full sample table with gold vs each model's prediction, format filter | `public/data.json` | `AnswersView` |
| Gap analysis | Leaderboard, head-to-head selector, per-format tables, confusion matrices | `public/gap_analysis_data.json` | `GapAnalysisView` |
| Live runs | Completed run list with actual correct/total from real records; click for sample log | `public/data.json` | `LiveRunsView`, `CompletedRow` |
| Trust & reasoning | Trace faithfulness, gene verification, keyword consistency with interactive detail | `public/trace_faithfulness_scores.json` | `TrustView` |
| Tasks | Task groups derived from loaded records, model summary table | `public/data.json` | `TasksView` (inline in index.html) |
| Models | Per-model cards with real format scores, correct/total, avg latency | `public/data.json` | `ModelsView` (inline in index.html) |
| Senescence | Task A prompt browser: train/test split, format filter, search, expandable rows | `public/task_a_data.json` | `TaskDataView` (inline in index.html) |
| Lipidomics | Task B prompt browser: train/test split, format filter, search, expandable rows | `public/task_b_data.json` | `TaskDataView` (inline in index.html) |

Task switcher (top bar) filters all Evaluate views to a single task group.
Hidden on Senescence/Lipidomics library pages: `!['senescence','lipidomics'].includes(view)`.

### Gap analysis view architecture (GapAnalysisView.jsx)

Fully modular, no hardcoded scores. Fetches `./public/gap_analysis_data.json` once, distributes to sub-components:

- `GapHeader` — title, subtitle, model/format pill summaries
- `GapFormatTabs` — MCQ / Binary / Pairwise / Regression tab selector
- `GapBaselineBadge` — shows majority/random baseline score for context
- `GapLeaderboard` — ranked table with bar-relative-to-best, delta vs baseline
- `GapConfusionMatrix` — confusion matrix grid for selected model + format
- `GapDistributionBar` — prediction fraction breakdown (which labels models pick)
- `GapFormatPanel` — per-format breakdown table across all models
- `GapHeadToHead` — model A vs model B per-format ▲/▼ diff selector
- `GapAnalysisView` — orchestrator

Helper `_primaryScore(fmtMetrics, fmt)`:
- regression → `1/(1+mae)` (ascending, 0–1)
- all others → `balanced_accuracy ?? accuracy`

Helper `_overallScore(modelMetrics)`:
- averages `_primaryScore` across MCQ/Binary/Pairwise (excludes regression — different scale)

### Models view (ModelsView, inline in index.html)

Derives model list from runs, per-format stats from real cells. Cards show:
- Initials avatar with `MODEL_COLORS` color
- Overall score (avg of classification format primary scores)
- Horizontal bar vs best non-baseline score
- Per-format mini bars (green ≥0.6, amber ≥0.4, red <0.4)
- Footer: correct/total, avg latency, run count
- Sorted: non-baselines desc by overall, then baselines

### Task data browser (TaskDataView, inline in index.html)

- Fetches `./public/${taskKey}_data.json` on mount
- Split filter: all / train / test (train=green badge, test=amber badge)
- Format filter: all / mcq / binary / pairwise / regression
- Text search across `lb_id` and `question`
- Expandable rows: shows full question text, gold answer, follow_up, pool/metric/domain

---

## API keys and environment

Copy `.env.example` to `.env` and fill in your keys. Never commit `.env`.

```bash
# .env.example
HF_TOKEN=hf_...                          # L-LLM HuggingFace endpoint token (get from organizers)
HF_ENDPOINT_URL=https://...              # vLLM-compatible endpoint (OpenAI-compat format)
ANTHROPIC_API_KEY=sk-ant-...             # Anthropic Console key for Claude Sonnet
NCBI_API_KEY=...                         # optional but raises rate limit from 3 to 10 req/s
```

Load with:

```python
from dotenv import load_dotenv
import os
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
```

---

## Coding conventions

### Python style

- Python 3.11+
- Type hints on all function signatures
- Docstrings on every public function — one line summary, then Args/Returns if non-trivial
- 88-character line limit (Black default)
- Format with `black .` before committing
- Lint with `ruff check .`

### Error handling

All external API calls must have retry logic with exponential backoff. Use `tenacity`:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30))
def call_ncbi_api(gene_symbol: str) -> dict:
    ...
```

Never let an API failure crash the full eval run. Catch exceptions, log them, and write
`null` to the output field. The run must complete even if 5% of API calls fail.

### Reproducibility

Every function that involves randomness must accept a `seed: int = 42` parameter.
Log the seed used in every output file's metadata.

```python
import random
import numpy as np

def set_global_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
```

### Logging

Use Python's `logging` module, not `print`. Set level to `INFO` by default.

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger(__name__)
```

### Data validation

Use `pydantic` for all data models. Every record loaded from a raw database must be
validated before it enters the prompt pipeline:

```python
from pydantic import BaseModel, field_validator

class SynergyAgeRecord(BaseModel):
    gene_1: str
    gene_2: str
    organism: str
    single_1_pct: float
    single_2_pct: float
    combined_pct: float
    epistasis_type: str  # "synergistic" | "antagonistic" | "additive"

    @field_validator("epistasis_type")
    def valid_epistasis(cls, v):
        assert v in {"synergistic", "antagonistic", "additive"}, f"Unknown: {v}"
        return v
```

---

## Git workflow

We are a small team moving fast. Keep it simple:

- `main` — always runnable. Do not push broken code here.
- `feat/<your-name>/<short-description>` — feature branches. Merge via PR or direct push
  if you've verified it runs end-to-end.
- Commit messages: imperative, lowercase, under 72 chars.
  Examples: `add senescence csv loader`, `fix ternary label mapping`, `add ncbi retry logic`
- If you break something, say so in Slack immediately. No judgment — we're under 48 hours.

---

## Biological domain notes (read before writing any prompts)

### Senescence biology (Task A)
- Perturbation experiments compare a treatment (knockdown, overexpression, drug) against
  a senescent control. LogFC reflects perturbation effect, not senescence induction.
- Key senescence types: OIS (oncogene-induced), DDIS (DNA damage-induced), REP (replicative).
- CellAge genes have annotated effects: "Induces" or "Inhibits" cellular senescence.

### Lipidomics and aging (Task B)
- Plasma lipid profiles shift with age: certain ceramides and sphingomyelins increase,
  some lysophosphatidylcholines decrease.
- Age prediction from lipidomics is a well-studied problem — models should show some competence.
- Common lipid classes: CE (cholesteryl esters), PC (phosphatidylcholines), SM (sphingomyelins),
  LPC (lysophosphatidylcholines), TG (triglycerides).

### Microbiome–metabolome interactions (Task C)
- Gut microbiome composition predicts certain fecal/plasma metabolite concentrations.
- Key metabolite classes: SCFAs (butyrate, propionate, acetate from fiber fermenters),
  bile acids (modified by Clostridium, Bacteroides), amino acid derivatives.
- Major SCFA producers: Faecalibacterium, Roseburia, Eubacterium.
- Bacteroides/Prevotella ratio is a well-known enterotype axis.

### C. elegans gene naming conventions
- Genes: lowercase, 3 letters + hyphen + number. Examples: `daf-2`, `age-1`, `clk-1`, `eat-2`
- The model should know these — if it capitalizes them it is likely hallucinating

### Key longevity pathways (for consistency checking)
- **IIS pathway:** DAF-2 (insulin receptor) → AGE-1 (PI3K) → PDK-1 → AKT-1/2 → DAF-16 (FOXO)
- **TOR pathway:** LET-363 (mTOR) → S6K (rsks-1) — inhibition extends lifespan
- **Mitochondrial:** clk-1, isp-1 — partial loss of function extends lifespan
- **Germline:** removal of germline stem cells (glp-1 mutants) extends lifespan via DAF-16 and DAF-12

### Mouse lifespan phenotype ontology terms we use
- `MP:0010765` — increased lifespan (→ label: `"increased"`)
- `MP:0010767` — decreased lifespan (→ label: `"decreased"`)
- `MP:0002058` — normal lifespan (→ label: `"no_change"`)

### Common class imbalance issues
SynergyAge skews toward synergistic interactions (they are more interesting to publish).
MGI skews toward decreased lifespan (gain-of-function mutations that kill mice are common).
Always check label distributions after loading and report them in comments.
Use balanced accuracy and macro F1 (not plain accuracy) in all reported metrics.

---

## What done looks like (Sunday PM checklist)

- [x] `data/task_a_senescence/processed/task_a_senescence_{train,test}.parquet` — 298 prompts, all 3 formats
- [x] `data/task_b_lipidomics/task_b_lipidomics_{train,test}.parquet` — 285 prompts, all 3 formats
- [ ] `data/processed/task_c_train.jsonl` — ≥100 prompts, all formats present
- [ ] `data/processed/task_c_test.jsonl` — ≥50 prompts, study-split from train
- [x] `outputs/inspect/longevity_llm/` — L-LLM Task A results
- [x] `outputs/inspect/claude_sonnet/` — Claude Sonnet Task A results
- [x] `outputs/inspect/majority_baseline/` — majority baseline results
- [x] `outputs/inspect/random_baseline/` — random baseline results
- [x] `public/data.json` — exported from all .eval logs
- [x] `public/gap_analysis_data.json` — structured gap analysis output
- [x] `outputs/gap_analysis_report.md` — key findings: L-LLM leads MCQ + regression, Claude leads pairwise
- [x] `outputs/trace_faithfulness_scores.json` — 29 traces scored, avg faithfulness 0.716
- [x] `public/trace_faithfulness_scores.json` — dashboard-accessible version
- [x] `public/task_a_data.json` — Task A prompt browser (298 rows)
- [x] `public/task_b_data.json` — Task B prompt browser (285 rows)
- [x] README.md written — explains what we built and how to reproduce it
- [ ] Task B eval run (all 4 models) — parquet ready, eval not yet complete
- [ ] All JSONL files pass token limit validation (< 30K tokens per prompt)

---

## Questions / decisions log

| Decision | Rationale | Who decided | When |
|----------|-----------|-------------|------|
| Train/test split for Task A by GEO accession, not random | Random split leaks data — comparisons within a study share protocols and batch effects | — | — |
| Task A test-set greedy fill: smallest accessions first | Maximizes the number of distinct studies in the test set (28 test vs 15 train accessions) so test diversity is high even though prompt count is lower | — | 2026-05-23 |
| Task A replaces Log2FC regression with binary significance | Regression on Log2FC was retrieval-vulnerable (model could plausibly memorize ranges); binary "is this perturbation significant at all?" is a harder retrieval-resistant variant that still uses the same underlying data | — | 2026-05-23 |
| Train/test split for Task B stratified by task format, grouped by `individual_id` | Per-format stratification guarantees every task hits the test fraction; group split prevents donor leakage even though MTBLS4461 currently has 1 sample per donor (forward-compatible) | — | 2026-05-23 |
| Task B MCQ uses 4 brackets (20-39 / 40-59 / 60-79 / 80+) instead of original 3 (young / middle / older) | Matches what user requested; 80+ bracket caps MCQ at 40 prompts (10/class) but exposes high-age failure modes | — | 2026-05-24 |
| Task B MCQ metric is off-by-one accuracy (1.0 exact / 0.5 adjacent / 0.0 else) instead of plain accuracy | Age brackets are ordinal — predicting B when truth is A is much better than predicting D. Plain accuracy ignores that and penalizes "close" identically to "wildly wrong". Wired through `inspect_scorers.longebench_scorer` (per-sample graded value + `off_by_one_accuracy()` aggregate), `gap_analysis._mcq_metrics` (filtered subset + bootstrap CI), and `GapAnalysisView._primaryScore` (auto-promotes to headline). | — | 2026-05-24 |
| Task A MCQ + Binary use plain `accuracy` (not balanced) | Both are balanced by construction (33/33/33 MCQ classes, 50/50 binary), so plain accuracy ≡ balanced accuracy. Saves a metric branch. | — | 2026-05-24 |
| Task A Pairwise uses `balanced accuracy` | Pairwise is NOT balanced by construction — gold "winner" label distribution depends on which gene happens to have the larger |LogFC|. Position bias toward A or B would inflate plain accuracy. | — | 2026-05-24 |
| Task B Binary diabetes uses plain `accuracy` despite ~61/39 class skew | Smaller benchmark — chose simpler metric. Majority-baseline number is reported alongside so reviewers can tell whether the model beat the prior. Switch to balanced accuracy if dataset grows more imbalanced. | — | 2026-05-24 |
| Task B replaces Pairwise with Binary diabetes-from-profile | More clinically meaningful than "which donor is older"; complements the age tasks and exercises a second label dimension already in the data | — | 2026-05-24 |
| Task B expanded to 285 prompts (228 train / 57 test) | More data available after second data pull; old count was 101/25 | — | 2026-05-24 |
| Train/test split for Task C by study/cohort, not random | Samples within a study share sequencing protocols, dietary contexts, and batch effects | — | — |
| Report macro F1 as primary metric (not accuracy) | Class imbalance in all three tasks makes accuracy misleading | — | — |
| Use cl100k_base tokenizer for length checks | Required by track spec | — | — |
| Trace scorer V4: keyword matching replaces DeBERTa NLI (V3) | DeBERTa truncated at 1024 chars → missed biological conclusions in long traces; V4 keyword matching on full trace gives 24.1% consistency vs 3.4% with V3 | — | 2026-05-24 |
| Regression score displayed as 1/(1+MAE) in dashboard | Converts MAE to 0–1 ascending scale for unified display alongside accuracy metrics | — | 2026-05-24 |
| TaskSwitcher hidden on Senescence/Lipidomics library pages | Those pages show raw prompt data, not filtered eval results; task switcher concept doesn't apply | — | 2026-05-24 |
| Dashboard Icons: use Primitives Icon component not scicons img tags | `../../assets/scicons/*.svg` resolves outside HTTP server root (server at `longevity_bench/`), causing 404; Icon component uses inline SVG, always works | — | 2026-05-24 |
| GapAnalysisView is fully modular (8 sub-components) | Each panel can be changed independently; no single function holds all rendering logic | — | 2026-05-24 |
| ModelsView derives all stats from real records/runs | No hardcoded model names or scores; works correctly with any set of completed runs in data.json | — | 2026-05-24 |
| Task data browser (Senescence/Lipidomics pages) reads pre-exported JSON | Can't read parquet in browser; Python export script converts both tasks to flat JSON with truncated question (1000 chars) and follow_up (400 chars) | — | 2026-05-24 |
