SPICE Main Study v3 — clearer training/calibration
=================================================

WHAT CHANGED
------------
1. Main study remains unchanged:
   - 12 validation stories: 01, 08, 09, 15, 17, 27, 28, 29, 32, 53, 57, 64
   - 4 sequences per participant
   - 50 assignment groups
   - 200 total sequence evaluations

2. Training is now 7 short screens instead of a wordy tutorial:
   1) Three rules
   2) Identity + Attributes
   3) Text–Image Alignment
   4) Background + Temporal
   5) Adjacent repetition
   6) Reference reuse + Style
   7) Overall

3. Every practice page mirrors the real survey logic.
   - 1–5 direction is explicit: 5 = best, 1 = worst.
   - N/A is explained as insufficient evidence, not uncertainty between ratings.
   - Each component has LOOK AT / IGNORE guidance.
   - Each page has one quick comprehension check.
   - A participant cannot continue until that rule is answered correctly.

4. Pilot-supported real examples are used where the pilot gives clear evidence:
   - Identity/Attributes high: Story 60 NaiveBaseline, Guan Yu, frames 4–6.
     Pilot rating: Identity 5, Attributes 5.
   - Identity/Attributes low: Story 24 StoryDiffusion, Jo, frames 3, 7, 8.
     All three pilot raters gave Identity 1 and Attributes 1.
   - Alignment high: Story 60 NaiveBaseline, frame 3.
     Pilot alignment anchor: 5.
   - Alignment low: Story 24 StoryDiffusion, frame 12.
     Pilot alignment ratings around 1–2.
   - Temporal stronger: Story 60 Gemini.
     Two pilot raters gave Temporal 4.
   - Temporal weaker: Story 24 StoryDiffusion.
     Pilot Temporal = 1, 1, 2.
   - Overall low: Story 68 NaiveBaseline.
     Pilot Overall = 1.

5. For concepts not directly/cleanly measured in pilot 1 (especially Style and exact repetition-category boundaries),
   the training uses deliberately simple illustrations rather than inventing a "correct" label for an ambiguous dataset pair.

6. Reference reuse training deliberately contrasts Story 60 Gemini and Story 60 NaiveBaseline.
   The same Story 60 NaiveBaseline sequence is also used as a strong Identity example. This is intentional:
   participants learn that strong character identity does not imply good reference-reuse behavior.

FILES TO DEPLOY
---------------
- index.html
- Code.gs
- data/assignments.json
- data/manifest.json
- data/shot_character_mapping.json

Your existing data/VistoryBench/ image/story asset tree is still required on GitHub Pages.
This ZIP does not duplicate the 1,500+ image assets.

GOOGLE SHEETS
-------------
Code.gs now uses fresh v3 sheets:
- AssignmentPool_Main_v3
- SequenceRatings_Main_v3
- AlignmentRatings_Main_v3
- CharacterRatings_Main_v3
- RepetitionRatings_Main_v3
- ParticipantSessions_Main_v3

Run setupSheets() ONCE after replacing Code.gs, then update/redeploy the Apps Script web app.
The existing /exec URL can stay the same if you update the same deployment.

VERSION TAGS
------------
Survey:   SPICE-HUMAN-2026-MAIN-v3
Training: SPICE-TRAINING-v3

VALIDATION PERFORMED
--------------------
- Browser JavaScript extracted from index.html passes node --check.
- Code.gs passes JavaScript syntax check after copying to .js.
- All configured training item IDs exist in the supplied manifest.
- All configured training frame numbers exist.
- Configured training characters (Guan Yu, Jo) exist in reference metadata.
