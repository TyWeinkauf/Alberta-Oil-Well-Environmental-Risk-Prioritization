# Spatial proximity methodology — Phase 2

The completed project will screen **real** AER well and government environmental data from the [supplied source reference](dataset_reference.md). Phase 2 verifies the reusable calculation against synthetic geometry with known distances. Live source adapters and coverage verification are Phase 4 work.

## Calculation

`src/spatial/engine.py` operates on EPSG:3400 geometry in metres. It requires the run's configured analysis CRS and standard 50/100/250/500 m thresholds to agree with that method. It never measures in Web Mercator or treats map tiles as analytical data.

For every well in the selected run and each of the five environmental categories:

1. Read the explicit run/category coverage status and its explanation.
2. For complete coverage, preselect actual feature geometries with `ST_DWithin(well, feature, 500)`, using the existing GiST geometry indexes.
3. Compute `ST_Distance` to those geometries and choose the nearest. Equal-distance ties sort by source feature ID, source key, snapshot ID and database key, giving stable selection for unchanged inputs.
4. Store a row even if there is no candidate or coverage is unknown. Features and wells are both restricted through their source snapshots to the same run; another run's geometry cannot become a match.

Distance to a line is to the line, not its centroid. Distance to a polygon is zero for a point on or inside it. Distances beyond the 500 m search radius are not calculated/stored: a null distance with complete coverage means **no feature within 500 m**, not an exact farther distance.

The calculation transaction locks the parent run, replaces only that run's derived rows and verifies `well count × 5 categories` row accounting. On failure, its deletes/inserts and coverage overrides roll back together, retaining the previous analysis. Repeating it does not duplicate rows. The separate ingestion status remains `seeded`; analysis is reported as `analyzed` in `analysis.json`, without claiming full application publication.

## Coverage and missing-data semantics

`screening.category_coverage` records a status and explanation for each run/category. The analysis copies that status into each proximity row.

| Coverage / result | Distance | Threshold flags | Meaning |
|---|---|---|---|
| Complete, candidate within 500 m | Measured distance | Cumulative true/false | Known nearest candidate in the verified search area |
| Complete, no candidate within 500 m | null | All false | Known negative within the search radius |
| Incomplete | null | All null | Some coverage is missing or rejected; a negative cannot be established |
| Unavailable | null | All null | Source coverage is not supplied/verified |

Coverage completeness must include the study area **and 500 m environmental search margin**, input quality and source availability; it must not be inferred from the mere presence of some features. With incomplete coverage the current engine conservatively withholds even partial distances. A later adapter may expose partial observations separately, but must not relabel them complete.

The main demo's water layer is a declared closed synthetic world. Its protected-area layer is **incomplete** because the fixture deliberately contains a quarantined invalid polygon. Other categories are unavailable. The analysis CLI therefore selects **water only** by default. The separate boundary fixture contains valid water/protected geometries and exercises exact combined-category results. These declarations do not establish coverage for real Alberta data.

If reseeding detects that formerly complete synthetic coverage must be downgraded because of quarantined inputs, it clears stale derived results for that run. Otherwise reseeding preserves existing analysis rows. Live-source coverage remains unverified until acquisition/quality checks are implemented.

## Bands, selection and sensitivity

Display bands are mutually exclusive: `within_50m`, `within_100m`, `within_250m`, `within_500m`, `none_within_500m`. Their colors are red, orange, yellow, blue and gray. Exact boundaries are inclusive. The `within_50/100/250/500` flags are cumulative.

`summarize_wells` recomputes the minimum from the currently selected categories, retaining wells with no nearby feature. Changing the selected threshold changes `matches_threshold`; the distance band remains a property of the measured distance. An empty category selection returns `no_categories_selected`, with unknown flags, for all wells.

When any selected category has unknown coverage, the exact overall band is `unknown`. A positive from another complete category remains a known `True` threshold match; otherwise the threshold outcome is null rather than false. `observed_min_distance_m` reports only the minimum across complete categories in that case. This policy preserves evidence without claiming an exact overall minimum from missing data.

`scripts/analyze_demo.py` writes `outputs/runs/<run_id>/analysis.json` with per-category results, current selection, well-level bands/flags, source checksum, result-state counts and a 500 m versus 50 m comparison. `compare_selections` also supports category sensitivity and reports changed well IDs and matched/unknown counts for the same well population.

## Verified examples

The main demo's water distances are **50 m for DEMO-WELL-001** and **150 m for DEMO-WELL-002**. Changing the water threshold from 500 m to 50 m changes matches from **2 to 1**, affecting DEMO-WELL-002. Adding the incomplete protected-area category makes the exact overall bands unknown; it does not justify a negative threshold result.

`tests/fixtures/spatial_boundaries.json` independently defines wells at 0, 50, 100, 250, 500 and 500.01 m from a synthetic line. Tests check inclusive flags, just-over-500 exclusion, a point inside a polygon (distance 0), an off-centroid point on a long line, deterministic ties, category/threshold sensitivity, run isolation, incomplete/unavailable coverage, repeated analysis, seed/analysis compatibility and rollback after a forced database error.

These are proximity-screening checks, not a professional environmental assessment or a claim that real-source ingestion has been validated.
