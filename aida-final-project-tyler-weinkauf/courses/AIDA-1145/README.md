# AIDA 1145 Final Professional Project

**Individual assessment · 25% of the AIDA 1145 course grade**

## Purpose

Build a small, tested, documented, reproducible data pipeline that turns permitted source data into a clearly described, analysis-ready output. State the practical question, intended user, and decision the output could support. The project should show the quality of the data workflow as well as what the output can and cannot support. It does not need to be a production system or a large application.

## How to approach the work

1. **Bound the task.** Choose one user, one practical question/decision, a small number of suitable sources, and one analysis-ready output.
2. **Check permissions first.** Record source, licence/permission, date or version, sensitivity, and retention limits. Do not use confidential employer/client or personal data unless the instructor has explicitly approved both the data and its handling.
3. **Describe the input.** State row/record meaning, fields, types, identifiers, expected ranges/categories, and known quality limitations.
4. **Design a short pipeline.** Show the steps to acquire or load, clean, validate, transform, and save the permitted input. Keep source data distinct from outputs.
5. **Add checks and failure handling.** Check expected fields/types, missing and duplicate records, valid values, and output shape. Explain what the pipeline does when a check fails.
6. **Make it repeatable.** List required software/packages and exact steps or commands; provide an expected output and a clean-run log.
7. **Explain lineage and use.** Trace the output to its input, name assumptions/exclusions, state privacy/security limits, and explain what analysis the output enables.

## Required final deliverables

Organize the course work in `courses/AIDA-1145/`. Include:

- a short project question, named user/team, decision, boundary, and success/quality check;
- a data inventory with source, permission/licence, date/version, record grain, important fields, and known limitations;
- readable pipeline code or queries that load/acquire, clean, validate, and transform the approved input;
- automated tests or clearly documented validation checks for schema/types, missingness, duplicates, valid ranges/categories, and expected output; include what happens when checks fail;
- one named analysis-ready output plus a schema/data dictionary and an explanation of how to use it;
- lineage notes for the transformations, exclusions, assumptions, and source-to-output trace;
- run instructions listing software/packages, setup, commands, expected result, and a clean-run log;
- a responsible-use note covering permission, privacy, licensing, security, retention, risks, and limits;
- a release note and presentation notes showing the working pipeline/output, evidence, and limitations.

The course outline does not establish a detailed rubric breakdown here. Follow the current D2L assignment and any instructor-approved scope/criteria for the exact submission package and marking. Do not infer new rubric weights from this README.

## How progress is checked

The shared Weeks 6, 8, 10, 12, 14, and 15 checkpoints are for feedback, not extra grades. Update `project-progress.md` with a link/path to the evidence you bring. The instructor checks whether the question is manageable, the data are permitted and understood, the pipeline runs, quality checks are meaningful, and the output and claims match the evidence. The D2L rubric and course instructions remain authoritative for the final grade.

- **Week 6 — scope:** user, question, decision, boundary, likely source and permission, first feasibility question.
- **Week 8 — design:** sample/data inventory, pipeline steps, output specification, and planned quality tests.
- **Week 10 — prototype:** first small end-to-end run producing an initial output.
- **Week 12 — validation:** test results, clean run, fixes, limitations, and source-to-output trace.
- **Week 14 — release candidate:** organized files, rerun instructions, peer comments and response, unresolved risks.
- **Week 15 — final handoff:** final package and in-class working demonstration/presentation. Finish all project work by the end of Week 15; no Week 16 project or final-exam activity is scheduled.

## Submission and presentation

Use the AIDA 1145 Final Professional Project D2L assignment for the required final package. Include the private repository link and clean project ZIP when requested in the live assignment. Git supports version history; it does not replace D2L submission. Present in class in Week 14 or Week 15. Keep weekly graded labs separate.

## Shared project dates and class activities

The final project is due in D2L on **December 7, 2026**. Check the course assignment for the exact time and required package. In-class presentations take place during Week 14 or Week 15; the presentation schedule will be posted in D2L. Each student will review at least one assigned classmate's repository or code plan and submit the peer-review template in D2L. The peer-review schedule and template will be posted in D2L. Complete all project work by the end of Week 15.
