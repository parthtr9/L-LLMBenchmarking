# LongevityBench-X · Task A Senescence · Gap Analysis Report

_Generated: 2026-05-24T12:09:17.400375+00:00_

## 1. Dataset Summary

### Train split
- Total samples: **467**
- Per-format: binary=163, mcq=143, pairwise=81, regression=80
- GEO accessions: 15
- Label distributions:
  - `binary`: A=82, B=81
  - `mcq`: A=48, B=48, C=38, D=9
  - `pairwise`: A=38, B=43
  - `regression`: 32=1, 33=1, 34=2, 35=3, 36=5, 37=2, 38=3, 39=2, 45=1, 50=9, 51=2, 52=2, 53=2, 54=3, 55=7, 56=1, 58=1, 59=2, 60=8, 62=1, 63=1, 64=2, 65=5, 68=1, 70=2, 72=1, 75=1, 80=8, 87=1

### Test split
- Total samples: **18**
- Per-format: binary=6, mcq=6, pairwise=3, regression=3
- GEO accessions: 9
- Label distributions:
  - `binary`: B=6
  - `mcq`: B=3, C=3
  - `pairwise`: A=2, B=1
  - `regression`: 50=1, 53=1, 60=1

**Split logic:** Train/test split by GEO accession — all samples from one study stay together. 
Prevents label leakage from shared batch effects and analysis pipelines.

## 2. Evaluation Coverage

| Model | binary/significance | mcq | pairwise | regression |
|---|---|---|---|---|
| L-LLM | 6 | 6 | 3 | 3 |
| L-LLM (think) | 6 | 6 | 3 | 3 |
| Claude Sonnet | 6 | 6 | 3 | 3 |
| Majority | 6 | 6 | 3 | 0 |
| Random | 6 | 6 | 3 | 0 |

## 3. Main Results

### Format: `binary/significance`

| Model | N | Accuracy | Balanced Acc | Acc(A) | Acc(B) | CI (Acc) |
|---|---|---|---|---|---|---|
| L-LLM | 6 | 0.500 | 0.500 | — | 0.5 | [0.167, 0.833] |
| L-LLM (think) | 6 | 0.667 | 0.667 | — | 0.6667 | [0.333, 1.000] |
| Claude Sonnet | 6 | 0.667 | 0.667 | — | 0.6667 | [0.333, 1.000] |
| Majority | 6 | 1.000 | 1.000 | — | 1.0 | [1.000, 1.000] |
| Random | 6 | 0.333 | 0.333 | — | 0.3333 | [0.000, 0.667] |

### Format: `mcq`

| Model | N | Accuracy | Macro F1 | Balanced Acc | CI (F1) |
|---|---|---|---|---|---|
| L-LLM | 6 | 0.500 | 0.486 | 0.500 | [0.143, 0.829] |
| L-LLM (think) | 6 | 0.333 | 0.250 | 0.333 | [0.000, 0.400] |
| Claude Sonnet | 6 | 0.333 | 0.191 | 0.333 | [0.000, 0.303] |
| Majority | 6 | 0.667 | 0.667 | 0.667 | [0.250, 1.000] |
| Random | 6 | 0.333 | 0.191 | 0.333 | [0.000, 0.303] |

**Confusion matrices:**

_L-LLM_

| pred→ | B | C |
|---|---|---|
| gold=B | 1 | 2 |
| gold=C | 1 | 2 |

_L-LLM (think)_

| pred→ | B | C |
|---|---|---|
| gold=B | 0 | 3 |
| gold=C | 1 | 2 |

_Claude Sonnet_

| pred→ | A | B | C |
|---|---|---|---|
| gold=A | 0 | 0 | 0 |
| gold=B | 0 | 2 | 1 |
| gold=C | 1 | 2 | 0 |

_Majority_

| pred→ | B | C |
|---|---|---|
| gold=B | 2 | 1 |
| gold=C | 1 | 2 |

