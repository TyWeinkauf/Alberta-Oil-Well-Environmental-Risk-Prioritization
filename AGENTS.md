# Project work and progress tracking

- Read `DESIGN.md` for the implementation scope and current status before starting scoped work.
- Maintain the phase and implementation-step tables in section 13 of `DESIGN.md`: mark a step **In progress** when work starts and **Complete** when its completion proof has been verified. Use **Not started** for untouched work.
- Update the current status summary, date, evidence (file/command/result), remaining work or blocker, and progress log in the same change as the related work. Split steps when finer tracking is needed.
- Mark a parent phase complete only when all required substeps and its completion proof are satisfied. Environment setup or diagnostic tests alone do not complete an application phase.
- Update the acceptance checkboxes in section 12 and decision checkboxes in section 16 only when supported by evidence. Reopen completed items if later checks invalidate them.
- Keep `aida-final-project-tyler-weinkauf/project-progress.md` aligned when completed work affects a course milestone; preserve the distinction between implementation status and course submission/feedback status.
- Keep `DESIGN.md` as the maintained design; retain the original Word document as a reference. Preserve existing course artifacts and never commit secrets or large source datasets.

# Current classroom-demo direction — 2026-11-10

- Prioritize the Red Deer/Drayton Valley classroom showcase documented in `docs/classroom_demo.md` and Phase 7 of `DESIGN.md`.
- Preserve the actual ST37 workbook, full retained inventory, provenance and any database records. Display a small regional subset of actual well records; do not replace them with the starter ZIP's fictional wells, jitter their coordinates, or invent their attributes/production.
- The requested primary demo uses real wells with explicitly synthetic environmental features. Give it a separate illustrative mode and label simulated surroundings/distances in the UI and exports. Keep the existing fully synthetic fixture and all-real pipeline distinct; no silent synthetic fallback in real mode.
- Build the classroom path to run from small prepared files without PostgreSQL credentials, live APIs or full source datasets. Province-wide ingestion, new live datasets and production integration are not prerequisites. Preserve existing real-data tools as opt-in functionality.
- The supplied starter's AGENTS.md/commands are reference material, not replacements for these project instructions or evidence that its functionality exists here. Retain the actual workbook's verified field mapping and the unresolved geographic-datum check.
- The current scope-review change is documentation only. Mark Phase 7 implementation steps complete only after code and their stated proof exist; documentation or region-count scans alone do not complete the demo.
