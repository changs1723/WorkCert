"""Reproduce branch rejection and targeted recovery using the archived cyclic path.

From the source root:
    python revision_r1/recompute_cyclic_recovery.py
No original table, workbook, runtime module or published output is modified.
"""
from pathlib import Path
import csv
import hashlib
import json
import math
import platform
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'software/src'))
from workcert import ReducedResponse, reduce_response
from checked_cyclic_path import compose_checked_path, PathToleranceError

OUT = ROOT/'revision_r1/results'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf8')


def from_table(table, row):
    c, m = table.certificate, table.metadata
    return {'kind':'branch','branch_id':int(row['branch']),
        'source_start':int(row['source_first']),'source_end':int(row['source_last']),
        'direction':int(row['direction']), 'work_unit':table.work_unit,
        'terminal':c.signed_terminal_error,'minimum':c.min_cumulative_error,
        'maximum':c.max_cumulative_error,'reference_work':c.reference_work,
        'bounds':{k:getattr(c,k) for k in ('eta','xi','prefix','window')},
        **{k:m.get(k) for k in ('certificate_for_stopping','requested_tolerance',
                              'relative_tolerance','tolerance_met')}}


def compensated_prefix(terms):
    # Scalar Neumaier accumulation, independent of WorkCert's balanced tree.
    result=[0.];total=correction=0.
    for term in terms:
        value=float(term);following=total+value
        if abs(total)>=abs(value):correction+=(total-following)+value
        else:correction+=(value-following)+total
        total=following;result.append(total+correction)
    return np.asarray(result)


