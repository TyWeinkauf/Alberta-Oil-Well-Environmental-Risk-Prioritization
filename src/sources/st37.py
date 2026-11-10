"""Read the publisher's surface-hole Excel without changing it or guessing its CRS.

The province-wide inventory is staging evidence. Only a bounded CSV is prepared
for the existing screening pipeline; absent environmental layers stay absent.
"""
import csv
import hashlib
import json
import math
import shutil
import tempfile
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from openpyxl import load_workbook

from src.artifacts import write_json

SHEET = 'ST37_Surface_Holes'
FIELDS = (
    'Well_Licence_Number', 'Licensee', 'Licence_Status', 'Licence_Status_Date',
    'Ground_Elevation', 'Spud_Date', 'Most_Recent_Final_Drill_Date',
    'Energy_Devlpmt_Category_Type', 'SH_Actual_Latitude', 'SH_Actual_Longitude',
    'Licence_Surface_Location_Label',
)
CSV_FIELDS = ('source_row', *FIELDS, 'validation_errors', 'quality_warnings')
FIELD_MAPPING = {
    'source_well_id': 'Well_Licence_Number', 'licensee_name': 'Licensee',
    'status': 'Licence_Status', 'lsd_text': 'Licence_Surface_Location_Label',
}
DATE_FIELDS = ('Licence_Status_Date', 'Spud_Date', 'Most_Recent_Final_Drill_Date')
VERSION = 2


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def text_value(value):
    if value is None:
        return ''
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def parse_date(value):
    """Source dates are either MM/DD/YYYY or YYYYMMDD; blanks remain null."""
    if not value:
        return None
    for fmt in ('%m/%d/%Y', '%Y%m%d', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError('Unrecognized ST37 date')


def finite_number(value):
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) else None


def row_errors(raw):
    errors = []
    if not raw['Well_Licence_Number'].strip():
        errors.append('missing_licence')
    lon, lat = (finite_number(raw[field]) for field in ('SH_Actual_Longitude', 'SH_Actual_Latitude'))
    if lon is None or lat is None:
        errors.append('invalid_coordinates')
    elif not (-120.1 <= lon <= -109.9 and 48.9 <= lat <= 60.1):
        # Broad Alberta envelope is a plausibility check, not a legal boundary.
        errors.append('outside_alberta_envelope')
    for field in DATE_FIELDS:
        try:
            parse_date(raw[field])
        except ValueError:
            errors.append(f'invalid_date:{field}')
    if raw['Ground_Elevation'] and finite_number(raw['Ground_Elevation']) is None:
        errors.append('invalid_ground_elevation')
    return errors


def surface_rows(path):
    """Stream cells, retaining text identifiers and failing on schema drift."""
    book = load_workbook(path, read_only=True, data_only=False, keep_links=False)
    try:
        if book.sheetnames != [SHEET]:
            raise ValueError(f'Expected only the {SHEET} worksheet; found {book.sheetnames}')
        rows = book[SHEET].iter_rows()
        header = tuple(cell.value for cell in next(rows))
        if len(header) != len(set(header)) or set(header) != set(FIELDS):
            raise ValueError('ST37 surface-hole headers differ from the inspected 11-field schema')
        for source_row, cells in enumerate(rows, 2):
            if all(cell.value is None for cell in cells):
                raise ValueError(f'Unexpected blank ST37 row at {source_row}; input was not truncated')
            if len(cells) != len(header):
                raise ValueError(f'Unexpected ST37 row width at {source_row}')
            values = dict(zip(header, cells))
            raw = {field: text_value(values[field].value) for field in FIELDS}
            errors = row_errors(raw)
            if values['Well_Licence_Number'].value is not None and not isinstance(values['Well_Licence_Number'].value, str):
                errors.append('nontext_licence')  # Never guess lost leading zeros.
            if any(cell.data_type in ('f', 'e') for cell in cells):
                errors.append('formula_or_excel_error')
            yield source_row, raw, errors
    finally:
        book.close()


def verify_prepared(report):
    """Do not reuse or load changed/corrupt output bytes."""
    for entry in report['artifacts'].values():
        path = Path(entry['path'])
        if not path.is_file() or checksum(path) != entry['sha256']:
            raise ValueError('Prepared ST37 artifact is missing or corrupt; rebuild from the original')


