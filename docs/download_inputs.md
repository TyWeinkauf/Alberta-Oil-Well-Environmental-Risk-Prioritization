# Download your own project inputs

The current scope is **AER well locations/attributes plus environmental layers**. The user has removed Petrinex and monthly production from the required project. The ST37 production-string layer describes well/string attributes; it is not a monthly-volume dataset. No Petrinex download is required.

## File-to-database workflow

1. Download permitted data from the publisher on your machine. Keep the original package and record its URL, download date, version and terms.
2. Put files under `data/raw/`, for example:

```text
data/raw/
  aer/ST37.zip
  environment/water.geojson
  environment/protected_areas.geojson
  environment/critical_habitat.zip
  imports/catalog.yml
```

These are example names, not bundled data. **The entire `data/` directory is ignored by Git**, including private catalogues, caches and source ZIPs. Generated `outputs/` and `.env` are also ignored. No existing tracked file was found under `data/`. Small synthetic fixtures remain versioned under `tests/fixtures/`.

3. Copy `config/source_catalog.local.example.yml` to your private catalogue and set the actual paths/mappings/provenance. With the layout above, paths in `imports/catalog.yml` would start `../aer/` or `../environment/` because they resolve relative to the YAML file.
4. Inspect actual layers, fields, unique IDs, geometry/CRS, extent and package size. Configure verified mappings and permitted use before enabling sources. Use [the ST37 guide review](st37_reference.md) for candidate fields, not as proof of the downloaded schema.
5. Run the project's ingestion pipeline to create its expected PostGIS tables, source snapshots, quarantine and proximity results. The Streamlit app then reads those normalized tables; downloading files alone does not populate them.

```bash
python scripts/setup_db.py
python scripts/run_live.py --catalog data/raw/imports/catalog.yml
```

For the app's **Run full pipeline** button, set `SOURCE_CATALOG_PATH` to the catalogue's absolute path in your local `.env` or process environment, restart Streamlit and configure all required sources. See [input configuration](data_access.md). The example above requires supported input sizes and completed mappings. For the large ST37 original, first use [regional preparation](regional_extracts.md) and use its generated small-package catalogue for ingestion.

## AER wells