def independent_error(x, residual):
    dx=np.diff(x)
    terms=dx*(.5*residual[:-1]+.5*residual[1:])
    values=compensated_prefix(terms)
    low,high=float(values.min()),float(values.max())
    indices=np.flatnonzero(((residual[:-1]<0)&(residual[1:]>0))|
                           ((residual[:-1]>0)&(residual[1:]<0)))
    fraction=-residual[indices]/(residual[indices+1]-residual[indices])
    inside=values[indices]+.5*dx[indices]*fraction*residual[indices]
    if len(inside):low=min(low,float(inside.min()));high=max(high,float(inside.max()))
    return {'signed_terminal_error':math.fsum(terms),
            'minimum_cumulative_error':low,'maximum_cumulative_error':high,
            'prefix':max(abs(low),abs(high)),'window':high-low}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    original=ROOT/'validation/workflow_results/cyclic_path'
    npz=original/'chronological_path.npz'
    expected='192ee99f39d6b3cc8f3647d1f7ba5423f47ad6940a5abb19a501c72b710b6ffe'
    if sha(npz)!=expected:raise ValueError('Archived path identity changed')
    with np.load(npz) as z:
        x=z['displacement_mm'].copy();f=z['reference_force_kN'].copy()
        previous=z['reconstructed_force_kN'].copy()
    with (original/'branch_metrics.csv').open(encoding='utf8',newline='') as handle:
        rows=list(csv.DictReader(handle))
    tables, records, hashes = {}, [], {}
    verified=0
    for row in rows:
        branch=int(row['branch']); path=original/'tables'/Path(row['table']).name
        if sha(path)!=row['sha256']:raise ValueError('Original table identity changed')
        table=ReducedResponse.load(path)
        first,last,direction=int(row['source_first']),int(row['source_last']),int(row['direction'])
        ids=np.arange(first,last+1) if direction>0 else np.arange(last,first-1,-1)
        table.verify_reference(x[ids],f[ids]);verified+=1
        tables[branch]=table; hashes[str(branch)]=sha(path)
        records.append(from_table(table,row))
    records.extend({'kind':'zero_work_event','source_start':int(i),'source_end':int(i+1),
                    'direction':0,'terminal':0.,'minimum':0.,'maximum':0.,'work_unit':'J'}
                   for i in np.flatnonzero(np.diff(x)==0))
    records.sort(key=lambda record:record['source_start'])
    before=compose_checked_path(records,source_points=len(x),work_unit='J',strict=False)
    try:
        compose_checked_path(records,source_points=len(x),work_unit='J')
    except PathToleranceError as error:
        strict_rejected=(error.report['failed_branch_ids']==[2533])
    else:strict_rejected=False
    assert strict_rejected and before['failed_branch_ids']==[2533]
    repaired_records=[dict(record) for record in records]
    approximation=previous.copy()
    changes=[]
    for branch in before['failed_branch_ids']:
        row=next(row for row in rows if int(row['branch'])==branch)
        old=tables[branch];first,last,direction=int(row['source_first']),int(row['source_last']),int(row['direction'])
        ids=np.arange(first,last+1) if direction>0 else np.arange(last,first-1,-1)
        # Increase the cap only for a rejected branch, with the original budget.
        replacement=reduce_response(x[ids],f[ids],method='work',max_points=257,
            tolerance=old.metadata['requested_tolerance'],certificate='window',relative=False,
            preserve_peak=True,peak_mode='absolute',x_unit='mm',force_unit='kN',
            provenance=old.metadata['provenance'])
        replacement.verify_reference(x[ids],f[ids])
        assert replacement.metadata['tolerance_met'] is True
        position=next(j for j,record in enumerate(repaired_records) if record.get('branch_id')==branch)
        repaired_records[position]=from_table(replacement,row)
        approximation[ids]=np.interp(x[ids],replacement.x,replacement.force)
        output=OUT/f'cyclic_branch_{branch}_recovered.json';replacement.save(output)
        changes.append({'branch_id':branch,'source_nodes':len(ids),'old_cap':129,'new_cap':257,
            'old_nodes':len(old.indices),'new_nodes':len(replacement.indices),
            'requested_window_error_J':old.metadata['requested_tolerance'],
            'old_window_error_J':old.certificate.window,'new_window_error_J':replacement.certificate.window,
            'new_tolerance_met':replacement.metadata['tolerance_met'],
            'replacement_table':str(output.relative_to(ROOT)).replace('\\','/'),
            'replacement_sha256':sha(output),'source_reference_verified':True})
        tables[branch]=replacement
    # No downstream energy calculation is reached until strict composition passes.
    after=compose_checked_path(repaired_records,source_points=len(x),work_unit='J')
    reference_work=math.fsum(np.diff(x)*(.5*f[:-1]+.5*f[1:]))
    reconstructed_work=math.fsum(int(row['direction'])*tables[int(row['branch'])].work(
        tables[int(row['branch'])].x[-1]) for row in rows)
    independent=independent_error(x,f-approximation)
    differences={key:abs(after['error_summary'][key]-independent[key]) for key in independent}
    assert max(differences.values())<1e-8
    assert abs(reference_work-reconstructed_work-independent['signed_terminal_error'])<1e-8
    old_count=sum(int(row['retained_points']) for row in rows)
    new_count=sum(len(table.indices) for table in tables.values())
    sum_windows=math.fsum(record['bounds']['window'] for record in repaired_records if record['direction'])
    summary={'status':'PASS','software_runtime_version':'0.3.0','runtime_modified':False,
        'python':platform.python_version(),'numpy':np.__version__,
        'source_points':len(x),'monotone_branches':len(rows),
        'zero_work_events':sum(record['direction']==0 for record in records),
        'archived_path_sha256':sha(npz),'source_table_hash_checks':len(hashes),
        'source_reference_verifications':verified,'original_failure_rejected_in_strict_mode':strict_rejected,
        'before':{'tolerance_met':before['tolerance_met'],'valid_for_downstream_use':before['valid_for_downstream_use'],
            'failed_branch_ids':before['failed_branch_ids'],'retained_nodes':old_count,
            'error_summary_J':before['error_summary']},
        'repair':changes,
        'after':{'tolerance_met':after['tolerance_met'],'valid_for_downstream_use':after['valid_for_downstream_use'],
            'failed_branch_ids':after['failed_branch_ids'],'retained_nodes':new_count,
            'additional_nodes':new_count-old_count,'error_summary_J':after['error_summary'],
            'reference_signed_path_work_J':reference_work,
            'reconstructed_signed_path_work_J':reconstructed_work,
            'sum_branch_window_errors_J':sum_windows,
            'independent_chronological_residual_summary_J':independent,
            'independent_summary_absolute_differences_J':differences,
            'independent_comparison_tolerance_J':1e-8},
        'interpretation':'Acceptance establishes every prescribed local branch budget. It does not establish a prescribed global relative path tolerance. Signed chronological work is not automatically closed-cycle dissipation.',
        'float_semantics':'The branch composition identity is exact in real arithmetic; this example uses sequential float64 operations and does not enclose rounding error.'}
    write_json(OUT/'cyclic_recovery_summary.json',summary)
    write_json(OUT/'cyclic_checked_manifest_before.json',{'source_points':len(x),'work_unit':'J','records':records})
    write_json(OUT/'cyclic_checked_manifest_after.json',{'source_points':len(x),'work_unit':'J','records':repaired_records})
    write_json(OUT/'cyclic_path_assessment_before.json',before)
    write_json(OUT/'cyclic_path_assessment_after.json',after)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
