# Shared data inventory

Record each shared input, its source, permission, retrieval/version, and limits before using it in more than one course.

## Synthetic development input — 8 November 2026

| Field | Recorded value |
|---|---|
| Input | `../../tests/fixtures/demo.json` (fixture version 1) |
| Source / permission | Project-authored synthetic test data included with the repository; no real sites or company records. No official data has been downloaded. |
| Record grain | 7 well inputs + 3 environmental feature inputs; 4 accepted, 6 explicitly quarantined. |
| CRS / extent | Explicit EPSG:3400; synthetic development extent in `../../config/study_area.yml`; no live study region selected. |
| Fields | Internal source IDs, nullable company/status/legal-location labels, point/line/polygon geometry, environmental category. These are internal contracts, not official source field mappings. |
| Version / lineage | Fixture bytes are archived and SHA-256 hashed by `../../scripts/demo_seed.py`; run ID, config hash, counts and row rejection references are exported in the ignored run manifest. |
| Limits | Training data only. No real well production, risk inference, permissions for official datasets or evidence of live-source completeness. |

See `../../docs/data_dictionary.md` and `../../docs/reproducibility.md` for schema, checks and clean-run evidence. Live input inventory and permission verification remain open.
## Intended real-data inputs — reference received 8 November 2026

The completed project will use real data. The following records the user's supplied dataset reference, not completed acquisition/permission checks. Full source text is retained in `../../docs/dataset_reference.md`; catalogue entries distinguish reference CRS/licensing from verified acquisition metadata.

| Source | Intended use / priority | Reference CRS / conditions |
|---|---|---|
| AER ST37 wells | Core real well locations/IDs | Actual product CRS and terms must be verified; do not assume OGL. |
| Alberta Base Water Feature | Core surface-water proximity | Reference EPSG:3400; OGL Alberta; analytical layers/metadata still to verify. |
| Alberta parks/protected areas | Core proximity/intersection | Reference EPSG:3400; capture exact resource-use terms; boundaries are not controlling legal descriptions. |
| Federal critical habitat | Core proximity/intersection | Reference EPSG:3978; reproject to 3400; OGL Canada; sensitive/generalized locations require care. |
| Alberta Merged Wetland Inventory | Optional additional factor | Reference EPSG:3400; circa 1998-2015 source vintages; older licence needs review. |
| Alberta ESA 2014 | Optional historical comparison | Reference EPSG:3400; historical inventory limits and distribution terms need review. |
| OpenStreetMap | Display basemap only | Web display EPSG:3857; attribution/ODbL and tile usage policy; not used for authoritative distances. |

No endpoint URLs or ArcGIS layer IDs were supplied in the reference. Actual retrieval/version, metadata, permissions, native CRS and field mappings remain to be verified in Phase 4. Petrinex production remains a separate design milestone and is not described by this supplied reference.