_Random_

| pred→ | A | B | C |
|---|---|---|---|
| gold=A | 0 | 0 | 0 |
| gold=B | 1 | 0 | 2 |
| gold=C | 1 | 0 | 2 |

### Format: `pairwise`

| Model | N | Accuracy | Balanced Acc | Pred A% | Pred B% | A-bias | CI (Acc) |
|---|---|---|---|---|---|---|---|
| L-LLM | 3 | 0.667 | 0.750 | 33.3% | 66.7% | -0.3334 | [0.000, 1.000] |
| L-LLM (think) | 3 | 0.000 | 0.000 | 33.3% | 66.7% | -0.3334 | [0.000, 0.000] |
| Claude Sonnet | 3 | 0.667 | 0.500 | 100.0% | 0.0% | 0.3333 | [0.000, 1.000] |
| Majority | 3 | 0.667 | 0.500 | 100.0% | 0.0% | 0.3333 | [0.000, 1.000] |
| Random | 3 | 0.667 | 0.500 | 100.0% | 0.0% | 0.3333 | [0.000, 1.000] |

### Format: `regression`

| Model | N | MAE | Median AE | Spearman r | Sign Acc | CI (MAE) |
|---|---|---|---|---|---|---|
| L-LLM | 3 | 2.333 | 1.000 | 0.866 | 1.000 | [0.000, 6.000] |
| L-LLM (think) | 3 | 3.667 | 4.000 | 1.000 | 1.000 | [1.000, 6.000] |
| Claude Sonnet | 3 | 6.000 | 6.000 | -0.866 | 1.000 | [3.000, 9.000] |
| Majority | 0 | — | — | — | — | — |
| Random | 0 | — | — | — | — | — |

## 4. Failure Analysis

### MCQ — class-level errors

**L-LLM:** most-confused pairs:
- gold=B predicted as C: 2×
- gold=C predicted as B: 1×

**L-LLM (think):** most-confused pairs:
- gold=B predicted as C: 3×
- gold=C predicted as B: 1×

**Claude Sonnet:** most-confused pairs:
- gold=C predicted as B: 2×
- gold=C predicted as A: 1×
- gold=B predicted as C: 1×

**Majority:** most-confused pairs:
- gold=C predicted as B: 1×
- gold=B predicted as C: 1×

**Random:** most-confused pairs:
- gold=B predicted as C: 2×
- gold=C predicted as A: 1×
- gold=B predicted as A: 1×

### Binary/significance — class-wise accuracy
- **L-LLM**: class A acc=—, class B acc=0.5
- **L-LLM (think)**: class A acc=—, class B acc=0.6667
- **Claude Sonnet**: class A acc=—, class B acc=0.6667
- **Majority**: class A acc=—, class B acc=1.0
- **Random**: class A acc=—, class B acc=0.3333

### Pairwise — A/B prediction bias
- **L-LLM**: predicted A=33.3%, predicted B=66.7%, A-bias=-0.3334
- **L-LLM (think)**: predicted A=33.3%, predicted B=66.7%, A-bias=-0.3334
- **Claude Sonnet**: predicted A=100.0%, predicted B=0.0%, A-bias=0.3333
- **Majority**: predicted A=100.0%, predicted B=0.0%, A-bias=0.3333
- **Random**: predicted A=100.0%, predicted B=0.0%, A-bias=0.3333

### Regression — direction errors
See sign_accuracy in the regression metrics table above.

## 5. Baseline Summary

| Baseline | MCQ acc | Binary acc | Pairwise acc | Regression MAE |
|---|---|---|---|---|
| Majority | 0.6667 | 1.0 | 0.6667 | None |
| Random | 0.3333 | 0.3333 | 0.6667 | None |

_Majority baseline uses per-format most-frequent label from training split._  
_Random baseline draws uniformly from valid label set per format (A/B/C for MCQ, A/B for binary/pairwise)._
