/**
 * SPICE Human Evaluation — Google Sheets backend
 *
 * Features:
 * 1. Automatically allocates one unused assignment group G01-G54.
 * 2. Uses a script lock so two participants cannot receive the same group.
 * 3. Remembers the same PID -> same group on repeated allocation requests.
 * 4. Marks the group COMPLETE when session_complete is received.
 * 5. Stores sequence-level ratings, alignment-frame ratings, and sessions.
 *
 * SETUP:
 * 1. Create a Google Sheet.
 * 2. Put the spreadsheet ID into SPREADSHEET_ID.
 * 3. Run setupSheets() once.
 * 4. Deploy > New deployment > Web app.
 *    Execute as: Me
 *    Who has access: Anyone
 * 5. Paste the /exec URL into index.html CONFIG.googleAppsScriptUrl.
 */

const SPREADSHEET_ID = "PASTE_GOOGLE_SHEET_ID_HERE";

const GROUP_COUNT = 54;

const SHEET_ASSIGNMENTS = "AssignmentPool";
const SHEET_SEQUENCE = "SequenceRatings";
const SHEET_ALIGNMENT = "AlignmentRatings";
const SHEET_PARTICIPANTS = "ParticipantSessions";

const ASSIGNMENT_HEADERS = [
  "group_id",
  "status",
  "pid",
  "claimed_at_utc",
  "completed_at_utc"
];

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
  "available_frames",
  "coverage",
  "missing_shots_json",
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


/**
 * GET endpoint.
 *
 * Public allocation request:
 *   ?action=claim&pid=PXXXX&callback=someFunction
 *
 * callback is optional. If supplied, response is JSONP so a static
 * GitHub Pages survey can request the assignment without CORS problems.
 */
function doGet(e) {
  try {
    const params = (e && e.parameter) ? e.parameter : {};
    const action = String(params.action || "").toLowerCase();

    let result;

    if (action === "claim") {
      result = claimAssignment(String(params.pid || ""));
    } else {
      result = {
        ok: true,
        service: "SPICE Human Evaluation",
        message: "Google Sheets endpoint is running."
      };
    }

    return apiResponse(result, params.callback);

  } catch (err) {
    console.error(err);

    const callback =
      e && e.parameter
        ? e.parameter.callback
        : "";

    return apiResponse(
      {
        ok: false,
        error: String(err)
      },
      callback
    );
  }
}


/**
 * POST endpoint for ratings and session completion.
 */
function doPost(e) {
  const lock = LockService.getScriptLock();

  try {
    lock.waitLock(30000);

    if (!e || !e.postData || !e.postData.contents) {
      throw new Error("No POST body received.");
    }

    const payload = JSON.parse(e.postData.contents);
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);

    initializeWorkbook(ss);

    if (payload.submissionType === "sequence_rating") {
      validateParticipantAssignment(
        ss,
        String(payload.pid || ""),
        String(payload.groupId || "")
      );

      saveSequenceRating(ss, payload);

    } else if (payload.submissionType === "session_complete") {
      validateParticipantAssignment(
        ss,
        String(payload.pid || ""),
        String(payload.groupId || "")
      );

      saveParticipantCompletion(ss, payload);

      markAssignmentComplete(
        ss,
        String(payload.pid || ""),
        String(payload.groupId || "")
      );

    } else {
      throw new Error(
        "Unknown submissionType: " +
        payload.submissionType
      );
    }

    SpreadsheetApp.flush();

    return jsonResponse({
      ok: true
    });

  } catch (err) {
    console.error(err);

    return jsonResponse({
      ok: false,
      error: String(err)
    });

  } finally {
    try {
      lock.releaseLock();
    } catch (_) {}
  }
}


/**
 * Run ONCE manually after setting SPREADSHEET_ID.
 */
function setupSheets() {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);

  initializeWorkbook(ss);

  SpreadsheetApp.flush();

  Logger.log(
    "SPICE sheets initialized, including " +
    GROUP_COUNT +
    " assignment groups."
  );
}


