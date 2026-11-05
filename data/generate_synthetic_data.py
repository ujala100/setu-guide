
from pathlib import Path

import numpy as np
import pandas as pd


# --------------------------------------------------
# Configuration
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent
INPUT_FILE = ROOT / "dating_app_behavior_sambandh_setu_synthetic.csv"
OUTPUT_FILE = ROOT / "dating_app_behavior_sambandh_setu_synthetic.csv"

N_ROWS = 50_000
RANDOM_SEED = 42

rng = np.random.default_rng(RANDOM_SEED)


# --------------------------------------------------
# Load existing synthetic dataset
# --------------------------------------------------

source = pd.read_csv(INPUT_FILE)

# These are the base columns inherited from the existing CSV.
# Their original upstream generation process is not documented here.
BASE_COLS = [
    "relationship_intent",
    "app_usage_time_min",
    "likes_received",
    "mutual_matches",
    "message_sent_count",
    "last_active_hour",
    "match_outcome",
    "synthetic_cohort_date",
]

missing = [c for c in BASE_COLS if c not in source.columns]
if missing:
    raise ValueError(f"Missing base columns: {missing}")

# Sample base records with replacement to generate 50,000 rows.
df = source[BASE_COLS].sample(
    n=N_ROWS,
    replace=True,
    random_state=RANDOM_SEED
).reset_index(drop=True)

df.insert(
    0,
    "record_id",
    [f"R{i:06d}" for i in range(1, N_ROWS + 1)]
)


# --------------------------------------------------
# Estimate conditional probabilities from old data
# --------------------------------------------------

def probability(column, condition=None):
    """Estimate an event probability from the existing synthetic data."""
    if column not in source.columns:
        return 0.0

    if condition is None:
        values = source[column]
    else:
        mask = condition.fillna(False).astype(bool)
        values = source.loc[mask, column]

    if len(values) == 0:
        return 0.0

    return float(values.fillna(0).astype(int).mean())


def generate_event(prob, eligible):
    """Generate an event only for eligible records."""
    eligible = np.asarray(eligible, dtype=bool)
    result = np.zeros(N_ROWS, dtype=int)
    result[eligible] = rng.binomial(
        1, np.clip(prob, 0, 1), eligible.sum()
    )
    return result


# --------------------------------------------------
# Generate the sequential journey
# --------------------------------------------------

# Connection established
p = probability("synthetic_connection_established")
df["synthetic_connection_established"] = rng.binomial(1, p, N_ROWS)

# Setu opened, only after connection
eligible = df["synthetic_connection_established"] == 1
p = probability("synthetic_setu_opened", eligible)
df["synthetic_setu_opened"] = generate_event(p, eligible)

# Setu explored, only after opening
eligible = df["synthetic_setu_opened"] == 1
p = probability("synthetic_setu_explored", eligible)
df["synthetic_setu_explored"] = generate_event(p, eligible)

# Building understanding
eligible = df["synthetic_setu_explored"] == 1
p = probability("synthetic_building_understanding_started", eligible)
df["synthetic_building_understanding_started"] = generate_event(p, eligible)

eligible = df["synthetic_building_understanding_started"] == 1
p = probability("synthetic_building_understanding_completed", eligible)
df["synthetic_building_understanding_completed"] = generate_event(p, eligible)

# Important discussions
eligible = df["synthetic_building_understanding_completed"] == 1
p = probability("synthetic_important_discussions_started", eligible)
df["synthetic_important_discussions_started"] = generate_event(p, eligible)

eligible = df["synthetic_important_discussions_started"] == 1
p = probability("synthetic_important_discussions_completed", eligible)
df["synthetic_important_discussions_completed"] = generate_event(p, eligible)

# Mutual readiness
eligible = df["synthetic_important_discussions_completed"] == 1
p = probability("synthetic_mutual_readiness_started", eligible)
df["synthetic_mutual_readiness_started"] = generate_event(p, eligible)

eligible = df["synthetic_mutual_readiness_started"] == 1
p = probability("synthetic_mutual_readiness_completed", eligible)
df["synthetic_mutual_readiness_completed"] = generate_event(p, eligible)

# Next-step decision
eligible = df["synthetic_mutual_readiness_completed"] == 1
p = probability("synthetic_next_step_decision_started", eligible)
df["synthetic_next_step_decision_started"] = generate_event(p, eligible)

