# Real-source verification and acquisition status

**Phase 4 is in progress, not complete.** Acquisition infrastructure is implemented and tested against explicitly synthetic local HTTP/GIS fixtures. No official AER, Alberta environmental or federal habitat dataset has been downloaded or represented as verified.

## Access scope

All access failures below were observed in this managed cloud session. They do not establish whether the user's eventual runtime can reach a publisher API or download URL. The user may also download files separately for the implemented local-import route. Keep those sources in scope; actual-file/schema/licence verification can happen in that runtime or with supplied samples. See [data access routes and implementation status](data_access.md). Cloud allowlist changes are not a prerequisite for the final project's real-data use.

## Current access and verification — 8 November 2026

The new published environment applies all five previously requested discovery hosts. Fresh provincial catalogue, ArcGIS portal and Petrinex public-page requests returned HTTP 200. This supersedes the earlier blanket discovery-host CONNECT denial. See [official-source discovery](source_discovery.md) and its response hashes for the inspected resources, terms, reporting limitations and exact remaining access failures.

The provincial parks catalogue now establishes an official service URL and Open Government Licence – Alberta metadata. Petrinex's current Alberta Public Data page establishes the separate public-download host, and linked learning aids document CSV/XML ZIPs, reporting lag, masking and mixed facility/well identifier semantics. Actual service layers/files and AER/Petrinex identifier correspondence remain uninspected; catalogue entries stay disabled/unverified.

Newly discovered `geospatial.alberta.ca`, `geodiscover.alberta.ca`, `search.open.canada.ca` and `www.petrinex.gov.ab.ca` are blocked by proxy CONNECT 403. AER instead returns HTTP 403 with a “request is blocked” page, while Canada's earlier CKAN search returned HTTP 429. A later successful search now identifies ECCC's national critical-habitat record and its listed FileGDB ZIP; see [the download checklist](download_inputs.md) and [new metadata evidence](evidence/input_discovery_2026-11-08.json). These failures require different follow-up; allowing discovery roots alone does not resolve them. No environment configuration was changed or published during this pass.

The previously published OpenStreetMap tile permission returned HTTP 200 in the prior phase. That result establishes display access only. No credentials have been requested for the intended public analytical sources.

## Prepared implementation

- `src/sources/http.py`: inherited proxy/CA trust, HTTPS for remote sources, bounded GET retries (including 429/5xx), streamed download caps, SHA-256 byte cache, conditional refresh and corruption detection. Unchanged responses retain their input identity. HTTP is allowed only for local fixture servers.
- `src/sources/files.py`: inspect actual layers/fields/CRS before bounded reads; ZIP Shapefile, GeoPackage and OpenFileGDB support; no unsafe ZIP extraction or silent layer choice. Acquired CRS must match verified catalogue metadata. Local files use immutable acquisition snapshots too; plain well CSV supports explicitly configured coordinates/CRS.
- `src/sources/arcgis.py`: inspect layer metadata and fields, require supported GeoJSON output, query the study envelope plus a 500 m environmental margin, check count/ID completeness, acquire ID batches and reject missing/duplicate/unexpected records or contradictory response CRS.
- `src/sources/pipeline.py`: require all core sources to be enabled/verified with explicit coverage notes; acquire and validate all inputs before loading, archive raw-response metadata and selected-record lineage, then load all source snapshots/wells/features/quarantine and calculate proximity in one database transaction. A source/page/load failure retains the previous analyzed run. Persistent attempts contain stage/error class, without connection credentials.
- `scripts/inspect_source.py` and `scripts/run_live.py`: inspection and bounded-run commands with `--path` for local GIS inspection and `--catalog` for runtime source selection. The current official catalogue deliberately fails preflight until verified metadata is configured. The UI's full-pipeline action uses this readiness gate; demo actions remain usable.

The initial configurable pilot is `config/study_area.live.yml`: **Drayton Valley**, WGS84 box `[-115.08, 53.20, -114.94, 53.30]`, with EPSG:3400 analysis and 50/100/250/500 m thresholds. This is an educational pilot choice, not an assertion that a source covers it or that any location needs operational review. Keep or revise it after inspecting data availability.

## Verification sequence with accessible runtime sources or supplied files

