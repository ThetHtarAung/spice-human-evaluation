/**
 * SPICE Human Evaluation — Google Sheets backend
 *
 * Deploy this file as a Google Apps Script Web App.
 * The survey sends:
 *   - sequence_rating: one row per participant × model × story evaluation
 *   - session_complete: one completion row per participant
 *
 * Alignment ratings are also normalized into a separate sheet:
 * one row per sampled alignment frame.
 *
 * IMPORTANT:
 * 1. Create a Google Sheet.
 * 2. Copy its spreadsheet ID into SPREADSHEET_ID below.
 * 3. Run setupSheets() once from the Apps Script editor.
 * 4. Deploy > New deployment > Web app.
 *    Execute as: Me
 *    Who has access: Anyone
 * 5. Copy the /exec URL into CONFIG.googleAppsScriptUrl in index.html.
 */

const SPREADSHEET_ID = "PASTE_GOOGLE_SHEET_ID_HERE";

const SHEET_SEQUENCE = "SequenceRatings";
const SHEET_ALIGNMENT = "AlignmentRatings";
const SHEET_PARTICIPANTS = "ParticipantSessions";

const SEQUENCE_HEADERS = [
  "submission_id",
  "timestamp_utc",
  "survey_version",
  "dataset",
  "pid",
  "group_id",
  "item_index",
  "total_items",
  "item_id",
  "story_id",
  "model",
  "model_group",
  "num_frames",
  "num_refs",
  "vision_condition",
  "ai_image_experience",
  "art_design_experience",
  "visual_test_passed",
  "q1_identity",
  "q2_attribute",
  "q3_background",
  "q4_temporal",
  "q5_alignment_mean",
  "q6_noncopy",
  "q7_overall",
  "na_components_json",
  "alignment_na_json",
  "condition_checks_json"
];

const ALIGNMENT_HEADERS = [
  "alignment_submission_id",
  "sequence_submission_id",
  "timestamp_utc",
  "survey_version",
  "dataset",
  "pid",
  "group_id",
  "item_id",
  "story_id",
  "model",
  "model_group",
  "shot_id",
  "shot_number",
  "rating",
  "is_na"
];

const PARTICIPANT_HEADERS = [
  "submission_id",
  "timestamp_utc",
  "survey_version",
  "dataset",
  "pid",
  "group_id",
  "completed_items",
  "vision_condition",
  "ai_image_experience",
  "art_design_experience",
  "visual_test_passed",
  "condition_checks_json"
];

function doGet() {
  return jsonResponse({
    ok: true,
    service: "SPICE Human Evaluation",
    message: "Google Sheets endpoint is running."
  });
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(30000);

    if (!e || !e.postData || !e.postData.contents) {
      throw new Error("No POST body received.");
    }

    const payload = JSON.parse(e.postData.contents);
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);

    ensureSheet(ss, SHEET_SEQUENCE, SEQUENCE_HEADERS);
    ensureSheet(ss, SHEET_ALIGNMENT, ALIGNMENT_HEADERS);
    ensureSheet(ss, SHEET_PARTICIPANTS, PARTICIPANT_HEADERS);

    if (payload.submissionType === "sequence_rating") {
      saveSequenceRating(ss, payload);
    } else if (payload.submissionType === "session_complete") {
      saveParticipantCompletion(ss, payload);
    } else {
      throw new Error("Unknown submissionType: " + payload.submissionType);
    }

    SpreadsheetApp.flush();
    return jsonResponse({ok: true});
  } catch (err) {
    console.error(err);
    return jsonResponse({ok: false, error: String(err)});
  } finally {
    try { lock.releaseLock(); } catch (_) {}
  }
}

function setupSheets() {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  ensureSheet(ss, SHEET_SEQUENCE, SEQUENCE_HEADERS);
  ensureSheet(ss, SHEET_ALIGNMENT, ALIGNMENT_HEADERS);
  ensureSheet(ss, SHEET_PARTICIPANTS, PARTICIPANT_HEADERS);
  SpreadsheetApp.flush();
}

