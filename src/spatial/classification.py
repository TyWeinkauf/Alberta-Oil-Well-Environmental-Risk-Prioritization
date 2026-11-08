"""Shared threshold/category logic for CLI results and the future map UI."""
import math
from collections import defaultdict

from src.contracts.spatial import CATEGORIES

THRESHOLDS = (50, 100, 250, 500)
BAND_COLORS = {50:'red', 100:'orange', 250:'yellow', 500:'blue', 'none':'gray', 'unknown':'gray'}


def classify_distance(distance_m: float | None) -> dict:
    """Classify a known distance; None here means complete coverage/no match <=500 m.

    Unknown source coverage must be handled by summarize_wells, not mapped to
    this function's known-negative None case.
    """
    if distance_m is not None and (isinstance(distance_m, bool) or not math.isfinite(distance_m) or distance_m < 0):
        raise ValueError('Distance must be finite and nonnegative')
    band = next((t for t in THRESHOLDS if distance_m is not None and distance_m <= t), 'none')
    return {'band': 'none_within_500m' if band == 'none' else f'within_{band}m',
            'color': BAND_COLORS[band],
            **{f'within_{t}': distance_m is not None and distance_m <= t for t in THRESHOLDS}}


def summarize_wells(rows: list[dict], categories: list[str], threshold_m: int = 500) -> list[dict]:
    """Recompute overall bands from selected categories, retaining all well IDs.

    Incomplete coverage never becomes a known negative. An observed positive
    remains True even with another unknown category; the exact overall band is
    unknown because a missing category could contain a closer feature.
    """
    if threshold_m not in THRESHOLDS:
        raise ValueError('Threshold must be one of 50, 100, 250, 500 metres')
    if any(category not in CATEGORIES for category in categories):
        raise ValueError('Unknown environmental category')
    categories = sorted(set(categories))
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['well_pk']].append(row)
    output = []
    for well_rows in grouped.values():
        first = well_rows[0]
        selected = {r['category']: r for r in well_rows if r['category'] in categories}
        complete = bool(categories) and all(
            category in selected and selected[category]['coverage_status'] == 'complete' for category in categories)
        distances = [r['distance_m'] for r in selected.values()
                     if r['coverage_status'] == 'complete' and r['distance_m'] is not None]
        observed = min(distances) if distances else None
        classification = classify_distance(observed)
        if not complete:
            classification.update({'band':'unknown' if categories else 'no_categories_selected', 'color':'gray'})
            for threshold in THRESHOLDS:
                classification[f'within_{threshold}'] = True if observed is not None and observed <= threshold else None
        output.append({
            'well_pk':first['well_pk'], 'source_well_id':first['source_well_id'],
            'selected_categories':categories, 'coverage_complete':complete,
            'distance_m':observed if complete else None, 'observed_min_distance_m':observed,
            'threshold_m':threshold_m, 'matches_threshold':classification[f'within_{threshold_m}'],
            **classification,
        })
    return sorted(output, key=lambda r: (r['source_well_id'], r['well_pk']))


def compare_selections(baseline: list[dict], changed: list[dict]) -> dict:
    """Report stable well identities affected by a changed category/threshold selection."""
    before = {row['well_pk']: row for row in baseline}
    after = {row['well_pk']: row for row in changed}
    if before.keys() != after.keys():
        raise ValueError('Sensitivity comparison requires the same well population')
    changed_ids = [before[key]['source_well_id'] for key in before if
                   any(before[key][field] != after[key][field] for field in ('band','matches_threshold','distance_m'))]
    return {'changed_well_ids':sorted(changed_ids), 'changed_count':len(changed_ids),
            'baseline_matched':sum(r['matches_threshold'] is True for r in baseline),
            'changed_matched':sum(r['matches_threshold'] is True for r in changed),
            'baseline_unknown':sum(r['matches_threshold'] is None for r in baseline),
            'changed_unknown':sum(r['matches_threshold'] is None for r in changed)}
