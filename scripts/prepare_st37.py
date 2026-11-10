"""Profile ST37 surface-hole Excel and prepare inventory/pilot CSVs; no database writes."""
import argparse
import json
from datetime import date
from pathlib import Path

from _bootstrap import run_cli
from src.config import ROOT, load_study_area
from src.sources.st37 import prepare_st37


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', type=Path, required=True)
    parser.add_argument('--study-area', type=Path, default=ROOT / 'config/study_area.live.yml')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'data/raw/st37')
    parser.add_argument('--max-rows', type=int, default=1000000)
    parser.add_argument('--max-pilot-records', type=int, default=10000)
    parser.add_argument('--as-of', type=date.fromisoformat, help='Date for quality flags, YYYY-MM-DD (default: today)')
    args = parser.parse_args()
    report = prepare_st37(args.path, load_study_area(args.study_area), args.output_root,
                          max_rows=args.max_rows, max_pilot_records=args.max_pilot_records,
                          as_of=args.as_of,
                          progress=lambda message: print(message, flush=True))
    print(json.dumps({key: report[key] for key in (
        'identity', 'source_rows', 'accepted_rows', 'quarantined_rows', 'pilot_rows',
        'duplicate_licence_count', 'quarantine_reason_counts', 'warning_rows', 'warning_reason_counts', 'artifacts')}, indent=2))


if __name__ == '__main__':
    run_cli(main, error_hint='Check the surface-hole workbook and docs/st37_excel.md. Original data is never changed.')