Use the [AER website](https://www.aer.ca/) and locate **ST37: List of Wells in Alberta**, as in the user's screenshot. The [previously used ST37 publication URL](https://www.aer.ca/providing-information/data-and-reports/statistical-reports/st37) is included for navigation, but returned an HTTP block page in the cloud session; its current page content was not independently checked. If that address has moved, search the AER site for the exact ST37 title. Choose **Geodatabase ZIP**, not the reference-guide PDF. The screenshot lists that ZIP as 1.23 GB and the alternative **Excel ZIP** as 170 MB. The attached June 2026 guide distinguishes surface holes, bottom holes, production strings and connecting geometry. Surface holes are the proposed location grain for site screening.

Keep the ZIP intact for inspection. Actual layer names, geometry, CRS, unique keys and terms still need verification. Excel workbooks are not a direct supported input; a documented CSV conversion with verified coordinates/CRS is an alternative. Do not infer that the two distributions have identical tables.

**Prepare a regional package before loading:** the 1.23 GB original exceeds normal acquisition limits. `scripts/prepare_extract.py` now reads the local ZIP or `.gdb` directly, selects the configured study area/layer/fields and creates a small package. It does not copy the whole original to the cache or load the province into PostGIS. Normal 512 MiB input and ZIP limits remain in effect for app ingestion. See [regional extract instructions](regional_extracts.md), including provenance, the 500 m environmental margin, capped output and the cost of hashing the original. Full ST37 compatibility/performance is still unverified until its real file is available.

## Environmental websites and which format to choose

Metadata checked 8 November 2026; [verification receipt](evidence/download_checklist_2026-11-08.json). The first version needs **water features, parks/protected areas and federal critical habitat**. The following links are collected here so a local user can obtain the inputs without following the development chat. The catalogue resources were rechecked through publisher APIs; actual file contents, service-layer schemas, CRS and pilot coverage remain unverified. Access from your computer may differ from this cloud environment.

| Input | Website to start with | File type / access route to choose |
|---|---|---|
| Water: streams/rivers **and** lakes/waterbody polygons | [GeoDiscover Alberta](https://geodiscover.alberta.ca/) and [Alberta Open Data](https://open.alberta.ca/); use the specific water links below | Prefer **File Geodatabase ZIP**, **zipped Shapefile**, **GeoPackage (.gpkg)** or **GeoJSON (.geojson)** when a vector download/export is actually offered. Alternatively configure the verified **ArcGIS REST** layer(s). No one-click vector file download has been confirmed for these catalogue records. |
| Parks and protected areas | [Parks and Protected Areas of Alberta — catalogue](https://open.alberta.ca/dataset/gda-6b96341f-2e19-4885-98af-66d12ed4f8dd) and [GeoDiscover metadata](https://geodiscover.alberta.ca/geoportal/rest/metadata/item/0d1ac1474eba42fe9444a42a23a4ea1b/html) | Choose polygon data in **FileGDB ZIP, zipped Shapefile, GeoPackage or GeoJSON**, if offered; otherwise use the listed **FeatureServer** route below. The catalogue's downloadable outline ZIP is **KMZ/KML**, which is not a supported direct input in the current importer. |
| Critical habitat | [Critical Habitat for Species at Risk National Dataset — Canada](https://open.canada.ca/data/en/dataset/47caa405-be2b-4e9e-8f53-c478ade2ca74) | Select the English **FGDB/GDB** resource: [CriticalHabitat.zip — direct publisher link](https://data-donnees.ec.gc.ca/data/species/protectrestore/critical-habitat-species-at-risk-canada/CriticalHabitat.zip). This is the listed spatial File Geodatabase ZIP; do not select the WMS link or XLSX data dictionary as the geometry input. The archive itself has not been downloaded/tested here. |

### Water links and layer selection

- [Base Water Feature MapServer](https://geospatial.alberta.ca/titan/rest/services/Environment/base_water_feature/MapServer) is the intended service candidate. The [ArcGIS portal item](https://www.arcgis.com/home/item.html?id=c2fbd445f89a4139bcfdae771e44b93a) points to it; that item belongs to `SN-ArcGIS`, so publisher identity/current coverage still need confirmation from the government service/metadata.
- [Base Stream and Flow Representation — catalogue](https://open.alberta.ca/dataset/gda-7f9c0f33-6ddb-4479-b2d9-1419d79e2d26) and [GeoDiscover metadata](https://geodiscover.alberta.ca/geoportal/rest/metadata/item/a8739420b43f467ebde0b1618a177409/html) are the located base stream/network references.
- [Base Waterbody Polygon Update — catalogue](https://open.alberta.ca/dataset/gda-91d6eac8-e03d-49c1-bed1-9bf962f7eb71) and [GeoDiscover metadata](https://geodiscover.alberta.ca/geoportal/rest/metadata/item/103556b6869a4957955c2971eb6588b2/html).
- [Base Stream and Flow Representation Update — catalogue](https://open.alberta.ca/dataset/gda-07172210-57aa-4958-a127-ce204ccb21c2) and [GeoDiscover metadata](https://geodiscover.alberta.ca/geoportal/rest/metadata/item/c14c4ea78aa741f795d7106e1d31b6cd/html).
- Both update records list the [hydrography update MapServer](https://geospatial.alberta.ca/titan/rest/services/environment/inland_base_hydrography_update_10tm_nad83_aep/MapServer). **Do not use update-only data as the complete base.** Establish whether the selected resource is a full current base, a delta, or needs a documented merge.

Select actual water lines and waterbody polygons; exclude arbitrary network connectors used to connect the hydrographic network. A line-only source does not replace lake polygons. The pipeline can combine multiple configured sources in category `water`. Layer IDs and field mappings must be inspected; they are not guessed here.

### Parks and habitat service/reference links

- Parks [FeatureServer](https://geospatial.alberta.ca/titan/rest/services/boundary/parks_protected_areas_alberta/FeatureServer) and [MapServer](https://geospatial.alberta.ca/titan/rest/services/boundary/parks_protected_areas_alberta/MapServer), as listed in the provincial catalogue.
- Parks [KMZ outline ZIP](https://www.albertaparks.ca/media/6492787/protected-area-kmz-outline.zip) is included to identify the catalogue option: **skip it for direct ingestion**. A ZIP extension alone does not establish that the archive contains a supported format. KML/KMZ would need a separately validated conversion; that conversion is not implemented in this workflow. GIS park boundaries are screening data; written legal descriptions take precedence.
- Habitat [English REST layer 0](https://maps-cartes.ec.gc.ca/arcgis/rest/services/CWS_SCF/CriticalHabitat/MapServer/0), [French FileGDB ZIP](https://data-donnees.ec.gc.ca/data/species/protectrestore/critical-habitat-species-at-risk-canada/HabitatEssentiel.zip) and [bilingual XLSX data dictionary](https://data-donnees.ec.gc.ca/data/species/protectrestore/critical-habitat-species-at-risk-canada/HE_CH_DictionnaireDonnees_DataDictionary.xlsx). Choose the English ZIP for the current workflow; the dictionary is reference material. This dataset is distinct from the similarly titled Auditor General report, which is not a geometry dataset.
- Licence references: [Open Government Licence — Alberta](https://open.alberta.ca/licence) and [Open Government Licence — Canada](https://open.canada.ca/en/open-government-licence-canada). Verify the selected resource's terms, dates, exclusions and any location generalization before use.

**If a page lists only HTML/XML and ESRI REST:** HTML/XML are metadata, and REST is a service URL. Look for a supported vector download inside the publisher metadata/download portal, if one is offered. If there is no vector export, the app can query a compatible ArcGIS service after its layer ID, fields, GeoJSON support and paging have been configured/verified. A bare service page saved as JSON is not the dataset; a single browser query response may be incomplete. The adapter handles scoped paging. WMS, map tiles, PDF maps, screenshots and the XLSX dictionary do not supply the analytical geometry required here. Do not rename a PDF/KMZ to `.geojson`.

### Optional layers — not needed for the first run

Wetlands and the 2014 ESA remain optional. [Alberta Open Data](https://open.alberta.ca/) and [GeoDiscover Alberta](https://geodiscover.alberta.ca/) are the publisher search starting points for **Alberta Merged Wetland Inventory**. No current direct vector download was confirmed in this check; terms and inventory vintage still need review.

For ESA, the located [2014 update report record](https://open.alberta.ca/dataset/environmentally-significant-areas-in-alberta-2014-update-final-report) provides a [report PDF](https://open.alberta.ca/dataset/91444b6b-395b-4c83-ba37-a2e07ffbe69e/resource/21f22275-ae8e-4976-9caa-f5be09a11fec/download/2014-esa-final-report-april-2014.pdf) and [map PDF](https://open.alberta.ca/dataset/91444b6b-395b-4c83-ba37-a2e07ffbe69e/resource/f805b623-b37e-4fa2-899c-3f9d2f178fb5/download/esa-2014-pdfwebmap-opt.pdf). These are references, not the polygon input; a historical vector layer and its permitted use would still have to be located/verified before enabling this category.

## Local-project handoff: steps after the data is added

All boxes below are **remaining local actions/acceptance checks**. Documentation and synthetic/cloud tests do not mark your real-data local deployment complete. The full current code suite previously passed 128 tests; actual local inputs and the intended user platform still need validation.

### 1. Set up the local project and database

- [ ] Commit/push the latest code and checklist before switching machines, then clone/pull the intended commit into your local project folder: [GitHub repository](https://github.com/TyWeinkauf/Alberta-Oil-Well-Environmental-Risk-Prioritization). Keep the entire repository structure, including `src/`, `scripts/`, `sql/`, `config/` and `vendor/`.
- [ ] Install [Python 3.12](https://www.python.org/downloads/), [PostgreSQL 17](https://www.postgresql.org/download/) and its matching [PostGIS extension](https://postgis.net/documentation/getting_started/). Create local application database `alberta_risk`; use a database role allowed to create the extension/schema, or have an administrator enable PostGIS first.
- [ ] Follow the [README local/Windows setup](../README.md#windows-setup-powershell) to create a **new local `.venv`** and install `requirements.txt`. Do not copy the cloud virtual environment, cloud Unix-socket connection URL or `/workspace/alberta-environment` helper paths to your machine. Linux/macOS instructions are also in the README; Windows execution remains unverified.
- [ ] Copy `.env.example` to local `.env` and set `DATABASE_URL` for your local role/password/host/port/database. Keep `.env` private. Add your own downloaded files to `data/raw/`; ignored data does not arrive with a Git clone. A stale shell `DATABASE_URL` overrides `.env`, so check the actual target before ingestion.
- [ ] Activate the local virtual environment and run `python scripts/setup_db.py`, then `python -m pytest -q tests/unit`. Repeat setup to confirm migrations are current. On Windows, `.venv\Scripts\python.exe` can replace `python` in the commands here without activating the environment. This is a unit check, not the full database test suite.

### 2. Inspect the actual inputs and finish configuration

- [ ] Copy `config/source_catalog.local.example.yml` to `data/raw/imports/catalog.yml`. Set actual original file paths or API URLs; file paths are relative to the catalogue, not the project root. Leave entries disabled/unverified while investigating. The current scope has no required Petrinex entry.
- [ ] For each local GIS source, run the inspection command below, substituting its source key. For a small single file you can also use `python scripts/inspect_source.py file --path <local-file>`. Large original ZIPs/FileGDBs use `prepare_extract.py --inspect` to avoid copying the whole file into the normal cache.

```bash
python scripts/prepare_extract.py --catalog data/raw/imports/catalog.yml --source aer_wells --inspect
```

- [ ] Select the actual **surface-hole** layer and confirm its CRS, unique licence/site ID, licensee, legal location and licence-status meaning. Fill the verified `file_layer`, any `archive_member`, `native_crs` and `field_mapping`. The [guide review](st37_reference.md) supplies candidates only; its surface-layer list does not include UWI. Preserve IDs as text where supplied; leave unsupported optional fields unavailable.
- [ ] Inspect water/parks/habitat geometry, IDs, fields, dates and coverage. Water needs a verified full base with appropriate lines/polygons; do not silently use only updates/network connectors. A `kind: arcgis` source needs a verified service URL, layer ID, fields, CRS, paging/GeoJSON compatibility and geographic coverage. It does not require a local file if the service is reachable.
- [ ] Record publisher, download timestamp, original resource/metadata URL, source version where available, licence/permission note and explicit `coverage_note`. Resolve actual-file schema differences or any needed source-specific transformations. Set `verified: true` / `enabled: true` only when those checks are supported. Missing required input/coverage still blocks a complete run.
- [ ] Choose the pilot boundary in `config/study_area.live.yml` before preparation; Drayton Valley is the initial configured example. Confirm the data covers that area and its environmental margin.

### 3. Prepare bounded regional packages

- [ ] Prepare each large **local** input from its publisher original. A FileGDB ZIP can stay zipped; an existing `.gdb` directory is also supported. Already prepared regional packages cannot be used as originals for another scope.

```bash
python scripts/prepare_extract.py --catalog data/raw/imports/catalog.yml --source aer_wells --study-area config/study_area.live.yml --output-root data/raw/extracts/aer
```

- [ ] Inspect `report.json` and the generated package/source metadata. Check original SHA-256, selected layer/fields, record count, region and CRS. Preparation preserves flags; it does not automatically enable a source or populate PostGIS. Default caps are 10,000 selected records and 512 MiB output. Shrink the region if a cap is exceeded; the command refuses truncation.
- [ ] If a second source also needs preparation, pass the previous `prepared_catalogue.json` as `--catalog` and the second source key with a different `--output-root`. This preserves already prepared entries. Keep the **last generated catalogue** as the final input catalogue; bounded files and verified REST sources can remain as their original entries.
- [ ] Use the same study-area configuration for preparation and ingestion. Environmental extracts retain the 500 m margin; inspection/preparation does not itself establish publisher coverage. Keep original downloads or a trustworthy external archive for audit/rebuilding. See [regional extract instructions](regional_extracts.md).

### 4. Ingest into local PostGIS, then start the app

- [ ] Ingest with the **final prepared catalogue** and chosen study file. Example for the single AER-preparation command above:

```bash
python scripts/run_live.py --catalog data/raw/extracts/aer/prepared_catalogue.json --study-area config/study_area.live.yml
```

- [ ] Check the completed run ID, manifest, counts, CRS, coverage and quarantine reasons under `outputs/runs/<run-id>/`. Previously successful data must remain selectable if a new run fails. Inspect failures and fix the source/mapping rather than treating missing data as zero nearby features.
- [ ] Set `SOURCE_CATALOG_PATH` in `.env` to the **absolute path of the final catalogue**, restart Streamlit and select the real-source dataset. For example, use your own local path rather than this placeholder:

```text
SOURCE_CATALOG_PATH="C:/Projects/alberta/data/raw/extracts/aer/prepared_catalogue.json"
```

```bash
python -m streamlit run app.py
```

The CLI above can use a custom `--study-area`; the app's **Run full pipeline** action currently uses `config/study_area.live.yml`. Keep that file aligned with the prepared packages when using the app to rerun ingestion. Read-only selection of an existing result uses its stored study area.

### 5. Finish the real-data acceptance and handoff

- [ ] Validate a small real-data run before enlarging the region. Spot-check well positions/identifiers, licensee/legal-location/licence-status fields and the selected surface-location grain. Confirm environmental layers and the nearest actual feature geometry make sense at known sites.
- [ ] Check source extent and completeness; investigate all quarantines/duplicates and missing geometry/CRS. An empty critical-habitat selection can be legitimate only with verified source coverage. No nearby feature, unavailable coverage and incomplete coverage have different meanings.
- [ ] Repeat unchanged inputs/catalogue/area and verify stable run ID and no duplicate well/proximity rows. Test a failed input refresh while preserving earlier results. The existing synthetic checks cover mechanics; these local-data checks remain to be executed.
- [ ] Check markers/detail selection, licensee/category/threshold filters, 50/100/250/500 m results, matching CSV/GeoJSON exports and standalone HTML. Record the real baseline and at least one changed-threshold comparison with well IDs and interpretation.
- [ ] If running all integration tests, create a **separate initially empty `_test` database**, set `TEST_DATABASE_URL` to it and follow the [README integration-test instructions](../README.md#database-integration-tests). Do not use `alberta_risk`; skipped database tests are not passing evidence.
- [ ] Measure actual extraction/import/dashboard time and disk needs. The synthetic 1,000-well benchmark does not establish full ST37 performance or Windows behavior.
- [ ] Save permitted final manifests/validation summaries, exports, screenshots, methodology, source/permission records and limitations. Finish the separate [AIDA 1145](../aida-final-project-tyler-weinkauf/courses/AIDA-1145/EVIDENCE.md) and [AIDA 2362](../aida-final-project-tyler-weinkauf/courses/AIDA-2362/EVIDENCE.md) evidence packages and current instructor/D2L requirements.
- [ ] Update `DESIGN.md` with actual completion evidence. Phase 4 still needs the official regional run; revised Phase 5 needs actual AER well-attribute validation; Phase 6 still needs the final committed checkout/intended platform and course handoff. These are not marked complete simply because data files were added.

For the optional online basemap, retain [OpenStreetMap attribution/copyright](https://www.openstreetmap.org/copyright) and follow the [standard tile usage policy](https://operations.osmfoundation.org/policies/tiles/). OpenStreetMap supplies display context, not the analytical environmental layers; the app's offline geometry mode remains available.

## Git and other users

Commit code, requirements, the disabled example catalogue, documentation and permitted small synthetic fixtures. Each user downloads their own inputs and configures a private catalogue/connection. The README links this checklist; large publisher datasets are not distributed through GitHub. Verify exclusion with `git check-ignore -v data/raw/aer/ST37.zip` before committing. Avoid forcing ignored datasets into Git; already-tracked files require separate handling, although none are currently tracked under `data/`.
