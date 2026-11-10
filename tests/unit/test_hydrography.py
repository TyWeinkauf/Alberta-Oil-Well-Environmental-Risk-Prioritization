import pytest
from pydantic import ValidationError

from src.config import ROOT, SourceCatalog, load_source_catalog, load_study_area
from src.sources.arcgis import acquire_arcgis
from src.sources.hydrography import water_requirements, water_sources
from src.sources.http import HttpCache
from tests.hydro_helpers import hydro_service


def test_verified_water_catalogue_uses_base_layers_and_explicit_feature_codes():
    catalog = load_source_catalog(ROOT / 'config/source_catalog.yml')
    assert not water_requirements(catalog)
    assert {source.layer_id for source in water_sources(catalog)} == {72,107}
    assert {source.layer_id for source in water_sources(catalog, True)} == {72,107,76,108}
    seasonal = next(source for source in catalog.sources if source.layer_id == 108)
    assert 'FLOW-ARB' not in seasonal.arcgis_where
    assert all(source.arcgis_preserve_properties and source.native_crs == 'EPSG:3400'
               for source in water_sources(catalog, True))
    assert all(source.license_url and source.metadata_url for source in water_sources(catalog, True))


def test_water_readiness_does_not_require_or_enable_missing_wells_or_other_categories():
    assert water_requirements(SourceCatalog(sources=[]))
    with hydro_service() as (catalog, _):
        assert not water_requirements(catalog)
        disabled = catalog.model_copy(deep=True)
        disabled.sources[0].enabled = False
        assert any('verified/enabled' in message for message in water_requirements(disabled))
        optional = catalog.model_copy(deep=True)
        optional.sources[-1].verified = False
        assert not water_requirements(optional)
        assert water_requirements(optional, True)
        with pytest.raises(ValidationError):
            catalog.sources[0].model_validate(catalog.sources[0].model_dump() | {'arcgis_batch_size': 0})


def test_arcgis_filters_all_requests_and_retains_full_publisher_properties(tmp_path):
    with hydro_service() as (catalog, state):
        source = catalog.sources[0]
        acquired = acquire_arcgis(source, load_study_area(ROOT/'config/study_area.live.yml'), HttpCache(tmp_path))
        assert acquired.records[0]['_source_properties']['SOURCE'] == 'Synthetic raw attribute'
        assert acquired.records[0]['feature_type_code'] == 'LAKE-PER'
        assert all(query['where'] == [source.arcgis_where] for query in state['queries'])
        pages = [query for query in state['queries'] if 'objectIds' in query]
        assert pages[0]['outFields'] == ['*']
        assert acquired.inspection['environmental_margin_m'] == 500
        with pytest.raises(ValueError, match='record limit'):
            acquire_arcgis(source, load_study_area(ROOT/'config/study_area.live.yml'), HttpCache(tmp_path), max_records=0)
