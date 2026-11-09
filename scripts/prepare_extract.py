"""Inspect a large local GIS input or prepare a bounded regional package before database ingestion."""
import argparse
import json
from pathlib import Path

from _bootstrap import run_cli
from src.artifacts import write_json
from src.config import ROOT, Source, SourceCatalog, load_source_catalog, load_study_area
from src.sources.extract import inspect_original, prepare_extract


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',type=Path,required=True)
    parser.add_argument('--source',required=True,help='Entry key, for example aer_wells')
    parser.add_argument('--study-area',type=Path,default=ROOT/'config/study_area.live.yml')
    parser.add_argument('--inspect',action='store_true',help='List original layers/selected metadata without copying or hashing the entire download')
    parser.add_argument('--output-root',type=Path,default=ROOT/'data/raw/extracts')
    parser.add_argument('--max-records',type=int,default=10000)
    parser.add_argument('--max-output-mib',type=int,default=512)
    args=parser.parse_args()
    catalog=load_source_catalog(args.catalog)
    source=next((s for s in catalog.sources if s.key==args.source),None)
    if source is None:raise ValueError('Requested source key is absent from the catalogue')
    if args.inspect:
        _,_,metadata=inspect_original(source);print(json.dumps(metadata,indent=2));return
    report=prepare_extract(source,load_study_area(args.study_area),args.output_root,
                           max_records=args.max_records,max_output_bytes=args.max_output_mib*1024**2,
                           progress=lambda message:print(message,flush=True))
    prepared=Source.model_validate({**report['catalogue_entry'],'local_path':report['package_path']})
    sources=[prepared if s.key==source.key else s for s in catalog.sources]
    output=args.output_root.resolve()/'prepared_catalogue.json'
    write_json(output,SourceCatalog(sources=sources).model_dump(mode='json'))
    print(json.dumps({'source':source.key,'records':report['record_count'],'package_bytes':report['package_bytes'],
                      'package':report['package_path'],'prepared_catalogue':str(output),
                      'note':'Verification/enabled flags are preserved; this command does not load PostGIS.'},indent=2))


if __name__=='__main__':
    run_cli(main,error_hint='Check original GIS path/layer/CRS, source metadata, study area and docs/regional_extracts.md.')
