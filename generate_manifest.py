"""
SPICE / ViStoryBench-Lite manifest generator

General behavior:
- Uses the real folder structure:
    data/VistoryBench/story_info/story_XX/
    data/VistoryBench/<model>/story_XX/
- Uses 1-based shot numbering:
    shot_01 ... shot_N
- Automatically detects ANY missing shot.
- Missing shots are recorded in manifest.json.
- Missing shots do NOT stop manifest generation.
- Unexpected extra shot numbers still raise an error.
- The manifest preserves exact shot positions so text/image alignment
  never shifts after a missing frame.

Expected layout:

data/
└── VistoryBench/
    ├── story_info/
    │   ├── story_01/
    │   │   ├── story.json       # or prompts.json
    │   │   └── image/
    │   │       └── character_name/
    │   │           ├── 00.jpg
    │   │           └── 01.jpg
    │   └── ...
    │
    ├── NaiveBaseline/
    │   └── story_01/
    │       ├── shot_01.avif
    │       ├── shot_02.avif
    │       └── ...
    │
    ├── StoryDiffusion_photomaker/
    ├── UNO/
    ├── NanoBanana/
    ├── QwenImageEdit-2509/
    └── Gemini/

Manifest fields per model-story item:
- numFrames:
    expected number of story shots
- availableFrames:
    number of actual generated images found
- coverage:
    availableFrames / numFrames
- missingShots:
    automatically detected missing shot numbers
- frames:
    fixed-length shot-position records
- frameFiles:
    fixed-length compatibility list; missing positions are null
- availableFrameFiles:
    only actual image files, useful when missing frames should be skipped
"""

import json
import re
from pathlib import Path


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

# Your terminal log showed this exact spelling.
# If your folder is actually "ViStoryBench", change only this line.
DATA_ROOT = PROJECT_ROOT / "data" / "VistoryBench"

STORY_INFO_ROOT = DATA_ROOT / "story_info"
MANIFEST_PATH = PROJECT_ROOT / "data" / "manifest.json"


# ============================================================
# Study stories
# ============================================================

STORY_FRAME_COUNTS = {
    1: 23,
    8: 21,
    9: 25,
    15: 26,
    17: 13,
    24: 15,
    27: 15,
    28: 5,
    29: 14,
    32: 10,
    52: 19,
    53: 16,
    55: 17,
    57: 4,
    60: 8,
    64: 5,
    68: 5,
    79: 14,
}


# ============================================================
# Models
# ============================================================

MODELS = [
    {"model": "NaiveBaseline", "modelGroup": "Baseline", "modelBlind": "Model A"},
    {"model": "StoryDiffusion_photomaker", "modelGroup": "Mid", "modelBlind": "Model B"},
    {"model": "UNO", "modelGroup": "Strong", "modelBlind": "Model C"},
    {"model": "NanoBanana", "modelGroup": "Strong", "modelBlind": "Model D"},
    {"model": "QwenImageEdit-2509", "modelGroup": "Strong", "modelBlind": "Model E"},
    {"model": "Gemini", "modelGroup": "Frontier", "modelBlind": "Model F"},
]


IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".avif",
    ".bmp",
}

SHOT_RE = re.compile(r"^shot_(\d+)$", flags=re.IGNORECASE)


# ============================================================
# Helpers
# ============================================================

def natural_key(path: Path):
    return [
        int(x) if x.isdigit() else x.lower()
        for x in re.split(r"(\d+)", path.name)
    ]


