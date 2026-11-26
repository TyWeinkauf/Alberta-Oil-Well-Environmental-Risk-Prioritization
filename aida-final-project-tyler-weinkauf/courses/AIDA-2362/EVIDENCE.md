# AIDA 2362 — GIS evidence index

## November classroom release candidate

The fictional reclamation screening team uses one surface-hole point per AER licence in two bounded study areas to see which locations enter a simulated water-proximity shortlist. The November ST37 sample contains 28 wells per region. NAD83 (EPSG:4269) supplies the preserved input coordinates, EPSG:3400 supplies metres, and WGS84 supplies displayed and GeoJSON coordinates. The maps show a scale bar. Use the regional view and zoom to the well to inspect its buffer. [Region extents, data and GIS methods](../../../docs/classroom_demo.md) · [Datum and geometry checks](../../../docs/st37_excel.md#verified-november-release-and-datum)

With Water selected, the 500 m baseline includes 5 of 56 wells and the 100 m comparison includes 2. Red Deer changes from 2 to 1 and Drayton Valley from 3 to 1. Three licences leave the shortlist (`0016125`, `0173144`, `0430751`). The portable map, its exact CSV equivalent, regional screenshots and sensitivity manifest preserve the selected categories and threshold. The threshold changes who would be reviewed in this exercise. [Sensitivity results](../../../docs/classroom_demo.md#verification-and-remaining-work)

The sample is deterministic and limited to two regions. It does not estimate prevalence across Alberta or reflect production, contamination, habitat, real hydrography, legal setbacks, community impact or Indigenous jurisdiction. Real locations remain public AER source records. Keep the demo educational and review real conditions with qualified reviewers and the relevant authorities before any operational use. The project used Codex for implementation and verification. The course's required student AI declaration, peer review and confirmation of the Streamlit/Folium alternative remain open. [AER terms](https://www.aer.ca/copyright-and-disclaimer) · [Course brief](README.md)

**Classroom build, 20 November 2026.** The app opens the actual regional ST37 records in a preview. A declared-CRS test scenario verifies metre distances, selected-well buffers, baseline comparison and matching map/table exports. The browser test ran with external network access blocked from a copy that held only app files and the fixture package. The retained workbook datum is still required for the actual-well map and sensitivity export. [Classroom verification](../../../docs/classroom_demo.md#verification-and-remaining-work)

**Current scope revision:** Petrinex/monthly production is excluded. AER well locations/attributes and environmental layers remain required; retained production evidence below is historical/optional and does not require a download. See [download checklist](../../../docs/download_inputs.md).

**Course handoff clarification, 20 November 2026.** The user selected Streamlit/Folium with OpenStreetMap to demonstrate GIS workflows using the repository's [assignment brief](README.md). The brief specifies a portable QGIS project. The chosen tooling reflects the user's understanding of acceptable alternatives, with instructor confirmation unverified.

**Real-water inputs, 20 November 2026.** The project PostgreSQL/PostGIS database holds the retained well records and the full layer-72 inventory, including 38 retained geometry rejects. The actual-well map and distance comparison require the workbook datum. [Import evidence](../../../docs/hydrography.md#project-database-status)

The [charter](../../project-charter.md) names the fictional reclamation team. The bounded GIS question is which wells in a selected area warrant further review based on proximity to selected environmental features. The [scope matrix](../../scope-matrix.md) distinguishes that interpretation from the shared data pipeline.

| Deliverable | Existing implementation/evidence | Remaining evidence |
|---|---|---|
| Study area and CRS | Configurable Drayton Valley pilot; [methodology](../../../docs/spatial_methodology.md) and [source reference](../../../docs/dataset_reference.md) | Inspect actual source CRS/extent and justify the real pilot coverage |
| Spatial processing | [Engine](../../../src/spatial/engine.py), projected validation and 500 m feature margin; actual feature geometry rather than centroid distances | Validate real geometry/coverage and positional limits |
| Baseline and sensitivity | 50/100/250/500 m inclusive distance flags; synthetic 500-to-50 m comparison changes matched wells from 2 to 1, affecting `DEMO-WELL-002` | Actual-data comparison table and justified interpretation |
| Map and table parity | [UI workflow](../../../docs/ui_workflow.md), [exports](../../../src/exports/selection.py), offline Chromium marker/filter/export/standalone HTML checks | Final screenshots/exports tied to a real run and selection |
| Quality and validation | Known-distance boundaries, polygon interiors, ties, CRS, invalid/duplicate records, unavailable/incomplete categories and scoped joins; [release evidence](../../../docs/release_verification.md) | Real-source checks, anomalies and documented revisions |
| Supporting well details | Stable well IDs, licence status filter, nullable legal location/status, available AER licence/location attributes | Confirm actual AER field meanings, company roles, surface-site identity and missing attributes |
| Interpretation and limitations | [Limitations](../../../docs/limitations.md), explicit coverage states and [production rules](../../../docs/production.md) | Actual findings, uncertainty, comparison and next steps without operational risk claims |

Synthetic water distances are 50 m and 150 m. The demo's invalid protected-area geometry is quarantined, so that category remains incomplete; an unknown result is not evidence of no feature. OpenStreetMap supplies display tiles only. EPSG:3400 supplies analysis distances; exported GeoJSON uses WGS84.

Save final map screenshots, filtered CSV/GeoJSON, standalone HTML where used, the exact selected categories/thresholds, run ID and source manifest together. Generated results live under ignored `outputs/`; package only permitted outputs. The measured 1,000-well benchmark is performance evidence on synthetic inputs, not an environmental finding or province-wide capacity estimate.

For the classroom handoff, produce the baseline and sensitivity comparison with changed well IDs and counts, map screenshots with an exact table equivalent, CRS and geometry validation, interpretation and limitations, and a portable package tested from a clean checkout. Include provenance for the actual wells and simulated environmental layers, and evidence from the presentation and peer review as it becomes available. See the [classroom demo plan](../../../docs/classroom_demo.md) and the paired [data engineering index](../AIDA-1145/EVIDENCE.md).
