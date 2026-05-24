# LongevityBench-X · Task A Senescence · Gap Analysis Report

_Generated: 2026-05-24T11:39:48.290297+00:00_

## 1. Dataset Summary

### Train split
- Total samples: **239**
- Per-format: binary=83, mcq=75, pairwise=81
- GEO accessions: 15
- Label distributions:
  - `binary`: A=44, B=39
  - `mcq`: A=27, B=26, C=22
  - `pairwise`: A=38, B=43

### Test split
- Total samples: **59**
- Per-format: binary=17, mcq=24, pairwise=18
- GEO accessions: 28
- Label distributions:
  - `binary`: A=6, B=11
  - `mcq`: A=6, B=7, C=11
  - `pairwise`: A=9, B=9

**Split logic:** Train/test split by GEO accession — all samples from one study stay together. 
Prevents label leakage from shared batch effects and analysis pipelines.

## 2. Evaluation Coverage

| Model | binary/significance | mcq | pairwise | regression |
|---|---|---|---|---|
| L-LLM | 47 | 49 | 18 | 27 |
| L-LLM (think) | 10 | 10 | 10 | — |
| Claude Sonnet | 47 | 49 | 18 | 27 |
| Majority | 47 | 49 | 18 | 0 |
| Random | 47 | 49 | 18 | 0 |
| Population Prior Prediction | 20 | 17 | — | 20 |

## 3. Main Results

### Format: `binary/significance`

| Model | N | Accuracy | Balanced Acc | Acc(A) | Acc(B) | CI (Acc) |
|---|---|---|---|---|---|---|
| L-LLM | 47 | 0.553 | 0.564 | 0.6667 | 0.4615 | [0.404, 0.702] |
| L-LLM (think) | 10 | 0.700 | 0.438 | 0.0 | 0.875 | [0.400, 1.000] |
| Claude Sonnet | 47 | 0.575 | 0.551 | 0.3333 | 0.7692 | [0.425, 0.723] |
| Majority | 47 | 0.362 | 0.368 | 0.4286 | 0.3077 | [0.213, 0.511] |
| Random | 47 | 0.447 | 0.454 | 0.5238 | 0.3846 | [0.298, 0.596] |
| Population Prior Prediction | 20 | 0.500 | 0.500 | 0.5 | 0.5 | [0.299, 0.700] |

### Format: `mcq`

| Model | N | Accuracy | Macro F1 | Balanced Acc | CI (F1) |
|---|---|---|---|---|---|
| L-LLM | 49 | 0.388 | 0.273 | 0.280 | [0.169, 0.374] |
| L-LLM (think) | 10 | 0.100 | 0.067 | 0.111 | [0.000, 0.182] |
| Claude Sonnet | 49 | 0.327 | 0.234 | 0.274 | [0.140, 0.324] |
| Majority | 49 | 0.204 | 0.148 | 0.181 | [0.070, 0.228] |
| Random | 49 | 0.367 | 0.228 | 0.268 | [0.152, 0.296] |
| Population Prior Prediction | 17 | 0.412 | 0.240 | 0.264 | [0.108, 0.355] |

**Confusion matrices:**

_L-LLM_

| pred→ | A | B | C | D |
|---|---|---|---|---|
| gold=A | 3 | 3 | 8 | 0 |
| gold=B | 1 | 4 | 7 | 0 |
| gold=C | 1 | 8 | 12 | 0 |
| gold=D | 0 | 1 | 1 | 0 |

_L-LLM (think)_

| pred→ | A | B | C |
|---|---|---|---|
| gold=A | 0 | 1 | 3 |
| gold=B | 0 | 0 | 3 |
| gold=C | 1 | 1 | 1 |

_Claude Sonnet_

| pred→ | A | B | C | D |
|---|---|---|---|---|
| gold=A | 2 | 6 | 6 | 0 |
| gold=B | 3 | 8 | 1 | 0 |
| gold=C | 3 | 12 | 6 | 0 |
| gold=D | 0 | 0 | 2 | 0 |

_Majority_

| pred→ | A | B | C | D |
|---|---|---|---|---|
| gold=A | 6 | 4 | 4 | 0 |
| gold=B | 7 | 3 | 2 | 0 |
| gold=C | 11 | 9 | 1 | 0 |
| gold=D | 0 | 1 | 1 | 0 |

_Random_

| pred→ | A | B | C | D |
|---|---|---|---|---|
| gold=A | 9 | 1 | 4 | 0 |
| gold=B | 8 | 0 | 4 | 0 |
| gold=C | 9 | 3 | 9 | 0 |
| gold=D | 0 | 1 | 1 | 0 |

