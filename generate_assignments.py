"""
SPICE Main Study v2 assignment generator

Design:
- 12 main-study stories
- 6 generation models
- 50 participant groups (G01-G50)
- 4 sequences per participant
- 200 total sequence evaluations
- each participant sees 4 different stories and 4 different models
- every story-model cell receives either 2 or 3 raters
- total coverage: 56 cells x 3 raters + 16 cells x 2 raters = 200
- presentation order randomized within each participant

The six reserved stories (24, 52, 55, 60, 68, 79) are NOT used here.
They are reserved for calibration/training examples.
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter
from pathlib import Path

MAIN_STORY_IDS = [1, 8, 9, 15, 17, 27, 28, 29, 32, 53, 57, 64]
RESERVED_TRAINING_STORY_IDS = [24, 52, 55, 60, 68, 79]

MODELS = [
    "NaiveBaseline",
    "StoryDiffusion_photomaker",
    "UNO",
    "NanoBanana",
    "QwenImageEdit-2509",
    "Gemini",
]

NUM_GROUPS = 50
ITEMS_PER_GROUP = 4
TOTAL_EVALUATIONS = NUM_GROUPS * ITEMS_PER_GROUP
RANDOM_SEED = 20261008
MAX_RESTARTS = 10000

OUTPUT_DIR = Path("data")
ASSIGNMENTS_JSON = OUTPUT_DIR / "assignments.json"
SUMMARY_CSV = OUTPUT_DIR / "assignment_summary.csv"
PARTICIPANT_CSV = OUTPUT_DIR / "participant_assignments.csv"


def item_id(story_id: int, model: str) -> str:
    return f"story{story_id:02d}_{model}"


def choose_double_rated_cells(stories, models, rng):
    """
    There are 72 story-model cells. If every cell had 3 raters we would need
    216 ratings, but the 50x4 design provides 200. Therefore exactly 16 cells
    receive 2 raters and the remaining 56 receive 3.

    Balance target:
    - 8 stories have one double-rated cell -> 17 ratings/story
    - 4 stories have two double-rated cells -> 16 ratings/story
    - 2 models have two double-rated cells -> 34 ratings/model
    - 4 models have three double-rated cells -> 33 ratings/model
    """
    story_degree = {s: 1 for s in stories}
    # Give four stories one additional double-rated cell.
    extra_stories = list(stories)
    rng.shuffle(extra_stories)
    for s in extra_stories[:4]:
        story_degree[s] = 2

    model_degree = {m: 3 for m in models}
    # Two models have only two double-rated cells.
    lighter_models = list(models)
    rng.shuffle(lighter_models)
    for m in lighter_models[:2]:
        model_degree[m] = 2

    # Randomized degree-constrained bipartite construction.
    for _ in range(5000):
        remaining_model = dict(model_degree)
        chosen = []
        ok = True

        story_order = list(stories)
        rng.shuffle(story_order)
        story_order.sort(key=lambda s: -story_degree[s])

        for s in story_order:
            need = story_degree[s]
            candidates = [m for m in models if remaining_model[m] > 0]
            rng.shuffle(candidates)
            candidates.sort(key=lambda m: -remaining_model[m])
            picks = candidates[:need]
            if len(picks) != need:
                ok = False
                break
            for m in picks:
                chosen.append((s, m))
                remaining_model[m] -= 1

        if ok and all(v == 0 for v in remaining_model.values()):
            return set(chosen)

    raise RuntimeError("Could not construct balanced 2-rater cells.")


def build_target_counts(stories, models, rng):
    double_cells = choose_double_rated_cells(stories, models, rng)
    counts = {
        (s, m): (2 if (s, m) in double_cells else 3)
        for s in stories
        for m in models
    }
    assert sum(counts.values()) == TOTAL_EVALUATIONS
    return counts, double_cells


def build_groups(target_counts, rng):
    """Pack all required cell copies into 50 four-item participant groups.

    Each group is a matching in the story x model bipartite graph:
    no repeated story and no repeated model. With 50 groups, this is much
    less restrictive than the maximum story/model degree, so randomized
    balanced coloring converges quickly.
    """
    base_edges = []
    for cell, n in target_counts.items():
        base_edges.extend([cell] * n)

    for attempt in range(1, MAX_RESTARTS + 1):
        edges = list(base_edges)
        rng.shuffle(edges)
        # Place the 3-copy cells before 2-copy cells; random order remains
        # within equal multiplicities.
        edges.sort(key=lambda c: -target_counts[c])

        groups = [[] for _ in range(NUM_GROUPS)]
        used_stories = [set() for _ in range(NUM_GROUPS)]
        used_models = [set() for _ in range(NUM_GROUPS)]
        failed = False

        for s, m in edges:
            candidates = [
                g for g in range(NUM_GROUPS)
                if len(groups[g]) < ITEMS_PER_GROUP
                and s not in used_stories[g]
                and m not in used_models[g]
            ]

            if not candidates:
                failed = True
                break

            # Keep groups balanced while retaining randomized assignment.
            min_load = min(len(groups[g]) for g in candidates)
            candidates = [g for g in candidates if len(groups[g]) == min_load]
            g = rng.choice(candidates)

            groups[g].append((s, m))
            used_stories[g].add(s)
            used_models[g].add(m)

        if not failed and all(len(g) == ITEMS_PER_GROUP for g in groups):
            for group in groups:
                rng.shuffle(group)
            if attempt > 1:
                print(f"Assignment built on restart {attempt}.")
            return groups

    raise RuntimeError(
        f"Failed to pack the assignment after {MAX_RESTARTS} restarts."
    )


def verify(groups, target_counts, stories, models):
    assert len(groups) == NUM_GROUPS
    assert all(len(g) == ITEMS_PER_GROUP for g in groups)

    observed = Counter()
    for i, group in enumerate(groups, start=1):
        ss = [s for s, _m in group]
        mm = [m for _s, m in group]
        assert len(ss) == len(set(ss)), f"G{i:02d} repeats a story: {ss}"
        assert len(mm) == len(set(mm)), f"G{i:02d} repeats a model: {mm}"
        for cell in group:
            assert cell[0] in stories
            assert cell[1] in models
            observed[cell] += 1

    assert dict(observed) == target_counts

    story_counts = Counter()
    model_counts = Counter()
    for (s, m), n in observed.items():
        story_counts[s] += n
        model_counts[m] += n

    assert max(story_counts.values()) - min(story_counts.values()) <= 1
    assert max(model_counts.values()) - min(model_counts.values()) <= 1
    assert set(observed.values()) <= {2, 3}
    assert sum(observed.values()) == TOTAL_EVALUATIONS

    return story_counts, model_counts


def write_outputs(groups, target_counts, double_cells):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    groups_json = {
        "groups": {
            f"G{i:02d}": [item_id(s, m) for s, m in group]
            for i, group in enumerate(groups, start=1)
        },
        "design": {
            "version": "SPICE-HUMAN-2026-MAIN-v2",
            "main_story_ids": MAIN_STORY_IDS,
            "reserved_training_story_ids": RESERVED_TRAINING_STORY_IDS,
            "participants": NUM_GROUPS,
            "items_per_participant": ITEMS_PER_GROUP,
            "total_evaluations": TOTAL_EVALUATIONS,
            "cell_replication": "56 cells x3; 16 cells x2",
            "random_seed": RANDOM_SEED,
        },
    }
    ASSIGNMENTS_JSON.write_text(
        json.dumps(groups_json, indent=2), encoding="utf-8"
    )

    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["story_id", *MODELS, "story_total"])
        for s in MAIN_STORY_IDS:
            vals = [target_counts[(s, m)] for m in MODELS]
            w.writerow([s, *vals, sum(vals)])
        model_totals = [
            sum(target_counts[(s, m)] for s in MAIN_STORY_IDS)
            for m in MODELS
        ]
        w.writerow(["MODEL_TOTAL", *model_totals, sum(model_totals)])

    with PARTICIPANT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group_id", "position", "story_id", "model", "item_id"])
        for i, group in enumerate(groups, start=1):
            for pos, (s, m) in enumerate(group, start=1):
                w.writerow([f"G{i:02d}", pos, s, m, item_id(s, m)])

    print(f"Wrote {ASSIGNMENTS_JSON}")
    print(f"Wrote {SUMMARY_CSV}")
    print(f"Wrote {PARTICIPANT_CSV}")
    print("Double-rated cells (2 raters):")
    for s, m in sorted(double_cells):
        print(f"  story {s:02d} x {m}")


def main():
    rng = random.Random(RANDOM_SEED)
    target_counts, double_cells = build_target_counts(
        MAIN_STORY_IDS, MODELS, rng
    )
    groups = build_groups(target_counts, rng)
    story_counts, model_counts = verify(
        groups, target_counts, MAIN_STORY_IDS, MODELS
    )

    print("Verification passed.")
    print("Story totals:", dict(sorted(story_counts.items())))
    print("Model totals:", dict(model_counts))
    print("Cell count distribution:", dict(Counter(target_counts.values())))

    write_outputs(groups, target_counts, double_cells)


if __name__ == "__main__":
    main()
