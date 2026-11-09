# Final-project progress record

**Final project due date: December 7, 2026.** Check the course assignment for the exact time and required package. The presentation schedule, peer-review schedule, and peer-review template will be posted in D2L.

Use this file to keep a short record of the evidence you have produced and the next task to complete. Update it at each feedback checkpoint. It is a planning aid, not an additional graded submission. The course rubric and D2L assignment determine the final assessment.

For each row, choose one status: **Not started**, **In progress**, **Ready for feedback**, **Feedback received**, or **Complete**. Link a file, folder, commit, or D2L item as evidence. A commit count alone does not show project quality; reviewers look for a working, checked, well-explained result.

| Week / checkpoint | Evidence to prepare | Status | Evidence path or commit | Feedback / next action |
|---|---|---|---|---|
| 6 — scope and feasibility | Approved or reviewed question; intended user/decision; scope boundary; course contribution; data source/permission; feasibility question. | Not started |  |  |
| 8 — data and evidence plan | Data inventory/sample; permission/provenance; method/pipeline plan; baseline; success and quality checks. | In progress | `../config/`, `../docs/source_verification.md`, `shared-resources/data-inventory.md` | Drayton Valley pilot configured; published discovery hosts now respond; official parks/Petrinex documentation inspected, while actual services/downloads and field mappings remain unverified. |
| 10 — working prototype | One repeatable end-to-end run or spatial/vision/analysis workflow with an initial output and short run note. | In progress | `../app.py`, `../docs/ui_workflow.md`, `../docs/reproducibility.md`, `../tests/` | 2026-11-08: 118 Python tests and both offline Chromium checks pass from a candidate checkout/new dependency environment; local-file spatial/production and recovery mechanics verified. Synthetic spatial/production demos work; official documentation discovery advanced; actual service/download hosts remain blocked and no real ingestion is claimed. |
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
