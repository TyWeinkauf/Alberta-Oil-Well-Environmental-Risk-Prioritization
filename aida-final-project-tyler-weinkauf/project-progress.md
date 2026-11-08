# Final-project progress record

**Final project due date: December 7, 2026.** Check the course assignment for the exact time and required package. The presentation schedule, peer-review schedule, and peer-review template will be posted in D2L.

Use this file to keep a short record of the evidence you have produced and the next task to complete. Update it at each feedback checkpoint. It is a planning aid, not an additional graded submission. The course rubric and D2L assignment determine the final assessment.

For each row, choose one status: **Not started**, **In progress**, **Ready for feedback**, **Feedback received**, or **Complete**. Link a file, folder, commit, or D2L item as evidence. A commit count alone does not show project quality; reviewers look for a working, checked, well-explained result.

| Week / checkpoint | Evidence to prepare | Status | Evidence path or commit | Feedback / next action |
|---|---|---|---|---|
| 6 — scope and feasibility | Approved or reviewed question; intended user/decision; scope boundary; course contribution; data source/permission; feasibility question. | Not started |  |  |
| 8 — data and evidence plan | Data inventory/sample; permission/provenance; method/pipeline plan; baseline; success and quality checks. | In progress | `../config/`, `../docs/architecture.md`, `../docs/data_dictionary.md`, `shared-resources/data-inventory.md` | Synthetic inputs and contracts documented; verify live sources, permissions and baseline methodology in later phases. |
| 10 — working prototype | One repeatable end-to-end run or spatial/vision/analysis workflow with an initial output and short run note. | In progress | `../scripts/analyze_demo.py`, `../docs/spatial_methodology.md`, `../docs/reproducibility.md`, `../tests/` | 2026-11-08: Phases 0-2 implemented, 61 tests passed; synthetic seed plus spatial analysis verified. Interactive application and real-data ingestion remain unfinished. |
| 12 — validation and revision | Validation/check results; sensitivity or changed-setting comparison; error/limitation; revisions and what changed. | In progress | `../tests/integration/test_spatial.py`, `../docs/spatial_methodology.md` | Known-distance boundaries, coverage semantics, failure rollback and 500-to-50 m sensitivity verified on fixtures. Real-data, UI and final course validation remain open. |
| 14 — release candidate | Organized course folders; evidence index; clean-run/release checks; peer review and response; presentation practice. | Not started |  |  |
| 15 — final handoff | Final course packages; submission manifest; D2L submission evidence; in-class presentation; final limitation and next step. | Not started |  |  |

## Implementation tracking

See [the Markdown design and implementation tracker](../DESIGN.md#13-phased-codex-implementation-plan) for phase and step status. Update it when implementation work starts or completes. The course checkpoints in this file require their own evidence and are not automatically completed by environment setup.

## How to ask for feedback

Email the instructor before a scheduled checkpoint if you need guidance. Include the repository link, exact course folder and file or commit to review, what you have already tried, and one or two specific questions. Do not send credentials or restricted data.

## Completion rule

All final-project work ends by the end of Week 15. Present in class in Week 14 or Week 15. No project work or final exam is scheduled in Week 16.