/**
 * Create all required sheets and populate G01-G54.
 */
function initializeWorkbook(ss) {
  ensureSheet(
    ss,
    SHEET_ASSIGNMENTS,
    ASSIGNMENT_HEADERS
  );

  ensureSheet(
    ss,
    SHEET_SEQUENCE,
    SEQUENCE_HEADERS
  );

  ensureSheet(
    ss,
    SHEET_ALIGNMENT,
    ALIGNMENT_HEADERS
  );

  ensureSheet(
    ss,
    SHEET_PARTICIPANTS,
    PARTICIPANT_HEADERS
  );

  initializeAssignmentPool(
    ss.getSheetByName(SHEET_ASSIGNMENTS)
  );
}


/**
 * Populate AssignmentPool with G01-G54 if it has no data yet.
 */
function initializeAssignmentPool(sheet) {
  if (sheet.getLastRow() >= 2) {
    return;
  }

  const rows = [];

  for (let i = 1; i <= GROUP_COUNT; i++) {
    rows.push([
      "G" + String(i).padStart(2, "0"),
      "AVAILABLE",
      "",
      "",
      ""
    ]);
  }

  sheet
    .getRange(
      2,
      1,
      rows.length,
      rows[0].length
    )
    .setValues(rows);
}


/**
 * Allocate the next unused group.
 *
 * Rules:
 * - If this PID already owns a group, return that same group.
 * - Otherwise assign the first AVAILABLE group.
 * - Lock prevents duplicate allocation under simultaneous access.
 * - If all 54 groups are claimed/completed, return full:true.
 */
function claimAssignment(pid) {
  if (!pid) {
    return {
      ok: false,
      error: "Participant ID is required."
    };
  }

  const lock = LockService.getScriptLock();

  try {
    lock.waitLock(30000);

    const ss =
      SpreadsheetApp.openById(
        SPREADSHEET_ID
      );

    initializeWorkbook(ss);

    const sheet =
      ss.getSheetByName(
        SHEET_ASSIGNMENTS
      );

    const lastRow =
      sheet.getLastRow();

    const values =
      sheet
        .getRange(
          2,
          1,
          lastRow - 1,
          ASSIGNMENT_HEADERS.length
        )
        .getValues();

    // Existing PID -> same assignment.
    for (let i = 0; i < values.length; i++) {
      const groupId =
        String(values[i][0] || "");

      const status =
        String(values[i][1] || "")
          .toUpperCase();

      const rowPid =
        String(values[i][2] || "");

      if (
        rowPid === pid &&
        (
          status === "CLAIMED" ||
          status === "COMPLETE"
        )
      ) {
        return {
          ok: true,
          groupId: groupId,
          status: status,
          existing: true
        };
      }
    }

    // First free assignment.
    for (let i = 0; i < values.length; i++) {
      const status =
        String(values[i][1] || "")
          .toUpperCase();

      if (status === "AVAILABLE") {
        const rowNumber = i + 2;
        const groupId =
          String(values[i][0] || "");

        sheet
          .getRange(
            rowNumber,
            2,
            1,
            3
          )
          .setValues([[
            "CLAIMED",
            pid,
            new Date().toISOString()
          ]]);

        SpreadsheetApp.flush();

        return {
          ok: true,
          groupId: groupId,
          status: "CLAIMED",
          existing: false
        };
      }
    }

    return {
      ok: false,
      full: true,
      error:
        "All study assignments have been claimed."
    };

  } catch (err) {
    console.error(err);

    return {
      ok: false,
      error: String(err)
    };

  } finally {
    try {
      lock.releaseLock();
    } catch (_) {}
  }
}


/**
 * Confirm that submitted group belongs to submitted PID.
 */
