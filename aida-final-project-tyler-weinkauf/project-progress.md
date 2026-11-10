# Final-project progress record

**Final project due date: December 7, 2026.** Check the course assignment for the exact time and required package. The presentation schedule, peer-review schedule, and peer-review template will be posted in D2L.

Use this file to keep a short record of the evidence you have produced and the next task to complete. Update it at each feedback checkpoint. It is a planning aid, not an additional graded submission. The course rubric and D2L assignment determine the final assessment.

For each row, choose one status: **Not started**, **In progress**, **Ready for feedback**, **Feedback received**, or **Complete**. Link a file, folder, commit, or D2L item as evidence. A commit count alone does not show project quality; reviewers look for a working, checked, well-explained result.

| Week / checkpoint | Evidence to prepare | Status | Evidence path or commit | Feedback / next action |
|---|---|---|---|---|
| 6 — scope and feasibility | Approved or reviewed question; intended user/decision; scope boundary; course contribution; data source/permission; feasibility question. | Not started |  |  |
| 8 — data and evidence plan | Data inventory/sample; permission/provenance; method/pipeline plan; baseline; success and quality checks. | In progress | `../config/`, `../docs/st37_excel.md`, `../docs/hydrography.md`, `shared-resources/data-inventory.md` | 2026-11-10: ST37 schema/keys and official water layers 72/107/76/108 metadata/CRS/OGL terms verified. Explicit code filters and actual water quality gap recorded. AER datum/download provenance, parks/habitat and final coverage remain open. |
| 10 — working prototype | One repeatable end-to-end run or spatial/vision/analysis workflow with an initial output and short run note. | In progress | `../app.py`, `../docs/hydrography.md`, `../docs/evidence/hydrography_2026-11-10.json`, `../tests/` | 2026-11-10: 142 tests/type checks pass. Actual water import/preview works before wells are ready: 33 default or 121 seasonal features, one quarantined river polygon, incomplete coverage warning; running-app checks and repeat counts pass in a separate temporary DB. ST37 inventory validation retained. User connection and full real screening remain open; no submission/feedback outcome claimed. |
| 12 — validation and revision | Validation/check results; sensitivity or changed-setting comparison; error/limitation; revisions and what changed. | In progress | `../tests/integration/`, `../tests/browser/`, `../docs/production.md`, `../docs/spatial_methodology.md` | Spatial and production contracts, exact-ID ambiguity, no facility allocation, failed refresh retention and chart/availability checked on synthetic inputs. Actual source and release validation remain open. |
| 14 — release candidate | Organized course folders; evidence index; clean-run/release checks; peer review and response; presentation practice. | In progress | `../docs/release_verification.md`, `courses/AIDA-1145/EVIDENCE.md`, `courses/AIDA-2362/EVIDENCE.md` | Candidate checkout/new venv/new DB and 118 tests plus both browser checks pass; actual-data results, final commit/platform check, review and presentation remain open. |
| 15 — final handoff | Final course packages; submission manifest; D2L submission evidence; in-class presentation; final limitation and next step. | Not started |  |  |

## Implementation tracking

See [the Markdown design and implementation tracker](../DESIGN.md#13-phased-codex-implementation-plan) for phase and step status. Update it when implementation work starts or completes. The course checkpoints in this file require their own evidence and are not automatically completed by environment setup.

## How to ask for feedback

Email the instructor before a scheduled checkpoint if you need guidance. Include the repository link, exact course folder and file or commit to review, what you have already tried, and one or two specific questions. Do not send credentials or restricted data.

## Completion rule

All final-project work ends by the end of Week 15. Present in class in Week 14 or Week 15. No project work or final exam is scheduled in Week 16.

Scope revision: Petrinex/monthly production removed at the user's request. Phase 5 now verifies AER well attributes; default catalogue/UI excludes production. AER ST37 guide and environmental catalogue resources are documented, but actual file/schema/CRS/coverage and full-size archive validation remain open. Downloaded inputs belong under ignored data/ and are not shipped on GitHub.

Regional-input update: 128 tests now pass, including FileGDB/ZIP preparation, parent lineage, scope/cap failures and PostGIS edge-distance checks. `../docs/regional_extracts.md` documents the small-extract workflow; actual source/schema/terms and real-data outputs remain open.

Actual-input update, 2026-11-10: [ST37 Excel preparation/staging](../docs/st37_excel.md) is verified with 541,190 source rows and 477 pilot candidates; all 136 tests pass on Windows/PostGIS. Inventory-only import/repeat was validated in a separate temporary database. The original and outputs remain ignored; the user's database has not been loaded. Original datum/release/download metadata, environmental acquisition and final real screening/course outputs remain open. No checkpoint is marked submitted, approved or feedback-complete by this implementation evidence.

Waterways update, 2026-11-10: [water import and app preview](../docs/hydrography.md) are verified with actual official data in a separate validation DB. All 142 tests/type checks and running-app checks pass. One source polygon is quarantined, so water coverage remains incomplete. User database credentials, coverage-gap resolution and complete AER/parks/habitat screening remain open; course checkpoint statuses are unchanged.