def prepare_st37(path, area, output_root, *, max_rows=1000000, max_pilot_records=10000,
                 as_of=None, progress=lambda message: None):
    path, output_root = Path(path).resolve(), Path(output_root).resolve()
    if not path.is_file() or path.suffix.lower() != '.xlsx':
        raise ValueError('Supply a local .xlsx surface-hole workbook')
    if not 1 <= max_rows <= 1048575 or not 1 <= max_pilot_records <= 100000:
        raise ValueError('Invalid source-row or pilot-record limit')
    original_hash = checksum(path)
    as_of = as_of or date.today()
    scope = area.model_dump(mode='json')
    identity_data = {'version': VERSION, 'sha256': original_hash, 'study_area': scope,
                     'max_rows': max_rows, 'max_pilot_records': max_pilot_records,
                     'as_of': as_of.isoformat()}
    identity = hashlib.sha256(json.dumps(identity_data, sort_keys=True).encode()).hexdigest()
    destination = output_root / identity
    if destination.exists():
        report = json.loads((destination / 'report.json').read_text(encoding='utf-8'))
        if report['identity'] != identity or report['source']['sha256'] != original_hash:
            raise ValueError('Prepared ST37 report identity is inconsistent')
        verify_prepared(report)
        return report
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.st37-', dir=output_root))
    try:
        ids, statuses, licensees, missing = Counter(), Counter(), Counter(), Counter()
        dates = {field: [] for field in DATE_FIELDS}
        extent = [math.inf, math.inf, -math.inf, -math.inf]
        count = 0
        warning_rows, warning_reasons, warning_examples = 0, Counter(), []
        progress('Reading the original Excel and checking all source rows')
        with (temporary / 'spool.csv').open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for source_row, raw, errors in surface_rows(path):
                count += 1
                if count > max_rows:
                    raise ValueError('ST37 source exceeds the row limit; input was not truncated')
                identifier = raw['Well_Licence_Number'].strip()
                ids[identifier] += 1
                statuses[raw['Licence_Status'] or '(missing)'] += 1
                licensees[raw['Licensee'] or '(missing)'] += 1
                missing.update(field for field, value in raw.items() if not value)
                warnings = []
                for field in DATE_FIELDS:
                    try:
                        value = parse_date(raw[field])
                        if value:
                            bounds = dates[field]
                            dates[field] = [min(bounds[0], value), max(bounds[1], value)] if bounds else [value, value]
                            if value > as_of:
                                warnings.append(f'future_date:{field}')
                            if value == date(1900, 1, 1):
                                warnings.append(f'possible_placeholder_date:{field}')
                    except ValueError:
                        pass
                lon, lat = finite_number(raw['SH_Actual_Longitude']), finite_number(raw['SH_Actual_Latitude'])
                if lon is not None and lat is not None:
                    extent = [min(extent[0], lon), min(extent[1], lat), max(extent[2], lon), max(extent[3], lat)]
                if warnings:
                    warning_rows += 1
                    warning_reasons.update(warnings)
                    if len(warning_examples) < 10:
                        warning_examples.append({'source_row': source_row,
                            'well_licence_number': identifier, 'warnings': warnings,
                            'source_dates': {field: raw[field] for field in DATE_FIELDS}})
                writer.writerow({'source_row': source_row, **raw, 'validation_errors': json.dumps(errors),
                                 'quality_warnings': json.dumps(warnings)})
                if count % 100000 == 0:
                    progress(f'Checked {count:,} rows')
        if not count:
            raise ValueError('ST37 worksheet contains no source records')
        duplicates = {identifier for identifier, n in ids.items() if identifier and n > 1}
        accepted, rejected, pilot_count = 0, 0, 0
        reasons = Counter()
        west, south, east, north = area.bbox_wgs84
        with (temporary / 'spool.csv').open(encoding='utf-8', newline='') as source, \
             (temporary / 'inventory.csv').open('w', encoding='utf-8', newline='') as inventory, \
             (temporary / 'pilot.csv').open('w', encoding='utf-8', newline='') as pilot, \
             (temporary / 'quarantine.csv').open('w', encoding='utf-8', newline='') as quarantine, \
             (temporary / 'warnings.csv').open('w', encoding='utf-8', newline='') as warnings_file:
            inventory_writer = csv.DictWriter(inventory, fieldnames=CSV_FIELDS)
            pilot_writer = csv.DictWriter(pilot, fieldnames=FIELDS)
            rejected_writer = csv.DictWriter(quarantine, fieldnames=CSV_FIELDS)
            warnings_writer = csv.DictWriter(warnings_file, fieldnames=CSV_FIELDS)
            for writer in (inventory_writer, pilot_writer, rejected_writer, warnings_writer):
                writer.writeheader()
            for row in csv.DictReader(source):
                errors = json.loads(row['validation_errors'])
                if row['Well_Licence_Number'].strip() in duplicates:
                    errors.append('duplicate_licence')
                row['validation_errors'] = json.dumps(errors)
                inventory_writer.writerow(row)
                if json.loads(row['quality_warnings']):
                    warnings_writer.writerow(row)
                if errors:
                    rejected += 1
                    reasons.update(errors)
                    rejected_writer.writerow(row)
                else:
                    accepted += 1
                    lon, lat = float(row['SH_Actual_Longitude']), float(row['SH_Actual_Latitude'])
                    if west <= lon <= east and south <= lat <= north:
                        pilot_count += 1
                        if pilot_count > max_pilot_records:
                            raise ValueError('ST37 pilot exceeds record limit; choose a smaller study area')
                        pilot_writer.writerow({field: row[field] for field in FIELDS})
        (temporary / 'spool.csv').unlink()
        if checksum(path) != original_hash:
            raise ValueError('Original ST37 workbook changed during preparation')
        artifacts = {name: {'path': str(destination / f'{name}.csv'),
                            'sha256': checksum(temporary / f'{name}.csv'),
                            'bytes': (temporary / f'{name}.csv').stat().st_size}
                     for name in ('inventory', 'pilot', 'quarantine', 'warnings')}
        report = {
            'version': VERSION, 'identity': identity, 'prepared_at': datetime.now(timezone.utc).isoformat(),
            'source': {'path': str(path), 'bytes': path.stat().st_size, 'sha256': original_hash,
                       'worksheet': SHEET, 'fields': list(FIELDS), 'publisher': 'Alberta Energy Regulator',
                       'metadata_url': 'https://www.aer.ca/providing-information/data-and-reports/statistical-reports/st37',
                       'downloaded_at': None, 'release_date': None},
            'study_area': scope, 'source_rows': count, 'accepted_rows': accepted, 'quarantined_rows': rejected,
            'pilot_rows': pilot_count, 'distinct_nonblank_licences': len(ids) - int('' in ids),
            'duplicate_licence_count': len(duplicates), 'duplicate_licence_examples': sorted(duplicates)[:10],
            'licence_status_counts': dict(statuses), 'distinct_licensees': len(licensees),
            'top_10_licensees': [list(item) for item in licensees.most_common(10)], 'missing_values': dict(missing),
            'date_ranges': {field: [value.isoformat() for value in bounds] for field, bounds in dates.items()},
            'coordinate_extent': extent if all(math.isfinite(x) for x in extent) else None,
            'quarantine_reason_counts': dict(reasons), 'field_mapping': FIELD_MAPPING,
            'quality_as_of': as_of.isoformat(), 'warning_rows': warning_rows,
            'warning_reason_counts': dict(warning_reasons), 'warning_examples': warning_examples,
            'coordinate_crs': None,
            'limitations': [
                'Excel has no embedded coordinate CRS. Supply publisher datum evidence before projecting geometry.',
                'Licence status is not operational well status; UWI and operator are not supplied.',
                'Download timestamp and release date were not supplied; filesystem times are not publisher provenance.',
                'Inventory staging does not publish environmental proximity results.',
            ],
            'artifacts': artifacts,
        }
        assert count == accepted + rejected
        write_json(temporary / 'report.json', report)
        temporary.rename(destination)
        return report
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
