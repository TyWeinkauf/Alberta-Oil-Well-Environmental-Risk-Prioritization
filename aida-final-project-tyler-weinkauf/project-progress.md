# Final-project progress record

**Final project due date: December 7, 2026.** Use the [AIDA 1145 brief](courses/AIDA-1145/README.md) and [AIDA 2362 brief](courses/AIDA-2362/README.md) to prepare the course packages. The presentation schedule, peer-review schedule, and peer-review template are expected in D2L.

Use this planning aid to keep a short record of the evidence you have produced and the next task to complete. Update it at each feedback checkpoint. The course briefs describe the assessment, and D2L records submissions and feedback.

For each row, choose one status: **Not started**, **In progress**, **Ready for feedback**, **Feedback received**, or **Complete**. Link a file, folder, commit, or D2L item as evidence. A commit count alone does not show project quality; reviewers look for a working, checked, well-explained result.

| Week / checkpoint | Evidence to prepare | Status | Evidence path or commit | Feedback / next action |
|---|---|---|---|---|
| 6 — scope and feasibility | Approved or reviewed question; intended user/decision; scope boundary; course contribution; data source/permission; feasibility question. | Not started |  |  |
| 8 — data and evidence plan | Data inventory/sample; permission/provenance; method/pipeline plan; baseline; success and quality checks. | In progress | `../docs/classroom_demo.md`, `../DESIGN.md`, `shared-resources/data-inventory.md` | 2026-11-20 preview preserves 28 actual wells per region, with reproducible sampling and unchanged source hashes. Workbook datum, release and datum-aware membership remain open. |
| 10 — working prototype | One repeatable end-to-end run or spatial/vision/analysis workflow with an initial output and short run note. | In progress | `../app.py`, `../docs/classroom_demo.md`, `../tests/unit/test_classroom_demo.py` | The running app shows real ST37 preview tables, filters, details and exports from a small local package. The projected path was verified with known-CRS fixtures. Final map and distances for actual wells await workbook datum. |
| 12 — validation and revision | Validation/check results; sensitivity or changed-setting comparison; error/limitation; revisions and what changed. | In progress | `../tests/unit/test_classroom_demo.py`, `../tests/integration/`, `../docs/classroom_demo.md` | Verified the actual sample and byte-identical package rebuild. Fixture checks cover inclusive distance boundaries, coverage, marker selection, buffer and export parity. The actual-well threshold comparison and interpretation remain open. |
| 14 — release candidate | Organized course folders; evidence index; clean-run/release checks; peer review and response; presentation practice. | In progress | `../docs/classroom_demo.md`, `courses/AIDA-1145/EVIDENCE.md`, `courses/AIDA-2362/EVIDENCE.md` | The extracted preview ZIP launched with no full source files or credentials. Final actual-well map, course packages, final checkout validation, review and presentation remain open. |
| 15 — final handoff | Final course packages; submission manifest; D2L submission evidence; in-class presentation; final limitation and next step. | Not started |  |  |

## Implementation tracking

**Course handoff clarification — 20 November 2026.** The user confirmed that the repository contains the assignment briefs and selected Streamlit/Folium with OpenStreetMap for the GIS demonstration. The published repository brief for AIDA 2362 specifies QGIS. The selected tooling reflects the user's understanding, with instructor confirmation unverified. [Classroom handoff](../docs/classroom_demo.md)

**Classroom build — 20 November 2026.** The offline preview and declared-CRS test scenarios are available. Final actual-well results, packages, presentation, feedback and submissions remain open. Keep the final handoffs identifiable for each course.

See [the Markdown design and implementation tracker](../DESIGN.md#13-phased-codex-implementation-plan) for phase and step status. Update it when implementation work starts or completes. The course checkpoints in this file require their own evidence and are not automatically completed by environment setup.

## How to ask for feedback

Email the instructor before a scheduled checkpoint if you need guidance. Include the repository link, exact course folder and file or commit to review, what you have already tried, and one or two specific questions. Do not send credentials or restricted data.

## Completion rule

All final-project work ends by the end of Week 15. Present in class in Week 14 or Week 15. No project work or final exam is scheduled in Week 16.

Scope revision: Petrinex/monthly production removed at the user's request. Phase 5 now verifies AER well attributes; default catalogue/UI excludes production. AER ST37 guide and environmental catalogue resources are documented, but actual file/schema/CRS/coverage and full-size archive validation remain open. Downloaded inputs belong under ignored data/ and are not shipped on GitHub.

Regional-input update: 128 tests now pass, including FileGDB/ZIP preparation, parent lineage, scope/cap failures and PostGIS edge-distance checks. `../docs/regional_extracts.md` documents the small-extract workflow; actual source/schema/terms and real-data outputs remain open.

Actual-input update, 2026-11-10: [ST37 Excel preparation/staging](../docs/st37_excel.md) is verified with 541,190 source rows and 477 pilot candidates; all 136 tests pass on Windows/PostGIS. Inventory-only import/repeat was validated in a separate temporary database. The original and outputs remain ignored; the user's database has not been loaded. Original datum/release/download metadata, environmental acquisition and final real screening/course outputs remain open. No checkpoint is marked submitted, approved or feedback-complete by this implementation evidence.

Waterways update, 2026-11-10: [water import and app preview](../docs/hydrography.md) are verified with actual official data in a separate validation DB. All 142 tests/type checks and running-app checks pass. One source polygon is quarantined, so water coverage remains incomplete. User database credentials, coverage-gap resolution and complete AER/parks/habitat screening remain open; course checkpoint statuses are unchanged.

Province waterbody update, 2026-11-20. The live ten-polygon probe and layer-72 count/ID checks add official-source validation evidence. The PostGIS importer accounts for accepted polygons and rejects, and the comparison uses a documented ST37 snapshot. The project database connection and retained workbook datum still gate the actual comparison. [Layer-72 evidence and commands](../docs/hydrography.md#province-wide-layer-72-and-st37-comparison)

Streamlit workflow update, 2026-11-20. Both imports and the comparison ran from app buttons with disposable PostGIS fixtures. All 148 tests passed. The retained workbook's 541,190-row preparation was checksum-verified for reuse. [App workflow and verification](../docs/hydrography.md#import-and-compare)

Live project database update, 2026-11-20. The Streamlit buttons loaded 541,190 actual ST37 records and accounted for all 127,227 layer-72 records in PostGIS, with 127,189 polygons accepted and 38 quarantined. The worksheet datum still gates the actual comparison. [Import results](../docs/hydrography.md#project-database-status)

The Streamlit stream import loaded 143,568 layer-107 lines and retained two invalid geometry records in quarantine. All 149 tests passed. The [ordered completion checklist](../DESIGN.md#remaining-work-in-order) tracks the next database, GIS demo and course handoff steps.
