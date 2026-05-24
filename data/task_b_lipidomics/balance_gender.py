# This script performs steps 1-3 of the class imbalance reduction pipeline:
#   1. Drop samples with NaN diabetes labels
#   2. Undersample Males down to Female count, stratified on diabetes status
#   3. Combine undersampled Males with all Females into a balanced dataset

import pandas as pd

RANDOM_SEED = 42
INPUT = "combined_lipidomics.tsv"
OUTPUT = "balanced_lipidomics.tsv"

df = pd.read_csv(INPUT, sep="\t")

# Step 1: Drop NaN diabetes rows
df = df.dropna(subset=["diabetes"])
print(f"After dropping NaN diabetes: {len(df)} samples")

# Step 2: Undersample Males stratified on diabetes
females = df[df["gender"] == "Female"]
males = df[df["gender"] == "Male"]

target_n = len(females)
diabetes_proportions = males["diabetes"].value_counts(normalize=True)

sampled_indices = []
for diabetes_label, group in males.groupby("diabetes"):
    n = round(target_n * diabetes_proportions[diabetes_label])
    sampled_indices.extend(group.sample(n=n, random_state=RANDOM_SEED).index)

males_sampled = males.loc[sampled_indices]

print(f"Males sampled: {len(males_sampled)} "
      f"(diabetes dist: {males_sampled['diabetes'].value_counts().to_dict()})")

# Step 3: Combine
balanced = pd.concat([females, males_sampled]).sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)

print(f"\nFinal balanced dataset: {len(balanced)} samples")
print(balanced["gender"].value_counts().to_string())

balanced.to_csv(OUTPUT, sep="\t", index=False)
print(f"\nWritten → {OUTPUT}")