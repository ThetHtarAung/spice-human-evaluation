/* Google Apps Script backend for data-driven SPICE human evaluation */
const SPREADSHEET_ID = "AKfycbxDOI_Vt9-YuBHQQNV1MXONbUGuoOgV-3Kkym7tnI8xtmCo0xfBFal-dtffO9ypkrLH";
const SHEET_NAME = "responses";

function doPost(e) {
  try {
    const sheet = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SHEET_NAME);
    ensureHeader_(sheet);
    const data = JSON.parse(e.postData.contents);
    const rows = [];
    Object.entries(data.responses || {}).forEach(([itemId, r]) => {
      const meta = data.itemMeta || {};
      rows.push([
        data.pid || "",
        data.groupId || "",
        data.timestamp || "",
        data.participantMeta?.vision || "",
        data.participantMeta?.aiExperience || "",
        data.participantMeta?.designExperience || "",
        itemId,
        meta.storyId || "",
        meta.modelBlind || "",
        meta.modelReal || "",
        meta.path || "",
        meta.numFrames || "",
        r.q1_identity ?? "",
        r.q2_attribute ?? "",
        r.q3_background ?? "",
        r.q4_temporal ?? "",
        r.q5_alignment ?? "",
        JSON.stringify(r.alignment || {}),
        (r.alignmentNA || []).join(";"),
        r.q6_noncopy ?? "",
        r.q7_overall ?? "",
        (r.na || []).join(";"),
        data.itemIndex || "",
        data.totalItems || ""
      ]);
    });
    if (rows.length) sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
    return ContentService.createTextOutput(JSON.stringify({status:"ok", rows:rows.length})).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({status:"error", message:String(err)})).setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet() {
  return ContentService.createTextOutput("SPICE backend is running.").setMimeType(ContentService.MimeType.TEXT);
}

function ensureHeader_(sheet) {
  if (sheet.getLastRow() > 0) return;
  sheet.appendRow([
    "participant_id","group_id","timestamp","vision","ai_experience","design_experience",
    "item_id","story_id","model_blind","model_real","path","num_frames",
    "q1_identity","q2_attribute","q3_background","q4_temporal",
    "q5_alignment_average","q5_alignment_detail_json","q5_alignment_na",
    "q6_noncopy","q7_overall","na_questions","item_index","total_items"
  ]);
}
