# Prepare a small study-area extract

The project now uses a regional preparation step for large local GIS downloads. Keep the publisher original on disk, select the actual layer and study area, and prepare a small immutable package before the normal PostGIS pipeline. The application keeps its **512 MiB input limit and 10,000-record default**; growth of a province-wide file does not automatically enlarge app/database imports.

This reduces the records, fields and bytes passed to the application. It **does not reduce the publisher download itself**. Without a verified publisher-side spatial API, the full ST37 ZIP must still be downloaded, or obtained as a permitted smaller extract. Preparation hashes the original twice and the GIS driver may scan/decompress substantial data, so original-file I/O and elapsed time can still grow. Memory/output are constrained by the returned record count and package limits; complex individual geometries and native driver buffers also consume resources.

## Supported originals and output

- A local FileGDB `.gdb` directory, or a ZIP containing a FileGDB, Shapefile, GeoPackage or GeoJSON. ZIP members are read in place through GDAL; the command does not unpack the entire archive to disk. Unsafe paths and ambiguous datasets are rejected. Multi-file inputs must stay together; unzipped Shapefiles are rejected.
- A standalone GeoPackage or GeoJSON. Close GeoPackage writers/checkpoint their transactions before preparing; active journal/WAL sidecars are rejected so unaccounted sidecar changes cannot escape the parent checksum.
- Coordinate CSV, Excel, remote URLs and APIs are not handled by this preparation command. Existing API and bounded CSV acquisition remain separate routes. Keep the original in a stable state; `.gdb` symlinks are rejected and original content changes abort publication.

The result is a small ZIP containing `extract.gpkg` and `extract_manifest.json`. The selected source fields and native geometry/CRS are retained. Native coordinate precision is not reduced by a WGS84 round trip, and geometries are not clipped/repaired during preparation. The normal ingestion contracts still validate/quarantine selected records and perform final projection/clipping. Output container timestamps and SQLite counters are normalized for reproducible bytes; original download dates remain in the manifest.

## Inspect before preparing

Put the original under ignored `data/raw/` or on another local disk. Create your private catalogue from `config/source_catalog.local.example.yml`. For `aer_wells`, point `local_path` at the original ZIP or `.gdb` directory and leave unverified entries disabled. Then run:

```bash
python scripts/prepare_extract.py --catalog data/raw/imports/catalog.yml --source aer_wells --inspect
```

This inspects the original directly, without the ordinary cache's full-file copy/512 MiB cap. It lists actual layers and, when a layer is selected/unambiguous, its CRS/fields/types. With multiple layers, configure `file_layer` with the inspected surface-hole layer name and repeat inspection. If the ZIP contains multiple datasets, configure `archive_member` with the intended `.gdb` directory or other spatial member; `python -m zipfile -l <local-zip-path>` can list archive names. Do not assume that guide spellings exactly match the current release.

Fill in the inspected `native_crs` and `field_mapping`, plus publisher, original URL or metadata URL, timezone-aware `downloaded_at`, terms and coverage evidence. The [ST37 guide review](st37_reference.md) gives candidate fields and explains surface-hole grain; it does not verify actual data or terms. No schema, EPSG code, unique key or coverage is inferred from a filename.

## Prepare and ingest

The study boundary remains in `config/study_area.live.yml`; the initial pilot is Drayton Valley. Choose the area before running:

```bash
python scripts/prepare_extract.py --catalog data/raw/imports/catalog.yml --source aer_wells --study-area config/study_area.live.yml
```

By default, preparation writes:

```text
data/raw/extracts/
  <input-and-scope-identity>/
    extract.zip
    report.json
    source.json
  prepared_catalogue.json
```

`prepared_catalogue.json` replaces only the selected entry's local path/layer/archive settings with the small package; other catalogue entries are preserved. Flags are preserved too: preparation does not verify or enable a source automatically. Inspect the report and finish source/coverage checks, then enable only verified entries in your private catalogue.

