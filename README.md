# SPICE Human Evaluation Website — Data-Driven Version

This version is for GitHub Pages and uses a folder structure similar to the SPICE pipeline.

## Folder structure

```text
index.html
apps_script.gs
data/
  manifest.json
  assignments.json
  Model_A/
    story_01/
      prompts.json
      frames/
        shot_01.avif
        shot_02.avif
      refs/
        01.jpg
        02.jpg
  Model_B/
    story_01/
      prompts.json
      frames/
      refs/
```

The website reads `data/manifest.json`, `data/assignments.json`, and each story's `prompts.json`.

## prompts.json format

Recommended format:

```json
{
  "title": "Story title",
  "summary": "Short story introduction.",
  "characters": [
    {"name": "Character 1", "description": "...", "ref": "refs/01.jpg"}
  ],
  "shots": [
    {
      "shot_id": "shot_01",
      "plot": "Plot text for this shot.",
      "setting": "Setting description.",
      "static": "Static shot description.",
      "frame": "frames/shot_01.avif"
    }
  ]
}
```

## Multi-stage evaluation per story output

Each story-model output is no longer evaluated on only one page.

1. Story introduction page
   - story summary
   - reference character images
   - character descriptions

2. Shot-level text-image alignment pages
   - selected shots are shown one by one
   - each shot is displayed with plot, setting, and shot description
   - participants rate alignment for each selected shot

3. Full-sequence consistency page
   - all frames are shown in chronological order
   - participants rate identity, attribute, background, temporal smoothness, non-copy, and overall consistency

## Setup

1. Replace `CONFIG.googleAppsScriptUrl` in `index.html` with your deployed Apps Script Web App URL.
2. Replace `SPREADSHEET_ID` in `apps_script.gs`.
3. Replace demo `manifest.json` and `assignments.json`.
4. Upload real folders under `data/ModelName/story_XX/`.
5. Enable GitHub Pages from `main` branch, `/root`.
