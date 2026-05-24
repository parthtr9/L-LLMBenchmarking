import json
from pathlib import Path
from collections import Counter

RESULTS_PATH = Path("benchmark_results/franzosa_ibd_combined_omics_results.jsonl")

def normalize_answer(answer):
    if answer is None:
        return None

    answer = str(answer).strip().upper()

    if answer.startswith("A"):
        return "A"
    if answer.startswith("B"):
        return "B"

    if "IBD" in answer:
        return "A"
    if "CONTROL" in answer:
        return "B"

    return answer

def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def main():
    if not RESULTS_PATH.exists():
        print(f"Results file not found: {RESULTS_PATH}")
        print("\nExpected JSONL format per line:")
        print(json.dumps({
            "sample_id": "PRISM.9148",
            "variant": "combined_omics",
            "answer": "B",
            "model_answer": "B"
        }, indent=2))
        return

    records = load_jsonl(RESULTS_PATH)

    total = 0
    correct = 0

    by_label = Counter()
    by_label_correct = Counter()

    invalid = []

    for record in records:
        true_answer = normalize_answer(record.get("answer"))
        model_answer = normalize_answer(record.get("model_answer"))
        label = record.get("benchmark_label", "unknown")

        if model_answer not in {"A", "B"}:
            invalid.append(record)
            continue

        total += 1
        by_label[label] += 1

        if model_answer == true_answer:
            correct += 1
            by_label_correct[label] += 1

    print("\nEvaluation results")
    print("=" * 80)
    print(f"Results file: {RESULTS_PATH}")
    print(f"Valid predictions: {total}")
    print(f"Invalid predictions: {len(invalid)}")

    if total > 0:
        print(f"Accuracy: {correct / total:.3f} ({correct}/{total})")

    print("\nAccuracy by label")
    print("-" * 80)
    for label in sorted(by_label):
        n = by_label[label]
        c = by_label_correct[label]
        print(f"{label}: {c / n:.3f} ({c}/{n})")

    if invalid:
        print("\nFirst invalid predictions")
        print("-" * 80)
        for record in invalid[:5]:
            print({
                "sample_id": record.get("sample_id"),
                "model_answer": record.get("model_answer"),
            })

if __name__ == "__main__":
    main()