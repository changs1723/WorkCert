"""Verify table hashes and small-n optimality with independent full certificates."""
from pathlib import Path
import hashlib
import itertools
import json
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/results_v02'
sys.path.insert(0,str(ROOT/'software/src'))
from workcert import certify
from optimal_dp import edge_costs,solve_dp,recover

def main():
    manifests=[json.loads((OUT/name).read_text())['tables'] for name in ('table_manifest.json','dp_table_manifest.json')]
    paths=set()
    for rows in manifests:
        for row in rows:
            assert row['table'] not in paths;paths.add(row['table'])
            assert hashlib.sha256((ROOT/row['table']).read_bytes()).hexdigest()==row['sha256']
            assert hashlib.sha256((ROOT/row['reference']).read_bytes()).hexdigest()==row['reference_sha256']
    assert len(paths)==3544
    rng=np.random.RandomState(741);edge_checks=0;objective_checks=0;candidate_checks=0
    for trial in range(8):
        x=np.r_[0.,np.cumsum(rng.uniform(.1,2.,7))];f=rng.normal(size=8)
        peak=int(np.argmax(abs(f)));area,vertical=edge_costs(x,f)
        for a in range(7):
            for b in range(a+1,8):
                c=certify(x[a:b+1],f[a:b+1],np.array([0,b-a]))
                assert np.isclose(area[a,b],c.eta,atol=2e-12,rtol=2e-12)
                assert np.isclose(vertical[a,b],c.delta,atol=2e-12,rtol=2e-12)
                edge_checks+=1
        for objective,cost,additive in [('eta',area,True),('delta',vertical,False)]:
            dp,parent=solve_dp(cost,6,peak,additive)
            for k in range(3 if 0<peak<7 else 2,7):
                best=np.inf
                for inside in itertools.combinations(range(1,7),k-2):
                    ids=np.array([0,*inside,7])
                    if peak not in ids:continue
                    c=certify(x,f,ids);actual=c.eta if objective=='eta' else c.delta
                    best=min(best,actual);candidate_checks+=1
                assert np.isclose(dp[k,-1],best,atol=2e-12,rtol=2e-12)
                chosen=np.asarray(recover(parent,k));c=certify(x,f,chosen)
                assert np.isclose(c.eta if objective=='eta' else c.delta,best,atol=2e-12,rtol=2e-12)
                objective_checks+=1
    report={'status':'PASS','actual_tables_hashed':len(paths),'reference_hashes_checked':len(paths),
            'edge_cost_pairs_checked_against_global_certificate':edge_checks,
            'brute_force_full_certificate_candidates':candidate_checks,
            'optimal_objectives_checked_against_full_certificate_enumeration':objective_checks,
            'objective_scope':['eta','maximum vertical residual'],'prefix_or_window_optimality_claimed':False,
            'core_sha256':hashlib.sha256((ROOT/'software/src/workcert/core.py').read_bytes()).hexdigest(),
            'baseline_selector_sha256':hashlib.sha256((ROOT/'validation/baselines.py').read_bytes()).hexdigest()}
    (OUT/'independent_extended_verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
