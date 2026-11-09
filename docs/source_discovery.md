# Official-source discovery — 8 November 2026

The newly published environment applies all five previously requested discovery hosts. This pass acquired **metadata and documentation only**. No official wells, environmental geometries or production records were imported. [Response evidence](evidence/source_discovery_2026-11-08.json) records URLs, statuses, byte counts and SHA-256 values; raw web responses and publisher PDFs remain outside Git. UTC capture times fall on 9 November; the project date is 8 November in America/Regina.

## Provincial resources

The Alberta Open Data CKAN API returned HTTP 200. The exact-title parks search identifies **Parks and Protected Areas of Alberta**, record `gda-6b96341f-2e19-4885-98af-66d12ed4f8dd`, with **Open Government Licence – Alberta** metadata. Its listed FeatureServer is:

`https://geospatial.alberta.ca/titan/rest/services/boundary/parks_protected_areas_alberta/FeatureServer`

The catalogue also links to [publisher XML metadata](https://geodiscover.alberta.ca/geoportal/rest/metadata/item/0d1ac1474eba42fe9444a42a23a4ea1b/xml). Both hosts receive proxy CONNECT 403, so layer IDs, geometry, fields, service limits, actual CRS and pilot coverage are still uninspected. The [Alberta licence page](https://open.alberta.ca/licence) itself returned HTTP 200. The ArcGIS portal item `478c3bd0ad9f444aaa089d6652346082` points to the same service and says written legal descriptions take precedence over GIS boundaries. Its `spatialReference` is `102184`; this has not been substituted for an inspected layer CRS.

ArcGIS search also located item `c2fbd445f89a4139bcfdae771e44b93a`, titled **Base_Water_Feature**, pointing to:

`https://geospatial.alberta.ca/titan/rest/services/Environment/base_water_feature/MapServer`

This is a discovery candidate, not an independently authenticated publisher record: the item owner is `SN-ArcGIS`. Its description mentions a single-line network, arbitrary network connectors and waterbody polygons. Layer selection must distinguish actual water geometry from connectors before distances can be interpreted. The service is blocked by the same host policy. The provincial catalogue's hydrography results also link to an updated hydrography service; these products have not been silently substituted for the requested Base Water Feature.

## Petrinex resources and attribution implications

The old `/PD/Pages/APD.aspx` path returned 404. Starting from the live homepage located [Public Data](https://www.petrinex.ca/public-data/) and [Alberta Public Data](https://www.petrinex.ca/public-data/apd/), both HTTP 200. The latter links to the actual data application at `https://www.petrinex.gov.ab.ca/PublicData?Jurisdiction=AB`, whose host receives proxy CONNECT 403.

The linked October 2026 [Conventional Volumetric Data learning aid](https://www.petrinex.ca/media/4gfhoah5/pd_conventional_volumetrics_report.pdf) and March 2022 [Well to Facility Link learning aid](https://www.petrinex.ca/media/1q5dwf5w/pd_well_to_facility_link_report.pdf) were retrieved successfully and read with `pdftotext`. These documents describe, without verifying actual acquired file headers:

- Monthly conventional volumetrics generated after the AER reporting deadline, covering the current production year and four preceding years. Confidentiality changes and UWI changes can trigger regenerated files. A completed calendar month does not establish that its download is available.
- CSV/XML downloads, packaged as ZIP files. The documented volumetrics API pattern is `https://www.petrinex.gov.ab.ca/publicdata/API/Files/{Jurisdiction}/Vol/{FileName}/{FileFormat}`, with a `2022-01` example. No current-month API response has been acquired.
- Production Month, Reporting Facility ID, Activity ID, Product ID, From/To ID and its type, Volume, Energy and other elements. The From/To ID can denote a facility or a well; a matching ID alone does not establish that a row is well production.
- Volume units depend on product: cubic metres for liquids and thousands of cubic metres for gas; Energy is separately measured in GJ. There is no inspected source `unit` column or verified product-to-unit mapping yet.
- Masked `***` identifiers and confidentiality-driven aggregations/omissions. These cannot support a verified well join. Missing public data is not zero production.
- The well-link report represents **current** links as of file creation, refreshed nightly. Its Well ID combines province/state, node type and a well identifier; Well Type is `WI`. A current facility link is insufficient evidence for allocating historical facility totals to wells. Actual AER identifier correspondence remains unverified.

The [Petrinex terms page](https://www.petrinex.ca/terms), HTTP 200, permits non-commercial use/reproduction/storage/transmission with Crown copyright acknowledgment and requires prior consent for commercial purposes. This is not an unrestricted Open Government Licence grant. The linked learning aids also carry a confidentiality notice despite being linked publicly; record this inconsistency and resolve product-specific terms before distributing source extracts. These documents are referenced, not copied into the repository. No permission is inferred from successful download alone.

The generic importer still requires a verified record identity, explicit units and defensible attribution. A source-specific transform must account for the documented grain, masking and unit rules after inspecting actual files. The official catalogue remains disabled.

## Remaining access and verification

| Destination | Fresh observation | Next work |
|---|---|---|
| `www.aer.ca` | HTTP 403 with “The request is blocked” HTML for homepage and candidate ST37 path; no CONNECT failure | Investigate the HTTP block or locate an authoritative distribution link. ST37 location/schema/CRS/terms remain unknown. |
| `open.canada.ca` | CKAN search HTTP 429 without Retry-After | Retry later at a reasonable rate; do not treat throttling as a missing dataset. |
| `search.open.canada.ca` | Catalogue UI redirects here, then proxy CONNECT 403 | Permit the actual search host before UI discovery. |
| `geospatial.alberta.ca` | Proxy CONNECT 403 | Permit official provincial service metadata and bounded GIS queries. |
| `geodiscover.alberta.ca` | Proxy CONNECT 403 | Permit official resource metadata/terms inspection. |
| `www.petrinex.gov.ab.ca` | Proxy CONNECT 403 | Permit actual public data application/API before inspecting files. |

The four newly discovered hosts are listed for environment review; no environment settings were changed or published during this pass. These are observations from this cloud session; runtime APIs/downloads or user-supplied files can support later verification independently. Full local-file ingestion is now implemented (steps 4.2c/5.2c); see [data access](data_access.md). With accessible inputs, inspect actual service layers/files, finish licence/identifier checks and configure verified mappings before executing the real pilot and production refresh. Phases 4 and 5 remain in progress.
