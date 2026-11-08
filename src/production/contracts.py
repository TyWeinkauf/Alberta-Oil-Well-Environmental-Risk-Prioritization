"""Canonical production contracts; source-specific column names stay in config."""
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from src.config import Source


def month(value: str) -> date:
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}',value):
        raise ValueError('Month must use YYYY-MM')
    try:return date.fromisoformat(value+'-01')
    except ValueError:raise ValueError('Invalid calendar month') from None


@dataclass
class ProductionValidation:
    accepted: list[dict]
    rejected: list[dict]
    excluded_records: int
    input_records: int


def validate_production(rows: list[dict], source: Source, start: str, end: str) -> ProductionValidation:
    first,last=month(start),month(end)
    if first>last:raise ValueError('Production window start must not follow its end')
    accepted=[];rejected=[];excluded=0
    ids=Counter(r.get('source_record_id','').strip() for r in rows
                if isinstance(r,dict) and isinstance(r.get('source_record_id'),str) and r['source_record_id'].strip())
    for index,row in enumerate(rows,1):
        reference=f'csv_record/{index}'
        code='invalid_record';detail='Production record must be an object'
        try:
            if not isinstance(row,dict):raise ValueError(detail)
            code='invalid_period';detail='A valid YYYY-MM reporting month is required'
            period=month(row.get('period'))
            if not first<=period<=last:
                excluded+=1;continue
            code='missing_id';detail='source_record_id must be a nonempty string'
            identifier=row.get('source_record_id')
            if not isinstance(identifier,str) or not identifier.strip():raise ValueError(detail)
            code='duplicate_id';detail='All occurrences of a duplicate source record ID are quarantined'
            if ids[identifier.strip()]>1:raise ValueError(detail)
            code='missing_fields';detail='Product, activity and reporting unit must be explicit nonempty strings'
            if any(not isinstance(row.get(k),str) or not row[k].strip() for k in ('product','activity','unit')):
                raise ValueError(detail)
            code='invalid_volume';detail='Volume must be finite, with at most 38 significant/integer digits and 12 decimals'
            try:volume=Decimal(str(row.get('volume')))
            except InvalidOperation:raise ValueError(detail) from None
            if not volume.is_finite() or len(volume.as_tuple().digits)>38 or volume.adjusted()>37 or volume.as_tuple().exponent < -12:
                raise ValueError(detail)
            if volume<0 and not (row['activity'] in source.adjustment_activities and source.adjustment_note):
                code='undocumented_adjustment';detail='Negative values require a documented allowed adjustment activity'
                raise ValueError(detail)
            code='invalid_attribution';detail='Reporting level must be well, facility or unknown'
            level=row.get('attribution_level','unknown')
            if level not in ('well','facility','unknown'):raise ValueError(detail)
            code='invalid_identifier';detail='Optional facility/well identifiers must be strings or null'
            if any(row.get(k) is not None and not isinstance(row[k],str) for k in ('reporting_facility_id','well_identifier_nullable')):
                raise ValueError(detail)
            accepted.append({'source_record_id':identifier.strip(),'period':period,'volume':volume,
                'product':row['product'].strip(),'activity':row['activity'].strip(),'unit':row['unit'].strip(),
                'attribution_level':level,'reporting_facility_id':row.get('reporting_facility_id') or None,
                'well_identifier_nullable':row.get('well_identifier_nullable') or None,
                'record_reference':reference})
        except (ValueError,TypeError,InvalidOperation):
            rejected.append({'record_reference':reference,'reason_code':code,'reason_detail':detail})
    assert len(accepted)+len(rejected)+excluded==len(rows)
    return ProductionValidation(accepted,rejected,excluded,len(rows))


def resolve_link(record: dict, candidates: dict[str,list[int]], source: Source) -> tuple[str,str,list[int]]:
    """Exact namespaced ID match only; facility totals are never allocated."""
    if record['attribution_level']=='facility':return 'facility','reported_at_facility_level',[]
    if record['attribution_level']!='well':return 'unknown','reporting_level_unverified',[]
    identifier=record.get('well_identifier_nullable')
    if not identifier:return 'unmatched','missing_source_well_identifier',[]
    if not (source.well_identifier_field and source.identifier_namespace and source.join_evidence):
        return 'unmatched','identifier_scheme_unverified',[]
    matches=candidates.get(identifier.strip(),[])
    if len(matches)==1:return 'verified','exact_verified_identifier',matches
    if len(matches)>1:return 'ambiguous','ambiguous_well_identifier',matches
    return 'unmatched','no_matching_well_in_run',[]