function validateParticipantAssignment(
  ss,
  pid,
  groupId
) {
  if (!pid || !groupId) {
    throw new Error(
      "Missing participant ID or group ID."
    );
  }

  const sheet =
    ss.getSheetByName(
      SHEET_ASSIGNMENTS
    );

  const lastRow =
    sheet.getLastRow();

  if (lastRow < 2) {
    throw new Error(
      "Assignment pool is empty."
    );
  }

  const values =
    sheet
      .getRange(
        2,
        1,
        lastRow - 1,
        ASSIGNMENT_HEADERS.length
      )
      .getValues();

  for (let i = 0; i < values.length; i++) {
    const rowGroup =
      String(values[i][0] || "");

    const rowStatus =
      String(values[i][1] || "")
        .toUpperCase();

    const rowPid =
      String(values[i][2] || "");

    if (rowGroup === groupId) {
      if (rowPid !== pid) {
        throw new Error(
          "Assignment does not belong to this participant."
        );
      }

      if (
        rowStatus !== "CLAIMED" &&
        rowStatus !== "COMPLETE"
      ) {
        throw new Error(
          "Assignment is not active."
        );
      }

      return true;
    }
  }

  throw new Error(
    "Unknown group assignment: " +
    groupId
  );
}


/**
 * Mark a participant's group COMPLETE after all 6 items finish.
 */
function markAssignmentComplete(
  ss,
  pid,
  groupId
) {
  const sheet =
    ss.getSheetByName(
      SHEET_ASSIGNMENTS
    );

  const lastRow =
    sheet.getLastRow();

  const values =
    sheet
      .getRange(
        2,
        1,
        lastRow - 1,
        ASSIGNMENT_HEADERS.length
      )
      .getValues();

  for (let i = 0; i < values.length; i++) {
    const rowGroup =
      String(values[i][0] || "");

    const rowPid =
      String(values[i][2] || "");

    if (
      rowGroup === groupId &&
      rowPid === pid
    ) {
      const rowNumber =
        i + 2;

      sheet
        .getRange(
          rowNumber,
          2
        )
        .setValue("COMPLETE");

      sheet
        .getRange(
          rowNumber,
          5
        )
        .setValue(
          new Date().toISOString()
        );

      return;
    }
  }

  throw new Error(
    "Could not mark assignment complete."
  );
}


function saveSequenceRating(ss, p) {
  const responsesObj =
    p.responses || {};

  const itemId =
    Object.keys(responsesObj)[0];

  if (!itemId) {
    throw new Error(
      "No item response found."
    );
  }

  const r =
    responsesObj[itemId] || {};

  const meta =
    p.itemMeta || {};

  const participantMeta =
    p.participantMeta || {};

  const submissionId =
    String(p.pid) +
    "__" +
    String(itemId);

  const sequenceRow = [
    submissionId,
    p.timestamp ||
      new Date().toISOString(),
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
    valueOrBlank(meta.numFrames),
    valueOrBlank(meta.availableFrames),
    valueOrBlank(meta.coverage),
    JSON.stringify(meta.missingShots || []),
    valueOrBlank(meta.numRefs),
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
    JSON.stringify(
      participantMeta.conditionChecks || {}
    )
  ];

  upsertRowsById(
    ss.getSheetByName(
      SHEET_SEQUENCE
    ),
    [sequenceRow]
  );

  const alignment =
    r.alignment || {};

  const alignmentNA =
    new Set(
      r.alignmentNA || []
    );

  const keys =
    Array.from(
      new Set(
        Object.keys(alignment)
          .concat(
            Array.from(alignmentNA)
          )
      )
    ).sort();

  const alignmentRows =
    keys.map(key => {
      const shotId =
        String(key)
          .replace(/^align_/, "");

      const m =
        shotId.match(/(\d+)/);

      const shotNumber =
        m
          ? Number(m[1])
          : "";

      return [
        submissionId +
          "__" +
          shotId,
        submissionId,
        p.timestamp ||
          new Date().toISOString(),
        p.surveyVersion || "",
        p.dataset || "",
        p.pid || "",
        p.groupId || "",
        itemId,
        meta.storyId || "",
        meta.model || "",
        meta.modelGroup ||
          meta.group ||
          "",
        shotId,
        shotNumber,
        alignmentNA.has(key)
          ? ""
          : valueOrBlank(
              alignment[key]
            ),
        alignmentNA.has(key)
      ];
    });

  if (alignmentRows.length) {
    upsertRowsById(
      ss.getSheetByName(
        SHEET_ALIGNMENT
      ),
      alignmentRows
    );
  }
}


