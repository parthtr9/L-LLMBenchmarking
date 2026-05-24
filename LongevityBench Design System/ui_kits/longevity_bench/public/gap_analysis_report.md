# LongevityBench-X · Task A Senescence · Gap Analysis Report

_Generated: 2026-05-24T09:47:29.521284+00:00_

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
| L-LLM | 27 | 32 | 18 | 7 |
| L-LLM (think) | 10 | 10 | 10 | — |
| Claude Sonnet | 27 | 32 | 18 | 7 |
| Majority | 27 | 32 | 18 | 0 |
| Random | 27 | 32 | 18 | 0 |

## 3. Main Results

### Format: `binary/significance`

| Model | N | Accuracy | Balanced Acc | Acc(A) | Acc(B) | CI (Acc) |
|---|---|---|---|---|---|---|
| L-LLM | 27 | 0.556 | 0.500 | 0.3333 | 0.6667 | [0.370, 0.741] |
| L-LLM (think) | 10 | 0.700 | 0.438 | 0.0 | 0.875 | [0.400, 1.000] |
| Claude Sonnet | 27 | 0.593 | 0.500 | 0.2222 | 0.7778 | [0.407, 0.778] |
| Majority | 27 | 0.333 | 0.500 | 1.0 | 0.0 | [0.148, 0.518] |
| Random | 27 | 0.370 | 0.389 | 0.4444 | 0.3333 | [0.185, 0.556] |

### Format: `mcq`

| Model | N | Accuracy | Macro F1 | Balanced Acc | CI (F1) |
|---|---|---|---|---|---|
| L-LLM | 32 | 0.500 | 0.351 | 0.367 | [0.203, 0.479] |
| L-LLM (think) | 10 | 0.100 | 0.067 | 0.111 | [0.000, 0.182] |
| Claude Sonnet | 32 | 0.312 | 0.222 | 0.258 | [0.112, 0.331] |
| Majority | 32 | 0.219 | 0.113 | 0.171 | [0.043, 0.188] |
| Random | 32 | 0.344 | 0.212 | 0.258 | [0.121, 0.296] |

**Confusion matrices:**

_L-LLM_

| pred→ | A | B | C | D |
|---|---|---|---|---|
| gold=A | 3 | 2 | 5 | 0 |
| gold=B | 1 | 3 | 5 | 0 |
| gold=C | 1 | 1 | 10 | 0 |
| gold=D | 0 | 0 | 1 | 0 |

_L-LLM (think)_

| pred→ | A | B | C |
|---|---|---|---|
| gold=A | 0 | 1 | 3 |
| gold=B | 0 | 0 | 3 |
| gold=C | 1 | 1 | 1 |

_Claude Sonnet_

| pred→ | A | B | C | D |
|---|---|---|---|---|
| gold=A | 2 | 5 | 3 | 0 |
| gold=B | 3 | 6 | 0 | 0 |
| gold=C | 3 | 7 | 2 | 0 |
| gold=D | 0 | 0 | 1 | 0 |

_Majority_

| pred→ | A | B | C | D |
|---|---|---|---|---|
| gold=A | 6 | 0 | 4 | 0 |
| gold=B | 7 | 0 | 2 | 0 |
| gold=C | 11 | 0 | 1 | 0 |
| gold=D | 0 | 0 | 1 | 0 |

_Random_

| pred→ | A | B | C | D |
|---|---|---|---|---|
| gold=A | 7 | 1 | 2 | 0 |
| gold=B | 5 | 0 | 4 | 0 |
| gold=C | 6 | 2 | 4 | 0 |
| gold=D | 0 | 0 | 1 | 0 |

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
| L-LLM | 7 | 10.571 | 10.000 | 0.319 | 1.000 | [7.714, 13.150] |
| Claude Sonnet | 7 | 25.787 | 16.000 | 0.248 | 1.000 | [10.778, 42.864] |
| Majority | 0 | — | — | — | — | — |
| Random | 0 | — | — | — | — | — |

## 4. Failure Analysis

### MCQ — class-level errors

**L-LLM:** most-confused pairs:
- gold=B predicted as C: 5×
- gold=A predicted as C: 5×
- gold=A predicted as B: 2×

**L-LLM (think):** most-confused pairs:
- gold=B predicted as C: 3×
- gold=A predicted as C: 3×
- gold=C predicted as B: 1×

**Claude Sonnet:** most-confused pairs:
- gold=C predicted as B: 7×
- gold=A predicted as B: 5×
- gold=C predicted as A: 3×

**Majority:** most-confused pairs:
- gold=C predicted as A: 11×
- gold=B predicted as A: 7×
- gold=A predicted as C: 4×

**Random:** most-confused pairs:
- gold=C predicted as A: 6×
- gold=B predicted as A: 5×
- gold=B predicted as C: 4×

### Binary/significance — class-wise accuracy
- **L-LLM**: class A acc=0.3333, class B acc=0.6667
- **L-LLM (think)**: class A acc=0.0, class B acc=0.875
- **Claude Sonnet**: class A acc=0.2222, class B acc=0.7778
- **Majority**: class A acc=1.0, class B acc=0.0
- **Random**: class A acc=0.4444, class B acc=0.3333

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
| Majority | 0.2188 | 0.3333 | 0.5 | None |
| Random | 0.3438 | 0.3704 | 0.6667 | None |

_Majority baseline uses per-format most-frequent label from training split._  
_Random baseline draws uniformly from valid label set per format (A/B/C for MCQ, A/B for binary/pairwise)._
