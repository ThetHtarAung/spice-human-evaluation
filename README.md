# SPICE Human Evaluation Website — GitHub Pages Version

This package changes the platform from a local-only prototype into an online GitHub Pages website.

## Files

```text
index.html          Participant website for GitHub Pages
apps_script.gs      Google Apps Script backend for Google Sheets
storyboards/        Put standardized 5×6 storyboard PNG images here
items_template.csv  Metadata template
assignments_template.csv  Group assignment template
```

## Important

GitHub Pages is static. It cannot save responses by itself. This website sends responses to Google Sheets through Google Apps Script.

## Google Sheets backend setup

1. Create a Google Sheet.
2. Rename one sheet to `responses`.
3. Copy the Sheet ID from the URL.
4. Open `Extensions -> Apps Script`.
5. Paste `apps_script.gs`.
6. Replace:

```javascript
const SPREADSHEET_ID = "PASTE_YOUR_GOOGLE_SHEET_ID_HERE";
```

7. Deploy as Web App:

```text
Deploy -> New deployment -> Web app
Execute as: Me
Who has access: Anyone
```

8. Copy the Web App URL.
9. In `index.html`, replace:

```javascript
googleAppsScriptUrl: "PASTE_YOUR_GOOGLE_APPS_SCRIPT_WEB_APP_URL_HERE",
```

with your Web App URL.

## GitHub Pages setup

1. Create a GitHub repository, for example `spice-human-eval`.
2. Upload `index.html` and the `storyboards/` folder.
3. Go to `Settings -> Pages`.
4. Select:

```text
Deploy from branch
Branch: main
Folder: /root
```

5. Your participant link will be:

```text
https://YOUR_USERNAME.github.io/spice-human-eval/
```

## Storyboard images

Put each fixed 5×6 storyboard PNG in `storyboards/`.

Example:

```text
storyboards/story_01_A.png
storyboards/story_01_B.png
storyboards/story_01_C.png
```

## Before sharing with participants

- Replace demo `ITEMS` in `index.html` with your real 60 story-model outputs.
- Replace demo `ASSIGNMENTS` with 30 real group codes.
- Paste the Google Apps Script Web App URL.
- Test with one dummy group code and confirm rows appear in Google Sheets.
