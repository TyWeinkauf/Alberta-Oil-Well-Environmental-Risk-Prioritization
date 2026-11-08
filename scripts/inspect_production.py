"""Preview CSV headers before defining a verified production field mapping."""
import argparse
import csv
import io
import json
import zipfile
from pathlib import Path

from _bootstrap import run_cli
from src.sources.http import HttpCache


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    inputs=parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--url',help='Candidate official public HTTPS CSV/ZIP URL')
    inputs.add_argument('--path',type=Path,help='Local permitted CSV/ZIP file')
    parser.add_argument('--encoding',default='utf-8-sig')
    parser.add_argument('--delimiter',default=',')
    args=parser.parse_args()
    if len(args.delimiter)!=1:raise ValueError('CSV delimiter must be one character')
    path=HttpCache().get(args.url).path if args.url else args.path
    if path.stat().st_size>512*1024**2:raise ValueError('CSV inspection file exceeds the 512 MiB cap')
    archive=None
    if zipfile.is_zipfile(path):
        archive=zipfile.ZipFile(path);members=[m for m in archive.infolist() if m.filename.lower().endswith('.csv')]
        if len(members)!=1 or members[0].file_size>512*1024**2:
            archive.close();raise ValueError('ZIP must contain one bounded CSV file')
        stream=archive.open(members[0])
    else:stream=path.open('rb')
    try:
        with io.TextIOWrapper(stream,encoding=args.encoding,newline='') as handle:
            reader=csv.DictReader(handle,delimiter=args.delimiter)
            sample=[]
            for row in reader:
                sample.append(row)
                if len(sample)==3:break
            print(json.dumps({'columns':reader.fieldnames,'sample':sample},indent=2,ensure_ascii=False))
    finally:
        if archive:archive.close()
    print('Preview only: verify publisher terms, record grain, units and identifier semantics before enabling ingestion.')


if __name__=='__main__':run_cli(main,error_hint='Check the public URL or local file, network policy, format, encoding and delimiter.')
