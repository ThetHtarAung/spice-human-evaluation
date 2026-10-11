SPICE Main Study v4 — same-story training + de-crowded survey UI
=================================================================

MAIN STUDY DESIGN (UNCHANGED)
-----------------------------
- 12 validation stories: 01, 08, 09, 15, 17, 27, 28, 29, 32, 53, 57, 64
- 6 generation models
- 4 sequences per participant
- 50 assignment groups
- 200 total sequence evaluations
- Existing assignments.json is unchanged.

WHAT CHANGED IN v4
------------------
1. Back navigation
   - Consent -> Welcome
   - Setup -> Consent
   - Training -> previous training page (or Setup from its first page)
   - Alignment -> previous alignment frame; first alignment frame -> Story Intro
   - Character -> previous character; first character -> last Alignment page
   - Scene -> previous frame / back from survey questions; first scene frame -> last Character page
   - Repetition -> previous adjacent pair; first pair -> Scene survey
   - Reference reuse -> back to repetition review
   - Style -> Reference reuse
   - Overall -> Style
   - Summary -> Overall
   - After a story is submitted, that completed story is intentionally locked. This prevents duplicate or contradictory submissions.

2. Training examples now keep story content fixed whenever possible
   Character Identity + Attributes:
   - Same Story 60, same character Guan Yu
   - GOOD: NaiveBaseline, frames 4-6
   - LOW: UNO, frames 4-6
   Pilot support: Guan Yu was rated 5/5 (Identity/Attributes) for NaiveBaseline and 2/2 for UNO.

   Text-Image Alignment:
   - Same Story 60, same shots 1-2
   - GOOD: NanoBanana
   - LOW: NaiveBaseline
   - Both sides display the same Setting Description + Static Shot Description.
   The contrast was chosen because the existing SPICE diagnostic results for Story 60 show much stronger alignment for NanoBanana than NaiveBaseline. These metric values are NOT shown to participants.

   Background + Temporal:
   - Same Story 60
   - NanoBanana vs NaiveBaseline
   - Background uses shots 1-3, which share the same stated street location.
   - Temporal uses the full 8-frame Story 60 progression.
   - A separate simple room illustration explicitly teaches:
       GOOD = same stated location remains recognizable
       LOW  = same stated location unexpectedly changes
   - Expected changes to a new location are explicitly allowed.

   Adjacent repetition:
   - More visual explanation of Distinct / Similar / Near-duplicate
   - Each category includes a visual pair, a meaningful-change meter, and a short decision rule.
   - "Similar is not automatically bad" is emphasized.

   Reference reuse:
   - Story 60 Gemini vs Story 60 NaiveBaseline
   - Same story; reference images are visible.

   Style:
   - Generated frames only
   - Expanded visual demonstration of stable rendering vs shifts in realism, line work, shading and color treatment.

   Overall:
   - Same Story 24
   - More coherent example: QwenImageEdit-2509
   - Lower-consistency example: StoryDiffusion_photomaker
   - Frames 1-8 are used so the missing Qwen Story 24 frame 15 is irrelevant.

3. Late-stage survey pages are less crowded
   Adjacent repetition:
   - Only the two compared images are prominent.
   - Shot context is collapsed under "View expected shot context".
   - A small three-category legend remains visible.

   Reference reuse:
   - Reference images are a compact horizontal strip.
   - Generated story is a clean 4-column responsive gallery.
   - No shot-description text is repeated under every frame.

   Visual style:
   - Generated frames only.
   - No references and no story text on the main view.

   Overall:
   - Clean generated-frame gallery.
   - Story/shot context is optional under "View shot context".
   - Previous component ratings remain hidden.

FILES TO DEPLOY
---------------
- index.html
- Code.gs
- data/assignments.json
- data/manifest.json
- data/shot_character_mapping.json

Your existing data/VistoryBench/ story/image asset tree is still required on GitHub Pages.
This package contains metadata/code, not the 1,500+ image assets.

GOOGLE SHEETS
-------------
This package uses fresh v4 sheets:
- AssignmentPool_Main_v4
- SequenceRatings_Main_v4
- AlignmentRatings_Main_v4
- CharacterRatings_Main_v4
- RepetitionRatings_Main_v4
- ParticipantSessions_Main_v4

After replacing Code.gs:
1. Run setupSheets() ONCE.
2. Update/redeploy the Apps Script web app.
3. If you update the existing deployment rather than creating a new one, the /exec URL can remain unchanged.

VERSION TAGS
------------
Survey:   SPICE-HUMAN-2026-MAIN-v4
Training: SPICE-TRAINING-v4

VALIDATION PERFORMED
--------------------
- index.html JavaScript passes node --check.
- Code.gs passes node --check after copying to .js.
- Every training itemId exists in manifest.json.
- Every configured training frame exists.
- Story 60 Guan Yu appears in frames 4, 5 and 6 in shot_character_mapping.json.
- Main assignment file remains 50 groups x 4 sequences.
