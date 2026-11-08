"""Bounded CSV reader driven entirely by verified/internal canonical mappings."""
import csv
import io
import zipfile
from datetime import datetime

from src.config import Source


def read_csv(path,source: Source,*,max_records=100000):
    if path.stat().st_size>512*1024**2:
        raise ValueError('Production input exceeds the 512 MiB file cap')
    required={'source_record_id','period','product','activity','volume','unit'}
    if not required<=source.field_mapping.keys():
        raise ValueError('Production mapping must define record ID, period, product, activity, volume and unit')
    archive=None
    if zipfile.is_zipfile(path):
        archive=zipfile.ZipFile(path)
        members=[m for m in archive.infolist() if m.filename.lower().endswith('.csv')]
        if len(members)!=1 or members[0].file_size>512*1024**2:
            archive.close();raise ValueError('Production ZIP must contain one bounded CSV file')
        stream=archive.open(members[0])
    else:stream=open(path,'rb')
    try:
        with io.TextIOWrapper(stream,encoding=source.csv_encoding,newline='') as handle:
            reader=csv.DictReader(handle,delimiter=source.csv_delimiter)
            headers=reader.fieldnames or []
            if len(headers)!=len(set(headers)) or not set(source.field_mapping.values())<=set(headers):
                raise ValueError('CSV headers do not match the configured production mapping')
            rows=[]
            for raw in reader:
                if len(rows)>=max_records:raise ValueError('Production CSV exceeds the record cap; input was not truncated')
                if None in raw or any(value is None for value in raw.values()):
                    raise ValueError('Malformed CSV row has unexpected/missing columns')
                row={key:raw[field] for key,field in source.field_mapping.items()}
                period=row.get('period','')
                if source.period_format!='%Y-%m':
                    try:row['period']=datetime.strptime(period,source.period_format).strftime('%Y-%m')
                    except ValueError:row['period']=None  # Contract quarantines the unparseable period.
                if source.reporting_level=='mixed':
                    raw_level=row.get('attribution_level','')
                    row['attribution_level']=source.attribution_values.get(raw_level,'invalid')
                else:row['attribution_level']=source.reporting_level
                rows.append(row)
            return rows
    finally:
        if archive:archive.close()
