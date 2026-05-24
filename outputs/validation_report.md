# Trace Scorer V2 — Validation Report

## 1. Adding-Mistakes Perturbation Test (Lanham et al. 2023)

Perturb the 10 highest-scoring traces in two ways and check faithfulness drops.

| Perturbation | Mean faithfulness drop | Threshold | Result |
|---|---|---|---|
| Wrong gene (XYZQ1, FAKE7) | 0.308 | ≥ 0.15 | ✓ PASS |
| Flipped direction | 0.068 | ≥ 0.15 | ✗ FAIL |

### Per-trace deltas

| Sample | Original | Wrong gene | Flipped dir | Δ gene | Δ dir |
|---|---|---|---|---|---|
| `LB-SEN-MCQ-0008_00002` | 0.820 | 0.603 | 0.824 | +0.217 | -0.004 |
| `LB-SEN-SIG-0012_00023` | 0.819 | 0.657 | 0.819 | +0.162 | +0.000 |
| `LB-SEN-PAIR-0026_00017` | 0.795 | 0.772 | 0.795 | +0.023 | +0.000 |
| `LB-SEN-MCQ-0003_00000` | 0.783 | 0.635 | 0.783 | +0.148 | +0.000 |
| `LB-SEN-PAIR-0042_00019` | 0.778 | 0.280 | 0.778 | +0.498 | +0.000 |
| `LB-SEN-SIG-0011_00022` | 0.768 | 0.315 | 0.768 | +0.453 | +0.000 |
| `LB-SEN-PAIR-0009_00013` | 0.762 | 0.333 | 0.422 | +0.428 | +0.339 |
| `LB-SEN-MCQ-0012_00003` | 0.760 | 0.379 | 0.760 | +0.381 | +0.000 |
| `LB-SEN-MCQ-0028_00006` | 0.756 | 0.382 | 0.409 | +0.374 | +0.347 |
| `LB-SEN-MCQ-0022_00005` | 0.755 | 0.363 | 0.755 | +0.392 | +0.000 |

## 2. Spearman Correlation: Faithfulness vs Answer Correctness

| Metric | Value |
|---|---|
| Spearman ρ | -0.3641 |
| p-value | 0.0522 |
| 95% CI | [None, None] |
| n traces | 29 |

**Weak signal** — inspect Groq judge quality or increase sample size.