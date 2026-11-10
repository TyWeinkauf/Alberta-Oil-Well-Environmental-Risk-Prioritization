# Shared data inventory

Record each shared input, its source, permission, retrieval/version, and limits before using it in more than one course.

## Actual ST37 surface-hole input — 10 November 2026

This entry supersedes older statements below that no official well file has been acquired. Historical synthetic/cloud evidence remains labelled separately. The user confirmed **one Point per surface-hole entry**, built from source longitude (X) and latitude (Y).

| Field | Recorded value |
|---|---|
| Local original | `../courses/AIDA-1145/data/ST37_SH.xlsx`, retained in place and explicitly ignored by Git |
| Publisher / resource | Alberta Energy Regulator, [ST37: List of Wells in Alberta](https://www.aer.ca/providing-information/data-and-reports/statistical-reports/st37); worksheet `ST37_Surface_Holes` |
| Source size / SHA-256 | 38,596,313 bytes; `5b7139f06817b3458689bb82a3219c963165e3e671373e493222d948bb08e4f4` |
| Permission / attribution | [AER copyright terms](https://www.aer.ca/copyright-and-disclaimer), checked 2026-11-10: educational/noncommercial use subject to accuracy, AER attribution and no implied endorsement, unless otherwise indicated. Not assumed OGL; no commercial-redistribution permission claimed. Source bytes are not committed. |
| Record grain / key | 541,190 source surface-hole rows, 541,190 unique nonblank text licence numbers, no duplicate IDs; preserve leading zeros. A surface hole is not a production-string event or a bottom-hole location. |
| Actual fields | `Well_Licence_Number`, `Licensee`, `Licence_Status`, `Licence_Status_Date`, `Ground_Elevation`, `Spud_Date`, `Most_Recent_Final_Drill_Date`, `Energy_Devlpmt_Category_Type`, `SH_Actual_Latitude`, `SH_Actual_Longitude`, `Licence_Surface_Location_Label` |
| Attribute meaning | Licensee is not automatically operator/producer; licence status is not operational status; legal-location text is preserved. No UWI or verified operator is supplied. |
| Quality / missingness | Zero structural rejects. Six records have date-review warnings (future date/possible 1900-01-01 placeholders). Missing: 14,808 elevations, 59,053 spud dates, 59,297 final-drill dates. Both `Re-Entered` and `Re-entered` source spellings are retained. |
| Coordinates / intended geometry | Point per entry. Longitude range −120.009424 to −110.005051; latitude 48.997462 to 59.998135. Excel geographic datum is unconfirmed; coordinate numbers are retained, and staged geometry is null until documented CRS declaration. Final analytical points must be projected to EPSG:3400. |
| Bounded input | 477 candidates in the configured Drayton Valley coordinate envelope; `pilot.csv` is 65,626 bytes. Datum-aware geographic inclusion and environmental coverage remain to verify. |
| Retrieval / release | Supplied by the user on 2026-11-10; original publisher download timestamp and release date were not supplied. Filesystem times are not substituted. |
| Lineage / outputs | Read-only Excel extraction, original SHA-256 before/after, immutable output checksums, original row numbers, full raw attributes, quarantine/warnings and report under ignored `../../data/raw/st37/7b77926624ee1c2c7fb554d8426eab5ac5b1c6a17d7226fce6429cd2b3c1d8f4/`. |
| PostGIS proof / remaining work | Full 541,190-row inventory loaded/repeated in a separate temporary validation database; same ID/counts, six warning rows, first/middle/last raw values match. No screening run published. **User database not loaded**; private `.env` awaits actual values. Datum/provenance/environmental sources remain open. |

See [actual schema and commands](../../docs/st37_excel.md) and [retained aggregate evidence](../../docs/evidence/st37_excel_2026-11-10.json). All 136 Python tests pass on Windows PostgreSQL 17.11/PostGIS 3.6.2. These are implementation/source-inventory results, not course submission or instructor feedback evidence.

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
## Phase 4 acquisition preparation — 8 November 2026

The configurable pilot is Drayton Valley (`../../config/study_area.live.yml`, WGS84 `[-115.08, 53.20, -114.94, 53.30]`). It is an educational pilot choice, not confirmed source coverage or an operational review area. Environmental inputs will use a projected 500 m margin.

The acquisition/cache/provenance and atomic PostGIS workflow is tested against synthetic local HTTP services and generated Shapefile/GPKG/FileGDB inputs. Those tests are not official source acquisitions. No real AER, provincial environmental or federal habitat input is currently inventoried as acquired or verified.

Requests to AER, ArcGIS portal, Open Canada and Alberta Open Data were denied by cloud policy (CONNECT 403). Domain additions are saved in the environment draft but not applied; actual download/service URLs, layer IDs, schemas, licences and native CRS remain pending. See `../../docs/source_verification.md` for the exact blocker and verification sequence. The previously published OpenStreetMap tile host now returns HTTP 200; that is display access only.
## Synthetic production proof and pending Petrinex source — 8 November 2026

`../../tests/fixtures/production_demo.csv` is a project-authored internal fixture, not actual Petrinex data or a claim about its column names. It contains 9 records: 6 accepted, 2 quarantined and 1 outside the August-October 2026 example window. Three records link uniquely to one synthetic well; facility, unmatched and unknown-level rows remain separate. Facility quantities are never allocated to wells.

The candidate reporting window is configurable in `../../config/production_window.yml`. Actual public availability, reporting lag, units/activities, source record grain, well/facility attribution, identifier compatibility and licence remain unverified. `www.petrinex.ca` discovery received proxy CONNECT 403; its domain was added to the pending environment draft. No real production input is inventoried as acquired or verified. See `../../docs/production.md` for contracts, provenance, audits, tests and the official verification steps still required.

## Published-environment metadata discovery — 8 November 2026

The prior discovery-host denial is superseded. Fresh provincial/ArcGIS searches and Petrinex public pages/terms returned HTTP 200. Official parks catalogue record `gda-6b96341f-2e19-4885-98af-66d12ed4f8dd` identifies its service and OGL-Alberta; Petrinex learning aids describe CSV/XML ZIPs, lag, masking and identifiers. These are metadata/documents only, not acquired analytical/production records. See `../../docs/source_discovery.md` and its URL/status/hash evidence. Actual service/metadata/download hosts remain CONNECT-denied; AER HTTP 403 and federal CKAN HTTP 429 require separate follow-up. No environment settings changed or published.

User clarification: cloud access failures do not determine runtime source availability. Publisher APIs/direct downloads or user-downloaded CSV/GeoJSON/GIS files remain intended acquisition routes. Remote HTTP/ArcGIS acquisition is implemented; full local-file ingestion is planned in DESIGN step 4.2c, while the existing local production command only inspects files. See `../../docs/data_access.md`. No additional official dataset is claimed as acquired.

## Local-file acquisition implemented — 8 November 2026

Steps 4.2c/5.2c are complete: local GIS/GeoJSON, coordinate-mapped well CSV and production CSV/ZIP use immutable byte snapshots with publisher URL, original download timestamp and checksums. Runtime catalogue selection works through CLI/app; all 113 tests pass with synthetic offline import/refresh evidence. The disabled example catalogue is `../../config/source_catalog.local.example.yml`; see `../../docs/data_access.md`. No official analytical/production record has been acquired; source-specific schemas, terms and real-data validation remain open. This supersedes the earlier local-import planning status, not the source-verification limits.

## Revised required inputs — 8 November 2026

The user removed Petrinex/monthly production. Required inputs are AER surface-well locations/attributes plus water, protected areas and federal critical habitat. The uploaded June 2026 ST37 guide was reviewed; candidate fields/layer grain and file-size limits are documented in `../../docs/st37_reference.md`. Fresh metadata located ECCC record `47caa405-be2b-4e9e-8f53-c478ade2ca74` and its listed FileGDB ZIP, plus provincial water/parks resources. See `../../docs/download_inputs.md` and `../../docs/evidence/input_discovery_2026-11-08.json`. These are metadata/documentation, not loaded official records. All data/ is ignored; users download their own files.

## Regional preparation — 8 November 2026

Step 4.2d is complete on synthetic data: large local GIS/ZIP/FileGDB originals can be read directly into bounded regional packages with selected fields, native geometry, parent SHA-256 provenance and embedded area/margin checks. Normal app/import caps remain unchanged. The original download/hash I/O still scales with source size. CLI inspect/preparation/reuse/cap failure and 128 tests (including PostGIS distances/failed-scope retention) pass; no real ST37 compatibility/coverage is claimed. See `../../docs/regional_extracts.md` and its evidence. The entire data/ directory remains ignored.
