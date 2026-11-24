# ST37 surface-hole Excel preparation and inventory staging

The workbook supplied on 10 November 2026 is the first actual well input inspected for this project. It contains **541,190 surface-hole records**, **541,190 distinct nonblank text licence numbers**, and **477 candidates** in the configured Drayton Valley longitude/latitude envelope. No duplicate licences, invalid coordinates, unparseable dates or invalid elevation numbers were found. These are input-contract checks, not a finding that the data is error-free or that wells pose an environmental hazard.

Phases 0–3 already work on synthetic fixtures. This work advances **Phase 4** (actual-source preparation/import) and **Phase 5** (AER attributes). A wells-only inventory does not satisfy the full four-source screening milestone. Water, protected areas and critical habitat still need verified inputs, coverage and an analytical run.

The publisher [ST37 page](https://www.aer.ca/data-and-performance-reports/statistical-reports/st37), [June 2026 reference guide](https://www.aer.ca/prd/documents/sts/st37/ST37_ReferenceGuide.pdf) and [copyright terms](https://www.aer.ca/copyright-and-disclaimer) were checked on 10 November 2026. The page lists Excel and geodatabase distributions; the guide identifies the surface-hole fields. AER permits educational/noncommercial reproduction subject to accuracy, attribution, and no implied endorsement, unless otherwise indicated. This is not an Open Government Licence claim or permission for commercial redistribution. Keep the original workbook and generated data out of Git.

**Publisher check, 20 November 2026.** The user supplied the current ST37 product page. It confirms monthly distribution and directs readers to the ZIP metadata. The linked guide lists the workbook's latitude and longitude fields under the projected surface-hole geodatabase layer. The page and guide leave the retained workbook's release month and native coordinate datum unresolved. The local network could not retrieve the Excel archive directory via a bounded range request. [AER ST37](https://www.aer.ca/data-and-performance-reports/statistical-reports/st37) · [ST37 reference guide, page 3](https://www.aer.ca/prd/documents/sts/st37/ST37_ReferenceGuide.pdf#page=3)

## Verified November release and datum

On 23 November 2026, bounded HTTPS range requests recovered the AER Excel ZIP directory and its single surface-hole member. The decompressed `ST37_SH.xlsx` matches the retained workbook at all 38,596,313 bytes by SHA-256. AER's index lists this monthly update on 3 November 2026, which also matches the date on the exact ZIP member. The retained workbook's original download time is still unknown. [AER statistical reports index](https://www.aer.ca/providing-information/data-and-reports/statistical-reports?page=0) · [Range and checksum evidence](evidence/st37_datum_2026-11-23.json)

The paired November geodatabase's catalog documents NAD83 lineage for the ST37 surface-hole locations. Inspection found 541,190 valid points in EPSG:3400 with NAD83 geographic base CRS EPSG:4269. An exact string join on `Well_Licence_Number` matched every retained row and both coordinate fields exactly. Projecting the workbook columns from EPSG:4269 to EPSG:3400 reproduced all publisher point geometries within **0.000109 m**. This verifies the workbook coordinate interpretation against the corresponding publisher geometry. The residual measures agreement between formats. Ground position accuracy requires independent survey evidence. [AER ST37 distributions](https://www.aer.ca/data-and-performance-reports/statistical-reports/st37) · [Comparison evidence](evidence/st37_datum_2026-11-23.json)

## Alberta boundary and distance accuracy

On 23 November 2026, a point-in-polygon check in EPSG:3400 against Alberta's ATS v4.1 provincial boundary found **541,188 wells on or inside Alberta**. Two reported surface positions were outside, about **135 m** and **492 m** from the boundary. The map excludes those two positions for the audited projected snapshot. **Workbook records** marks them for review and retains the original coordinates. The stored comparison summaries still cover the whole inventory. [Official boundary layer](https://geospatial.alberta.ca/titan/rest/services/boundary/goa_administrative_area/MapServer/0) · [Boundary check evidence](evidence/st37_alberta_boundary_2026-11-23.json)

The app reads `SH_Actual_Longitude` as X and `SH_Actual_Latitude` as Y. It transforms the NAD83 points to WGS84 (EPSG:4326) for display on the Leaflet/OpenStreetMap basemap. PostGIS measures straight-line distance from the well point to the nearest accepted imported water geometry within 500 m in Alberta 10-TM (EPSG:3400). The well positions and hydrography have independent location uncertainty. Distances are for screening, and values near a threshold or the provincial border warrant review of the source geometry. [Hydrography and coverage](hydrography.md#browse-shuffled-well-batches)

## Actual schema and meaning

Worksheet: `ST37_Surface_Holes`. Every source field is retained in the inventory CSV and in each database row's `raw_payload`.

| Source field | Staged column / use |
|---|---|
| `Well_Licence_Number` | `well_licence_number`, text with original leading zeros; screening mapping `source_well_id` |
| `Licensee` | `licensee_name`; not assumed to be an operator or producer |
| `Licence_Status` | `licence_status`; licence lifecycle classification, not operational well status |
| `Licence_Status_Date` | `licence_status_date`, parsed from MM/DD/YYYY |
| `Ground_Elevation` | `ground_elevation`, numeric when supplied; no vertical datum is inferred |
| `Spud_Date` | `spud_date`, parsed from YYYYMMDD when supplied |
| `Most_Recent_Final_Drill_Date` | `most_recent_final_drill_date`, parsed from YYYYMMDD when supplied |
| `Energy_Devlpmt_Category_Type` | `energy_development_category`, source text |
| `SH_Actual_Latitude` | `surface_latitude`, source latitude value |
| `SH_Actual_Longitude` | `surface_longitude`, source longitude value |
| `Licence_Surface_Location_Label` | `legal_location`; screening mapping `lsd_text` |

No UWI or verified operator is supplied by this sheet. These values remain unavailable. The source has 3,509 distinct licensee names. Status spellings `Re-Entered` (2,703 records) and `Re-entered` (2 records) are retained separately. Optional missingness: 14,808 ground elevations, 59,053 spud dates and 59,297 final-drill dates. Licence-status dates range from 1900-01-01 to 2030-04-04. Six records have date-review flags: one future licence-status date, five possible 1900-01-01 licence-status placeholders, and one possible 1900-01-01 final-drill placeholder (one record has two flags). These flags preserve source values and do not reject otherwise usable locations. Read the generated warning CSV and report for the exact examples.

The workbook has no embedded spatial CRS, publisher release date or original download timestamp. The paired publisher comparison above establishes **EPSG:4269** for the retained workbook's latitude and longitude. The pipeline projects those geographic values to EPSG:3400 for metre-based analysis.

## Prepare without a database

Use Python 3.12 and the project's requirements (`openpyxl==3.1.5` is added for read-only Excel extraction). From the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_st37.py --path aida-final-project-tyler-weinkauf/courses/AIDA-1145/data/ST37_SH.xlsx --as-of 2026-11-10
```

The command reads all rows, checks the 11-field schema, preserves text licence IDs, parses dates/numbers, tests a broad Alberta coordinate envelope, detects duplicate licences across the entire sheet, and records missingness/date ranges/status counts. All occurrences of duplicate licences are quarantined. Formula/error cells and numeric licence IDs are rejected instead of guessing values or lost zero padding. No record-limit truncation is allowed.

Outputs are under ignored `data/raw/st37/<identity>/`:

- `inventory.csv`: all source rows, their Excel row numbers, validation errors and quality warnings.
- `pilot.csv`: the 11 original fields for accepted Drayton Valley candidates; this is the bounded coordinate-CSV input for the existing pipeline.
- `quarantine.csv`: all rejected rows and reasons, retaining original values.
- `warnings.csv`: all rows with review flags, retaining original values.
- `report.json`: original SHA-256/size/path, schema, counts, configuration, quality-review date, summaries and output hashes.

Extraction uses read-only Excel streaming and one small CSV pass to reject every occurrence of global duplicate IDs. The original workbook is hashed before/after reading and never modified. Outputs publish atomically; repeat preparation verifies/reuses immutable bytes. Default caps are 1,000,000 source rows and 10,000 pilot records. A changed original, study area, quality date or preparation version creates a new identity. Runtime limits for ordinary GIS/CSV ingestion remain unchanged.

The original pilot CSV used the reported longitude and latitude values to select candidates. Classroom preparation now explicitly transforms from EPSG:4269 to WGS84 for regional inclusion. The normal full-pipeline gates still require verified environmental sources and coverage.

## Configure the application database

The repository's `.env.example` provides the template for the private database connection:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:CHANGE_ME@localhost:5432/alberta_risk
```

Replace the password, role, host, port and database as needed. URL-encode special characters in the password. The database must already exist; migration enables PostGIS and creates the project schema/tables using an appropriately permitted role. A process-level `DATABASE_URL` takes precedence over `.env`. Never send the password in chat or commit this file.

## Browse the workbook in Streamlit

Launch the app and select **ST37 well inventory** under **Dataset mode**. The verified November snapshot already has stored comparisons, so **Water proximity map** opens by default. Choose waterbody polygons or stream lines under **Imported water layer** and select a **Buffer distance**. The map starts with wells within 500 m of the selected layer. Uncheck **Only show wells within the buffer** to browse the full mapped inventory in batches. Enter the full **Well licence number**, including leading zeros, to zoom to a specific well and draw its selected buffer. [Map controls](hydrography.md#browse-shuffled-well-batches)

Select **Workbook records** to inspect the source coordinates and attributes. Use **Page** to browse 100 rows at a time or keep a licence entered to review the original row for that well. Snapshots without a stored comparison open directly to workbook records. Quarantined rows include their validation errors.

Use **Import ST37 wells** in the sidebar to load the retained `ST37_SH.xlsx` into a fresh PostgreSQL/PostGIS database. Create water comparisons from saved snapshot IDs using the comparison command. [Import and compare](hydrography.md#import-and-compare)

## Stage well information before environmental analysis

The app uses the retained `ST37_SH.xlsx` in the AIDA 1145 data folder. It reuses an intact matching preparation or prepares the workbook before staging the complete inventory.

This creates migration `005_st37_inventory.sql` and transactionally loads all source rows into **`screening.st37_surface_holes`**, with provenance in **`screening.st37_imports`**. The new tables are separate from the published `screening.wells` dataset. The importer retains invalid rows with errors and leaves their geometry null. Date warnings are stored separately from rejection reasons. Without verified datum evidence **every geometry stays null**, while well attributes and original coordinate values are available for inspection.

For the verified November workbook, enter `EPSG:4269` under **Workbook coordinate CRS**, the paired-archive evidence above under **Publisher datum evidence**, and `2026/11/03` under **Publisher release date**. Click **Import ST37 wells**. The importer projects valid points to EPSG:3400 and checks counts, SRID and validity. The declaration creates a distinct inventory snapshot. Keep the original download date unset.

The import uses the database-wide workflow lock, streams rows with PostgreSQL COPY, validates checksums before and after loading, verifies counts before commit, and rolls back on failure. Repeating the same input and declaration reuses its import ID. The app lists imports by snapshot and keeps coordinate evidence with the selected data in PostGIS.

For the full multi-source screening workflow, configure the bounded `pilot.csv` as a coordinate well CSV with the report's `field_mapping`, longitude/latitude field names, verified geographic CRS, attribution and download and coverage evidence. After verifying the other required sources, run `python scripts/run_live.py`.

## Verification

The **Import ST37 wells** button staged raw import `73363997-10a0-5817-9546-57cdf2b2b1a5` on 20 November 2026. On 23 November it published projected import `4bb2ac73-df0b-5698-9295-c86028ced168` with the verified `EPSG:4269` declaration and `2026-11-03` release date. A read-only SQL join on `source_row` reconciled **541,190 rows and distinct licences** in the two snapshots. It found zero changes in the original licence IDs, coordinates, raw attributes or warnings. The raw import has zero geometries, and the projected import has 541,190 valid EPSG:3400 points, six warning rows and zero rejects. [Water comparisons](hydrography.md#project-database-status)

All **136 unit/PostGIS integration tests passed** on Windows PostgreSQL 17.11/PostGIS 3.6.2. Tests cover leading-zero IDs, complete accounting, global duplicates, formula/numeric-ID rejection, malformed coordinates/dates, quality warnings, changed originals, immutable reuse/corruption, schema drift, fail-without-truncation limits, retained rejects/raw attributes, geometry projection, idempotency, no screening publication and failed-import rollback. Tests use synthetic records in a separate database ending in `_test`; they never reset the user's database.

A separate actual-source validation loaded all **541,190 records** into a temporary inventory database in **93.004 s**. The repeat took **0.648 s**, reused the same import ID and preserved the row count. SQL verifies 541,190 distinct licences, six warning rows, zero geometries (datum not declared), zero screening runs, and exact first/middle/last source attributes. The database occupied about 438 MB before cleanup. This is evidence of the importer on this machine, not a user-database import, geometry/coverage verification or a performance guarantee. [Aggregate evidence](evidence/st37_excel_2026-11-10.json) preserves the checks; the private original/derived CSVs remain available for rebuilding.

Windows checkout checks also exposed automatic CRLF conversion of vendored assets. `.gitattributes` now preserves their manifest-verified original bytes and fixes migration SQL to LF so applied-file checksums are stable across platforms. No applied SQL migration logic was changed. Existing provenance tests now compare timezone-aware instants, and killed-process recovery checks allow a bounded interval for the server to detect client exit; application lock behavior is unchanged.
