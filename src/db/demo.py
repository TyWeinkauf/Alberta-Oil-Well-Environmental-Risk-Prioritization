"""Offline, auditable fixture ingestion; spatial analysis begins in Phase 2."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import Engine, text

from src.db.workflow import serialized_workflow

from src.artifacts import write_json as _write_report
from src.config import ROOT, StudyArea, config_hash, load_study_area
from src.contracts.spatial import CATEGORIES, validate_records
from src.spatial.engine import demo_coverage

FIXTURE = ROOT / 'tests/fixtures/demo.json'


def _counts(conn, snapshot_id, run_id):
    result = {}
    # Fixed table identifiers; values are always bound parameters.
    for table in ('wells', 'environmental_features', 'production_monthly'):
        result[table] = conn.execute(text(
            f'SELECT count(*) FROM screening.{table} WHERE snapshot_id=:snapshot'
        ), {'snapshot': snapshot_id}).scalar_one()
    for table in ('quarantine_records', 'well_proximity'):
        result[table] = conn.execute(text(
            f'SELECT count(*) FROM screening.{table} WHERE run_id=:run'
        ), {'run': run_id}).scalar_one()
    return result


@serialized_workflow
def seed_demo(engine: Engine, fixture_path: Path = FIXTURE, *, study_area: StudyArea | None = None,
              raw_root: Path | None = None, output_root: Path | None = None) -> dict:
    """Load a content-addressed demo once; retain every rejected row's raw reference.

    Migrations must be applied first. This function never resets the schema or
    invents production data. Fixture, config and contract version define the run
    identity, making unchanged reruns idempotent and new versions independent.
    """
    study_area = study_area or load_study_area()
    if study_area.mode != 'demo':
        raise ValueError('Demo ingestion requires study-area mode: demo')
    raw = fixture_path.read_bytes()
    fixture = json.loads(raw)
    if fixture.get('fixture_version') != 1 or not fixture.get('license_note'):
        raise ValueError('Fixture version 1 and provenance/license note are required')
    batches = {entity: validate_records(fixture.get(entity), entity, fixture.get('crs'), study_area)
               for entity in ('wells', 'features')}
    checksum = hashlib.sha256(raw).hexdigest()
    settings_hash = config_hash(study_area)
    run_id = uuid5(NAMESPACE_URL, f'alberta-screening-demo-contract-v1:{checksum}:{settings_hash}')
    snapshot_id = uuid5(run_id, 'synthetic-demo')
    archive = (raw_root or ROOT / 'data/raw') / checksum / 'demo.json'
    archive.parent.mkdir(parents=True, exist_ok=True)
    try:
        with archive.open('xb') as handle:
            handle.write(raw)
    except FileExistsError:
        if archive.read_bytes() != raw:
            raise ValueError('Raw snapshot checksum mismatch; refusing to overwrite the archive') from None
    try:
        archive_reference = str(archive.relative_to(ROOT))
    except ValueError:
        archive_reference = str(archive)
    try:
        fixture_reference = str(fixture_path.resolve().relative_to(ROOT))
    except ValueError:
        fixture_reference = str(fixture_path.resolve())
    source_url = 'fixture:' + fixture_reference
    rejected = [row for batch in batches.values() for row in batch.rejected]
    incomplete_categories = set()
    for row in batches['features'].rejected:
        record = fixture['features'][int(row['record_reference'].split('/')[1])]
        category = record.get('category') if isinstance(record,dict) else None
        # Unknown rejected categories could conceal a feature in either supplied layer.
        incomplete_categories.update([category] if isinstance(category,str) and category in CATEGORIES
                                     else ['water','protected_area'])
    expected = {'wells': len(batches['wells'].accepted),
                'environmental_features': len(batches['features'].accepted),
                'quarantine_records': len(rejected), 'production_monthly': 0, 'well_proximity': 0}
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('alberta-screening-demo-seed'))"))
        status = conn.execute(text('SELECT status FROM screening.pipeline_runs WHERE run_id=:run FOR UPDATE'),
                              {'run': run_id}).scalar_one_or_none()
        if status is None:
            conn.execute(text('''INSERT INTO screening.pipeline_runs (run_id,status,study_area,config_hash)
                VALUES (:run,'loading',CAST(:area AS jsonb),:hash)'''),
                         {'run': run_id, 'area': study_area.model_dump_json(), 'hash': settings_hash})
            conn.execute(text('''INSERT INTO screening.source_snapshots
                (snapshot_id,run_id,source_key,url,checksum,license_note,native_crs,record_count)
                VALUES (:snapshot,:run,'synthetic-demo',:url,:sha,:note,:crs,:count)'''),
                         {'snapshot': snapshot_id, 'run': run_id, 'sha': checksum,
                          'note': fixture['license_note'], 'crs': fixture['crs'], 'url': source_url,
                          'count': sum(len(fixture[e]) for e in batches)})
            for row in batches['wells'].accepted:
                conn.execute(text('''INSERT INTO screening.wells
                    (snapshot_id,source_well_id,licensee_name,licensee_search,uwi_if_available,
                     operator_name_if_verified,lsd_text,status,geom)
                    VALUES (:snapshot,:source_well_id,:licensee_name,:licensee_search,:uwi_if_available,
                     :operator_name_if_verified,:lsd_text,:status,ST_GeomFromText(:geometry_wkt,3400))'''),
                             {'snapshot': snapshot_id, **row})
            for row in batches['features'].accepted:
                conn.execute(text('''INSERT INTO screening.environmental_features
                    (snapshot_id,source_key,source_feature_id,feature_type,name,geom)
                    VALUES (:snapshot,'synthetic-demo',:source_feature_id,:feature_type,:name,
                     ST_GeomFromText(:geometry_wkt,3400))'''), {'snapshot': snapshot_id, **row})
            for row in rejected:
                conn.execute(text('''INSERT INTO screening.quarantine_records
                    (run_id,source_key,record_reference,reason_code,reason_detail,raw_payload_reference)
                    VALUES (:run,'synthetic-demo',:record_reference,:reason_code,:reason_detail,:raw_ref)'''),
                             {'run': run_id, 'raw_ref': archive_reference + '#' + row['record_reference'], **row})
            conn.execute(text("UPDATE screening.pipeline_runs SET status='seeded', finished_at=now() WHERE run_id=:run"),
                         {'run': run_id})
        elif status != 'seeded':
            raise ValueError('Existing demo run has an incompatible status; do not overwrite it')
        counts = _counts(conn, snapshot_id, run_id)
        # Derived spatial rows may now exist; ingestion must preserve them.
        if any(counts[key] != value for key, value in expected.items() if key != 'well_proximity'):
            raise ValueError('Stored demo counts differ from validated fixture; refusing to report success')
        coverage_changed = False
        for category, coverage in demo_coverage(incomplete_categories).items():
            changed = conn.execute(text('''INSERT INTO screening.category_coverage VALUES (:run,:category,:status,:note)
                ON CONFLICT (run_id,category) DO UPDATE SET status=excluded.status,note=excluded.note
                WHERE screening.category_coverage.status='complete' AND excluded.status='incomplete'
                RETURNING run_id'''), {'run':run_id,'category':category,**coverage.model_dump()}).first()
            coverage_changed = coverage_changed or changed is not None
        if coverage_changed:
            # An older complete-coverage result must not survive a downgrade.
            conn.execute(text('DELETE FROM screening.well_proximity WHERE run_id=:run'), {'run':run_id})
            counts = _counts(conn,snapshot_id,run_id)
        retrieved_at = conn.execute(text(
            'SELECT retrieved_at FROM screening.source_snapshots WHERE snapshot_id=:snapshot'
        ), {'snapshot': snapshot_id}).scalar_one().isoformat()
    # A report failure is recoverable: rerunning verifies DB counts and rewrites reports.
    report = {
        'run_id': str(run_id), 'status': 'seeded', 'contract_version': 1,
        'disclaimer': 'Synthetic educational fixture ingestion only; spatial results are reported separately; no production attribution.',
        'config_hash': settings_hash, 'study_area': study_area.model_dump(mode='json'),
        'source': {'key': 'synthetic-demo', 'snapshot_id': str(snapshot_id), 'url': source_url,
                   'checksum_sha256': checksum, 'raw_payload_reference': archive_reference,
                   'retrieved_at': retrieved_at, 'native_crs': fixture['crs'],
                   'license_note': fixture['license_note']},
        'counts': counts,
        'validation': {'input_records': sum(len(fixture[e]) for e in batches),
                       'accepted_records': sum(len(b.accepted) for b in batches.values()),
                       'rejected_records': len(rejected),
                       'reason_counts': dict(Counter(row['reason_code'] for row in rejected)),
                       'quarantined': rejected},
    }
    destination = (output_root or ROOT / 'outputs/runs') / str(run_id)
    _write_report(destination / 'validation.json', report['validation'])
    _write_report(destination / 'manifest.json', report)
    return report
