# LongevityBench-X · Task A Senescence · Gap Analysis Report

_Generated: 2026-05-24T19:21:43.588128+00:00_

## 1. Dataset Summary

### Train split
- Total samples: **453**
- Per-format: binary=158, mcq=138, pairwise=77, regression=80
- GEO accessions: 13
- Label distributions:
  - `binary`: A=81, B=77
  - `mcq`: A=47, B=46, C=36, D=9
  - `pairwise`: A=36, B=41
  - `regression`: 32=1, 33=1, 34=2, 35=3, 36=5, 37=2, 38=3, 39=2, 45=1, 50=9, 51=2, 52=2, 53=2, 54=3, 55=7, 56=1, 58=1, 59=2, 60=8, 62=1, 63=1, 64=2, 65=5, 68=1, 70=2, 72=1, 75=1, 80=8, 87=1

### Test split
- Total samples: **130**
- Per-format: binary=42, mcq=46, pairwise=22, regression=20
- GEO accessions: 30
- Label distributions:
  - `binary`: A=19, B=23
  - `mcq`: A=11, B=12, C=22, D=1
  - `pairwise`: A=11, B=11
  - `regression`: 33=1, 36=1, 37=1, 38=3, 43=1, 50=1, 53=1, 60=5, 61=1, 65=2, 70=1, 75=1, 80=1

**Split logic:** Train/test split by GEO accession — all samples from one study stay together. 
Prevents label leakage from shared batch effects and analysis pipelines.

## 2. Evaluation Coverage

| Model | binary/significance | mcq | pairwise | regression |
|---|---|---|---|---|
| L-LLM | 158 | 138 | 77 | 80 |
| Claude Sonnet | 158 | 138 | 77 | 80 |
| Majority | 158 | 138 | 77 | 80 |
| Random | 158 | 138 | 77 | 80 |
| Population Prior Prediction | 158 | 138 | 77 | 80 |

## 3. Main Results

### Format: `binary/significance`

| Model | N | Accuracy | Balanced Acc | Acc(A) | Acc(B) | CI (Acc) |
|---|---|---|---|---|---|---|
| L-LLM | 158 | 0.468 | 0.468 | 0.4815 | 0.4545 | [0.386, 0.544] |
| Claude Sonnet | 158 | 0.608 | 0.615 | 0.3086 | 0.9221 | [0.532, 0.683] |
| Majority | 158 | 0.538 | 0.538 | 0.5309 | 0.5455 | [0.462, 0.620] |
| Random | 158 | 0.411 | 0.409 | 0.5062 | 0.3117 | [0.329, 0.494] |
| Population Prior Prediction | 158 | 0.373 | 0.371 | 0.4691 | 0.2727 | [0.297, 0.449] |

### Format: `mcq`

| Model | N | Accuracy | Macro F1 | Balanced Acc | Off-by-one | CI (Off-by-one) |
|---|---|---|---|---|---|---|
| L-LLM | 138 | 0.312 | 0.202 | 0.271 | 0.559 | [0.478, 0.640] |
| Claude Sonnet | 138 | 0.377 | 0.285 | 0.302 | 0.500 | [0.404, 0.596] |
| Majority | 138 | 0.348 | 0.208 | 0.258 | 0.596 | [0.514, 0.676] |
| Random | 138 | 0.261 | 0.202 | 0.217 | 0.419 | [0.338, 0.507] |
| Population Prior Prediction | 138 | 0.261 | 0.202 | 0.217 | 0.419 | [0.338, 0.507] |

**Confusion matrices:**

_L-LLM_

| pred→ | A | B | C | D |
|---|---|---|---|---|
| gold=A | 1 | 14 | 32 | 0 |
| gold=B | 1 | 17 | 28 | 0 |
| gold=C | 1 | 10 | 25 | 0 |
| gold=D | 0 | 5 | 4 | 0 |

_Claude Sonnet_

| pred→ | A | B | C | D |
|---|---|---|---|---|
| gold=A | 12 | 15 | 20 | 0 |
| gold=B | 5 | 26 | 15 | 0 |
| gold=C | 11 | 11 | 14 | 0 |
| gold=D | 0 | 4 | 5 | 0 |

_Majority_

| pred→ | A | B | C | D |
|---|---|---|---|---|
| gold=A | 26 | 21 | 0 | 0 |
| gold=B | 24 | 22 | 0 | 0 |
| gold=C | 20 | 16 | 0 | 0 |
| gold=D | 0 | 9 | 0 | 0 |

_Random_

| pred→ | A | B | C | D |
|---|---|---|---|---|
| gold=A | 13 | 17 | 17 | 0 |
| gold=B | 22 | 8 | 16 | 0 |
| gold=C | 13 | 8 | 15 | 0 |
| gold=D | 7 | 1 | 1 | 0 |

