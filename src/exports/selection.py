"""In-memory portable exports of a selection; GeoJSON coordinates are WGS84."""
import csv
import io
import json

FIELDS = ('run_id','source_well_id','licensee_name','operator_name_if_verified','uwi_if_available',
          'lsd_text','status','latitude','longitude','band','distance_m','observed_min_distance_m',
          'coverage_complete','threshold_m','matches_threshold','within_50','within_100','within_250','within_500',
          'selected_categories')


def table_records(records: list[dict], fields: tuple[str, ...] = FIELDS) -> list[dict]:
    return [{field:(';'.join(row[field]) if field=='selected_categories' else row.get(field))
             for field in fields} for row in records]


def csv_bytes(records: list[dict], fields: tuple[str, ...] = FIELDS) -> bytes:
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output,fieldnames=fields)
    writer.writeheader()
    writer.writerows(table_records(records, fields))
    return output.getvalue().encode('utf-8-sig')


def geojson_bytes(records: list[dict], selection: dict, fields: tuple[str, ...] = FIELDS) -> bytes:
    rows = table_records(records, fields)
    payload = {'type':'FeatureCollection','selection':selection,'features':[
        {'type':'Feature','id':str(original['well_pk']),
         'geometry':{'type':'Point','coordinates':[row['longitude'],row['latitude']]},'properties':row}
        for original,row in zip(records,rows)]}
    return json.dumps(payload,indent=2,allow_nan=False).encode()