_Population Prior Prediction_

| pred→ | A | B | C | D |
|---|---|---|---|---|
| gold=A | 2 | 0 | 2 | 0 |
| gold=B | 3 | 0 | 0 | 0 |
| gold=C | 3 | 1 | 5 | 0 |
| gold=D | 0 | 1 | 0 | 0 |

### Format: `pairwise`

| Model | N | Accuracy | Balanced Acc | Pred A% | Pred B% | A-bias | CI (Acc) |
|---|---|---|---|---|---|---|---|
| L-LLM | 18 | 0.556 | 0.556 | 61.1% | 38.9% | 0.1111 | [0.333, 0.778] |
| L-LLM (think) | 10 | 0.500 | 0.500 | 50.0% | 50.0% | -0.1 | [0.200, 0.800] |
| Claude Sonnet | 18 | 0.778 | 0.778 | 61.1% | 38.9% | 0.1111 | [0.556, 0.944] |
| Majority | 18 | 0.500 | 0.500 | 0.0% | 100.0% | -0.5 | [0.278, 0.722] |
| Random | 18 | 0.667 | 0.667 | 50.0% | 50.0% | 0.0 | [0.444, 0.889] |

### Format: `regression`

| Model | N | MAE | Median AE | Spearman r | Sign Acc | CI (MAE) |
|---|---|---|---|---|---|---|
| L-LLM | 27 | 12.074 | 12.000 | 0.075 | 1.000 | [9.740, 14.520] |
| Claude Sonnet | 27 | 22.182 | 19.000 | -0.145 | 1.000 | [15.893, 29.293] |
| Majority | 0 | — | — | — | — | — |
| Random | 0 | — | — | — | — | — |
| Population Prior Prediction | 20 | 25.450 | 28.500 | -0.378 | 1.000 | [19.450, 31.351] |

## 4. Failure Analysis

### MCQ — class-level errors

**L-LLM:** most-confused pairs:
- gold=C predicted as B: 8×
- gold=A predicted as C: 8×
- gold=B predicted as C: 7×

**L-LLM (think):** most-confused pairs:
- gold=B predicted as C: 3×
- gold=A predicted as C: 3×
- gold=C predicted as B: 1×

**Claude Sonnet:** most-confused pairs:
- gold=C predicted as B: 12×
- gold=A predicted as C: 6×
- gold=A predicted as B: 6×

**Majority:** most-confused pairs:
- gold=C predicted as A: 11×
- gold=C predicted as B: 9×
- gold=B predicted as A: 7×

**Random:** most-confused pairs:
- gold=C predicted as A: 9×
- gold=B predicted as A: 8×
- gold=B predicted as C: 4×

**Population Prior Prediction:** most-confused pairs:
- gold=C predicted as A: 3×
- gold=B predicted as A: 3×
- gold=A predicted as C: 2×

### Binary/significance — class-wise accuracy
- **L-LLM**: class A acc=0.6667, class B acc=0.4615
- **L-LLM (think)**: class A acc=0.0, class B acc=0.875
- **Claude Sonnet**: class A acc=0.3333, class B acc=0.7692
- **Majority**: class A acc=0.4286, class B acc=0.3077
- **Random**: class A acc=0.5238, class B acc=0.3846
- **Population Prior Prediction**: class A acc=0.5, class B acc=0.5

### Pairwise — A/B prediction bias
- **L-LLM**: predicted A=61.1%, predicted B=38.9%, A-bias=0.1111
- **L-LLM (think)**: predicted A=50.0%, predicted B=50.0%, A-bias=-0.1
- **Claude Sonnet**: predicted A=61.1%, predicted B=38.9%, A-bias=0.1111
- **Majority**: predicted A=0.0%, predicted B=100.0%, A-bias=-0.5
- **Random**: predicted A=50.0%, predicted B=50.0%, A-bias=0.0

### Regression — direction errors
See sign_accuracy in the regression metrics table above.

## 5. Baseline Summary

| Baseline | MCQ acc | Binary acc | Pairwise acc | Regression MAE |
|---|---|---|---|---|
| Majority | 0.2041 | 0.3617 | 0.5 | None |
| Random | 0.3673 | 0.4468 | 0.6667 | None |
| Population Prior Prediction | 0.4118 | 0.5 | — | 25.45 |

_Majority baseline uses per-format most-frequent label from training split._  
_Random baseline draws uniformly from valid label set per format (A/B/C for MCQ, A/B for binary/pairwise)._  
_Population Prior Prediction baseline samples regression age from US Census 2025 population estimates conditioned on donor sex (no train labels used)._
