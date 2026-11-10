"""Small synthetic OOXML fixtures, never official source data."""
from xml.sax.saxutils import escape
from zipfile import ZipFile

from src.sources.st37 import FIELDS, SHEET


def synthetic_row(identifier='0000123', **changes):
    return dict(zip(FIELDS, (identifier, 'Synthetic Licensee', 'Issued', '11/01/2026',
        750.5, '20010102', '20010105', 'Synthetic category', 53.25, -115.0,
        '01-01-001-01W5'))) | changes


def write_workbook(path, rows, *, headers=FIELDS, sheet=SHEET):
    values = [list(headers), *[[row.get(field) for field in headers] for row in rows]]
    xml_rows = []
    for index, row in enumerate(values, 1):
        cells = []
        for col, value in enumerate(row):
            address = f'{chr(65 + col)}{index}'
            if value is None:
                cells.append(f'<c r="{address}"/>')
            elif isinstance(value, (int, float)):
                cells.append(f'<c r="{address}" t="n"><v>{value}</v></c>')
            elif str(value).startswith('='):
                cells.append(f'<c r="{address}"><f>{escape(value[1:])}</f><v/></c>')
            else:
                cells.append(f'<c r="{address}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        xml_rows.append(f'<row r="{index}">{"".join(cells)}</row>')
    with ZipFile(path, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{sheet}" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet1.xml', f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:K{len(values)}"/><sheetData>{"".join(xml_rows)}</sheetData></worksheet>')
    return path
