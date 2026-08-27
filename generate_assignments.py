"""
SPICE Human Evaluation — Participant/Story/Model Assignment Generator

Builds a randomized assignment of participants to (story, model) evaluation
items satisfying all four design conditions from the human-evaluation plan:

  1. Every participant sees each model exactly once.
  2. No participant sees the same story twice.
  3. Every (story, model) combination is rated by exactly REPLICATES_PER_CELL
     independent participants.
  4. Presentation order (the order items appear within a participant's
     session) is randomized.

Construction: a randomized, most-constrained-first greedy assignment with
restart-on-failure. This is NOT trial-and-error luck for these parameters —
18 stories is an exact multiple of 6 models, which makes this a balanced,
highly-resolvable design; the constrained-first heuristic exists mainly to
make the script robust if you change the story/model counts later to
something less balanced.

Independent verification: after construction, verify_assignment() re-checks
all three combinatorial conditions completely from scratch (it does not
reuse any bookkeeping from the builder), so a bad assignment can never be
silently written to disk.

Output:
  data/assignments.json          — {"groups": {"G01": [itemId, ...], ...}},
                                    in the format the evaluation app reads.
  data/assignment_summary.csv    — story x model grid of replicate counts,
                                    for a quick visual sanity check.
  data/participant_assignments.csv — one row per participant x model,
                                    for manual spot-checking.

IMPORTANT: item_id() below encodes the itemId convention this script
assumes your manifest.json uses. If your actual manifest IDs are built
differently, edit that one function — nothing else needs to change.
"""

import csv
import json
import random
from collections import Counter
from pathlib import Path

# ============================================================
# Study configuration — edit this section only.
# Everything downstream is derived from these lists/numbers,
# nothing else in the script hardcodes counts.
# ============================================================

STORY_IDS = [1, 8, 9, 15, 17, 24, 27, 28, 29, 32, 52, 53, 55, 57, 60, 64, 68, 79]

MODELS = [
    "NaiveBaseline",
    "StoryDiffusion_photomaker",
    "UNO",
    "NanoBanana",
    "QwenImageEdit-2509",
    "Gemini",
]

REPLICATES_PER_CELL = 3     # ratings required per (story, model) combination
RANDOM_SEED = 20260827          # set an int for a reproducible assignment
MAX_RESTARTS = 500          # restart budget if a random attempt dead-ends

OUTPUT_DIR = Path("data")
ASSIGNMENTS_JSON = OUTPUT_DIR / "assignments.json"
SUMMARY_CSV = OUTPUT_DIR / "assignment_summary.csv"
PARTICIPANT_CSV = OUTPUT_DIR / "participant_assignments.csv"


def item_id(story_id, model) -> str:
    """
    itemId convention expected in manifest.json. Adjust this to match your
    actual manifest if item IDs are built differently there — this is the
    only place that assumption lives.
    """
    return f"story{story_id:02d}_{model}"


# ============================================================
# Assignment construction
# ============================================================

def build_assignment(story_ids, models, replicates, seed=None, max_restarts=500):
    """
    Returns a list of participant rows: [{model: story_id, ...}, ...], one
    row per participant, satisfying conditions 1-3. Presentation order
    (condition 4) is applied separately at output time, not here. Raises
    RuntimeError if no valid assignment is found within max_restarts random
    attempts.
    """
    num_stories = len(story_ids)
    num_models = len(models)

    if num_models > num_stories:
        raise ValueError(
            f"Need at least as many stories ({num_stories}) as models "
            f"({num_models}) so each participant can see distinct stories."
        )

    total_participants = num_stories * replicates
    rng = random.Random(seed)

    for attempt in range(1, max_restarts + 1):
        need = {m: {s: replicates for s in story_ids} for m in models}
        rows = []
        ok = True

        for _ in range(total_participants):
            used_stories = set()
            row = {}
            remaining_models = list(models)

            while remaining_models:
                # Break ties randomly before sorting by scarcity, so we
                # don't always resolve ties in a fixed model order.
                rng.shuffle(remaining_models)

                def candidates_for(m):
                    return [
                        s for s in story_ids
                        if need[m][s] > 0 and s not in used_stories
                    ]

                # Most-constrained-first: place the model with the fewest
                # currently-valid candidates first, to minimize the chance
                # of a later model getting boxed in with zero options.
                remaining_models.sort(key=lambda m: len(candidates_for(m)))
                m = remaining_models.pop(0)
                candidates = candidates_for(m)

                if not candidates:
                    ok = False
                    break

                # Among valid candidates, prefer the story with the least
                # remaining slack across all models, so scarce stories
                # don't get starved of their required replicates later.
                def slack(s):
                    return sum(need[mm][s] for mm in models)

                min_slack = min(slack(s) for s in candidates)
                tightest = [s for s in candidates if slack(s) == min_slack]
                s = rng.choice(tightest)

                row[m] = s
                used_stories.add(s)
                need[m][s] -= 1

            if not ok:
                break
            rows.append(row)

        if ok and len(rows) == total_participants:
            if attempt > 1:
                print(f"Built valid assignment on attempt {attempt}.")
            return rows

    raise RuntimeError(
        f"Failed to build a valid assignment in {max_restarts} attempts. "
        f"Try increasing MAX_RESTARTS, or check that REPLICATES_PER_CELL "
        f"and the story/model counts are compatible."
    )


# ============================================================
# Independent verification
# ============================================================

