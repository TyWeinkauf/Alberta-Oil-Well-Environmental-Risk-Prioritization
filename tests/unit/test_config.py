import pytest
from pydantic import ValidationError

from src.config import Source, StudyArea, config_hash, load_source_catalog, load_study_area


def test_default_sources_are_disabled_and_config_is_stable():
    assert all(not source.enabled and not source.verified for source in load_source_catalog().sources)
    assert all(source.role!='production' for source in load_source_catalog().sources)
    area = load_study_area()
    assert area.thresholds_m == [50, 100, 250, 500]
    assert config_hash(area) == config_hash(StudyArea.model_validate(area.model_dump()))


def test_unverified_enabled_source_fails_closed():
    with pytest.raises(ValidationError, match='verified URL'):
        Source(key='unverified', kind='arcgis', enabled=True)


def test_discovered_endpoint_cannot_enable_an_uninspected_source():
    source = next(s for s in load_source_catalog().sources if s.key == 'alberta_protected_areas')
    assert source.url and source.metadata_url and source.license_url
    assert not source.field_mapping and source.native_crs is None and source.layer_id is None
    with pytest.raises(ValidationError, match='verified URL'):
        Source.model_validate(source.model_dump() | {'enabled': True, 'verified': True})


def test_reference_records_real_data_intent_without_claiming_verified_acquisition():
    sources = {s.key:s for s in load_source_catalog().sources}
    assert sources['aer_wells'].reference_crs is None
    assert sources['alberta_water'].reference_crs == 'EPSG:3400'
    assert sources['federal_critical_habitat'].reference_crs == 'EPSG:3978'
    assert sources['openstreetmap'].role == 'basemap'
    assert sources['alberta_wetlands'].priority == sources['alberta_esa_2014'].priority == 'optional'
    assert all(s.reference_document for key,s in sources.items() if key != 'petrinex_production')
    assert all(not s.verified and not s.enabled for s in sources.values())


@pytest.mark.parametrize('change', [
    {'bbox_wgs84': [-110, 49, -120, 60]},
    {'thresholds_m': [100, 50]}, {'thresholds_m': [50, 50]},
    {'thresholds_m': [float('nan')]}, {'thresholds_m': [0]},
    {'analysis_crs': 'EPSG:4326'},
])
def test_invalid_analysis_configuration_is_rejected(change):
    with pytest.raises(ValidationError):
        StudyArea.model_validate(load_study_area().model_dump() | change)