eligible = df["synthetic_next_step_decision_started"] == 1
p = probability("synthetic_next_step_decision_completed", eligible)
df["synthetic_next_step_decision_completed"] = generate_event(p, eligible)


# --------------------------------------------------
# Derived progression indicators
# --------------------------------------------------

df["synthetic_progressed_building_understanding_to_important_discussions"] = (
    df["synthetic_building_understanding_completed"]
    * df["synthetic_important_discussions_started"]
)

df["synthetic_progressed_important_discussions_to_mutual_readiness"] = (
    df["synthetic_important_discussions_completed"]
    * df["synthetic_mutual_readiness_started"]
)

df["synthetic_progressed_mutual_readiness_to_next_step_decision"] = (
    df["synthetic_mutual_readiness_completed"]
    * df["synthetic_next_step_decision_started"]
)

# Discussion aliases
df["synthetic_discussion_started"] = df["synthetic_important_discussions_started"]
df["synthetic_discussion_completed"] = df["synthetic_important_discussions_completed"]

eligible = df["synthetic_discussion_started"] == 1
p = probability("synthetic_discussion_topic_selected", eligible)
df["synthetic_discussion_topic_selected"] = generate_event(p, eligible)

eligible = df["synthetic_discussion_started"] == 1
p = probability("synthetic_discussion_saved_for_later", eligible)
df["synthetic_discussion_saved_for_later"] = generate_event(p, eligible)

# Readiness aliases: one canonical mutual-readiness completion column
df["synthetic_readiness_started"] = df["synthetic_mutual_readiness_started"]
df["synthetic_readiness_completed"] = df["synthetic_mutual_readiness_completed"]

# Family involvement
eligible = df["synthetic_mutual_readiness_started"] == 1
p = probability("synthetic_family_involvement_eligible", eligible)
df["synthetic_family_involvement_eligible"] = generate_event(p, eligible)

eligible = df["synthetic_family_involvement_eligible"] == 1
p = probability("synthetic_family_involvement_started", eligible)
df["synthetic_family_involvement_started"] = generate_event(p, eligible)

eligible = df["synthetic_family_involvement_started"] == 1
p = probability("synthetic_family_member_invited", eligible)
df["synthetic_family_member_invited"] = generate_event(p, eligible)

# Next-step actions
eligible = df["synthetic_next_step_decision_started"] == 1
p = probability("synthetic_next_step_viewed", eligible)
df["synthetic_next_step_viewed"] = generate_event(p, eligible)

eligible = df["synthetic_next_step_viewed"] == 1
p = probability("synthetic_next_step_selected", eligible)
df["synthetic_next_step_selected"] = generate_event(p, eligible)

# Pause and re-engagement
p = probability("synthetic_journey_paused")
df["synthetic_journey_paused"] = rng.binomial(1, p, N_ROWS)

p = probability("synthetic_setu_reengaged")
df["synthetic_setu_reengaged"] = rng.binomial(1, p, N_ROWS)

# Final stage only after next-step completion
df["synthetic_final_stage_completed"] = (
    df["synthetic_next_step_decision_completed"]
)

# Provenance
df["data_provenance"] = (
    "synthetic_regeneration_from_existing_base_csv"
)


# --------------------------------------------------
# Validation
# --------------------------------------------------

completion_pairs = [
    ("synthetic_building_understanding_started",
     "synthetic_building_understanding_completed"),
    ("synthetic_important_discussions_started",
     "synthetic_important_discussions_completed"),
    ("synthetic_mutual_readiness_started",
     "synthetic_mutual_readiness_completed"),
    ("synthetic_next_step_decision_started",
     "synthetic_next_step_decision_completed"),
]

for started, completed in completion_pairs:
    invalid = (
        (df[completed] == 1) & (df[started] == 0)
    ).sum()

    assert invalid == 0, f"{completed} has {invalid} invalid completions"

assert len(df) == N_ROWS
assert df.columns.is_unique
assert list(df.columns).count(
    "synthetic_mutual_readiness_completed"
) == 1
assert "synthetic_mutual_readiness_completed.1" not in df.columns

# Save regenerated dataset
df.to_csv(OUTPUT_FILE, index=False)

print("Dataset regenerated successfully.")
print("Shape:", df.shape)
print("Duplicate columns:", df.columns.duplicated().sum())
print("Invalid stage completions: 0")
print(
    "Mutual readiness completion columns:",
    list(df.columns).count("synthetic_mutual_readiness_completed")
)
print("Saved to:", OUTPUT_FILE)
