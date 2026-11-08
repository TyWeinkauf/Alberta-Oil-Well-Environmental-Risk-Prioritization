"""Inspect a candidate source before configuring/enabling its verified mapping."""
import argparse
import json

from _bootstrap import run_cli
import pyogrio

from src.sources.files import spatial_path
from src.sources.http import HttpCache


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind',choices=['file','arcgis'])
    parser.add_argument('url',help='Candidate official public HTTPS URL; inspection does not certify its licence')
    parser.add_argument('--layer')
    parser.add_argument('--archive-member')
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    cache=HttpCache()
    snapshot=cache.get(args.url,{'f':'json'} if args.kind=='arcgis' else None,refresh=args.refresh)
    if args.kind=='arcgis':
        metadata=snapshot.json()
        if 'error' in metadata:
            raise ValueError('ArcGIS metadata request returned an error')
        print(json.dumps(metadata,indent=2))
    else:
        dataset=spatial_path(snapshot.path,args.archive_member)
        layers=pyogrio.list_layers(dataset)
        names=[str(row[0]) for row in layers]
        print('Available layers:',names)
        layer=args.layer or (names[0] if len(names)==1 else None)
        if layer is not None:
            info=pyogrio.read_info(dataset,layer=layer)
            print(json.dumps({key:info[key].tolist() if hasattr(info[key],'tolist') else info[key]
                              for key in ['driver','crs','geometry_type','features','fields','dtypes','total_bounds']},indent=2))
    print('Cached raw SHA-256:',snapshot.metadata['checksum_sha256'])


if __name__=='__main__':
    run_cli(main,error_hint='Check the public source URL, network allowlist, CA trust and download cap; see docs/source_verification.md.')