function saveSequenceRating(ss, p) {
  const responsesObj = p.responses || {};
  const itemId = Object.keys(responsesObj)[0];
  if (!itemId) throw new Error("No item response found.");

  const r = responsesObj[itemId] || {};
  const meta = p.itemMeta || {};
  const participantMeta = p.participantMeta || {};

  const submissionId = String(p.pid) + "__" + String(itemId);

  const sequenceRow = [
    submissionId,
    p.timestamp || new Date().toISOString(),
    p.surveyVersion || "",
    p.dataset || "",
    p.pid || "",
    p.groupId || "",
    p.itemIndex || "",
    p.totalItems || "",
    itemId,
    meta.storyId || "",
    meta.model || "",
    meta.modelGroup || meta.group || "",
    meta.numFrames || "",
    meta.numRefs || "",
    participantMeta.vision || "",
    participantMeta.aiExperience || "",
    participantMeta.designExperience || "",
    participantMeta.visualTestPassed === true,
    valueOrBlank(r.q1_identity),
    valueOrBlank(r.q2_attribute),
    valueOrBlank(r.q3_background),
    valueOrBlank(r.q4_temporal),
    valueOrBlank(r.q5_alignment),
    valueOrBlank(r.q6_noncopy),
    valueOrBlank(r.q7_overall),
    JSON.stringify(r.na || []),
    JSON.stringify(r.alignmentNA || []),
    JSON.stringify(participantMeta.conditionChecks || {})
  ];

  upsertRowsById(
    ss.getSheetByName(SHEET_SEQUENCE),
    [sequenceRow]
  );

  const alignment = r.alignment || {};
  const alignmentNA = new Set(r.alignmentNA || []);
  const keys = Array.from(
    new Set(Object.keys(alignment).concat(Array.from(alignmentNA)))
  ).sort();

  const alignmentRows = keys.map(key => {
    const shotId = String(key).replace(/^align_/, "");
    const m = shotId.match(/(\d+)/);
    const shotNumber = m ? Number(m[1]) : "";

    return [
      submissionId + "__" + shotId,
      submissionId,
      p.timestamp || new Date().toISOString(),
      p.surveyVersion || "",
      p.dataset || "",
      p.pid || "",
      p.groupId || "",
      itemId,
      meta.storyId || "",
      meta.model || "",
      meta.modelGroup || meta.group || "",
      shotId,
      shotNumber,
      alignmentNA.has(key) ? "" : valueOrBlank(alignment[key]),
      alignmentNA.has(key)
    ];
  });

  if (alignmentRows.length) {
    upsertRowsById(
      ss.getSheetByName(SHEET_ALIGNMENT),
      alignmentRows
    );
  }
}

function saveParticipantCompletion(ss, p) {
  const participantMeta = p.participantMeta || {};
  const submissionId = String(p.pid) + "__session_complete";

  const row = [
    submissionId,
    p.timestamp || new Date().toISOString(),
    p.surveyVersion || "",
    p.dataset || "",
    p.pid || "",
    p.groupId || "",
    p.completedItems || "",
    participantMeta.vision || "",
    participantMeta.aiExperience || "",
    participantMeta.designExperience || "",
    participantMeta.visualTestPassed === true,
    JSON.stringify(participantMeta.conditionChecks || {})
  ];

  upsertRowsById(
    ss.getSheetByName(SHEET_PARTICIPANTS),
    [row]
  );
}

function ensureSheet(ss, name, headers) {
  let sheet = ss.getSheetByName(name);
  if (!sheet) sheet = ss.insertSheet(name);

  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.setFrozenRows(1);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold");
  } else {
    const current = sheet
      .getRange(1, 1, 1, headers.length)
      .getValues()[0];

    if (current.join("||") !== headers.join("||")) {
      throw new Error(
        "Header mismatch in sheet '" + name +
        "'. Create a fresh sheet or restore the expected headers."
      );
    }
  }
  return sheet;
}

/**
 * Upsert rows using column A as the unique ID.
 * This prevents accidental duplicate rows if a participant resubmits.
 */
function upsertRowsById(sheet, rows) {
  if (!rows.length) return;

  const lastRow = sheet.getLastRow();
  const idToRow = {};

  if (lastRow >= 2) {
    const ids = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
    ids.forEach((r, i) => {
      if (r[0] !== "") idToRow[String(r[0])] = i + 2;
    });
  }

  const newRows = [];

  rows.forEach(row => {
    const id = String(row[0]);
    if (idToRow[id]) {
      sheet.getRange(idToRow[id], 1, 1, row.length).setValues([row]);
    } else {
      newRows.push(row);
    }
  });

  if (newRows.length) {
    sheet
      .getRange(sheet.getLastRow() + 1, 1, newRows.length, newRows[0].length)
      .setValues(newRows);
  }
}

function valueOrBlank(v) {
  return (v === undefined || v === null) ? "" : v;
}

function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
