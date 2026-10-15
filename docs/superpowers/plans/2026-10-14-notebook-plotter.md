# Notebook Plotter Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. The user requested immediate execution in this directory.

**Goal:** Photograph notes, select handwriting and write calibrated paper sheets with the connected Ender-3 Neo.

**Architecture:** Add a notes domain with image transcription and millimetre layout. Reuse scene jobs, profile binding and printer transport. Add a Russian-first notes view to the existing React app.

**Tech Stack:** Python 3.12, FastAPI, OpenAI SDK, FontTools, React, TypeScript.

**Spec:** docs/superpowers/specs/2026-10-14-notebook-plotter-design.md

## Global Constraints

- Ender-3 Neo, Marlin 2.0.8.2, serial 115200; stable by-id device path.
- Existing file authentication stays in place; local launcher binds loopback.
- No silent loss of Cyrillic or unsupported characters.
- No homing, heating or extrusion inside writing jobs.
- One sheet starts per user action; require calibrated pen/paper and known position.

## Review Focus

- Long words and paragraph breaks must paginate without cropping or duplication.
- Unsupported mathematical symbols must produce a useful error rather than disappear.
- Corrupt/oversized photos and failed/truncated provider responses must not become jobs.
- Changed calibration or an active print must prevent sending old jobs.
- Changing text/style must invalidate preview and saved jobs; a stale OCR response must not overwrite a newer photo.

### Task 1: Transcription and layout

Files: plotter/notes/{ocr,layout}.py; plotter/web/routes/notes.py; tests/test_notes.py.
Interfaces: POST /notes/transcribe → text; POST /notes/preview → pages; POST /notes/jobs → filenames with profile metadata.

- [x] Write API tests for missing key, malformed images, Cyrillic, wrapping, pagination, unsupported glyphs and safe jobs.
- [x] Run tests and confirm missing routes fail.
- [x] Implement validation, Responses transcription, real-glyph layout and safe scene jobs.
- [x] Run focused tests and existing text/profile tests.

### Task 2: Printer setup and writing

Files: plotter/web/routes/printer.py; scripts/run-notes.sh; docs/PLOTTER_RU.md; media/models/pen-holder.scad.
Interfaces: existing /printer/send detects notebook metadata and enforces readiness before upload.

- [x] Write tests for uncalibrated/unhomed/busy starts and no automatic homing.
- [x] Confirm those tests fail, implement checks, verify focused suite.
- [x] Save conservative local settings and hardware identification; create launcher and holder source.

### Task 3: User interface and verification

Files: frontend/src/features/notes/*; frontend/src/api/client/notes.ts; frontend/src/App.tsx; frontend/src/styles/notes.css.
Interfaces: upload, OCR configuration, editable transcription, handwriting choice, actual sheet preview, individual sheet print and stop.

- [x] Write component tests for text editing, stale previews and sheet start behavior; confirm failure.
- [x] Implement view using existing API/auth/printer control.
- [x] Run pytest, frontend tests, TypeScript build, changed-file lint and inspect actual screenshots.
- [x] Start loopback app and verify health, printer status, sample Cyrillic jobs and mount constraints. Report physical/key blockers honestly.

### Task 4: Entire photo → actual SVG (user clarification)

Files: plotter/notes/vectorize.py; frontend/src/features/notes/PhotoNotes.tsx; tests/test_notes_vector.py.

- [x] Replace the main workflow with local whole-page centreline vectorization.
- [x] Preserve formulas and diagrams, download SVG, parse that SVG for job generation.
- [x] Support optional text-region handwriting replacement with cached vision detection.
- [x] Disable automatic page cropping by default; retain regression for large drawn tables.
- [x] Preserve isolated dots as short pen strokes; assert survival in SVG and G-code.
- [x] Review changes and fix position, busy-state, paper containment and stale-preview issues.
- [x] Verify actual browser upload → SVG preview → download; writing remains disabled before pen calibration.

### Task 5: Ignore notebook ruling (reported photo regression)

Files: plotter/notes/ruling.py; plotter/notes/vectorize.py; tests/test_notebook_ruling.py.

- [x] Reproduce pale notebook grid leaking into SVG with failing API tests.
- [x] Remove repeated faint rules before tracing while preserving darker ink at crossings.
- [x] Verify black/blue strokes, decimal dots, genuine underlines and drawings remain,
      including many pale-blue underlines on the notebook rules.
- [x] Retrace older uploads from their preserved source photo on preview.
- [x] Check the user's original page and the running browser interface; notebook grid is absent.

Ruling-fix verification: `uv run pytest -q` → 690 passed; changed-file Ruff and
git diff checks passed. The live service returns the verified SVG; browser upload,
preview and download succeed. Artifacts: data/preview/user-notes-no-grid.svg and
data/preview/user-notes-no-grid-browser.png. Printer remains idle.

### Task 6: Reconnect after printer restart

- [x] Identify the real failure: USB port became ttyUSB1 and the per-device ACL
      disappeared; the by-id path still resolved correctly.
- [x] Add scripts/install-printer-access.sh; the user applied the persistent
      udev rule. The live device is owned by azod and accessible immediately.
- [x] Reproduce idle disconnect, silent heartbeat, ACK timeout and firmware
      restart with failing tests before changing the worker.
- [x] Add read-only M105 heartbeat, reconnect on timeout/reset, invalidate
      position and discard interrupted jobs and stale movement commands.
- [x] Verify all 694 backend tests, Ruff, shell syntax and diff checks; restart
      the service and observe the real printer online across four idle checks.

No physical restart was initiated by the agent. Connection restoration was
observed on the actual USB device after the user applied the permissions rule;
disconnect/reset scenarios are covered by controlled serial transports.

### Task 7: Reduce unnecessary SVG and printer travel

- [x] Reproduce long capture-order routes, excess lifts and redundant vertices.
- [x] Use exact-connectivity Euler trails, nearest-end ordering and 2-opt;
      compare draw/travel/lift time against the original and sorted routes.
- [x] Simplify within 0.02 mm while preserving small closed marks and dots.
- [x] Preserve the reviewed SVG path order during SVG import and G-code emission.
- [x] Verify the user's page: 740 → 111 strokes, 23928.4 → 698.2 mm pen-up
      travel, 7106 → 3740 vertices; measured maximum ink deviation 0.02 mm.

### Task 8: Remove two-factor authentication

- [x] Replace enrolment with single-step username/password admin setup.
- [x] Allow existing accounts to log in with their original password; remove
      obsolete second-factor data after successful password verification.
- [x] Remove code/recovery forms, obsolete translations, styles and pyotp.
- [x] Verify password-only setup/login, old accounts, wrong passwords, logout,
      protected routes and real auth gate/API client interaction.
- [x] Full verification: 701 backend tests, 125 frontend tests, production build,
      changed-file Ruff and diff checks passed; focused auth review found no
      critical or important issues.

## Execution Record

- User requested immediate work; implement in the supplied directory on feat/notebook-plotter.
- USB access granted by the user with setfacl; M115 successfully identified the printer. No motion has been sent.
- OpenAI key absent; do not invent OCR results or make paid provider calls in tests.
- Final verification: `uv run pytest -q` → 681 passed; `npm test` → 123 passed; frontend build passed; changed-file Ruff and git diff checks passed.
- Browser verification: uploaded synthetic Russian notes with equation and two diagrams; preserved layout in SVG. Artifacts in data/preview/.
- Runtime: loopback http://127.0.0.1:8010, serial backend online. No physical writing performed: pen installation and calibration require the user. Live vision-based font replacement needs a configured API key and real-photo validation.
