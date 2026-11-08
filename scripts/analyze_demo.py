"""Analyze the offline fixture and write screening/threshold sensitivity evidence."""
import argparse
import json
from collections import Counter

from _bootstrap import run_cli
from sqlalchemy import create_engine

from src.config import ROOT, database_url
from src.contracts.spatial import CATEGORIES
from src.db.demo import _write_report, seed_demo
from src.spatial.classification import THRESHOLDS, compare_selections, summarize_wells
from src.spatial.engine import analyze_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--categories', nargs='*', choices=sorted(CATEGORIES), default=['water'])
    parser.add_argument('--threshold', type=int, choices=THRESHOLDS, default=500)
    args = parser.parse_args()
    engine = create_engine(database_url(), pool_pre_ping=True)
    try:
        seed = seed_demo(engine)
        rows = analyze_run(engine, seed['run_id'])
        selected = summarize_wells(rows, args.categories, args.threshold)
        baseline = summarize_wells(rows, args.categories, 500)
        changed = summarize_wells(rows, args.categories, 50)
        report = {
            'run_id':seed['run_id'], 'status':'analyzed', 'analysis_version':1,
            'analysis_crs':'EPSG:3400', 'search_radius_m':500,
            'source_checksum_sha256':seed['source']['checksum_sha256'],
            'categories':sorted(set(args.categories)), 'threshold_m':args.threshold,
            'disclaimer':'Synthetic educational proximity screening; not an environmental risk assessment.',
            'counts':{'wells':len(selected),'proximity_rows':len(rows),
                      'matched':sum(r['matches_threshold'] is True for r in selected),
                      'unknown':sum(r['matches_threshold'] is None for r in selected),
                      'result_states':dict(Counter(r['result_state'] for r in rows))},
            'wells':selected, 'category_results':rows,
            'sensitivity':{'baseline_threshold_m':500,'changed_threshold_m':50,
                           **compare_selections(baseline,changed)},
        }
        destination = ROOT / 'outputs/runs' / seed['run_id'] / 'analysis.json'
        _write_report(destination, report)
        print(json.dumps({'run_id':report['run_id'],'counts':report['counts'],
                          'sensitivity':report['sensitivity']}, indent=2))
        print(f'Analysis: {destination.relative_to(ROOT)}')
    finally:
        engine.dispose()


if __name__ == '__main__':
    run_cli(main)
