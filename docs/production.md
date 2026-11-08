# Production ingestion and verified well attribution — Phase 5

**Phase 5 is in progress.** The generic CSV/ZIP importer, production contracts, exact-ID audit, immutable refresh history and verified-only chart are implemented and tested using project-authored synthetic observations. No actual Petrinex record has been acquired, and its current public access, reporting grain, licence, field names and identifier semantics remain unverified.

`https://www.petrinex.ca/` discovery was denied by the cloud proxy with CONNECT **403**. The candidate discovery host `www.petrinex.ca` is saved in the environment draft alongside the previously requested analytical discovery hosts; none of those source-access additions is applied yet. Review/save the pending network change in environment settings, and publish when ready. Further actual download hosts may be needed after authoritative resources are located. Do not infer that proxy denial means a missing account or request a token without verifying actual product access requirements.

## Data boundary and configuration

Petrinex ingestion is separate from geospatial ingestion. It appends production snapshots to an existing real analysis run and does not rerun the map pipeline. The current `petrinex_production` catalogue entry deliberately has no URL/mapping and remains disabled/unverified.

The adapter currently supports a bounded CSV, or a ZIP containing one bounded CSV. It does not claim that this is the current Petrinex distribution format. Actual format, download endpoints, reporting periods and licences must be inspected first. `config/production_window.yml` proposes August–October 2026 as three complete calendar months before 8 November; source availability/reporting lag is not yet verified. The UI lets the user choose its requested month window.

Canonical mapping keys are `source_record_id`, `period`, `product`, `activity`, `volume`, `unit`, optionally `reporting_facility_id`, `well_identifier_nullable`, and a mixed-source `attribution_level`. These are **internal contracts**, not invented Petrinex column names. The source's actual fields go in `field_mapping` only after inspection. If the public product lacks a unique record ID, a documented composite/hash strategy must be implemented from its verified grain before enabling it; row order is not an authoritative identifier.

`reporting_level` declares verified source grain (`well`, `facility`, `mixed` or `unknown`). Mixed data needs explicit `attribution_values` translating source labels. Unknown labels are quarantined; no company name or coordinate is used to guess reporting level. Tabular production has no spatial CRS; its database snapshot says “not applicable (tabular).”

## Validation

- Months normalize using the verified `period_format`, then must be valid `YYYY-MM`. Valid rows outside the requested window are counted separately as excluded, rather than silently dropped.
- Record IDs must be nonempty and unique; all occurrences of a duplicate ID are quarantined.
- Product, activity and unit must be explicit. They are retained without guessing conversions or treating unlike codes as comparable.
- Volume is stored as exact decimal. The technical contract supports at most 38 significant/integer digits and 12 decimal places; nonfinite or unsupported representations are quarantined. This is a representation limit, not a physical production limit.
- Negative values require an exact configured `adjustment_activities` match and a documented `adjustment_note`. They are not changed to absolute values or mixed into ordinary production without explanation.
- Rejected records retain reason codes and references to their exact archived input record. A wholly invalid batch does not replace the previous active batch.

## Join rules

A well chart accepts a record only when all of the following hold:

1. The record is explicitly reported at well level.
2. A source-supplied well identifier is present.
3. The configured `well_identifier_field`, `identifier_namespace` and `join_evidence` establish which well identifier it means.
4. The identifier exactly matches one well in the selected analysis run.

Only outer whitespace is ignored; leading zeros and punctuation are retained. Company text, nearest geometry, fuzzy strings and allocation of facility totals are never used to fabricate well-level production. Multiple exact candidates produce `ambiguous` audit entries/links, which cannot enter a chart. Missing/unmatched/unverified IDs, unknown reporting levels and facility records remain auditable separately.

The query serving a well chart additionally checks the active batch, snapshot, analysis-run membership, well attribution, audit status and verified link confidence. Historical batches and ambiguous links cannot be summed into the current chart. Facility records are visible in the production audit without being assigned to a well, even if a raw facility record contains a matching well-ID string.

## Storage, refresh and UI

Migration 004 adds production batch/active-pointer/audit/quarantine tables and snapshot role/revision metadata. Batch identity includes input bytes, configuration, month window and well-identifier evidence. Repeating unchanged input reuses the batch; changed input/evidence creates a new immutable revision. Active-batch switching is transactional. A failed import leaves earlier active data intact. Verified real refreshes retain stage/error-class attempts without connection credentials.

The map's spatial-input counts remain separate from monthly production records. Source provenance includes the production snapshot role, while production has its own validation/audit counts. The UI provides:

- **Load synthetic production demo**, available only for a demo analysis run. Synthetic production is never attached to a real-source run, and real refresh requires a real-source run.
- **Refresh production**, gated on verified source configuration, with a requested start/end month.
- **Monthly production** in well details: verified observations only, with a separate selector for each product/activity/unit combination. Duplicate observations within a month are shown as individual points rather than silently summed. Missing months are not filled with zeros. Decimal values remain exact in the table; chart coordinates use floating-point display values.
- **Production attribution audit** in Data quality: active source mode, window, counts, reporting-level/link outcomes, quarantine and a downloadable JSON audit.

Synthetic charts are clearly labelled. An unlinked well shows “Well-level production not available/verified.” No production source endpoint or licence is considered verified merely because the demo works.

## Reproducible synthetic evidence

```bash
python scripts/setup_db.py
python scripts/demo_production.py
```

The fixture `tests/fixtures/production_demo.csv` contains **9 inputs: 6 accepted, 2 quarantined, 1 outside the window**. Three accepted observations link uniquely to DEMO-WELL-001: two oil production months and a separately identified adjustment. The remaining accepted rows are one facility total, one unmatched ID and one unknown reporting level. DEMO-WELL-002 has no verified production. The 900-unit facility total is never displayed in either well chart.

The synthetic header names (`ROW_ID`, `MONTH`, etc.) are test-only. The synthetic source namespace/evidence does not certify actual AER/Petrinex identifier compatibility.

The Python suite tests month/decimal/unit/duplicate/adjustment validation, exact leading-zero IDs, ambiguous joins, idempotency, active-batch rollback, cross-run scope, synthetic/live separation, unavailable wells and persisted transport failure. `node tests/browser/production_smoke.cjs` verifies explicit demo import, a rendered monthly chart, switching to the adjustment series, unavailable other-well behavior and downloaded attribution audit. The original map/export browser smoke remains valid too.

## Official verification still required

Inspect authoritative access/licence/metadata, determine whether available reporting is facility-level, well-level or mixed, confirm actual record grain and units, verify identifier correspondence with the selected AER well product, and define the source mapping. Then test a bounded actual refresh and its unmatched/ambiguous outcomes. If public data does not support a defensible well-level join, keep well production explicitly unavailable and expose facility reporting separately. Phase 5 cannot be completed solely from the synthetic proof above.

The inspection helper can preview an acquired permitted file before defining the mapping:

```bash
python scripts/inspect_production.py --path tests/fixtures/production_demo.csv
```

For an actual verified candidate download, use `--url` with its official HTTPS URL. Once all metadata is verified, refresh with `python scripts/refresh_production.py --run-id <real-run-id> --start <YYYY-MM> --end <YYYY-MM>`. Placeholders are not actual endpoints or run identifiers. No official data/credentials belong in Git.
