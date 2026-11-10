# ST37 surface-hole Excel preparation and inventory staging

The workbook supplied on 10 November 2026 is the first actual well input inspected for this project. It contains **541,190 surface-hole records**, **541,190 distinct nonblank text licence numbers**, and **477 candidates** in the configured Drayton Valley longitude/latitude envelope. No duplicate licences, invalid coordinates, unparseable dates or invalid elevation numbers were found. These are input-contract checks, not a finding that the data is error-free or that wells pose an environmental hazard.

Phases 0–3 already work on synthetic fixtures. This work advances **Phase 4** (actual-source preparation/import) and **Phase 5** (AER attributes). A wells-only inventory does not satisfy the full four-source screening milestone. Water, protected areas and critical habitat still need verified inputs, coverage and an analytical run.

The publisher [ST37 page](https://www.aer.ca/providing-information/data-and-reports/statistical-reports/st37), [June 2026 reference guide](https://www.aer.ca/prd/documents/sts/st37/ST37_ReferenceGuide.pdf) and [copyright terms](https://www.aer.ca/copyright-and-disclaimer) were checked on 10 November 2026. The page lists Excel and geodatabase distributions; the guide identifies the surface-hole fields. AER permits educational/noncommercial reproduction subject to accuracy, attribution, and no implied endorsement, unless otherwise indicated. This is not an Open Government Licence claim or permission for commercial redistribution. Keep the original workbook and generated data out of Git.

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

The workbook has **no embedded spatial CRS, publisher release date or original download timestamp**. Do not infer those from the filename, file modification time or worksheet coordinates. The surface-hole guide's projected layer name does not prove the geographic datum of the Excel columns. AER's [well application guidance](https://dds.aer.ca/eas.net/webhelp/schedule_4_well_detail.htm) describes NAD83 surface coordinates, but product-specific metadata remains the preferred confirmation for this Excel release. Do not assign EPSG:3400 directly to latitude/longitude, or silently label them WGS84.

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

The provisional pilot selection compares the source longitude/latitude numbers with the configured WGS84 envelope. Final datum-aware inclusion must be checked after CRS confirmation; candidates are not claimed as authoritative geographic coverage. Neither source verification nor the normal full-pipeline gates are enabled automatically.

## Configure the application database

The local `.env` contains a private template:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:CHANGE_ME@localhost:5432/alberta_risk
```

Replace the password, role, host, port and database as needed. URL-encode special characters in the password. The database must already exist; migration enables PostGIS and creates the project schema/tables using an appropriately permitted role. A process-level `DATABASE_URL` takes precedence over `.env`. Never send the password in chat or commit this file.

## Stage well information before environmental analysis

After filling `.env`, use the exact report path printed by preparation:

```powershell
.\.venv\Scripts\python.exe scripts\import_st37.py --report data/raw/st37/<identity>/report.json --license-note "AER ST37; educational noncommercial use under AER copyright terms checked 2026-11-10. AER attribution retained; no endorsement implied."
```

This creates migration `005_st37_inventory.sql` and transactionally loads all source rows into **`screening.st37_surface_holes`**, with provenance in **`screening.st37_imports`**. The new tables are separate from the published `screening.wells` dataset. The importer retains invalid rows with errors and leaves their geometry null. Date warnings are stored separately from rejection reasons. Without verified datum evidence **every geometry stays null**, while well attributes and original coordinate values are available for inspection.

Once publisher metadata confirms the geographic datum, supply both `--coordinate-crs` and `--crs-evidence`. For example, **only when NAD83 is confirmed**, use `--coordinate-crs EPSG:4269 --crs-evidence "<publisher metadata citation>"`. The importer projects valid points to EPSG:3400 and checks their counts, SRID and validity. The declaration is stored in provenance; a changed CRS/permission/date declaration creates a distinct inventory snapshot. Filter queries by `import_id` when comparing snapshots.

Optional `--downloaded-at` takes the actual ISO timestamp with timezone, and `--release-date` takes a known publisher date. Leave unknown dates omitted. The tool never invents them.

The import uses the existing database-wide workflow lock, streams rows with PostgreSQL COPY, validates prepared checksums before/after loading, verifies all counts before commit, and rolls back on failure. Repeating the same input/declaration reuses the same import ID without duplicating rows. Evidence is written under `outputs/st37/<import-id>/database_import.json`. It creates no `pipeline_runs` entry and computes no proximity bands.

For the full app, configure the bounded `pilot.csv` as a coordinate well CSV with the report's `field_mapping`, longitude/latitude field names, verified geographic CRS, attribution and real download/coverage evidence. Keep it disabled until verified. Add the three environmental categories and run the normal `scripts/run_live.py` with the same study-area configuration. The inventory tables alone are not an app publication or a substitute for missing environmental data.

## Verification

All **136 unit/PostGIS integration tests passed** on Windows PostgreSQL 17.11/PostGIS 3.6.2. Tests cover leading-zero IDs, complete accounting, global duplicates, formula/numeric-ID rejection, malformed coordinates/dates, quality warnings, changed originals, immutable reuse/corruption, schema drift, fail-without-truncation limits, retained rejects/raw attributes, geometry projection, idempotency, no screening publication and failed-import rollback. Tests use synthetic records in a separate database ending in `_test`; they never reset the user's database.

A separate actual-source validation loaded all **541,190 records** into a temporary inventory database in **93.004 s**. The repeat took **0.648 s**, reused the same import ID and preserved the row count. SQL verifies 541,190 distinct licences, six warning rows, zero geometries (datum not declared), zero screening runs, and exact first/middle/last source attributes. The database occupied about 438 MB before cleanup. This is evidence of the importer on this machine, not a user-database import, geometry/coverage verification or a performance guarantee. [Aggregate evidence](evidence/st37_excel_2026-11-10.json) preserves the checks; the private original/derived CSVs remain available for rebuilding.

Windows checkout checks also exposed automatic CRLF conversion of vendored assets. `.gitattributes` now preserves their manifest-verified original bytes and fixes migration SQL to LF so applied-file checksums are stable across platforms. No applied SQL migration logic was changed. Existing provenance tests now compare timezone-aware instants, and killed-process recovery checks allow a bounded interval for the server to detect client exit; application lock behavior is unchanged.