def rel_to_project(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def item_id(story_id: int, model: str) -> str:
    return f"story{story_id:02d}_{model}"


# ============================================================
# Story JSON
# ============================================================

def find_story_file(story_dir: Path):
    """
    Priority:
        1. story.json
        2. prompts.json
    """
    for filename in ("story.json", "prompts.json"):
        path = story_dir / filename
        if path.exists():
            return path
    return None


# ============================================================
# Reference images
# ============================================================

def build_references(story_dir: Path):
    """
    Example:

    story_info/story_01/image/
        Alice/
            00.jpg
            01.jpg
        Bob/
            00.jpg
    """
    image_root = story_dir / "image"

    if not image_root.exists():
        return [], []

    references = []
    flat_files = []

    character_dirs = sorted(
        [p for p in image_root.iterdir() if p.is_dir()],
        key=lambda p: p.name.lower(),
    )

    for character_dir in character_dirs:
        files = sorted(
            [
                p
                for p in character_dir.rglob("*")
                if p.is_file()
                and p.suffix.lower() in IMAGE_EXTENSIONS
            ],
            key=natural_key,
        )

        if not files:
            continue

        relative_files = [
            p.relative_to(story_dir).as_posix()
            for p in files
        ]

        references.append({
            "character": character_dir.name,
            "files": relative_files,
        })

        flat_files.extend(relative_files)

    # Also support references placed directly under image/
    direct_files = sorted(
        [
            p
            for p in image_root.iterdir()
            if p.is_file()
            and p.suffix.lower() in IMAGE_EXTENSIONS
        ],
        key=natural_key,
    )

    if direct_files:
        direct_relative = [
            p.relative_to(story_dir).as_posix()
            for p in direct_files
        ]

        references.append({
            "character": "Reference",
            "files": direct_relative,
        })

        flat_files.extend(direct_relative)

    return references, flat_files


# ============================================================
# Generated frames
# ============================================================

def generated_frames(output_dir: Path):
    """
    Reads:
        model/story_01/shot_01.avif
        model/story_01/shot_02.avif
        ...
    """
    if not output_dir.exists():
        return []

    files = []

    for p in output_dir.iterdir():
        if not p.is_file():
            continue

        if p.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        if not SHOT_RE.match(p.stem):
            continue

        files.append(p)

    return sorted(files, key=natural_key)


def get_shot_number(path: Path):
    match = SHOT_RE.match(path.stem)
    return int(match.group(1)) if match else None


def map_frames_by_number(frames):
    """
    Example:
        shot_01.avif
        shot_03.avif

    becomes:
        {
            1: Path(...shot_01.avif),
            3: Path(...shot_03.avif)
        }
    """
    result = {}

    for frame in frames:
        number = get_shot_number(frame)

        if number is None:
            continue

        if number in result:
            raise ValueError(
                f"Duplicate shot number {number}: "
                f"{result[number]} and {frame}"
            )

        result[number] = frame

    return result


# ============================================================
# Main
# ============================================================

def main():
    items = []
    errors = []
    warnings = []

    print("=" * 68)
    print("SPICE / ViStoryBench-Lite manifest generator")
    print("=" * 68)
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Data root:    {DATA_ROOT}")

    if not DATA_ROOT.exists():
        raise SystemExit(
            f"\nData root does not exist:\n  {DATA_ROOT}\n"
            "Check whether your folder is named VistoryBench or ViStoryBench."
        )

    if not STORY_INFO_ROOT.exists():
        raise SystemExit(
            f"\nStory-info folder does not exist:\n  {STORY_INFO_ROOT}"
        )

    for story_id, expected_frames in STORY_FRAME_COUNTS.items():
        story_code = f"{story_id:02d}"
        story_folder = f"story_{story_id:02d}"

        # ----------------------------------------------------
        # Shared story information
        # ----------------------------------------------------
        story_dir = STORY_INFO_ROOT / story_folder

        if not story_dir.exists():
            errors.append(
                f"Story {story_code}: missing story folder: {story_dir}"
            )
            story_file = None
            references = []
            ref_files = []

        else:
            story_file = find_story_file(story_dir)

            if story_file is None:
                errors.append(
                    f"Story {story_code}: missing story.json / prompts.json "
                    f"in {story_dir}"
                )

            references, ref_files = build_references(story_dir)

            if not ref_files:
                warnings.append(
                    f"Story {story_code}: no reference images found under "
                    f"{story_dir / 'image'}"
                )

        # ----------------------------------------------------
        # Models
        # ----------------------------------------------------
        for spec in MODELS:
            model = spec["model"]
            model_group = spec["modelGroup"]
            model_blind = spec["modelBlind"]

            output_dir = DATA_ROOT / model / story_folder

            if not output_dir.exists():
                # A completely missing model/story folder is still serious.
                errors.append(
                    f"Missing output folder: {output_dir}"
                )
                frame_map = {}
                frames = []

            else:
                frames = generated_frames(output_dir)

                if not frames:
                    # Entirely empty sequence remains an error.
                    errors.append(
                        f"No shot_XX image files found: {output_dir}"
                    )
                    frame_map = {}
                else:
                    try:
                        frame_map = map_frames_by_number(frames)
                    except ValueError as exc:
                        errors.append(
                            f"{model} / Story {story_code}: {exc}"
                        )
                        frame_map = {}

            # Expected ViStoryBench positions are shot_01 ... shot_N.
            expected_numbers = set(
                range(1, expected_frames + 1)
            )

            actual_numbers = set(
                frame_map.keys()
            )

            missing_numbers = sorted(
                expected_numbers - actual_numbers
            )

            extra_numbers = sorted(
                actual_numbers - expected_numbers
            )

            # Extra shot positions are likely a data/file naming problem,
            # so keep them as errors.
            if extra_numbers:
                errors.append(
                    f"{model} / Story {story_code}: "
                    f"unexpected extra shot numbers: {extra_numbers}"
                )

            # Any partial missing shots are allowed and recorded.
            if missing_numbers and frames:
                warnings.append(
                    f"{model} / Story {story_code}: "
                    f"missing generated shot(s): {missing_numbers}. "
                    f"They will be recorded and skipped during evaluation."
                )

            # ------------------------------------------------
            # Build exact expected positions.
            # ------------------------------------------------
            frame_records = []
            frame_files = []
            available_frame_files = []

            for shot_number in range(1, expected_frames + 1):
                frame_path = frame_map.get(shot_number)

                if frame_path is None:
                    relative_file = None
                    missing = True
                else:
                    relative_file = (
                        frame_path
                        .relative_to(output_dir)
                        .as_posix()
                    )
                    missing = False
                    available_frame_files.append(relative_file)

                # Fixed-length compatibility list.
                # Null preserves the missing shot position.
                frame_files.append(relative_file)

                frame_records.append({
                    "shotNumber": shot_number,
                    "file": relative_file,
                    "missing": missing,
                })

            available_frames = sum(
                1
                for record in frame_records
                if not record["missing"]
            )

            coverage = (
                available_frames / expected_frames
                if expected_frames
                else 0.0
            )

            items.append({
                "itemId": item_id(story_id, model),
                "dataset": "ViStoryBench-Lite",

                "storyId": story_code,
                "storyFolder": story_folder,
                "storyNumber": story_id,

                "model": model,
                "modelGroup": model_group,
                "modelBlind": model_blind,

                "storyPath": rel_to_project(story_dir),
                "outputPath": rel_to_project(output_dir),

                "storyFile":
                    story_file.name
                    if story_file
                    else "",

                # Expected story positions
                "numFrames": expected_frames,

                # Actual generated images
                "availableFrames": available_frames,

                # Fraction successfully generated
                "coverage": round(coverage, 6),

                # Automatically detected
                "missingShots": missing_numbers,

                # Fixed-length; null at missing positions
                "frameFiles": frame_files,

                # Only real images; convenient for sampling available frames
                "availableFrameFiles": available_frame_files,

                # Rich exact-position representation
                "frames": frame_records,

                "numRefs": len(ref_files),
                "refFiles": ref_files,
                "references": references,
            })

    # ========================================================
    # Summary
    # ========================================================

    expected_items = (
        len(STORY_FRAME_COUNTS)
        * len(MODELS)
    )

    total_expected_frames = (
        sum(STORY_FRAME_COUNTS.values())
        * len(MODELS)
    )

    total_available_frames = sum(
        item["availableFrames"]
        for item in items
    )

    total_missing_frames = (
        total_expected_frames
        - total_available_frames
    )

    items_with_missing = [
        item
        for item in items
        if item["missingShots"]
    ]

    print()
    print(f"Stories:                    {len(STORY_FRAME_COUNTS)}")
    print(f"Models:                     {len(MODELS)}")
    print(f"Expected manifest items:    {expected_items}")
    print(f"Built items:                {len(items)}")
    print(f"Expected generated shots:   {total_expected_frames}")
    print(f"Available generated shots:  {total_available_frames}")
    print(f"Missing generated shots:    {total_missing_frames}")
    print(f"Sequences with missing shots:{len(items_with_missing)}")

    # ========================================================
    # Warnings
    # ========================================================

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print("  -", warning)

    # ========================================================
    # Errors
    # ========================================================

    if errors:
        print("\nERRORS:")
        for error in errors:
            print("  -", error)

        raise SystemExit(
            "\nmanifest.json was NOT written.\n"
            "Partial missing shots are allowed, but missing folders, "
            "empty sequences, duplicate shot numbers, or extra shot numbers "
            "must still be fixed."
        )

    if len(items) != expected_items:
        raise SystemExit(
            f"\nInternal validation failed: expected {expected_items} "
            f"items but built {len(items)}."
        )

    # ========================================================
    # Write manifest
    # ========================================================

    MANIFEST_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest = {
        "dataset": "ViStoryBench-Lite",

        "storyCount":
            len(STORY_FRAME_COUNTS),

        "modelCount":
            len(MODELS),

        "itemCount":
            len(items),

        "expectedGeneratedFrames":
            total_expected_frames,

        "availableGeneratedFrames":
            total_available_frames,

        "missingGeneratedFrames":
            total_missing_frames,

        "sequencesWithMissingFrames":
            len(items_with_missing),

        "stories": [
            f"{s:02d}"
            for s in STORY_FRAME_COUNTS
        ],

        "models": [
            m["model"]
            for m in MODELS
        ],

        "items":
            items,
    }

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print(f"Wrote: {MANIFEST_PATH}")
    print(
        f"Validation passed: {expected_items} model-story items. "
        f"{total_missing_frames} missing generated shot(s) were "
        f"automatically recorded."
    )


if __name__ == "__main__":
    main()
