"""Public-data response exchange and chronological cyclic-work examples.

Run from any directory. All quantities retain the declared source units.
The examples track source provenance, physical units and reconstruction errors.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import urllib.request

import numpy as np
import openpyxl
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'software/src'))
from workcert import ReducedResponse, reduce_response, split_monotone_branches, __version__

OUT=ROOT/'validation/workflow_results'
STROKES=(10.,20.,30.,40.)
WINDOWS=((10.,20.),(20.,30.),(30.,40.))
LEVELS=(1.,.25,.0625)
MAX_POINTS=129

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf8')

def primitive(x,f,q):
    q=np.asarray(q,dtype=float)
    s=np.r_[0.,np.cumsum(np.diff(x)*(f[:-1]+f[1:])*.5)]
    j=np.clip(np.searchsorted(x,q,side='right')-1,0,len(x)-2)
    h=q-x[j]
    return s[j]+h*f[j]+.5*(f[j+1]-f[j])/(x[j+1]-x[j])*h*h

def prefix_peak(x,f,q):
    return max(float(np.max(f[x<=q])),float(np.interp(q,x,f)))

def metrics(x,f,table,mass_g,stroke):
    work=float(primitive(x,f,stroke));approx=float(table.work(stroke))
    peak=prefix_peak(x,f,stroke);p_hat=prefix_peak(table.x,table.force,stroke)
    e=table.certificate.prefix;delta=table.certificate.delta
    mass_kg=mass_g/1000.
    plo,phi=max(0.,p_hat-delta),p_hat+delta
    wlo,whi=approx-e,approx+e
    cfe=work/(stroke*peak);cfe_hat=approx/(stroke*p_hat)
    cfe_lo=wlo/(stroke*phi) if phi>0 else None
    cfe_hi=whi/(stroke*plo) if plo>0 else None
    slack=1e-9*max(1.,abs(work))
    assert abs(work-approx)<=e+slack
    assert abs(peak-p_hat)<=delta+slack
    if cfe_lo is not None and cfe_hi is not None:assert cfe_lo-1e-9<=cfe<=cfe_hi+1e-9
    return {'stroke_mm':stroke,'mass_g':mass_g,'reference_EA_J':work,'reduced_EA_J':approx,
            'EA_bound_J':e,'EA_absolute_error_J':abs(work-approx),
            'reference_SEA_kJ_kg':work/mass_kg/1000.,'reduced_SEA_kJ_kg':approx/mass_kg/1000.,
            'SEA_lower_kJ_kg':wlo/mass_kg/1000.,'SEA_upper_kJ_kg':whi/mass_kg/1000.,
            'reference_MCF_kN':work/stroke,'reduced_MCF_kN':approx/stroke,'MCF_bound_kN':e/stroke,
            'reference_PCF_kN':peak,'reduced_PCF_kN':p_hat,'PCF_bound_kN':delta,
            'reference_CFE':cfe,'reduced_CFE':cfe_hat,'CFE_lower':cfe_lo,'CFE_upper':cfe_hi}

def pair_comparisons(all_metrics):
    unresolved=set();rows=[]
    for stroke in STROKES:
        at=[v for v in all_metrics if v['stroke_mm']==stroke]
        for i,a in enumerate(at):
            for b in at[i+1:]:
                decision=0
                if a['SEA_lower_kJ_kg']>b['SEA_upper_kJ_kg']:decision=1
                if b['SEA_lower_kJ_kg']>a['SEA_upper_kJ_kg']:decision=-1
                reference=int(np.sign(a['reference_SEA_kJ_kg']-b['reference_SEA_kJ_kg']))
                if decision:assert decision==reference
                else:unresolved.update((a['curve'],b['curve']))
                rows.append({'stroke_mm':stroke,'curve_a':a['curve'],'curve_b':b['curve'],
                    'reference_difference_kJ_kg':a['reference_SEA_kJ_kg']-b['reference_SEA_kJ_kg'],
                    'resolved_direction':decision,'reference_direction':reference})
    return rows,unresolved

def check_metric_units():
    x=np.array([0.,1.,2.]);f=np.array([0.,2.,0.])
    table=reduce_response(x,f,method='work',max_points=3,x_unit='mm',force_unit='kN')
    row=metrics(x,f,table,100.,2.)
    expected={'reference_EA_J':2.,'reference_SEA_kJ_kg':.02,'reference_MCF_kN':1.,
              'reference_PCF_kN':2.,'reference_CFE':.5}
    for key,value in expected.items():assert abs(row[key]-value)<1e-14

def pla_exchange():
    folder=OUT/'pla_exchange';folder.mkdir(parents=True,exist_ok=True)
    mass_file=ROOT/'data/raw/pla_v7p6y654ft_v4/Mass_and_Crash_Indicators.xlsx'
    workbook=openpyxl.load_workbook(mass_file,read_only=True,data_only=True)
    published={str(row[0]):row for row in list(workbook.active.values)[1:] if isinstance(row[1],(int,float))}
    workbook.close();assert len(published)==46
    inputs={};source_audit=[]
    for specimen,row in published.items():
        path=ROOT/'data/prepared'/('PLA_'+specimen+'.csv')
        frame=pd.read_csv(path,float_precision='round_trip');x=frame.x_mm.to_numpy();f=frame.force_kN.to_numpy()
        assert x[0]==0 and x[-1]>=max(STROKES) and row[2]>=max(STROKES)
        inputs[specimen]=(x,f,float(row[1]),sha(path))
        ea=float(primitive(x,f,float(row[2])));reported=float(row[4])*1000.
        source_audit.append({'curve':specimen,'mass_g':float(row[1]),'source_maximum_stroke_mm':float(row[2]),
            'archived_end_mm':float(x[-1]),'reported_EA_J':reported,'PL_EA_at_reported_stroke_J':ea,
            'absolute_difference_J':abs(ea-reported),'reference_sha256':sha(path)})
    pd.DataFrame(source_audit).to_csv(folder/'mass_and_metric_source_audit.csv',index=False)
    tables={};selected=set(inputs);stages=[];manifests=[]
    for stage,budget in enumerate(LEVELS):
        built=sorted(selected)
        for specimen in built:
            x,f,mass,digest=inputs[specimen]
            result=reduce_response(x,f,max_points=MAX_POINTS,tolerance=budget,certificate='window',relative=False,
                method='work',peak_mode='absolute',x_unit='mm',force_unit='kN',
                provenance={'specimen':specimen,'source_doi':'10.17632/v7p6y654ft.4','prepared_csv_sha256':digest,
                            'mass_workbook_sha256':sha(mass_file),'mass_g':mass})
            destination=folder/'tables'/('stage_%d'%stage)/(specimen+'.json')
            destination.parent.mkdir(parents=True,exist_ok=True);result.save(destination)
            restored=ReducedResponse.load(destination);assert restored.verify_reference(x,f)
            tables[specimen]=restored
            manifests.append({'stage':stage,'curve':specimen,'absolute_window_budget_J':budget,
                'table':destination.relative_to(ROOT).as_posix(),'sha256':sha(destination),
                'points':len(restored.x),'tolerance_met':restored.metadata['tolerance_met']})
        query_rows=[];window_rows=[]
        for specimen,(x,f,mass,digest) in inputs.items():
            result=tables[specimen]
            for stroke in STROKES:query_rows.append({'stage':stage,'curve':specimen,**metrics(x,f,result,mass,stroke)})
            for a,b in WINDOWS:
                truth=float(primitive(x,f,b)-primitive(x,f,a));value=float(result.window_work(a,b))
                assert abs(truth-value)<=result.certificate.window+1e-8
                window_rows.append({'curve':specimen,'start_mm':a,'end_mm':b,'reference_work_J':truth,
                    'reduced_work_J':value,'error_J':abs(truth-value),'bound_J':result.certificate.window})
        pairs,selected=pair_comparisons(query_rows)
        pd.DataFrame(query_rows).to_csv(folder/('queries_stage_%d.csv'%stage),index=False)
        pd.DataFrame(pairs).to_csv(folder/('pairs_stage_%d.csv'%stage),index=False)
        pd.DataFrame(window_rows).to_csv(folder/('windows_stage_%d.csv'%stage),index=False)
        stages.append({'stage':stage,'budget_for_refined_curves_J':budget,'rebuilt_curves':built,
            'curves_rebuilt':len(built),'total_retained_points':sum(len(t.x) for t in tables.values()),
            'median_retained_points':float(np.median([len(t.x) for t in tables.values()])),
            'resolved_pairs':sum(v['resolved_direction']!=0 for v in pairs),'total_pairs':len(pairs),
            'unresolved_pairs':sum(v['resolved_direction']==0 for v in pairs),'unresolved_curves':sorted(selected),
            'EA_maximum_absolute_error_J':max(v['EA_absolute_error_J'] for v in query_rows),
            'window_maximum_absolute_error_J':max(v['error_J'] for v in window_rows),
            'maximum_CFE_absolute_error':max(abs(v['reference_CFE']-v['reduced_CFE']) for v in query_rows),
            'finite_CFE_intervals':sum(v['CFE_lower'] is not None and v['CFE_upper'] is not None for v in query_rows),
            'current_tables_with_unmet_tolerance':sum(not t.metadata['tolerance_met'] for t in tables.values()),
            'all_interval_checks_pass':True})
        if not selected:break
    requests=sorted({(r[key],r['stroke_mm']) for r in pairs if r['resolved_direction']==0 for key in ('curve_a','curve_b')})
    scalar_records=[];final_queries=[dict(v) for v in query_rows]
    for specimen,stroke in requests:
        x,f,mass,digest=inputs[specimen]
        value=float(primitive(x,f,stroke));sea=value/(mass/1000.)/1000.
        scalar_records.append({'curve':specimen,'stroke_mm':stroke,'EA_J':value,'SEA_kJ_kg':sea,
            'prepared_reference_sha256':digest,'mass_g':mass,
            'purpose':'Query-specific exact scalar response after overlapping table-error intervals'})
        for row in final_queries:
            if row['curve']==specimen and row['stroke_mm']==stroke:
                row['SEA_lower_kJ_kg']=row['SEA_upper_kJ_kg']=sea
    final_pairs,unresolved=pair_comparisons(final_queries)
    write_json(folder/'query_specific_scalar_responses.json',scalar_records)
    pd.DataFrame(final_pairs).to_csv(folder/'pairs_after_scalar_followup.csv',index=False)
    summary={'software_version':__version__,'records':46,'reference_nodes':sum(len(v[0]) for v in inputs.values()),
        'scenario':'Public compression-database exchange and variable-stroke crashworthiness screening',
        'strokes_mm':STROKES,'window_requests_mm':WINDOWS,'mass_source':mass_file.relative_to(ROOT).as_posix(),
        'mass_workbook_sha256':sha(mass_file),'source_reported_EA_comparison':{
            'query_window':'Reported delta_max, not entire archived curve','median_absolute_difference_J':float(np.median([v['absolute_difference_J'] for v in source_audit])),
            'max_absolute_difference_J':max(v['absolute_difference_J'] for v in source_audit)},
        'stages':stages,'total_tables_saved':len(manifests),'table_manifest':manifests,
        'query_specific_followup':{'scalar_responses':len(scalar_records),
            'requested_curve_stroke_pairs':requests,'resolved_pairs':sum(r['resolved_direction']!=0 for r in final_pairs),
            'total_pairs':len(final_pairs),'unresolved_pairs':sum(r['resolved_direction']==0 for r in final_pairs),
            'false_resolved_orderings':0,'definition':'Exact source-reference EA scalar at a requested stroke; not an additional reduced response table'},
        'engineering_metrics':['EA_J','SEA_kJ_per_kg','MCF_kN','prefix_PCF_kN','CFE'],
        'interpretation':'Ordering intervals concern reconstruction of the supplied numerical records and fixed source masses.'}
    write_json(folder/'summary.json',summary)
    return summary

def ensure_cyclic():
    folder=ROOT/'data/extended/cyclic_RHS_10829958';folder.mkdir(parents=True,exist_ok=True)
    meta=folder/'repository_metadata.json'
    if not meta.exists():meta.write_bytes(urllib.request.urlopen('https://zenodo.org/api/records/10829958',timeout=45).read())
    metadata=json.loads(meta.read_text(encoding='utf8'));assert metadata['metadata']['license']['id']=='cc-by-4.0'
    item=metadata['files'][0];source=folder/'cyclic_RHS.xlsx'
    if not source.exists():source.write_bytes(urllib.request.urlopen(item['links']['self'],timeout=60).read())
    assert 'md5:'+hashlib.md5(source.read_bytes()).hexdigest()==item['checksum']
    workbook=openpyxl.load_workbook(source,read_only=True,data_only=True)
    sheet=workbook['S1_L1'];assert tuple(next(sheet.iter_rows(min_row=2,max_row=2,values_only=True)))[1:]==('Displacement','Force')
    rows=[(r[1],r[2]) for r in sheet.iter_rows(min_row=4,values_only=True) if isinstance(r[1],(float,int)) and isinstance(r[2],(float,int))]
    workbook.close();array=np.asarray(rows,float);assert array.shape==(125157,2) and np.all(np.isfinite(array))
    return source,array

def cyclic_example():
    folder=OUT/'cyclic_path';folder.mkdir(parents=True,exist_ok=True)
    source,array=ensure_cyclic();source_digest=sha(source);x,f=array.T
    series=split_monotone_branches(x,f,duplicate_policy='split')
    direct=float(np.sum(np.diff(x)*(f[:-1]+f[1:])*.5))
    covered=np.zeros(len(x)-1,dtype=np.int16)
    for branch in series.branches:
        first,last=int(np.min(branch.source_indices)),int(np.max(branch.source_indices))
        assert last-first+1==len(branch.source_indices)
        covered[first:last]+=1
    for event in series.events:
        assert event.source_end==event.source_start+1 and x[event.source_start]==x[event.source_end]
        covered[event.source_start]+=1
    assert np.all(covered==1),'Each original chronological interval must be represented exactly once'
    branch_work=np.array([float(primitive(b.x,b.force,b.end_x)-primitive(b.x,b.force,b.start_x)) for b in series.branches])
    scale=float(np.sum(np.abs(branch_work)));budget=.001*scale
    assert abs(branch_work.sum()-direct)<=1e-9*max(1.,scale)
    approximation=f.copy();records=[];bound=0.;reduced_work=0.;points=0;unmet=0;longest=None
    for index,(branch,work) in enumerate(zip(series.branches,branch_work)):
        allocation=.001*abs(float(work))
        response=reduce_response(branch.x,branch.force,max_points=min(MAX_POINTS,len(branch.x)),tolerance=allocation,
            certificate='window',relative=False,method='work',peak_mode='absolute',x_unit='mm',force_unit='kN',
            provenance={'source_doi':'10.5281/zenodo.10829958','source_xlsx_sha256':source_digest,
                        'branch':index,'chronological_direction':branch.direction})
        approximation[branch.source_indices]=response.force_at(branch.x)
        value=float(branch.directed_work(response));reduced_work+=value;bound+=response.certificate.window
        points+=len(response.x);unmet+=not response.metadata['tolerance_met']
        destination=folder/'tables'/('%04d.json'%index);destination.parent.mkdir(parents=True,exist_ok=True);response.save(destination)
        restored=ReducedResponse.load(destination);assert restored.verify_reference(branch.x,branch.force)
        records.append({'branch':index,'direction':branch.direction,'source_first':int(min(branch.source_indices)),
            'source_last':int(max(branch.source_indices)),'source_points':len(branch.x),'retained_points':len(response.x),
            'start_mm':branch.start_x,'end_mm':branch.end_x,'reference_directed_work_J':float(work),
            'reduced_directed_work_J':value,'window_bound_J':response.certificate.window,
            'allocated_bound_J':allocation,'tolerance_met':response.metadata['tolerance_met'],
            'table':destination.relative_to(ROOT).as_posix(),'sha256':sha(destination)})
        if longest is None or len(branch.x)>longest[0]:longest=(len(branch.x),index)
    residual=f-approximation;dx=np.diff(x)
    d=np.r_[0.,np.cumsum(dx*(residual[:-1]+residual[1:])*.5)]
    crosses=np.flatnonzero(residual[:-1]*residual[1:]<0)
    t=-residual[crosses]/(residual[crosses+1]-residual[crosses])
    interior=d[crosses]+dx[crosses]*t*residual[crosses]*.5
    maximum=float(max(np.max(np.abs(d)),np.max(np.abs(interior)) if len(interior) else 0))
    assert maximum<=bound+1e-8*max(1.,scale)
    assert abs(direct-reduced_work-d[-1])<=1e-8*max(1.,scale)
    np.savez_compressed(folder/'chronological_path.npz',displacement_mm=x,reference_force_kN=f,
                        reconstructed_force_kN=approximation,cumulative_error_J=d)
    selected=series.branches[longest[1]]
    chosen=ReducedResponse.load(folder/'tables'/('%04d.json'%longest[1]))
    pd.DataFrame({'displacement_mm':selected.x,'force_kN':selected.force}).to_csv(folder/'longest_branch_reference.csv',index=False,float_format='%.17g')
    pd.DataFrame({'displacement_mm':chosen.x,'force_kN':chosen.force}).to_csv(folder/'longest_branch_reduced.csv',index=False,float_format='%.17g')
    pd.DataFrame(records).to_csv(folder/'branch_metrics.csv',index=False)
    summary={'software_version':__version__,'dataset_doi':'10.5281/zenodo.10829958','license':'CC BY 4.0',
        'source_xlsx_sha256':source_digest,'source_points':len(x),'negative_force_observations':int(np.sum(f<0)),
        'branches':len(series.branches),'zero_displacement_events':len(series.events),
        'ascending_branches':sum(b.direction>0 for b in series.branches),'descending_branches':sum(b.direction<0 for b in series.branches),
        'longest_branch':{'index':longest[1],'source_points':longest[0]},'sum_retained_branch_nodes':points,
        'point_cap_per_branch':MAX_POINTS,'branches_unmet_cap':int(unmet),
        'reference_signed_path_work_J':direct,'reference_sum_of_branch_work_J':float(branch_work.sum()),
        'reduced_signed_path_work_J':reduced_work,'signed_terminal_error_J':direct-reduced_work,
        'maximum_continuous_chronological_work_error_J':maximum,'sum_branch_window_bounds_J':bound,
        'requested_aggregate_error_budget_J':budget,'allocation_scale_sum_abs_branch_work_J':scale,
        'all_global_error_checks_pass':True,
        'all_chronological_intervals_covered_once':True,
        'interpretation':'Signed chronological path integral F dx; not interpreted as crash energy or closed-cycle dissipation. No smoothing, contact alignment or reversal threshold is applied.'}
    write_json(folder/'summary.json',summary)
    return summary

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=('all','pla','cyclic'),default='all');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    check_metric_units()
    protocol={'date':'2026-10-31','PLA_specimens':'All 46 curves with numeric masses in the source workbook',
        'PLA_query_strokes_mm':STROKES,'PLA_interval_queries_mm':WINDOWS,'initial_window_tolerance_J':LEVELS[0],
        'selective_levels_J':LEVELS,'selection_rule':'Refine every response incident to any unresolved SEA interval pair across the four query strokes',
        'remaining_overlap_rule':'After the three table budgets, request exact query-specific EA scalars for both participants in each unresolved curve-stroke comparison',
        'maximum_points_per_table':MAX_POINTS,'cyclic_record':'Complete S1-L1 numerical record in Zenodo10829958',
        'cyclic_branch_rule':'Every exact reversal/dwell, no smoothing; direction and zero-work events retained',
        'cyclic_error_budget':'0.001 times sum of absolute directed branch work, allocated in proportion to each absolute branch work'}
    write_json(OUT/'protocol.json',protocol)
    results={'software_version':__version__,'core_sha256':sha(ROOT/'software/src/workcert/core.py')}
    if args.case in ('all','pla'):results['pla_exchange']=pla_exchange()
    if args.case in ('all','cyclic'):results['cyclic_path']=cyclic_example()
    write_json(OUT/('summary_'+args.case+'.json'),results)
    print(json.dumps({k:v for k,v in results.items() if k in ('software_version','core_sha256')},indent=2))
    print('Completed '+args.case+' workflow.')

if __name__=='__main__':main()
