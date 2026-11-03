"""Audit specimen-aware exchange against source curves and published indicators.

This is a numerical/source audit, separate from the independent quantities
reported in the original dataset's crash-indicator workbook.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

import numpy as np
import openpyxl
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'software/src'))
from workcert import ReducedResponse, from_indices
OUT=ROOT/'validation/workflow_results_round2'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def close(a,b):
    assert np.allclose(a,b,rtol=3e-13,atol=1e-10),(a,b)


def source_metrics(x,f,u,mass):
    # Integrate completed source segments, then its clipped linear segment.
    left=int(np.searchsorted(x,u,side='right')-1)
    left=min(left,len(x)-2)
    ea=float(np.dot(np.diff(x[:left+1]),(f[:left]+f[1:left+1])*.5))
    h=u-x[left];end=f[left]+h*(f[left+1]-f[left])/(x[left+1]-x[left])
    ea+=float(h*(f[left]+end)*.5)
    peak=float(max(np.max(f[:left+1]),end))
    return {'EA_J':ea,'SEA_kJ_kg':ea/mass,'MCF_kN':ea/u,'PCF_kN':peak,'CFE':ea/u/peak}


def main():
    s=json.loads((OUT/'summary.json').read_text(encoding='utf8'))
    assert s['core_sha256']==sha(ROOT/'software/src/workcert/core.py')
    assert s['client_sha256']==sha(ROOT/'examples/query_exchange.py')
    source=ROOT/s['source_workbook'];assert sha(source)==s['source_workbook_sha256']
    w=openpyxl.load_workbook(source,read_only=True,data_only=True)
    published={str(r[0]):r for r in w.active.values if isinstance(r[1],(int,float))};w.close()
    assert len(published)==46
    spec=importlib.util.spec_from_file_location('round2_consumer',ROOT/'examples/query_exchange.py')
    client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
    q=pd.read_csv(OUT/'queries.csv',dtype={'specimen':str,'configuration':str})
    external=pd.read_csv(OUT/'published_indicator_comparison.csv',dtype={'specimen':str,'configuration':str})
    source_values={};peakchecks=0;clientquantities=0
    for item in s['table_manifest']:
        name=item['specimen'];row=published[name]
        path=ROOT/'data/prepared'/('PLA_'+name+'.csv');assert sha(path)==item['reference_sha256']
        data=pd.read_csv(path,float_precision='round_trip');x=data.x_mm.to_numpy();f=data.force_kN.to_numpy()
        path=ROOT/item['table'];assert sha(path)==item['sha256'];table=ReducedResponse.load(path)
        assert table.verify_reference(x,f)
        assert len(table.x)==item['points'] and table.metadata['tolerance_met']==item['tolerance_met']
        subset=q[q.specimen==name].sort_values('stroke_mm');assert len(subset)==4
        response=client.query_metrics(table,float(row[1]),subset.stroke_mm.to_numpy())
        for received,(_,stored) in zip(response,subset.iterrows()):
            truth=source_metrics(x,f,float(stored.stroke_mm),float(row[1]))
            source_values[name,float(stored.stroke_mm)]=truth
            for key,value in received.items():
                close(value,stored[key]);clientquantities+=1
            for key,value in truth.items():
                close(value,stored['reference_'+key])
                stem=key.split('_')[0];unit=key[len(stem):]
                assert stored[stem+'_lower'+unit]-1e-9<=value<=stored[stem+'_upper'+unit]+1e-9
            if received['peak_exact']:
                close(received['PCF_lower_kN'],truth['PCF_kN']);close(received['PCF_upper_kN'],truth['PCF_kN']);peakchecks+=1
            assert stored.CFE_upper-stored.CFE_lower<=stored.old_CFE_upper-stored.old_CFE_lower+1e-12
        target=external[external.specimen==name].iloc[0]
        truth=source_metrics(x,f,float(row[2]),float(row[1]))
        endpoint=source_metrics(x,f,float(x[-1]),float(row[1]))
        close(target.archived_endpoint_mm,x[-1]);close(target.endpoint_offset_mm,x[-1]-float(row[2]))
        close(target.source_PL_EA_at_archived_endpoint_J,endpoint['EA_J'])
        close(target.published_EA_minus_endpoint_EA_J,float(row[4])*1000.-endpoint['EA_J'])
        assert bool(target.published_EA_matches_stated_stroke)==(abs(float(row[4])*1000.-truth['EA_J'])<1e-8)
        assert bool(target.published_EA_matches_archived_endpoint)==(abs(float(row[4])*1000.-endpoint['EA_J'])<1e-8)
        reported={'EA_J':row[4]*1000.,'PCF_kN':row[5],'MCF_kN':row[6],'SEA_kJ_kg':row[7],'CFE':row[8]}
        for key,value in reported.items():
            close(target['published_'+key],value);close(target['source_PL_'+key],truth[key])
            close(target[key+'_source_minus_published'],truth[key]-value)
            covered=target[key+'_lower']-1e-9<=value<=target[key+'_upper']+1e-9
            assert bool(target[key+'_published_in_interval'])==covered
    assert peakchecks==s['queries_with_exact_preserved_positive_peak']

    scatter=pd.read_csv(OUT/'repeat_scatter.csv',dtype={'configuration':str})
    for r in scatter.itertuples():
        names=[str(r.configuration)+'-'+str(i) for i in range(1,4)]
        ea=np.array([source_values[n,float(r.stroke_mm)]['EA_J'] for n in names])
        close(r.EA_mean_J,np.mean(ea));close(r.EA_sample_SD_J,np.std(ea,ddof=1))
        assert r.n==3
        assert bool(r.bound_below_sample_SD)==(r.maximum_prefix_bound_J<r.EA_sample_SD_J)
    groups=pd.read_csv(OUT/'configuration_queries.csv',dtype={'configuration':str})
    assert len(groups)==42*4
    for r in groups.itertuples():
        subset=q[(q.configuration==r.configuration)&(q.stroke_mm==r.stroke_mm)]
        assert r.specimens==len(subset)
        close(r.reference_SEA_kJ_kg,subset.reference_SEA_kJ_kg.mean())
        close(r.SEA_lower_kJ_kg,subset.SEA_lower_kJ_kg.mean());close(r.SEA_upper_kJ_kg,subset.SEA_upper_kJ_kg.mean())
    counts={}
    for filename,n in [('specimen_pairs.csv',4140),('configuration_pairs.csv',3444),('rounding_sensitivity_pairs.csv',4140)]:
        data=pd.read_csv(OUT/filename);assert len(data)==n
        resolved=data.resolved_direction!=0
        assert np.all(data.loc[resolved,'resolved_direction']==np.sign(data.loc[resolved,'reference_SEA_difference_kJ_kg']))
        expected=np.where(data.difference_lower>0,1,np.where(data.difference_upper<0,-1,0))
        assert np.array_equal(expected,data.resolved_direction)
        counts[filename]=int(resolved.sum())
    for r in q.itertuples():
        close(r.rounding_SEA_lower_kJ_kg,r.EA_lower_J/(r.mass_g+.05))
        close(r.rounding_SEA_upper_kJ_kg,r.EA_upper_J/(r.mass_g-.05))

    # Analytic positive-loading check with an unreduced peak and altered prefix.
    x=np.array([0.,1.,2.,3.]);f=np.array([0.,3.,10.,0.]);table=from_indices(x,f,[0,2,3],x_unit='mm',force_unit='kN')
    tests=client.query_metrics(table,100.,[1.5,3.])
    assert not tests[0]['peak_exact'] and tests[1]['peak_exact']
    assert tests[1]['PCF_lower_kN']==tests[1]['PCF_upper_kN']==10.
    for r in tests:
        truth=source_metrics(x,f,r['stroke_mm'],100.)
        assert r['CFE_lower']<=truth['CFE']<=r['CFE_upper']

    endpoint_cases=external[~external.published_EA_matches_stated_stroke]
    assert len(endpoint_cases)==13 and np.all(endpoint_cases.reported_stroke_mm==50.)
    assert np.all(endpoint_cases.published_EA_matches_archived_endpoint)
    assert np.max(np.abs(endpoint_cases.published_EA_minus_endpoint_EA_J))<1e-8
    coverage={key:{'covered':int(external[key+'_published_in_interval'].sum()),
                   'cases':len(external),'uncovered_specimens':external.loc[~external[key+'_published_in_interval'],'specimen'].tolist()}
              for key in ('EA_J','SEA_kJ_kg','PCF_kN','MCF_kN','CFE')}
    report={'status':'PASS','core_sha256':s['core_sha256'],'tables_hashed_and_source_verified':46,
            'client_contract_quantities_checked':clientquantities,'exact_peak_query_checks':peakchecks,
            'source_curve_metric_intervals':184*5,'configuration_records':42,'repeat_groups':2,
            'repeat_scatter_rows_independently_calculated':len(scatter),'comparison_counts':counts,
            'published_workbook_comparison':coverage,
            'source_endpoint_diagnostic':{'nominal_50mm_EA_discrepancies':13,'all_reproduced_at_archived_endpoint':True,
                                          'endpoint_range_mm':[float(endpoint_cases.archived_endpoint_mm.min()),float(endpoint_cases.archived_endpoint_mm.max())]},
            'external_comparison_scope':'Independent published crash-indicator workbook at its stated delta_max, from the same experimental dataset; not independent software adoption.',
            'outcome':'All source-reference bounds pass. The uncovered published indicator for specimen05 is retained as a source-derived-value discrepancy, not repaired by widening reconstruction bounds.'}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
