import json
import random
from pathlib import Path

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

PROMPT_PATH = Path("benchmark_prompts/franzosa_ibd_combined_omics.jsonl")
RESULTS_DIR = Path("benchmark_results")
RESULTS_DIR.mkdir(exist_ok=True)

RESULTS_PATH = RESULTS_DIR / "franzosa_ibd_combined_omics_results.jsonl"

with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    records = [json.loads(line) for line in f]

with open(RESULTS_PATH, "w", encoding="utf-8") as f:
    for record in records:
        model_answer = random.choice(["A", "B"])

        result = {
            "sample_id": record["sample_id"],
            "dataset": record["dataset"],
            "task": record["task"],
            "variant": record["variant"],
            "source_label": record["source_label"],
            "benchmark_label": record["benchmark_label"],
            "answer": record["answer"],
            "model_answer": model_answer,
            "model_name": "random_baseline",
        }

        f.write(json.dumps(result) + "\n")

print(f"Saved random baseline results to {RESULTS_PATH}")
print(f"Number of predictions: {len(records)}")