# Streamlit workflow

Run `python -m streamlit run app.py` from the repository root. Use **Dataset mode** to choose **Classroom demo** or **ST37 well inventory**.

## Classroom demo

The classroom demo opens the prepared local package with real ST37 wells and imported Alberta waterways. Choose a region, select a buffer distance and click a well to inspect its attributes. The map, table and exports follow the same filters. The imported-water view starts with matching wells within 500 m. OpenStreetMap tiles are optional. [Classroom setup and verification](classroom_demo.md)

## ST37 well inventory

The inventory uses the configured `DATABASE_URL`. Import the retained ST37 workbook from the sidebar or select an existing snapshot. For snapshots with stored water comparisons, select the imported water layer and a buffer distance, then browse matching wells in shuffled batches. Search by full licence to draw that well's buffer. Use **Workbook records** to review reported well attributes. [Inventory setup and coordinate accuracy](st37_excel.md#browse-the-workbook-in-streamlit)

## Database operations

Run the database workflows from the repository root with the project Python environment active.

| Operation | Command |
| --- | --- |
| Analyze the synthetic database fixture | `python scripts/analyze_demo.py` |
| Import regional waterways | `python scripts/import_hydrography.py` |
| Import provincial waterbodies | `python scripts/import_waterbodies.py` |
| Import provincial streams | `python scripts/import_waterbodies.py --layer streams` |
| Create or query a stored ST37 water comparison | `python scripts/compare_st37_waterbodies.py --help` |
| Run the verified multi-source pipeline | `python scripts/run_live.py` |

See the [hydrography instructions](hydrography.md#import-and-compare) for snapshot IDs and the [recovery checks](release_verification.md) for locks and retries.

## Browser check

With the imported-water classroom package and the local app running, run `node tests/browser/ui_smoke.cjs`. The test blocks remote HTTP requests and checks the retired URL, all four buffer choices, well selection, and a matching GeoJSON export. Set `APP_URL` and `CHROMIUM_PATH` when needed.