_Population Prior Prediction_

| pred→ | A | B | C | D |
|---|---|---|---|---|
| gold=A | 13 | 17 | 17 | 0 |
| gold=B | 22 | 8 | 16 | 0 |
| gold=C | 13 | 8 | 15 | 0 |
| gold=D | 7 | 1 | 1 | 0 |

### Format: `pairwise`

| Model | N | Accuracy | Balanced Acc | Pred A% | Pred B% | A-bias | CI (Acc) |
|---|---|---|---|---|---|---|---|
| L-LLM | 77 | 0.597 | 0.600 | 53.2% | 46.8% | 0.065 | [0.480, 0.701] |
| Claude Sonnet | 77 | 0.558 | 0.568 | 64.9% | 35.1% | 0.1819 | [0.454, 0.675] |
| Majority | 77 | 0.532 | 0.500 | 0.0% | 100.0% | -0.4675 | [0.429, 0.636] |
| Random | 77 | 0.519 | 0.520 | 50.6% | 49.4% | 0.039 | [0.403, 0.636] |
| Population Prior Prediction | 77 | 0.519 | 0.520 | 50.6% | 49.4% | 0.039 | [0.403, 0.636] |

### Format: `regression`

| Model | N | MAE | Median AE | Spearman r | Sign Acc | CI (MAE) |
|---|---|---|---|---|---|---|
| L-LLM | 80 | 11.425 | 10.000 | -0.021 | 1.000 | [9.487, 13.589] |
| Claude Sonnet | 80 | 75.200 | 12.500 | 0.017 | 0.963 | [16.337, 186.624] |
| Majority | 80 | 11.050 | 9.000 | 0.000 | 1.000 | [9.262, 12.913] |
| Random | 80 | 16.775 | 13.500 | 0.001 | 1.000 | [13.975, 19.865] |
| Population Prior Prediction | 80 | 21.938 | 22.000 | -0.202 | 1.000 | [18.774, 25.013] |

## 4. Failure Analysis

### MCQ — class-level errors

**L-LLM:** most-confused pairs:
- gold=A predicted as C: 32×
- gold=B predicted as C: 28×
- gold=A predicted as B: 14×

**Claude Sonnet:** most-confused pairs:
- gold=A predicted as C: 20×
- gold=B predicted as C: 15×
- gold=A predicted as B: 15×

**Majority:** most-confused pairs:
- gold=B predicted as A: 24×
- gold=A predicted as B: 21×
- gold=C predicted as A: 20×

**Random:** most-confused pairs:
- gold=B predicted as A: 22×
- gold=A predicted as C: 17×
- gold=A predicted as B: 17×

**Population Prior Prediction:** most-confused pairs:
- gold=B predicted as A: 22×
- gold=A predicted as C: 17×
- gold=A predicted as B: 17×

### Binary/significance — class-wise accuracy
- **L-LLM**: class A acc=0.4815, class B acc=0.4545
- **Claude Sonnet**: class A acc=0.3086, class B acc=0.9221
- **Majority**: class A acc=0.5309, class B acc=0.5455
- **Random**: class A acc=0.5062, class B acc=0.3117
- **Population Prior Prediction**: class A acc=0.4691, class B acc=0.2727

### Pairwise — A/B prediction bias
- **L-LLM**: predicted A=53.2%, predicted B=46.8%, A-bias=0.065
- **Claude Sonnet**: predicted A=64.9%, predicted B=35.1%, A-bias=0.1819
- **Majority**: predicted A=0.0%, predicted B=100.0%, A-bias=-0.4675
- **Random**: predicted A=50.6%, predicted B=49.4%, A-bias=0.039
- **Population Prior Prediction**: predicted A=50.6%, predicted B=49.4%, A-bias=0.039

### Regression — direction errors
See sign_accuracy in the regression metrics table above.

## 5. Baseline Summary

| Baseline | MCQ acc | Binary acc | Pairwise acc | Regression MAE |
|---|---|---|---|---|
| Majority | 0.3478 | 0.538 | 0.5325 | 11.05 |
| Random | 0.2609 | 0.4114 | 0.5195 | 16.775 |
| Population Prior Prediction | 0.2609 | 0.3734 | 0.5195 | 21.9375 |

_Majority baseline uses per-format most-frequent label from training split._  
_Random baseline draws uniformly from valid label set per format (A/B/C for MCQ, A/B for binary/pairwise)._  
_Population Prior Prediction baseline samples regression age from US Census 2025 population estimates conditioned on donor sex (no train labels used)._
