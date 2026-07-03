/*
Google Apps Script backend for SPICE human evaluation.

Setup:
1. Create a Google Sheet.
2. Rename one sheet to: responses
3. Extensions -> Apps Script.
4. Paste this file.
5. Replace SPREADSHEET_ID below.
6. Deploy -> New deployment -> Web app.
7. Execute as: Me.
8. Who has access: Anyone.
9. Copy the Web App URL into CONFIG.googleAppsScriptUrl in index.html.
*/

const SPREADSHEET_ID = "PASTE_YOUR_GOOGLE_SHEET_ID_HERE";
const SHEET_NAME = "responses";

function doPost(e) {
  try {
    const sheet = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SHEET_NAME);
    const data = JSON.parse(e.postData.contents);
    ensureHeader_(sheet);

    const itemMetaById = {};
    (data.itemMeta || []).forEach(item => itemMetaById[item.itemId] = item);

    const rows = [];
    Object.entries(data.responses || {}).forEach(([itemId, r]) => {
      const meta = itemMetaById[itemId] || {};
      rows.push([
        data.pid || "",
        data.groupId || "",
        data.timestamp || "",
        data.participantMeta?.vision || "",
        data.participantMeta?.aiExperience || "",
        data.participantMeta?.designExperience || "",
        itemId,
        meta.storyId || "",
        meta.title || "",
        meta.modelBlind || "",
        meta.modelReal || "",
        meta.numFrames || "",
        r.q1_identity ?? "",
        r.q2_attribute ?? "",
        r.q3_background ?? "",
        r.q4_temporal ?? "",
        r.q5_alignment ?? "",
        r.q6_noncopy ?? "",
        r.q7_overall ?? "",
        (r.na || []).join(";"),
        r.itemStartTime || "",
        r.itemEndTime || "",
        r.durationSec || "",
        (data.itemOrder || []).join(";"),
        data.userAgent || "",
        data.screen?.width || "",
        data.screen?.height || "",
        data.screen?.devicePixelRatio || ""
      ]);
    });

    if (rows.length > 0) {
      sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
    }

    return ContentService
      .createTextOutput(JSON.stringify({status: "ok", rows: rows.length}))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({status: "error", message: String(err)}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet() {
  return ContentService
    .createTextOutput("SPICE human evaluation backend is running.")
    .setMimeType(ContentService.MimeType.TEXT);
}

function ensureHeader_(sheet) {
  if (sheet.getLastRow() > 0) return;
  const header = [
    "participant_id", "group_id", "timestamp", "vision", "ai_experience", "design_experience",
    "item_id", "story_id", "title", "model_blind", "model_real", "num_frames",
    "q1_identity", "q2_attribute", "q3_background", "q4_temporal", "q5_alignment", "q6_noncopy", "q7_overall",
    "na_questions", "item_start_time", "item_end_time", "duration_sec", "item_order", "user_agent",
    "screen_width", "screen_height", "device_pixel_ratio"
  ];
  sheet.getRange(1, 1, 1, header.length).setValues([header]);
}
