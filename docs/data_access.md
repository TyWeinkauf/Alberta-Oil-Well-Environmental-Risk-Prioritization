# Data access when running the program

Sources inaccessible to ChatGPT/Codex may be accessible through APIs or downloads on the user's machine. Cloud errors describe that environment and request; they do not establish universal dataset unavailability. The required real-data inputs are now AER wells and environmental layers. Petrinex/monthly production is outside the current scope. See [the download checklist](download_inputs.md).

## Supported acquisition routes

| Route | Implemented behavior |
|---|---|
| Publisher API | Configured ArcGIS REST adapter with inspected layer metadata, bounded queries and completeness checks. Other API protocols need a specific adapter. |
| Verified Alberta waterways | Use **Waterways** in Streamlit for the bounded regional inventory or the full layer-72 polygon import. [Verification and limits](hydrography.md) |
| Direct download URL | HTTP cache plus GIS-file readers. Production CSV/ZIP remains optional legacy code. |
| User-downloaded local files | Explicit `local_path` for GIS files or coordinate-mapped well CSV. No network request is made for a local entry, even when its publisher URL is recorded. |
| ST37 surface-hole Excel | Click **Import ST37 wells** to prepare and stage the retained workbook. The app uses the recorded datum when the workbook matches the verified AER release. [Excel workflow](st37_excel.md) |

All routes require verified source terms, field mappings and coverage/attribution evidence before enabling entries. Official compatibility is still unverified. Local files use the same validation, quarantine, atomic load as remote inputs. Failed imports preserve earlier results.

## Configure files you downloaded

Copy [the disabled local catalogue template](../config/source_catalog.local.example.yml) into an ignored data directory, for example `data/raw/imports/catalog.yml`. Put downloaded files beside it or set each entry's `local_path` to another path. Relative paths resolve beside the YAML catalogue, independently of the process working directory. Prefer absolute paths for the catalogue itself when configuring the app.

For each of the four required source entries, inspect and fill in:

- `publisher`, `url` (original publisher download URL) or `metadata_url`, `license_note`, and timezone-aware `downloaded_at`, such as `2026-11-08T18:00:00-06:00` for a file actually downloaded then.
- Actual `field_mapping`, source `native_crs` for GIS/well coordinates, and an explicit `coverage_note` for analytical sources.
- `file_layer` or `archive_member` when a spatial file/ZIP contains multiple datasets.
- For a plain well CSV, `csv_x_field` and `csv_y_field` using the actual coordinate column names, with the CRS those coordinates use. IDs stay strings, preserving leading zeros. CSV has no embedded CRS; its configured CRS must be established from publisher metadata. Invalid coordinates are quarantined; malformed rows/headers fail acquisition. The well CSV record cap applies to all input rows, without truncation.


Then mark the inspected entries `verified: true` and `enabled: true`. Keep unsupported/unverified optional entries disabled. A complete spatial run still needs wells plus water, protected areas and critical habitat; missing required categories cannot be treated as known absence.

Single-file GeoJSON and GeoPackage are supported by the spatial reader. ZIP multi-file Shapefile/FileGDB datasets before import so geometry and CRS sidecars stay together. Environmental CSV without actual geometry is unsupported; point/centroid approximations are not substituted for feature boundaries. A local-file upload screen is not implemented; configure paths to files already on the runtime's filesystem.

## Inspect and load in Streamlit

For a developer inspection of a local example file:

```bash
python scripts/inspect_source.py file --path data/raw/imports/water.geojson
```

Set `SOURCE_CATALOG_PATH` in the local `.env` or process environment to the verified catalogue's absolute path. Run `python scripts/run_live.py` when the core sources are ready. Use [regional preparation](regional_extracts.md) for optional large geodatabase inputs.

## Snapshot and provenance behavior

Each explicit local acquisition copies and hashes bytes into the ignored cache before parsing. It records the original path, publisher URL, declared download timestamp, cache retrieval time, byte count and SHA-256. The local file is reread on each acquisition so same-size replacements are detected; unchanged bytes reuse the snapshot metadata and input identity. Missing, changing, corrupted or over-budget inputs fail instead of being accepted as empty data. Multi-file directory inputs must be packaged first. HTTP `--refresh` validators do not apply to local files, which are always reread.

The default spatial limits are 512 MiB per file, a 2 GiB total acquisition budget and 10,000 records per source; the live CLI permits explicit bounded changes. Production CSV parsing has a 512 MiB file/uncompressed-CSV cap and a 100,000-row default cap. The original publisher download date remains distinct from the local cache retrieval time. Paths locate inputs; publisher identity and permission come from recorded source evidence.

Keep input files, private catalogues, generated reports and credentials outside Git. The entire `data/` directory and `outputs/` are ignored. No official file or valid schema is inferred from the template.

## Verification in this pass

The current full suite passes **128 tests** with no skips: local snapshots/provenance, caps/corruption, relative catalogue paths, string IDs, invalid coordinate quarantine, four-source spatial load and distances, production CSV/ZIP, exact verified-only charts, repeat identity and failed-import retention. The local integration tests prevent HTTP requests and exercise the configured app's production refresh and rendered chart with Streamlit AppTest. These local-file tests use project-authored synthetic fixtures, not an actual AER/Petrinex release. Separate candidate-release Chromium checks are recorded in [release verification](release_verification.md).

See [source verification](source_verification.md), [production](production.md) and [the design tracker](../DESIGN.md). Phases 4 and revised Phase 5 still require verified environmental/AER mappings and bounded real-data validation, which can happen in the user's execution environment. Retained production-code checks are historical/optional; no production input is needed for the current project.

Large GIS downloads have a separate preparation route: `prepare_extract.py --inspect` reads original metadata without caching the entire input, and preparation creates a small study-area package with embedded provenance. The file adapter automatically checks its scope/mapping/data checksum and retains original lineage in the run manifest. Unzipped `.gdb` directories are supported by preparation, while normal acquisition continues to accept bounded regular files/ZIPs only. See [regional extracts](regional_extracts.md).