Use the generated catalogue for normal ingestion once all four required sources are ready:

```bash
python scripts/run_live.py --catalog data/raw/extracts/prepared_catalogue.json --study-area config/study_area.live.yml
```

For the app, set `SOURCE_CATALOG_PATH` to the absolute path of the prepared catalogue, restart Streamlit and use **Run full pipeline**. The app needs only the small package at ingestion time; the original remains referenced by path/checksum for audit/rebuilding. Keep the original or a trustworthy external archive for reproducibility.

Use `--output-root` to choose a different ignored destination, `--max-records` for an explicit record cap (default 10,000, maximum 100,000), and `--max-output-mib` for a smaller output cap (maximum 512 MiB). The output GeoPackage and ZIP must each fit the byte cap. Exceeding a limit fails with **no truncation**; shrink the area or use multiple independently defined study areas. The normal pipeline still has its own record limit, so a deliberately larger preparation cap does not change the app's defaults.

If another environmental input is also large, run preparation for its source key using the previous `prepared_catalogue.json` as the input catalogue; this preserves the already prepared AER entry. The command does not require PostgreSQL and never loads records into it.

## Scope, provenance and failure behavior

Well extracts use the study-area query envelope. Environmental extracts include the projected **500 m margin** needed for edge-well distances. Provider bounding-box candidates are retained, so outside-corner, duplicate or invalid records returned by the provider still reach normal validation. A driver may omit null/invalid geometry during its spatial query; regional preparation is not a province-wide quality audit or proof of source completeness.

The embedded manifest binds the package to the complete study configuration, source key, category and field mapping. The normal file adapter rejects a package prepared for a different scope rather than treating a smaller extract as complete coverage of a larger area. Use the same study-area file for preparation and ingestion; prepare another package from the original publisher input when changing it. A prepared package is rejected as a preparation input, so it cannot be re-labelled as coverage for a wider area. Ordinary UI threshold/filter changes do not modify that study configuration or trigger preparation.

Provenance includes original path, streamed SHA-256 (a deterministic aggregate of relative file names/sizes/hashes for `.gdb` directories), original byte/file counts, source metadata, original layer/CRS, selected fields, query envelope/margin, record count, output-data checksum and GDAL/pyogrio versions. Two content fingerprints detect a changing original before publication; they do not copy it into the cache. Keep external writers closed throughout preparation.

Packages are published atomically in immutable identity directories. Repeats verify/reuse existing bytes; changed originals, mappings or study settings create new identities. Record/size/read/write/checksum failures leave earlier packages and the previously generated catalogue intact. Corrupt prepared data/report/catalogue fragments fail validation. New temporary GeoPackages/ZIPs require disk headroom, but no second province-wide cached copy is created. All outputs under `data/` remain ignored by Git.

## Verification and remaining work

The full suite passes **128 tests**. New tests cover native FileGDB directories, zipped FileGDB and GeoPackage originals; exact coordinates/string IDs; irrelevant fields excluded; parent-file preservation; stable bytes/reuse; record/byte caps; metadata/scope/mapping/CRS errors; corrupt packages and changing originals; and environmental margin retention. An end-to-end PostGIS run from four prepared layers yields two wells, four features, ten proximity rows and 50/100 m water distances, including a feature outside the unbuffered study boundary. A wider-area retry fails without replacing the previous run.

The CLI was exercised from outside the checkout: inspect, prepare, repeat and record-cap failure. A synthetic 2,153,063-byte ZIP produced a 4,940-byte two-record package usable with a 65,536-byte ingestion cache limit. An empty environmental extract was also prepared/read successfully. See [retained evidence](evidence/regional_extracts_2026-11-08.json).

These checks use synthetic data, not the real 1.23 GB ST37 download. Actual AER/FileGDB schema, licensing, surface-key uniqueness, archive performance and pilot coverage remain to be verified when the file is available. The system avoids enlarging ordinary import limits; it does not promise constant preparation time as publisher inputs grow.
