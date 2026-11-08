import csv
import hashlib
import io
import json

from src.config import ROOT
from src.exports.selection import csv_bytes, geojson_bytes, table_records
from src.ui.map import build_map
from src.ui.model import filtered_wells, map_selection


def dashboard():
    wells = [{'well_pk':i,'source_well_id':f'SYNTHETIC-{i}','licensee_name':f'Company {i}',
              'status':'synthetic' if i==1 else None,'latitude':53.5,'longitude':-114+i/1000}
             for i in (1,2)]
    rows = [{'well_pk':i,'source_well_id':f'SYNTHETIC-{i}','category':category,
             'coverage_status':'complete' if category=='water' else 'incomplete',
             'distance_m':50 if i==1 and category=='water' else 150 if category=='water' else None}
            for i in (1,2) for category in ('water','protected_area')]
    return {'run_id':'synthetic-run','wells':wells,'proximity':rows}


def test_filters_table_and_exports_use_identical_ids_and_values():
    data = dashboard()
    rows = filtered_wells(data,['water'],50,matches_only=True)
    assert [r['source_well_id'] for r in rows]==['SYNTHETIC-1']
    assert filtered_wells(data,['water'],50,companies=['Company 2'],matches_only=True)==[]
    company = filtered_wells(data,['water'],companies=['Company 2'])
    assert len(company)==1
    assert company[0]['band']=='within_250m'
    assert len(filtered_wells(data,['water'],statuses=['Not available from this source']))==1
    csv_rows = list(csv.DictReader(io.StringIO(csv_bytes(rows).decode('utf-8-sig'))))
    geo = json.loads(geojson_bytes(rows,{'threshold_m':50}))
    assert csv_rows[0]['source_well_id']==geo['features'][0]['properties']['source_well_id']==table_records(rows)[0]['source_well_id']
    assert float(csv_rows[0]['distance_m'])==geo['features'][0]['properties']['distance_m']==50
    assert geo['features'][0]['geometry']['coordinates']==[-113.999,53.5]


def test_empty_filters_and_incomplete_categories_retain_honest_outcomes():
    assert filtered_wells(dashboard(),[],500,matches_only=True)==[]
    results=filtered_wells(dashboard(),['water','protected_area'],50)
    assert results[0]['band']=='unknown' and results[0]['matches_threshold'] is True
    assert results[1]['matches_threshold'] is None
    assert json.loads(geojson_bytes([],{}))['features']==[]
    assert len(list(csv.reader(io.StringIO(csv_bytes([]).decode('utf-8-sig')))))==1


def test_map_selection_uses_allowed_stable_ids_and_counts_not_coordinates():
    event={'last_object_clicked_popup':'<section data-well-key="2">Well</section>','last_object_clicked_count':1,
           'last_object_clicked':{'lat':0,'lng':0}}
    selected,previous=map_selection(event,{1,2},None)
    assert selected==2
    assert map_selection({'last_object_clicked_popup':'SCREENING_WELL:2\nWell'}, {1,2},None)[0]==2
    assert map_selection(event,{1,2},previous)[0] is None
    assert map_selection({**event,'last_object_clicked_count':2},{1,2},previous)[0]==2
    assert map_selection(event,{1},None)[0] is None
    assert map_selection({'last_object_clicked':{'lat':53.5,'lng':-114}},{1},None)[0] is None


def test_offline_map_preserves_ids_and_escapes_popup_template_literals():
    rows=filtered_wells(dashboard(),['water'])
    rows[0]['licensee_name']='<script>danger</script> ${window.alert(1)}`'
    view=build_map(rows,[],['water'])
    markup=view.get_root().render()
    assert 'data-well-key="1"' in markup and 'data-well-key="2"' in markup
    assert '<script>danger</script>' not in markup and '${window.alert(1)}' not in markup
    assert 'data:text/javascript;base64,' in markup
    assert 'https://tile.openstreetmap' not in markup
    for entry in json.loads((ROOT/'vendor/manifest.json').read_text()):
        assert hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest()==entry['sha256']
