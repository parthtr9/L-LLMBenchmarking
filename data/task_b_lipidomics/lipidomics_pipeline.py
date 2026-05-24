"""
Lipidomics Age & Diabetes Benchmark Pipeline
============================================
Loads the balanced lipidomics table (one row per plasma sample, ~497 lipid
species + age, gender, diabetes status) and emits three task formats:

  - MCQ:        Predict age bracket (20-39 / 40-59 / 60-79 / 80+) from the
                lipid profile alone.            Metric: accuracy.
  - Regression: Predict numeric age (years) from the lipid profile + diabetes
                status.                          Metric: MAE.
  - Binary:     Predict diabetes status (Yes/No) from the lipid profile +
                age in years.                    Metric: accuracy.

Inputs:
    --input balanced_lipidomics.tsv   (sample_id, individual_id, age, gender,
                                       diabetes, then N lipid feature columns)

Outputs (all written under --output-dir):
    task_b_lipidomics_train.{parquet,json}   80% train split
    task_b_lipidomics_test.{parquet,json}    20% test split
    task_b_lipidomics_summary.json           per-task + split statistics

Split:
    By individual_id (each individual's samples go entirely to one split).
    In MTBLS4461 each individual contributes a single sample, so the split is
    effectively random — we still implement it as a group split so future
    multi-sample-per-donor data does not leak.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


META_COLS = ["sample_id", "individual_id", "age", "gender", "diabetes"]

AGE_BIN_EDGES = [20, 40, 60, 80, 200]
AGE_BIN_LABELS = ["20-39", "40-59", "60-79", "80+"]
AGE_BRACKET_TO_LETTER = {"20-39": "A", "40-59": "B", "60-79": "C", "80+": "D"}

DIABETES_TO_LETTER = {"Yes": "A", "No": "B"}

SYSTEM_MSG = (
    "You are a biomedical AI specialized in lipidomics, plasma metabolite "
    "profiles, and aging biology."
)

STUDY_TAG = "MTBLS4461"


# ---------------------------------------------------------------------------
# 1. LOAD
# ---------------------------------------------------------------------------

def load_balanced(path: str) -> tuple[pd.DataFrame, list[str]]:
    """Load the balanced lipidomics TSV and split column list into meta + lipid."""
    df = pd.read_csv(path, sep="\t")
    missing = [c for c in META_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing metadata columns: {missing}")
    lipid_cols = [c for c in df.columns if c not in META_COLS]
    print(f"Loaded: {len(df):,} samples × {len(lipid_cols)} lipid features")
    print(f"  Age range: {df['age'].min()}–{df['age'].max()} "
          f"(median {df['age'].median():.0f})")
    print(f"  Diabetes:  {df['diabetes'].value_counts().to_dict()}")
    print(f"  Gender:    {df['gender'].value_counts().to_dict()}")
    return df, lipid_cols


def assign_age_bracket(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["age_bracket"] = pd.cut(
        df["age"],
        bins=AGE_BIN_EDGES,
        labels=AGE_BIN_LABELS,
        right=False,
    ).astype(str)
    counts = df["age_bracket"].value_counts().reindex(AGE_BIN_LABELS, fill_value=0)
    print(f"  Age brackets: {counts.to_dict()}")
    return df


# ---------------------------------------------------------------------------
# 2. PROMPT BUILDERS
# ---------------------------------------------------------------------------

def format_lipid_profile(row: pd.Series, lipid_cols: list[str]) -> str:
    """Render the lipid profile as a single comma-separated string.

    Drops NaN values (sample didn't measure that feature). Numeric values are
    rounded to 4 significant digits to keep prompt size sane.
    """
    parts = []
    for col in lipid_cols:
        val = row[col]
        if pd.isna(val):
            continue
        parts.append(f"{col}: {float(val):.4g}")
    return ", ".join(parts)


def _sample_context(row: pd.Series, include_age: bool, include_diabetes: bool) -> str:
    bits = [f"Sex: {row['gender']}"]
    if include_age:
        bits.append(f"Age: {int(row['age'])} years")
    if include_diabetes:
        bits.append(f"Diabetes status: {row['diabetes']}")
    bits.append("Measurement platform: DI-MS (alternating polarity)")
    bits.append(f"Study: {STUDY_TAG}")
    return ". ".join(bits) + "."


def _follow_up(row: pd.Series, extra: str = "") -> str:
    fu = (
        f"Donor age: {int(row['age'])} years. "
        f"Sex: {row['gender']}. "
        f"Diabetes status: {row['diabetes']}. "
        f"Sample: {row['sample_id']}. "
        f"Individual: {row['individual_id']}. "
        f"Study: {STUDY_TAG}."
    )
    if extra:
        fu += " " + extra
    return fu


def _base_metadata(row: pd.Series, follow_up: str) -> dict:
    return {
        "follow_up": follow_up,
        "sample_id": row["sample_id"],
        "individual_id": row["individual_id"],
        "age": int(row["age"]),
        "age_bracket": row["age_bracket"],
        "gender": row["gender"],
        "diabetes": row["diabetes"],
        "study": STUDY_TAG,
    }


# ---------------------------------------------------------------------------
# 3a. MCQ — age bracket from profile
# ---------------------------------------------------------------------------

def generate_mcq_prompt(row: pd.Series, lipid_cols: list[str],
                        lb_id_counter: int) -> dict:
    bracket = row["age_bracket"]
    answer = AGE_BRACKET_TO_LETTER[bracket]

    question = (
        "You are presented with a plasma lipidomics profile from a human donor. "
        "Given the following lipid species abundances, predict which age "
        "bracket the donor belongs to."
    )
    options = (
        "A. 20-39 years B. 40-59 years C. 60-79 years D. 80+ years"
    )
    profile = format_lipid_profile(row, lipid_cols)
    context = _sample_context(row, include_age=False, include_diabetes=False)

    user_content = (
        f"<question>\n{question}\n</question>\n"
        f"<options>\n{options}\n</options>\n"
        f"<lipid_profile>\n{profile}\n</lipid_profile>\n"
        f"<sample_context>\n{context}\n</sample_context>"
    )

    follow_up = _follow_up(
        row,
        extra=f"Correct bracket: {bracket} (answer {answer}).",
    )
    metadata = _base_metadata(row, follow_up)
    metadata["mcq_answer"] = answer

    return {
        "lb_id": f"LB-LIP-MCQ-{lb_id_counter:04d}",
        "pool": "lipidomics_age_mcq",
        "display_name": "Lipidomics Age / MCQ",
        "display_group": "Lipidomics Age",
        "domain": "lipidomics",
        "format": "mcq",
        "metric": "accuracy",
        "units": "age_bracket",
        "messages": [
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": answer},
        ],
        "task": "lipidomics_age_mcq",
        "has_reasoning": False,
        "metadata": json.dumps(metadata),
    }


# ---------------------------------------------------------------------------
# 3b. REGRESSION — age from profile + diabetes
# ---------------------------------------------------------------------------

def generate_regression_prompt(row: pd.Series, lipid_cols: list[str],
                               lb_id_counter: int) -> dict:
    answer = str(int(row["age"]))

    question = (
        "You are presented with a plasma lipidomics profile from a human donor "
        "together with the donor's diabetes status. Given this information, "
        "predict the donor's age in years. Respond with only a numeric value "
        "rounded to the nearest integer."
    )
    profile = format_lipid_profile(row, lipid_cols)
    context = _sample_context(row, include_age=False, include_diabetes=True)

    user_content = (
        f"<question>\n{question}\n</question>\n"
        f"<lipid_profile>\n{profile}\n</lipid_profile>\n"
        f"<sample_context>\n{context}\n</sample_context>"
    )

    follow_up = _follow_up(row, extra=f"Correct age: {answer} years.")
    metadata = _base_metadata(row, follow_up)
    metadata["regression_target"] = int(row["age"])

    return {
        "lb_id": f"LB-LIP-REG-{lb_id_counter:04d}",
        "pool": "lipidomics_age_regression",
        "display_name": "Lipidomics Age / Regression",
        "display_group": "Lipidomics Age",
        "domain": "lipidomics",
        "format": "regression",
        "metric": "mae",
        "units": "years",
        "messages": [
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": answer},
        ],
        "task": "lipidomics_age_regression",
        "has_reasoning": False,
        "metadata": json.dumps(metadata),
    }


# ---------------------------------------------------------------------------
# 3c. BINARY — diabetes from profile + age
# ---------------------------------------------------------------------------

def generate_binary_prompt(row: pd.Series, lipid_cols: list[str],
                           lb_id_counter: int) -> dict:
    answer = DIABETES_TO_LETTER[row["diabetes"]]

    question = (
        "You are presented with a plasma lipidomics profile from a human donor "
        "together with the donor's age in years. Given this information, "
        "predict whether the donor has been diagnosed with diabetes."
    )
    options = "A. Yes (diabetic) B. No (non-diabetic)"
    profile = format_lipid_profile(row, lipid_cols)
    context = _sample_context(row, include_age=True, include_diabetes=False)

    user_content = (
        f"<question>\n{question}\n</question>\n"
        f"<options>\n{options}\n</options>\n"
        f"<lipid_profile>\n{profile}\n</lipid_profile>\n"
        f"<sample_context>\n{context}\n</sample_context>"
    )

    follow_up = _follow_up(
        row,
        extra=f"Correct label: {row['diabetes']} (answer {answer}).",
    )
    metadata = _base_metadata(row, follow_up)
    metadata["binary_answer"] = answer

    return {
        "lb_id": f"LB-LIP-DIAB-{lb_id_counter:04d}",
        "pool": "lipidomics_diabetes_binary",
        "display_name": "Lipidomics Diabetes / Binary",
        "display_group": "Lipidomics Diabetes",
        "domain": "lipidomics",
        "format": "binary",
        "metric": "accuracy",
        "units": "diabetes",
        "messages": [
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": answer},
        ],
        "task": "lipidomics_diabetes_binary",
        "has_reasoning": False,
        "metadata": json.dumps(metadata),
    }


# ---------------------------------------------------------------------------
# 4. SAMPLING — keep classes balanced, avoid sample reuse across tasks
# ---------------------------------------------------------------------------

def _balanced_sample(df: pd.DataFrame, group_col: str, per_class: int,
                     rng: np.random.RandomState) -> pd.DataFrame:
    """Draw up to per_class rows from each value of group_col."""
    parts = []
    for label, group in df.groupby(group_col):
        take = min(per_class, len(group))
        parts.append(group.sample(take, random_state=rng))
    out = pd.concat(parts).sample(frac=1, random_state=rng).reset_index(drop=True)
    return out


def partition_for_tasks(df: pd.DataFrame, target_per_task: int,
                        random_state: int = 42) -> dict[str, pd.DataFrame]:
    """Split the input table into three disjoint subsets, one per task format.

    MCQ is fully balanced across 4 age brackets (capped by smallest bracket).
    Binary is fully balanced across Yes/No diabetes.
    Regression draws uniformly across the remaining pool (any age).

    Disjoint sampling: once a sample is allocated to a task, it cannot be
    reused. The 80+ bracket is sparse (~10 samples) so MCQ gets first pick,
    then binary, then regression.
    """
    rng = np.random.RandomState(random_state)
    pool = df.copy()
    used: set = set()

    # --- MCQ: balanced across 4 age brackets ---
    bracket_counts = pool["age_bracket"].value_counts()
    per_bracket = min(target_per_task // len(AGE_BIN_LABELS),
                      int(bracket_counts.min()))
    if per_bracket < 1:
        raise ValueError(
            f"Cannot build MCQ: smallest bracket has {bracket_counts.min()} samples"
        )
    mcq = _balanced_sample(pool, "age_bracket", per_bracket, rng)
    used.update(mcq["sample_id"].tolist())
    pool = pool[~pool["sample_id"].isin(used)]

    # --- Binary: balanced across diabetes Yes/No ---
    diab_counts = pool["diabetes"].value_counts()
    per_diab = min(target_per_task // 2, int(diab_counts.min()))
    binary = _balanced_sample(pool, "diabetes", per_diab, rng)
    used.update(binary["sample_id"].tolist())
    pool = pool[~pool["sample_id"].isin(used)]

    # --- Regression: roughly uniform across age brackets in remaining pool ---
    remaining_bracket_counts = pool["age_bracket"].value_counts()
    per_reg_bracket = max(
        1,
        min(
            target_per_task // len(AGE_BIN_LABELS),
            int(remaining_bracket_counts.min())
            if len(remaining_bracket_counts) == len(AGE_BIN_LABELS)
            else target_per_task // max(1, len(remaining_bracket_counts)),
        ),
    )
    reg = _balanced_sample(pool, "age_bracket", per_reg_bracket, rng)
    if len(reg) > target_per_task:
        reg = reg.sample(target_per_task, random_state=rng).reset_index(drop=True)

    print(f"\nPartition (target {target_per_task} per task):")
    print(f"  MCQ:        {len(mcq):3d} prompts "
          f"({per_bracket}/bracket × {len(AGE_BIN_LABELS)})")
    print(f"  Binary:     {len(binary):3d} prompts "
          f"({per_diab}/class × 2)")
    print(f"  Regression: {len(reg):3d} prompts "
          f"(stratified across remaining brackets)")
    return {"mcq": mcq, "regression": reg, "binary": binary}


# ---------------------------------------------------------------------------
# 5. TRAIN / TEST SPLIT BY individual_id
# ---------------------------------------------------------------------------

def _split_one_format(prompts: list[dict], test_fraction: float,
                      rng: np.random.RandomState
                      ) -> tuple[list[dict], list[dict], int, int]:
    """Group-split a single task's prompts by individual_id."""
    by_indiv: dict[str, list[int]] = {}
    for i, p in enumerate(prompts):
        meta = json.loads(p["metadata"])
        by_indiv.setdefault(meta["individual_id"], []).append(i)

    individuals = list(by_indiv.keys())
    rng.shuffle(individuals)

    total = len(prompts)
    target_test = int(round(total * test_fraction))
    test_ids: set = set()
    test_count = 0
    for ind in individuals:
        if test_count >= target_test:
            break
        test_ids.add(ind)
        test_count += len(by_indiv[ind])

    test_idxs = {i for ind in test_ids for i in by_indiv[ind]}
    train = [p for i, p in enumerate(prompts) if i not in test_idxs]
    test = [p for i, p in enumerate(prompts) if i in test_idxs]
    return train, test, len(individuals) - len(test_ids), len(test_ids)


def split_train_test_stratified(prompts_by_format: dict[str, list[dict]],
                                test_fraction: float = 0.20,
                                random_state: int = 42
                                ) -> tuple[list[dict], list[dict], dict]:
    """Stratified group split by individual_id, stratified by task format.

    Each task's prompts get split 80/20 independently, then concatenated.
    Guarantees each format hits the test fraction; donor leakage is still
    prevented within each task's split.
    """
    rng = np.random.RandomState(random_state)

    train_all: list[dict] = []
    test_all: list[dict] = []
    per_format = {}

    for fmt, prompts in prompts_by_format.items():
        if not prompts:
            continue
        train, test, n_train_ind, n_test_ind = _split_one_format(
            prompts, test_fraction, rng,
        )
        per_format[fmt] = {
            "n_train_prompts": len(train),
            "n_test_prompts": len(test),
            "n_train_individuals": n_train_ind,
            "n_test_individuals": n_test_ind,
            "actual_test_fraction": round(len(test) / max(len(prompts), 1), 4),
        }
        train_all.extend(train)
        test_all.extend(test)

    for p in train_all:
        m = json.loads(p["metadata"]); m["split"] = "train"
        p["metadata"] = json.dumps(m)
    for p in test_all:
        m = json.loads(p["metadata"]); m["split"] = "test"
        p["metadata"] = json.dumps(m)

    total = len(train_all) + len(test_all)
    report = {
        "stratified_by": "format",
        "grouped_by": "individual_id",
        "n_train_prompts": len(train_all),
        "n_test_prompts": len(test_all),
        "actual_test_fraction": round(len(test_all) / total, 4) if total else 0.0,
        "per_format": per_format,
    }

    print(f"\nTrain/test split (stratified by format, grouped by individual_id):")
    print(f"  Train: {len(train_all)} prompts")
    print(f"  Test:  {len(test_all)} prompts")
    print(f"  Actual test fraction: {report['actual_test_fraction']:.1%}")
    for fmt, stats in per_format.items():
        print(f"  {fmt:11s}  train={stats['n_train_prompts']:3d}  "
              f"test={stats['n_test_prompts']:3d}  "
              f"({stats['actual_test_fraction']:.1%} test)")

    return train_all, test_all, report


# ---------------------------------------------------------------------------
# 6. SAVE + SUMMARY
# ---------------------------------------------------------------------------

def save_prompts(prompts: list[dict], parquet_path: str, json_path: str) -> None:
    df = pd.DataFrame(prompts)
    df["messages"] = df["messages"].apply(json.dumps)
    df.to_parquet(parquet_path, index=False)
    print(f"  Parquet → {parquet_path}  ({len(df)} rows)")
    with open(json_path, "w") as f:
        json.dump(prompts, f, indent=2)
    print(f"  JSON    → {json_path}  ({len(prompts)} entries)")


def compute_summary(by_task: dict[str, list[dict]]) -> dict:
    def _stats(prompts: list[dict]) -> dict:
        if not prompts:
            return {"total_prompts": 0}
        labels = [p["messages"][-1]["content"] for p in prompts]
        meta_df = pd.DataFrame([json.loads(p["metadata"]) for p in prompts])
        return {
            "total_prompts": len(prompts),
            "format": prompts[0]["format"],
            "metric": prompts[0]["metric"],
            "label_distribution": {k: int(v) for k, v in
                                   pd.Series(labels).value_counts().items()},
            "unique_individuals": int(meta_df["individual_id"].nunique()),
            "age_range": [int(meta_df["age"].min()), int(meta_df["age"].max())],
        }

    return {
        "total_prompts": sum(len(v) for v in by_task.values()),
        "mcq": _stats(by_task.get("mcq", [])),
        "regression": _stats(by_task.get("regression", [])),
        "binary": _stats(by_task.get("binary", [])),
        "study": STUDY_TAG,
        "splitting_recommendation": (
            "Split by individual_id to prevent donor leakage. In MTBLS4461 "
            "each individual contributes one sample, so the split is "
            "effectively random — kept as a group split for forward "
            "compatibility with multi-sample-per-donor data."
        ),
    }


# ---------------------------------------------------------------------------
# 7. MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Lipidomics benchmark pipeline")
    parser.add_argument("--input", type=str, default="balanced_lipidomics.tsv",
                        help="Path to balanced lipidomics TSV")
    parser.add_argument("--output-dir", type=str, default=".",
                        help="Output directory")
    parser.add_argument("--target-per-task", type=int, default=50,
                        help="Target prompts per task format")
    parser.add_argument("--test-fraction", type=float, default=0.20,
                        help="Test set fraction (group split by individual_id)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed")
    parser.add_argument("--summary-output", type=str,
                        default="task_b_lipidomics_summary.json",
                        help="Summary JSON filename")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("LIPIDOMICS BENCHMARK PIPELINE")
    print("  Formats: MCQ (age bracket) + Regression (age) + Binary (diabetes)")
    print("  Split:   80/20 train/test by individual_id")
    print("=" * 60)

    print("\n--- Step 1: Load balanced lipidomics ---")
    df, lipid_cols = load_balanced(args.input)

    print("\n--- Step 2: Assign age brackets ---")
    df = assign_age_bracket(df)

    print("\n--- Step 3: Partition samples across tasks ---")
    parts = partition_for_tasks(df, args.target_per_task, args.seed)

    print("\n--- Step 4: Generate prompts ---")
    mcq_prompts = [generate_mcq_prompt(row, lipid_cols, i + 1)
                   for i, (_, row) in enumerate(parts["mcq"].iterrows())]
    reg_prompts = [generate_regression_prompt(row, lipid_cols, i + 1)
                   for i, (_, row) in enumerate(parts["regression"].iterrows())]
    bin_prompts = [generate_binary_prompt(row, lipid_cols, i + 1)
                   for i, (_, row) in enumerate(parts["binary"].iterrows())]
    print(f"  MCQ:        {len(mcq_prompts)}")
    print(f"  Regression: {len(reg_prompts)}")
    print(f"  Binary:     {len(bin_prompts)}")

    print("\n--- Step 5: Stratified train/test split by individual_id ---")
    train, test, split_report = split_train_test_stratified(
        {"mcq": mcq_prompts, "regression": reg_prompts, "binary": bin_prompts},
        test_fraction=args.test_fraction,
        random_state=args.seed,
    )

    print("\n--- Step 6: Save outputs ---")
    save_prompts(train,
                 str(out / "task_b_lipidomics_train.parquet"),
                 str(out / "task_b_lipidomics_train.json"))
    save_prompts(test,
                 str(out / "task_b_lipidomics_test.parquet"),
                 str(out / "task_b_lipidomics_test.json"))

    print("\n--- Step 7: Summary ---")
    summary = compute_summary({
        "mcq": mcq_prompts,
        "regression": reg_prompts,
        "binary": bin_prompts,
    })
    summary["split"] = split_report
    summary_path = out / args.summary_output
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary → {summary_path}")

    # Sample prompts for sanity check
    for label, prompts in [("MCQ", mcq_prompts),
                            ("REGRESSION", reg_prompts),
                            ("BINARY", bin_prompts)]:
        if not prompts:
            continue
        ex = prompts[0]
        print(f"\n--- Example {label} ---")
        print(f"lb_id: {ex['lb_id']}  format: {ex['format']}  metric: {ex['metric']}")
        user_msg = ex["messages"][1]["content"]
        # Truncate the lipid profile for legibility in the console
        if "<lipid_profile>" in user_msg:
            head, tail = user_msg.split("<lipid_profile>", 1)
            body, rest = tail.split("</lipid_profile>", 1)
            body_short = body[:240] + ("…" if len(body) > 240 else "")
            user_msg = f"{head}<lipid_profile>{body_short}</lipid_profile>{rest}"
        print(f"[user]\n{user_msg}")
        print(f"[assistant] {ex['messages'][2]['content']}")


if __name__ == "__main__":
    main()
