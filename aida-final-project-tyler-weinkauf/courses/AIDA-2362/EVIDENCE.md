# AIDA 2362 — GIS evidence index

**Current scope revision:** Petrinex/monthly production is excluded. AER well locations/attributes and environmental layers remain required; retained production evidence below is historical/optional and does not require a download. See [download checklist](../../../docs/download_inputs.md).

Candidate handoff index, 8 November 2026. The original [assignment brief](README.md) is preserved. The implementation follows the user-selected Streamlit/OpenStreetMap design. Verify the instructor's current tool/submission criteria; no approval or submission is claimed here.

The [charter](../../project-charter.md) names the fictional reclamation team. The bounded GIS question is which wells in a selected area warrant further review based on proximity to selected environmental features. The [scope matrix](../../scope-matrix.md) distinguishes that interpretation from the shared data pipeline.

| Deliverable | Existing implementation/evidence | Remaining evidence |
|---|---|---|
| Study area and CRS | Configurable Drayton Valley pilot; [methodology](../../../docs/spatial_methodology.md) and [source reference](../../../docs/dataset_reference.md) | Inspect actual source CRS/extent and justify the real pilot coverage |
| Spatial processing | [Engine](../../../src/spatial/engine.py), projected validation and 500 m feature margin; actual feature geometry rather than centroid distances | Validate real geometry/coverage and positional limits |
| Baseline and sensitivity | 50/100/250/500 m inclusive distance flags; synthetic 500-to-50 m comparison changes matched wells from 2 to 1, affecting `DEMO-WELL-002` | Actual-data comparison table and justified interpretation |
| Map and table parity | [UI workflow](../../../docs/ui_workflow.md), [exports](../../../src/exports/selection.py), offline Chromium marker/filter/export/standalone HTML checks | Final screenshots/exports tied to a real run and selection |
| Quality and validation | Known-distance boundaries, polygon interiors, ties, CRS, invalid/duplicate records, unavailable/incomplete categories and scoped joins; [release evidence](../../../docs/release_verification.md) | Real-source checks, anomalies and documented revisions |
| Supporting well details | Stable well IDs, licensee filter, nullable legal location/status, available AER licence/location attributes | Confirm actual AER field meanings, company roles, surface-site identity and missing attributes |
| Interpretation and limitations | [Limitations](../../../docs/limitations.md), explicit coverage states and [production rules](../../../docs/production.md) | Actual findings, uncertainty, comparison and next steps without operational risk claims |

Synthetic water distances are 50 m and 150 m. The demo's invalid protected-area geometry is quarantined, so that category remains incomplete; an unknown result is not evidence of no feature. OpenStreetMap supplies display tiles only. EPSG:3400 supplies analysis distances; exported GeoJSON uses WGS84.

Save final map screenshots, filtered CSV/GeoJSON, standalone HTML where used, the exact selected categories/thresholds, run ID and source manifest together. Generated results live under ignored `outputs/`; package only permitted outputs. The measured 1,000-well benchmark is performance evidence on synthetic inputs, not an environmental finding or province-wide capacity estimate.

Before submission: acquire/verify real inputs, produce the actual baseline/sensitivity interpretation and screenshots, verify the final committed checkout, add presentation/review evidence and follow the current D2L assignment. The paired [data engineering index](../AIDA-1145/EVIDENCE.md) provides shared pipeline/provenance evidence but does not replace the GIS analysis.
