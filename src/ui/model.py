"""Pure selection functions shared by the map, table, detail panel and exports."""
import re

from src.spatial.classification import summarize_wells


def filtered_wells(dashboard: dict, categories: list[str], threshold: int = 500,
                   companies: list[str] | None = None, statuses: list[str] | None = None,
                   matches_only: bool = False) -> list[dict]:
    summaries = summarize_wells(dashboard['proximity'],categories,threshold)
    source = {r['well_pk']:r for r in dashboard['wells']}
    result = []
    for summary in summaries:
        record = {**source[summary['well_pk']],**summary,'run_id':dashboard['run_id']}
        if companies and (record['licensee_name'] or 'Not available from this source') not in companies:
            continue
        if statuses and (record['status'] or 'Not available from this source') not in statuses:
            continue
        if matches_only and record['matches_threshold'] is not True:
            continue
        result.append(record)
    return result


def map_selection(event: dict | None, allowed_keys: set[int], previous: tuple | None) -> tuple[int | None, tuple | None]:
    """Decode a stable marker ID, never coordinates; ignore stale/untrusted payloads."""
    event = event or {}
    popup = event.get('last_object_clicked_popup')
    if not isinstance(popup,str):
        return None,previous
    signature = (event.get('last_object_clicked_count'),popup)
    if signature == previous:
        return None,previous
    match = re.search(r'(?:Record reference: |SCREENING_WELL:|data-well-key=[\"\'])(\d+)',popup)
    selected = int(match.group(1)) if match else None
    return (selected if selected in allowed_keys else None),signature
