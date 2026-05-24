# LongevityBench-X · Task A Senescence · Gap Analysis Report

_Generated: 2026-05-24T04:19:11.270547+00:00_

## 1. Dataset Summary

### Train split
- Total samples: **236**
- Per-format: binary=81, mcq=77, regression=78
- Label distributions:
  - `binary`: A=38, B=43
  - `mcq`: A=25, B=30, C=22
  - `regression`: -0.0=1, -0.03=1, -0.04=2, -0.06=1, -0.08=1, -0.1=1, -0.15=1, -0.29=1, -1.01=2, -1.03=1, -1.04=1, -1.11=2, -1.13=1, -1.21=1, -1.31=1, -1.33=1, -1.36=1, -1.41=1, -1.43=1, -1.44=1, -1.51=1, -1.57=1, -1.68=1, -1.92=1, -1.96=1, -10.0=4, -2.07=1, -2.08=1, -2.24=1, -2.46=1, -2.69=1, -3.28=1, -3.6=1, -6.25=1, 0.0=4, 0.05=1, 0.08=1, 0.14=1, 0.16=1, 0.2=2, 0.26=1, 1.01=1, 1.02=2, 1.05=1, 1.13=1, 1.15=1, 1.18=1, 1.19=1, 1.2=1, 1.23=1, 1.24=1, 1.26=1, 1.31=1, 1.32=1, 1.39=1, 1.4=1, 1.44=1, 1.64=1, 1.68=1, 1.83=1, 10.0=3, 2.15=1, 2.28=1, 2.34=1, 2.71=1

### Test split
- Total samples: **64**
- Per-format: binary=19, mcq=23, regression=22
- Label distributions:
  - `binary`: A=9, B=10
  - `mcq`: A=4, B=9, C=10
  - `regression`: -0.26=1, -1.1=1, -1.15=1, -1.32=1, -1.33=1, -1.37=1, -1.56=1, 0.0=1, 0.03=1, 0.06=1, 0.09=2, 0.11=1, 0.14=1, 0.19=1, 1.11=1, 1.18=1, 1.3=1, 1.34=1, 1.57=1, 10.0=2

**Split logic:** Train/test split by GEO accession — all samples from one study stay together. 
Prevents label leakage from shared batch effects and analysis pipelines.

## 2. Main Results

### Format: `binary`

| Model | N | Accuracy | Balanced Acc | Acc(A) | Acc(B) | CI (Acc) |
|---|---|---|---|---|---|---|
| L-LLM | 19 | 0.842 | 0.839 | 0.7778 | 0.9 | [0.684, 1.000] |
| Claude Sonnet | 19 | 0.632 | 0.644 | 0.8889 | 0.4 | [0.421, 0.842] |
| Majority | 19 | 0.526 | 0.500 | 0.0 | 1.0 | [0.316, 0.737] |
| Random | 19 | 0.421 | 0.422 | 0.4444 | 0.4 | [0.210, 0.632] |

### Format: `mcq`

| Model | N | Accuracy | Macro F1 | Balanced Acc | CI (F1) |
|---|---|---|---|---|---|
| L-LLM | 23 | 0.478 | 0.446 | 0.474 | [0.212, 0.644] |
| Claude Sonnet | 23 | 0.304 | 0.221 | 0.306 | [0.089, 0.370] |
| Majority | 23 | 0.391 | 0.188 | 0.333 | [0.099, 0.252] |
| Random | 23 | 0.217 | 0.189 | 0.267 | [0.051, 0.318] |

**Confusion matrices:**

_L-LLM_

| pred→ | A | B | C |
|---|---|---|---|
| gold=A | 2 | 1 | 1 |
| gold=B | 0 | 2 | 7 |
| gold=C | 3 | 0 | 7 |

_Claude Sonnet_

| pred→ | A | B | C |
|---|---|---|---|
| gold=A | 1 | 3 | 0 |
| gold=B | 3 | 6 | 0 |
| gold=C | 3 | 7 | 0 |

### Format: `regression`

| Model | N | MAE | Median AE | Spearman r | Sign Acc | CI (MAE) |
|---|---|---|---|---|---|---|
| L-LLM | 22 | 1.521 | 0.645 | 0.054 | 0.273 | [0.569, 2.768] |
| Claude Sonnet | 22 | 1.933 | 1.090 | 0.106 | 0.318 | [0.917, 3.254] |
| Majority | 22 | 1.605 | 1.130 | 0.000 | 0.045 | [0.653, 2.868] |
| Random | 22 | 1.605 | 1.130 | 0.000 | 0.045 | [0.653, 2.868] |

## 3. Failure Analysis

### MCQ — class-level errors

**L-LLM:** most-confused pairs:
- gold=B predicted as C: 7×
- gold=C predicted as A: 3×
- gold=A predicted as C: 1×

**Claude Sonnet:** most-confused pairs:
- gold=C predicted as B: 7×
- gold=C predicted as A: 3×
- gold=B predicted as A: 3×

### Regression — direction errors
See confusion of sign (positive vs negative Log2FC) in sign_accuracy metric above.


### Binary — A/B prediction bias
- **L-LLM**: class A acc=0.7778, class B acc=0.9
- **Claude Sonnet**: class A acc=0.8889, class B acc=0.4
- **Majority**: class A acc=0.0, class B acc=1.0
- **Random**: class A acc=0.4444, class B acc=0.4

## 4. Baseline Summary

| Baseline | MCQ acc | Binary acc | Regression MAE |
|---|---|---|---|
| Majority | 0.3913 | 0.5263 | 1.6045 |
| Random | 0.2174 | 0.4211 | 1.6045 |

_Majority baseline uses per-format most-frequent label from training split._  
_Random baseline draws uniformly from valid label set per format (A/B/C for MCQ, A/B for binary, 0 for regression)._
