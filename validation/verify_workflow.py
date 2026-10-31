"""Read-only audit of saved public-data workflow outputs and source links."""
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
from workcert import ReducedResponse

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    out=ROOT/'validation/workflow_results'
    summary=json.loads((out/'summary_all.json').read_text(encoding='utf8'))
    assert summary['core_sha256']==sha(ROOT/'software/src/workcert/core.py')
    pla=summary['pla_exchange'];case=out/'pla_exchange'
    mass=ROOT/pla['mass_source'];assert sha(mass)==pla['mass_workbook_sha256']
    references={}
    for entry in pla['table_manifest']:
        source=ROOT/'data/prepared'/('PLA_'+entry['curve']+'.csv')
        if entry['curve'] not in references:
            d=pd.read_csv(source,float_precision='round_trip')
            references[entry['curve']]=(d.x_mm.to_numpy(),d.force_kN.to_numpy())
        table=ROOT/entry['table'];assert sha(table)==entry['sha256']
        response=ReducedResponse.load(table)
        assert response.verify_reference(*references[entry['curve']])
        assert len(response.x)==entry['points'] and response.metadata['tolerance_met']==entry['tolerance_met']
    for stage in pla['stages']:
        data=pd.read_csv(case/('queries_stage_%d.csv'%stage['stage']))
        assert len(data)==184 and np.all(data.EA_absolute_error_J<=data.EA_bound_J+1e-8)
        assert np.all(data.reference_CFE>=data.CFE_lower-1e-9) and np.all(data.reference_CFE<=data.CFE_upper+1e-9)
        pairs=pd.read_csv(case/('pairs_stage_%d.csv'%stage['stage']))
        resolved=pairs.resolved_direction!=0
        assert np.all(pairs.loc[resolved,'resolved_direction']==pairs.loc[resolved,'reference_direction'])
        assert int(resolved.sum())==stage['resolved_pairs']
    spec=importlib.util.spec_from_file_location('workcert_exchange_client',ROOT/'examples/query_exchange.py')
    client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
    initial=pd.read_csv(case/'queries_stage_0.csv',dtype={'curve':str})
    quantities={'EA_J':'reduced_EA_J','SEA_kJ_kg':'reduced_SEA_kJ_kg','MCF_kN':'reduced_MCF_kN',
                'PCF_kN':'reduced_PCF_kN','CFE':'reduced_CFE','CFE_lower':'CFE_lower','CFE_upper':'CFE_upper'}
    checked=0;client_maximum_difference=0.
    for curve,group in initial.groupby('curve'):
        table=ReducedResponse.load(case/'tables/stage_0'/(curve+'.json'))
        received=client.query_metrics(table,float(group.mass_g.iloc[0]),group.stroke_mm.to_numpy())
        for value,(_,producer) in zip(received,group.iterrows()):
            for consumer_key,producer_key in quantities.items():
                difference=abs(value[consumer_key]-float(producer[producer_key]))
                assert difference<1e-10
                client_maximum_difference=max(client_maximum_difference,difference);checked+=1
    final=pd.read_csv(case/'pairs_after_scalar_followup.csv')
    assert len(final)==pla['query_specific_followup']['total_pairs']
    assert np.all(final.resolved_direction==final.reference_direction)
    cyclic=summary['cyclic_path'];folder=ROOT/'data/extended/cyclic_RHS_10829958'
    manifest=json.loads((folder/'download_manifest.json').read_text())
    source=folder/'cyclic_RHS.xlsx'
    assert sha(source)==cyclic['source_xlsx_sha256']==manifest['sha256']
    assert 'md5:'+hashlib.md5(source.read_bytes()).hexdigest()==manifest['repository_checksum']
    w=openpyxl.load_workbook(source,read_only=True,data_only=True)
    values=np.asarray([(r[1],r[2]) for r in w['S1_L1'].iter_rows(min_row=4,values_only=True)
                       if isinstance(r[1],(float,int)) and isinstance(r[2],(float,int))],dtype=float)
    w.close();assert len(values)==cyclic['source_points']
    path=np.load(out/'cyclic_path/chronological_path.npz')
    assert np.array_equal(values[:,0],path['displacement_mm']) and np.array_equal(values[:,1],path['reference_force_kN'])
    direct=float(np.sum(np.diff(values[:,0])*(values[:-1,1]+values[1:,1])*.5))
    assert direct==cyclic['reference_signed_path_work_J']
    branches=pd.read_csv(out/'cyclic_path/branch_metrics.csv');assert len(branches)==cyclic['branches']
    for record in branches.itertuples():
        table=ROOT/record.table;assert sha(table)==record.sha256
        response=ReducedResponse.load(table)
        ids=np.arange(record.source_first,record.source_last+1)
        if record.direction<0:ids=ids[::-1]
        assert response.verify_reference(values[ids,0],values[ids,1])
    assert cyclic['maximum_continuous_chronological_work_error_J']<=cyclic['sum_branch_window_bounds_J']+1e-8
    result={'status':'PASS','core_sha256':summary['core_sha256'],
            'preprocessing_sha256':sha(ROOT/'software/src/workcert/preprocessing.py'),
            'PLA_tables_hashed_and_source_verified':len(pla['table_manifest']),
            'cyclic_tables_hashed_and_source_verified':len(branches),'cyclic_samples_linked_to_original_XLSX':len(values),
            'all_metric_intervals_and_resolved_orderings_verified':True,'source_license':'CC BY 4.0',
            'independent_client_quantities_checked':checked,'maximum_client_producer_difference':client_maximum_difference,
            'output_policy':'Read-only numerical audit; only this verification record is written'}
    (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