def verify_assignment(rows, story_ids, models, replicates):
    """
    Re-checks all combinatorial design conditions from scratch against the
    final assignment — does not reuse any bookkeeping from build_assignment,
    so this catches bugs in the builder itself, not just confirm its own
    accounting. Raises AssertionError with a specific message on the first
    failure. Returns (True, report) on success.
    """
    report = {}

    # Condition 1: every participant sees each model exactly once.
    for i, row in enumerate(rows):
        assert set(row.keys()) == set(models), (
            f"Participant {i}: does not have exactly one entry per model. "
            f"Got models {sorted(row.keys())}, expected {sorted(models)}."
        )
    report["condition_1_each_model_once"] = "pass"

    # Condition 2: no repeated story within a participant.
    for i, row in enumerate(rows):
        stories_seen = list(row.values())
        assert len(stories_seen) == len(set(stories_seen)), (
            f"Participant {i}: repeats a story across models: {stories_seen}"
        )
    report["condition_2_no_repeated_story"] = "pass"

    # Condition 3: every (story, model) cell rated exactly `replicates` times.
    counts = Counter()
    for row in rows:
        for m, s in row.items():
            counts[(s, m)] += 1

    bad_cells = {cell: n for cell, n in counts.items() if n != replicates}
    missing_cells = [
        (s, m) for s in story_ids for m in models if (s, m) not in counts
    ]
    assert not bad_cells and not missing_cells, (
        f"Cell replicate mismatch. Wrong-count cells: {bad_cells}. "
        f"Never-rated cells: {missing_cells}."
    )
    report["condition_3_replicates_per_cell"] = "pass"
    report["total_participants"] = len(rows)
    report["total_ratings"] = sum(counts.values())
    report["expected_ratings"] = len(story_ids) * len(models) * replicates

    return True, report


def verify_presentation_order(groups: dict, item_ids_by_participant_unordered: dict):
    """
    Sanity check for condition 4: confirms the item SET shown to each
    participant is unchanged by shuffling (i.e. shuffling didn't drop or
    duplicate an item) and that at least some shuffling actually happened
    across the study (not e.g. every list left in the same relative order
    by coincidence).
    """
    for code, ordered in groups.items():
        unordered_expected = item_ids_by_participant_unordered[code]
        assert sorted(ordered) == sorted(unordered_expected), (
            f"{code}: shuffled item list does not match the original set. "
            f"Got {ordered}, expected some order of {unordered_expected}."
        )

    identical_order_count = sum(
        1
        for code, ordered in groups.items()
        if ordered == item_ids_by_participant_unordered[code]
    )
    total = len(groups)
    if total >= 10 and identical_order_count > total * 0.5:
        raise AssertionError(
            f"{identical_order_count}/{total} participants have an "
            f"unshuffled item order — presentation-order randomization "
            f"looks broken, not just unlucky."
        )


# ============================================================
# Output
# ============================================================

def to_assignments_json(rows, models, seed_for_order=None):
    """
    Converts participant rows into the {"groups": {code: [itemId, ...]}}
    structure the evaluation app reads, applying condition 4 (randomized
    presentation order) independently of the story/model assignment above.
    Also returns the pre-shuffle item sets per group, for
    verify_presentation_order().
    """
    rng = random.Random(seed_for_order)
    groups = {}
    unordered_by_group = {}

    for i, row in enumerate(rows, start=1):
        code = f"G{i:02d}"
        item_ids = [item_id(story_id, m) for m, story_id in row.items()]
        unordered_by_group[code] = list(item_ids)
        rng.shuffle(item_ids)  # condition 4
        groups[code] = item_ids

    return {"groups": groups}, unordered_by_group


def write_summary_csv(rows, story_ids, models, path):
    counts = Counter()
    for row in rows:
        for m, s in row.items():
            counts[(s, m)] += 1

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["story_id", *models])
        for s in story_ids:
            writer.writerow([s, *[counts[(s, m)] for m in models]])


def write_participant_csv(rows, path):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["participant", "model", "story_id", "item_id"])
        for i, row in enumerate(rows, start=1):
            code = f"G{i:02d}"
            for m, s in row.items():
                writer.writerow([code, m, s, item_id(s, m)])


# ============================================================
# Main
# ============================================================

def main():
    rows = build_assignment(
        STORY_IDS, MODELS, REPLICATES_PER_CELL,
        seed=RANDOM_SEED, max_restarts=MAX_RESTARTS,
    )

    _, report = verify_assignment(rows, STORY_IDS, MODELS, REPLICATES_PER_CELL)
    print("Combinatorial verification:")
    for k, v in report.items():
        print(f"  {k}: {v}")

    assignments, unordered_by_group = to_assignments_json(
        rows, MODELS, seed_for_order=RANDOM_SEED
    )
    verify_presentation_order(assignments["groups"], unordered_by_group)
    print("Presentation-order verification: pass")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ASSIGNMENTS_JSON.write_text(json.dumps(assignments, indent=2), encoding="utf-8")
    write_summary_csv(rows, STORY_IDS, MODELS, SUMMARY_CSV)
    write_participant_csv(rows, PARTICIPANT_CSV)

    print(f"\nWrote {len(rows)} participant groups to {ASSIGNMENTS_JSON}")
    print(f"Wrote per-cell replicate summary to {SUMMARY_CSV}")
    print(f"Wrote per-participant breakdown to {PARTICIPANT_CSV}")


if __name__ == "__main__":
    main()