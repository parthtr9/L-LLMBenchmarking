# Benchmark Card — Task A: Senescence Perturbation

## Overview

| Field | Value |
|---|---|
| Task name | Task A: Senescence Gene-Level Perturbation |
| Domain | Transcriptomics / Cellular Senescence |
| Organism | Human (fibroblasts) |
| Source dataset | Senescent Human Fibroblast Transcriptome Compendium + CellAge v3 |
| Source URL | https://genomics.senescence.info/cells/ |
| Total prompts | 300 (236 train, 64 test) |
| Primary metric | Macro F1 (classification), MAE (regression) |
| Retrieval resistance | Derived from raw GEO differential expression records, not paper abstracts |

## Format Distribution

| Format | Train | Test | Description |
|---|---|---|---|
| `mcq` | 77 | 23 | 3-way direction prediction (A=up, B=down, C=no change) |
| `binary` | 81 | 19 | Pairwise: which gene shows larger \|Log2FC\|? |
| `regression` | 78 | 22 | Predict numeric Log2FC value |
| **Total** | **236** | **64** | |

## Labeling Rules

- **Up/Down threshold:** \|Log2FC\| > 1.0 **and** p < 0.05 → upregulated or downregulated
- **No-change threshold:** \|Log2FC\| ≤ 1.0 **or** p ≥ 0.05 → no significant change
- **Pairwise gap:** minimum \|ΔLog2FC\| ≥ 0.5 between gene A and gene B
- **Regression target:** raw Log2FC value as a string, capped to ±10

## Train/Test Split

- **Split key:** GEO accession number (`Acc_no`)
- **Logic:** All samples from the same GEO study go entirely into train or test — never split across both
- **Ratio:** ~80/20 (236 train / 64 test)
- **Why accession split:** Samples within a study share lab protocols, analysis pipelines, batch effects, and normalization choices. Random splitting would leak this shared variance into the test set, artificially inflating scores.

## Class Balance

### MCQ test split (n=23)
| Label | Count | Fraction |
|---|---|---|
| C (no change) | 10 | 43% |
| B (downregulated) | 9 | 39% |
| A (upregulated) | 4 | 17% |

### Binary test split (n=19)
| Label | Count | Fraction |
|---|---|---|
| B (gene B larger change) | 10 | 53% |
| A (gene A larger change) | 9 | 47% |

**Note:** Class imbalance in MCQ (C=43%) means majority-class accuracy is misleading. Use macro F1 and balanced accuracy as primary metrics.

## Baselines

| Baseline | MCQ strategy | Binary strategy | Regression strategy |
|---|---|---|---|
| Random | Uniform over {A, B, C} | Uniform over {A, B} | Predict 0 (no change) |
| Majority | Most frequent label in training split per format | Most frequent label in training split | Median Log2FC from training split |

Training split majority labels: MCQ→C, binary→B, regression≈-0.015 (≈0 — no change).

## Retrieval Resistance Argument

Questions are constructed from raw experimental records in GEO (differential expression results), not from published paper text. The perturbation treatments, gene names, cell lines, and accession numbers are drawn directly from the Senescent Human Fibroblast Transcriptome Compendium database. A model that has memorized published senescence papers does not have direct access to the GEO log2FC values for each individual experiment.

## Known Weaknesses

1. **Small test set (n=64):** Bootstrap 95% CIs are wide. Headline numbers should be interpreted with their confidence intervals.
2. **Possible treatment leakage:** Some perturbation types (e.g., rapamycin treatment) appear in both train and test accessions. The split is by GEO accession, not by treatment type. A model that has memorized how rapamycin affects gene expression broadly may generalize across the split boundary.
3. **Single cell type:** All samples are lung fibroblasts (IMR-90 or WI-38). Scores may not generalize to other cell types or tissues.
4. **MCQ options are always A/B/C:** Models that have seen the prompt format before may exploit the letter position rather than the biological content.

## Evaluation Instructions

Run the eval pipeline via:

```bash
# Full test set, all models
python -m src.eval.run_inspect \
  --parquet data/task_a_senescence/processed/task_a_senescence_test.parquet \
  --models longevity_llm,claude_sonnet,majority_baseline,random_baseline

# Export and generate report
python -m tools.export_inspect_logs
python -m src.analysis.gap_analysis
```

## Citation

Senescent Human Fibroblast Transcriptome Compendium:  
CellAge v3: https://genomics.senescence.info/cells/  
Caltech Longevity Hackathon Track 01 · Insilico Medicine Prize
