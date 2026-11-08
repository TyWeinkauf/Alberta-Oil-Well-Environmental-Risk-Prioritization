from decimal import Decimal

import pytest

from src.config import Source
from src.production.contracts import month, resolve_link, validate_production


def spec(**change):
    return Source(key='synthetic',kind='file',role='production',well_identifier_field='source_well_id',
                  identifier_namespace='synthetic-source-id',join_evidence='Documented synthetic exact identifiers',**change)


def row(**change):
    return {'source_record_id':'SYNTHETIC-RECORD','period':'2026-09','product':'OIL','activity':'PRODUCTION',
            'volume':'12.50','unit':'m3','attribution_level':'well','well_identifier_nullable':'0001',**change}


@pytest.mark.parametrize('value',['2026-13','2026-00','2026-9','202609',None])
def test_invalid_months_are_rejected(value):
    with pytest.raises(ValueError):month(value)


@pytest.mark.parametrize('change,reason',[
    ({'source_record_id':''},'missing_id'),({'period':'2026-13'},'invalid_period'),
    ({'unit':''},'missing_fields'),({'volume':'NaN'},'invalid_volume'),
    ({'volume':'Infinity'},'invalid_volume'),({'volume':'1e1000'},'invalid_volume'),
    ({'volume':'-2'},'undocumented_adjustment'),({'attribution_level':'made-up'},'invalid_attribution'),
])
def test_invalid_production_is_explicitly_quarantined(change,reason):
    result=validate_production([row(**change)],spec(),'2026-08','2026-10')
    assert not result.accepted and result.rejected[0]['reason_code']==reason


def test_documented_adjustments_decimal_precision_and_window_accounting():
    source=spec(adjustment_activities=['ADJ'],adjustment_note='Synthetic documented signed corrections')
    result=validate_production([row(activity='ADJ',volume='-0.125'),row(source_record_id='OUTSIDE',period='2026-07')],source,'2026-08','2026-10')
    assert result.accepted[0]['volume']==Decimal('-0.125')
    assert result.excluded_records==1 and result.input_records==2
    duplicate=validate_production([row(),row()],source,'2026-08','2026-10')
    assert len(duplicate.rejected)==2 and all(r['reason_code']=='duplicate_id' for r in duplicate.rejected)


def test_exact_leading_zero_identifier_and_reporting_levels_control_links():
    source=spec();candidates={'0001':[1],'1':[2],'DUP':[3,4]}
    assert resolve_link(row(),candidates,source)==('verified','exact_verified_identifier',[1])
    assert resolve_link(row(attribution_level='facility'),candidates,source)[0]=='facility'
    assert resolve_link(row(attribution_level='unknown'),candidates,source)[0]=='unknown'
    assert resolve_link(row(well_identifier_nullable='DUP'),candidates,source)[0]=='ambiguous'
    assert resolve_link(row(well_identifier_nullable='missing'),candidates,source)[0]=='unmatched'
    assert resolve_link(row(),candidates,Source(key='unverified-scheme',kind='file',role='production'))[1]=='identifier_scheme_unverified'
