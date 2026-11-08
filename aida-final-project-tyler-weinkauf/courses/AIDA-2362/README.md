# AIDA 2362 Final Professional Project — GIS Decision Package

**Individual assessment · 25% of the AIDA 2362 course grade**

## Purpose and tool boundary

Build one fictional facilities-maintenance spatial decision package around a bounded question. Name the decision-maker, action, unit, geographic extent, time period, map scale, and consequences of error. QGIS is the core tool. Python may extend the work, but it cannot replace the QGIS evidence chain. Do not use real sensitive locations or claim operational readiness. Paid services, specialized hardware, mandatory Docker, or deployment are not required.

## How to approach the work

1. **Set the spatial decision.** Define user/action, features and area/time included, map scale, decision threshold if appropriate, uncertainty, and no-go conditions.
2. **Check every layer.** Record source, licence/permission, date/version, CRS, coordinate units, scale, fields, and limitations. Keep data within the approved fictional/supplied boundary.
3. **Build a reproducible QGIS chain.** Use documented processing history/model and/or code. Use stable identifiers and test joins/cardinality, geometry validity, missingness, CRS transformations, units, and output counts.
4. **Compare a baseline and changed setting.** Preserve a simple baseline and at least one changed-variable sensitivity test. Report which locations/IDs/counts move and whether the decision changes.
5. **Communicate the result accessibly.** Provide a readable decision map and an exact text/table equivalent; explain symbology, scale, uncertainty, and who should use the result.
6. **Review responsibility and release.** Address privacy, bias, community impacts, distinctions-based Indigenous authority, data licensing, limitations, implementation conditions, and what evidence would change the recommendation.
7. **Prepare the portable handoff.** Use relative paths, verify the project opens after extraction, and document the clean run and release decision.

## Required final deliverables

The course final submission is a complete, portable QGIS project package through D2L. Include:

- QGIS project file with relative/portable paths and all permitted required inputs;
- data inventory with sources, licences/permissions, metadata, CRS, units, dates, and limits;
- derived layers and a documented Processing history/model and/or code;
- checks for CRS/transformation, area of use, units, geometry validity, stable IDs/cardinality, missingness, output counts, and a clean run;
- a baseline plus at least one changed-variable sensitivity test, including changed IDs/counts and decision impact;
- accessible decision map and exact text/table equivalent;
- bounded decision brief with uncertainty, scale, limitations, implementation and no-go conditions, and next evidence;
- privacy, bias, community-impact and Indigenous-authority review; manifest, release checklist, README, and AI declaration.

The published 25-point rubric covers decision context (3), authorized data/provenance/governance (3), reproducible QGIS workflow/validation (5), spatial analysis/sensitivity (5), accessible map/equivalent (3), uncertainty/privacy/community/authority (3), and recommendation/ZIP/AI/presentation (3). A successful processing run by itself is not sufficient release evidence.

## How progress is checked

At each checkpoint, record the evidence path and the next action in `project-progress.md`. The gates are formative and add no separate weight. Your work should show visible steps from a scoped proposal to validated spatial evidence and a portable package.

- **Week 6 — proposal/scope:** decision, unit, extent/time, scale, source permission, feasibility.
- **Week 8 — evidence plan:** layer inventory, metadata/CRS plan, processing chain, baseline and validation plan.
- **Week 10 — prototype:** working QGIS project with one initial derived layer and a reproducible process note.
- **Week 12 — validation:** geometry/CRS/ID/output checks, sensitivity comparison, limitations and corrected errors.
- **Week 14 — release candidate:** portable project, map and equivalent, metadata, privacy/governance review, peer feedback and response.
- **Week 15 — release readiness:** clean extracted package, manifest, recommendation, presentation and final handoff. Finish all work by end Week 15; there is no Week 16 project or final-exam activity.

## Submission and presentation

Submit the complete GIS package through the AIDA 2362 D2L assignment. For GIS-only work, Git is optional; a Git repository never replaces the required D2L QGIS package. If you are also taking other courses, this repository can hold permitted GIS project notes/history, but you still submit the GIS package in D2L. Present in class during Week 14 or Week 15. Keep weekly graded labs separate.

## Shared project dates and class activities

The final project is due in D2L on **December 7, 2026**. Check the course assignment for the exact time and required package. In-class presentations take place during Week 14 or Week 15; the presentation schedule will be posted in D2L. Each student will review at least one assigned classmate's repository or code plan and submit the peer-review template in D2L. The peer-review schedule and template will be posted in D2L. Complete all project work by the end of Week 15.
