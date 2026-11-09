# AIDA 1145 — Data engineering evidence index

**Current scope revision:** Petrinex/monthly production is excluded. AER well locations/attributes and environmental layers remain required; retained production evidence below is historical/optional and does not require a download. See [download checklist](../../../docs/download_inputs.md).

Candidate handoff index, 8 November 2026. The original [assignment brief](README.md) is preserved. This index identifies implemented work; it does not claim instructor approval, a D2L submission or verified real-data results.

The intended user is the fictional reclamation screening team in the [charter](../../project-charter.md). The bounded engineering question is how permitted well/environmental inputs can become a reproducible, validated analysis-ready dataset. The [scope matrix](../../scope-matrix.md) separates this from the GIS question.

| Deliverable | Existing implementation/evidence | Remaining evidence |
|---|---|---|
| Source inventory and permissions | [Inventory](../../shared-resources/data-inventory.md), [discovery](../../../docs/source_discovery.md), [input routes](../../../docs/data_access.md) | Actual acquired source versions, licences, schemas and coverage |
| Input/output schema | [Data dictionary](../../../docs/data_dictionary.md), [contracts](../../../src/contracts/), [production contracts](../../../src/production/contracts.py) | Confirm actual field/identifier/unit mappings |
| ETL implementation | [Sources](../../../src/sources/), [production import](../../../src/production/store.py), [migrations](../../../sql/migrations/) | Any actual-source transformations, then a bounded real run |
| Analysis-ready output | `screening.wells`, `screening.well_proximity`, linked source snapshots, and the app's filtered CSV/GeoJSON/manifest exports | Save and name the final permitted output; synthetic output remains labelled |
| Quality, failure and rerun checks | [Integration tests](../../../tests/integration/), [release/recovery evidence](../../../docs/release_verification.md): 118 Python tests; immutable snapshots, quarantine, rollback, exact-ID links, repeat counts and killed-process recovery | Validate quality/accounting on real inputs |
| Lineage | Raw-byte checksums, original download dates, source mappings, selected-record bundles and run/batch manifests | Preserve actual source-to-final-output trace |
| Reproduction | [README](../../../README.md), [reproducibility](../../../docs/reproducibility.md), isolated Linux candidate checkout/new environment and repeated CLI demo | Check final committed checkout and intended user platform |
| Limits and use | [Limitations](../../../docs/limitations.md), [production attribution](../../../docs/production.md) | Resolve product-specific redistribution terms before packaging data |

The synthetic demo yields two wells, two environmental features, six spatial quarantines and ten proximity rows. Separate production demo: nine inputs, six accepted, two quarantined, one outside its window; three observations link to one synthetic well. These are implementation checks, not Alberta environmental findings.

Generated run artifacts are under ignored `outputs/runs/<run-id>/`; export them deliberately for the final permitted package. Keep source bytes, credentials, caches and environments out of the repository/package unless specific redistribution permission supports inclusion. Cite the run/batch ID, input checksum, source version, selected scope and quality counts with each output.

Before submission: complete real-data validation and final output, add release/presentation notes and review responses, verify the package runs independently, and follow the current D2L assignment. The paired [GIS index](../AIDA-2362/EVIDENCE.md) covers spatial interpretation rather than replacing this engineering evidence.