function saveParticipantCompletion(
  ss,
  p
) {
  const participantMeta =
    p.participantMeta || {};

  const submissionId =
    String(p.pid) +
    "__session_complete";

  const row = [
    submissionId,
    p.timestamp ||
      new Date().toISOString(),
    p.surveyVersion || "",
    p.dataset || "",
    p.pid || "",
    p.groupId || "",
    p.completedItems || "",
    participantMeta.vision || "",
    participantMeta.aiExperience || "",
    participantMeta.designExperience || "",
    participantMeta.visualTestPassed === true,
    JSON.stringify(
      participantMeta.conditionChecks || {}
    )
  ];

  upsertRowsById(
    ss.getSheetByName(
      SHEET_PARTICIPANTS
    ),
    [row]
  );
}


/**
 * Ensure a sheet exists and that its header row matches.
 */
function ensureSheet(
  ss,
  name,
  headers
) {
  let sheet =
    ss.getSheetByName(name);

  if (!sheet) {
    sheet =
      ss.insertSheet(name);
  }

  if (sheet.getLastRow() === 0) {
    sheet
      .getRange(
        1,
        1,
        1,
        headers.length
      )
      .setValues([headers]);

    sheet.setFrozenRows(1);

    sheet
      .getRange(
        1,
        1,
        1,
        headers.length
      )
      .setFontWeight("bold");

  } else {
    const current =
      sheet
        .getRange(
          1,
          1,
          1,
          headers.length
        )
        .getValues()[0];

    if (
      current.join("||") !==
      headers.join("||")
    ) {
      throw new Error(
        "Header mismatch in sheet '" +
        name +
        "'. Create a fresh sheet or restore the expected headers."
      );
    }
  }

  return sheet;
}


/**
 * Upsert rows using column A as unique ID.
 */
function upsertRowsById(
  sheet,
  rows
) {
  if (!rows.length) {
    return;
  }

  const lastRow =
    sheet.getLastRow();

  const idToRow = {};

  if (lastRow >= 2) {
    const ids =
      sheet
        .getRange(
          2,
          1,
          lastRow - 1,
          1
        )
        .getValues();

    ids.forEach((r, i) => {
      if (r[0] !== "") {
        idToRow[
          String(r[0])
        ] = i + 2;
      }
    });
  }

  const newRows = [];

  rows.forEach(row => {
    const id =
      String(row[0]);

    if (idToRow[id]) {
      sheet
        .getRange(
          idToRow[id],
          1,
          1,
          row.length
        )
        .setValues([row]);

    } else {
      newRows.push(row);
    }
  });

  if (newRows.length) {
    sheet
      .getRange(
        sheet.getLastRow() + 1,
        1,
        newRows.length,
        newRows[0].length
      )
      .setValues(newRows);
  }
}


function valueOrBlank(v) {
  return (
    v === undefined ||
    v === null
  )
    ? ""
    : v;
}


/**
 * Normal JSON response for POSTs and direct endpoint tests.
 */
function jsonResponse(obj) {
  return ContentService
    .createTextOutput(
      JSON.stringify(obj)
    )
    .setMimeType(
      ContentService.MimeType.JSON
    );
}


/**
 * JSON or JSONP response.
 *
 * JSONP makes GET assignment allocation work reliably from a static
 * GitHub Pages site without depending on cross-origin fetch headers.
 */
function apiResponse(
  obj,
  callback
) {
  const cb =
    String(callback || "");

  if (
    cb &&
    /^[A-Za-z_$][0-9A-Za-z_$]*$/.test(cb)
  ) {
    return ContentService
      .createTextOutput(
        cb +
        "(" +
        JSON.stringify(obj) +
        ");"
      )
      .setMimeType(
        ContentService.MimeType.JAVASCRIPT
      );
  }

  return jsonResponse(obj);
}