1. Locate authoritative product/catalogue pages. Record publisher, exact resource/download URLs, update/version, terms and redistribution limits. Preserve AER's product-specific copyright terms rather than assuming OGL.
2. Use the inspection command to read the actual file/layer metadata. Record source CRS, geometry types, IDs, company-role semantics, fields, source extent and ArcGIS limits. Do not infer an ST37 CRS from other products.
3. Configure source URL, `native_crs`, `field_mapping`, layer/archive selection where required, `license_note`, references and explicit `coverage_note`. Enable/mark verified only after inspecting those facts. Core environmental entries have known category labels; their external schema mappings are still empty.
4. Run the pilot with all core sources. Environmental geometry uses a projected 500 m margin and is clipped after validation. A complete valid input scope may have zero nearby environmental features; a missing source or incomplete page is not treated as a known absence.
5. Inspect source bundle checksums, counts, quarantined reasons, run manifest, source coverage and actual well/category results. Repeat unchanged inputs to verify stable identity/no duplicate rows and test a failed refresh preserving prior results.
6. Confirm the real dataset opens in the UI and that filters/exports match. Only then complete Phase 4 in DESIGN.md.

## Commands

After discovering an actual official endpoint, inspection supports:

```text
python scripts/inspect_source.py arcgis <verified-candidate-service-or-layer-URL>
python scripts/inspect_source.py file <verified-candidate-download-URL> --layer <inspected-layer-name>
```

Angle-bracket values above are placeholders, not source endpoints. `--archive-member` disambiguates multiple spatial datasets in one ZIP. The file inspector defaults to a 512 MiB response cap; inspect expected sizes/resources before increasing limits or acquiring a province-wide archive.

Once the catalogue is verified:

```bash
python scripts/run_live.py --study-area config/study_area.live.yml
python scripts/run_live.py --study-area config/study_area.live.yml --refresh
```

The default cap is 10,000 selected records per source, 512 MiB per HTTP response and a 2 GiB total transfer budget per cache client/run. Preflight reserves four times the total transfer budget as conservative disk headroom for cached inputs, selected bundles, PostGIS and WAL. Exceeding a transfer/record limit fails rather than truncating input; choose a smaller pilot or a documented larger budget after inspecting available resources. Cached/raw/generated records remain ignored by Git.

Source bundles record original HTTP request/final URL, checksums, retrieval time, ETag/Last-Modified when provided, inspected source CRS/layer/schema, selected mappings and canonical-record lineage. A content identity excludes access time/local cache paths for reproducibility. Published data is authoritative in PostGIS; unreferenced files from an interrupted attempt are not proof of a published dataset.

## Evidence so far

The Phase 4 suite had **80 passing tests**; the subsequent Phase 5 suite had **103 passing tests**. New tests use synthetic local HTTP services and generated GIS files: actual Shapefile/GPKG/FileGDB ZIP reads, CRS/subset checks, retry/304/corrupt-cache/byte-limit behavior, ArcGIS ID-page completeness, buffered clipping and transactional PostGIS loads. A simulated incomplete source and a trigger-induced load failure both preserve prior analyzed results. These tests validate adapter mechanics, not official schema compatibility or a real regional run.

Phase 5 independent work now supplies synthetic production contracts/import, exact-ID audit, active-batch history and chart/availability behavior. It does not resolve the official-access blocker; see [production status](production.md).

## Local-file implementation follow-up

Local spatial and production routes are implemented and covered by the 113-test suite. A custom catalogue can mix file inputs and remote sources. See [data access](data_access.md) for provenance fields, formats, limits, commands and the disabled template. The local end-to-end proof uses synthetic files; official CRS/schema/coverage, permissions and identifier compatibility still need actual-data evidence in a suitable runtime. Neither source publication nor cloud network changes are required to develop or execute the local route.

## Current source scope after user revision

Petrinex is excluded; no production download or join is required. Revised Phase 5 verifies AER surface-well attributes. The uploaded June 2026 [ST37 guide](st37_reference.md) establishes candidate surface/bottom/string layers and fields, with actual geometry/schema/unique keys still uninspected. The 1.23 GB geodatabase ZIP shown by the user exceeds current default acquisition limits; expanded ZIP size must also be checked. The [manual download checklist](download_inputs.md) explains current limits and the four required datasets. All of `data/` is ignored by Git; each user supplies their own files.

## Bounded regional preparation implemented

The ST37 size mismatch now has a local preparation route: inspect/select directly from the original ZIP or FileGDB, then ingest only a capped regional package. The 128-test suite includes FileGDB/ZIP originals, source lineage, exact geometry/ID preservation, reuse, limits, incompatible-scope refusal and a four-source PostGIS load with buffered edge distances. This is synthetic compatibility evidence, not an acquired official regional run. See [regional extracts](regional_extracts.md). Actual AER fields, terms, key uniqueness and original archive performance remain open.
