# Real-source verification and acquisition status

**Phase 4 is in progress, not complete.** Acquisition infrastructure is implemented and tested against explicitly synthetic local HTTP/GIS fixtures. No official AER, Alberta environmental or federal habitat dataset has been downloaded or represented as verified.

## Current external blocker — 8 November 2026

Fresh source-discovery requests were rejected by the managed proxy with CONNECT **403 Forbidden**. The running policy permits package-manager hosts and the published OpenStreetMap tile host, but not the discovery sites below. Their additions were saved in the environment configuration draft, preserving the existing tile host and package presets. Saving a draft does not apply or publish it.

| Host | Purpose / observed request | Current evidence |
|---|---|---|
| `www.aer.ca` | Locate current ST37 product/distribution and AER use terms | Proxy denied the candidate ST37 discovery path; its current path/download format remains unverified. |
| `www.arcgis.com` | Search public ArcGIS metadata for the named Alberta layers and verify publisher/service/layer IDs | Proxy denied the standard portal search request. No analytical service/layer endpoint has been selected. |
| `open.canada.ca` | Locate the critical-habitat catalogue record/resources and licence metadata | Proxy denied the catalogue search request. Dataset UUID and resources remain unverified. |
| `open.alberta.ca` | Verify provincial catalogue/licence metadata | Proxy denied the catalogue request. Product-specific use statements remain unverified. |
| `www.petrinex.ca` | Discover public production resources and reporting/licence metadata | Phase 5 discovery also denied with CONNECT 403; domain saved in the pending draft. Actual production access/schema remain unverified. |

Review and save these domains in environment settings to unblock discovery; publish the reusable environment when ready. Once access is applied, retry with a fresh connection, discover official service/download hosts and add only any further required destinations. Do not route requests through a different allowed service to bypass destination policy, disable TLS checks or invent dataset URLs/field mappings. No credentials have been requested for these intended public sources.

The previously saved `tile.openstreetmap.org` permission **is now published and a fresh tile request returned HTTP 200**. That result does not establish analytical-source access.

## Prepared implementation

- `src/sources/http.py`: inherited proxy/CA trust, HTTPS for remote sources, bounded GET retries (including 429/5xx), streamed download caps, SHA-256 byte cache, conditional refresh and corruption detection. Unchanged responses retain their input identity. HTTP is allowed only for local fixture servers.
- `src/sources/files.py`: inspect actual layers/fields/CRS before bounded reads; ZIP Shapefile, GeoPackage and OpenFileGDB support; no unsafe ZIP extraction or silent layer choice. Acquired CRS must match verified catalogue metadata.
- `src/sources/arcgis.py`: inspect layer metadata and fields, require supported GeoJSON output, query the study envelope plus a 500 m environmental margin, check count/ID completeness, acquire ID batches and reject missing/duplicate/unexpected records or contradictory response CRS.
- `src/sources/pipeline.py`: require all core sources to be enabled/verified with explicit coverage notes; acquire and validate all inputs before loading, archive raw-response metadata and selected-record lineage, then load all source snapshots/wells/features/quarantine and calculate proximity in one database transaction. A source/page/load failure retains the previous analyzed run. Persistent attempts contain stage/error class, without connection credentials.
- `scripts/inspect_source.py` and `scripts/run_live.py`: inspection and bounded-run commands. The current official catalogue deliberately fails preflight until verified metadata is configured. The UI's full-pipeline action uses this readiness gate; demo actions remain usable.

The initial configurable pilot is `config/study_area.live.yml`: **Drayton Valley**, WGS84 box `[-115.08, 53.20, -114.94, 53.30]`, with EPSG:3400 analysis and 50/100/250/500 m thresholds. This is an educational pilot choice, not an assertion that a source covers it or that any location needs operational review. Keep or revise it after inspecting data availability.

## Verification sequence after network access

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

The current suite has **80 passing tests**. New tests use synthetic local HTTP services and generated GIS files: actual Shapefile/GPKG/FileGDB ZIP reads, CRS/subset checks, retry/304/corrupt-cache/byte-limit behavior, ArcGIS ID-page completeness, buffered clipping and transactional PostGIS loads. A simulated incomplete source and a trigger-induced load failure both preserve prior analyzed results. These tests validate adapter mechanics, not official schema compatibility or a real regional run.

Phase 5 independent work now supplies synthetic production contracts/import, exact-ID audit, active-batch history and chart/availability behavior. It does not resolve the official-access blocker; see [production status](production.md).
