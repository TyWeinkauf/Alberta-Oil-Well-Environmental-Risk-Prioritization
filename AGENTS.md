# Project work and progress tracking

- Read `DESIGN.md` for the implementation scope and current status before starting scoped work.
- Maintain the phase and implementation-step tables in section 13 of `DESIGN.md`: mark a step **In progress** when work starts and **Complete** when its completion proof has been verified. Use **Not started** for untouched work.
- Update the current status summary, date, evidence (file/command/result), remaining work or blocker, and progress log in the same change as the related work. Split steps when finer tracking is needed.
- Mark a parent phase complete only when all required substeps and its completion proof are satisfied. Environment setup or diagnostic tests alone do not complete an application phase.
- Update the acceptance checkboxes in section 12 and decision checkboxes in section 16 only when supported by evidence. Reopen completed items if later checks invalidate them.
- Keep `aida-final-project-tyler-weinkauf/project-progress.md` aligned when completed work affects a course milestone; preserve the distinction between implementation status and course submission/feedback status.
- Keep `DESIGN.md` as the maintained design; retain the original Word document as a reference. Preserve existing course artifacts and never commit secrets or large source datasets.

# Current classroom-demo direction — 2026-11-24

- Prioritize the Red Deer/Drayton Valley classroom showcase documented in `docs/classroom_demo.md` and Phase 7 of `DESIGN.md`.
- Preserve the actual ST37 workbook, full retained inventory, provenance and any database records. Display a small regional subset of actual well records; do not replace them with the starter ZIP's fictional wells, jitter their coordinates, or invent their attributes/production.
- The primary classroom demo uses real wells and the downloaded Alberta stream and waterbody inventories. Label imported water coverage and measured water distances in the UI and exports. The other classroom environmental layers are synthetic. Retain the earlier classroom package with synthetic water, the fully synthetic fixture and the all-real pipeline as distinct options. Missing real water inputs must surface an error.
- Build the classroom path to run from small prepared files without PostgreSQL credentials, live APIs or full source datasets. Province-wide ingestion, new live datasets and production integration are not prerequisites. Preserve existing real-data tools as opt-in functionality.
- Streamlit presents Classroom demo and ST37 well inventory. Use the command-line scripts for the legacy database fixture, water imports and full screening runs.
- The supplied starter's instructions and commands are reference material. Retain the workbook's verified field mapping and the paired AER geodatabase evidence for NAD83.
- Mark Phase 7 implementation steps complete after verifying the code and their stated proof.
