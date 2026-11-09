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

On the AER website, locate **ST37: List of Wells in Alberta**, as in the user's screenshot. The screenshot offers a **Geodatabase ZIP (1.23 GB)** and an **Excel ZIP (170 MB)**. The geodatabase is the preferred spatial candidate. The attached June 2026 guide distinguishes surface holes, bottom holes, production strings and connecting geometry. Surface holes are the proposed location grain for site screening.

Keep the ZIP intact for inspection. Actual layer names, geometry, CRS, unique keys and terms still need verification. Excel workbooks are not a direct supported input; a documented CSV conversion with verified coordinates/CRS is an alternative. Do not infer that the two distributions have identical tables.

**Prepare a regional package before loading:** the 1.23 GB original exceeds normal acquisition limits. `scripts/prepare_extract.py` now reads the local ZIP or `.gdb` directly, selects the configured study area/layer/fields and creates a small package. It does not copy the whole original to the cache or load the province into PostGIS. Normal 512 MiB input and ZIP limits remain in effect for app ingestion. See [regional extract instructions](regional_extracts.md), including provenance, the 500 m environmental margin, capped output and the cost of hashing the original. Full ST37 compatibility/performance is still unverified until its real file is available.

## Environmental candidates located

These catalogue resources have been identified; actual layers/files, fields, CRS and pilot coverage remain to be inspected. Catalogue licence labels do not substitute for checking product limitations.

| Input | Publisher record / resource | Selection still needed |
|---|---|---|
| Surface water | Alberta [Base Waterbody Polygon Update](https://open.alberta.ca/dataset/gda-91d6eac8-e03d-49c1-bed1-9bf962f7eb71) and [Base Stream and Flow Representation Update](https://open.alberta.ca/dataset/gda-07172210-57aa-4958-a127-ce204ccb21c2); both catalogue records list OGL-Alberta and the [hydrography update MapServer](https://geospatial.alberta.ca/titan/rest/services/environment/inland_base_hydrography_update_10tm_nad83_aep/MapServer) | Compare with the intended Base Water Feature service. Verify full coverage versus update-only content, select actual streams/waterbodies, exclude artificial network connectors, and inspect layer IDs. Do not silently substitute update-only data for a complete base. Multiple water entries may share category `water`. |
| Protected areas | Alberta [Parks and Protected Areas of Alberta](https://open.alberta.ca/dataset/gda-6b96341f-2e19-4885-98af-66d12ed4f8dd), catalogue OGL-Alberta; [FeatureServer](https://geospatial.alberta.ca/titan/rest/services/boundary/parks_protected_areas_alberta/FeatureServer) | Inspect the actual polygon layer and fields. GIS boundaries are screening data; written legal descriptions take precedence. |
| Critical habitat | ECCC [Critical Habitat for Species at Risk National Dataset – Canada](https://open.canada.ca/data/en/dataset/47caa405-be2b-4e9e-8f53-c478ade2ca74), catalogue OGL-Canada; listed [English FileGDB ZIP](https://data-donnees.ec.gc.ca/data/species/protectrestore/critical-habitat-species-at-risk-canada/CriticalHabitat.zip) and [REST layer](https://maps-cartes.ec.gc.ca/arcgis/rest/services/CWS_SCF/CriticalHabitat/MapServer/0) | Inspect actual ZIP layer(s)/CRS or REST schema. Query/subset Alberta and the study margin. Review generalization, exclusions and source limitations; this is not proof of complete ecological sensitivity coverage. |

The national critical-habitat record was located through a successful fresh CKAN catalogue search; it is distinct from the similarly titled Auditor General report, which is not a geometry dataset. The Canadian catalogue had returned HTTP 429 earlier; this later successful metadata response supersedes that particular observation. Actual data-host download access has not been established.

Publisher web access can work on your machine even when this cloud session cannot reach a service. Choose permitted GeoJSON, GeoPackage, zipped Shapefile/FileGDB or a compatible API route where available. WMS/tiles are rendered images, not analytical feature geometry. Wetlands and the historical 2014 ESA remain optional, outside the first required input set.

## Git and other users

Commit code, requirements, the disabled example catalogue, documentation and permitted small synthetic fixtures. Each user downloads their own inputs and configures a private catalogue/connection. The README links this checklist; large publisher datasets are not distributed through GitHub. Verify exclusion with `git check-ignore -v data/raw/aer/ST37.zip` before committing. Avoid forcing ignored datasets into Git; already-tracked files require separate handling, although none are currently tracked under `data/`.
