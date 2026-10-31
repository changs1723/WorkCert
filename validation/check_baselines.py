"""Independent agreements with installed third-party tolerance selectors."""
from pathlib import Path
import importlib.metadata
import itertools
import json
import numpy as np
from rdp import rdp
from simplification.cutil import simplify_coords_vw_idx
from baselines import normalized_coordinates,rdp_epsilon_indices,vw_epsilon_indices,rdp_indices,vw_indices

ROOT=Path(__file__).resolve().parents[1]

def main():
    rng=np.random.RandomState(741);rdp_count=0;vw_count=0;failures=[]
    for trial in range(20):
        x=np.r_[0.,np.cumsum(rng.uniform(.1,2.,63))];f=rng.normal(size=64)
        xn,yn=normalized_coordinates(x,f);coords=np.column_stack([xn,yn])
        for epsilon in (1e-4,1e-3,.01,.05):
            a=rdp_epsilon_indices(x,f,epsilon)
            b=np.flatnonzero(rdp(coords,epsilon=epsilon,algo='iter',return_mask=True))
            assert np.array_equal(a,b),('RDP',trial,epsilon)
            rdp_count+=1
            a=vw_epsilon_indices(x,f,epsilon)
            b=np.asarray(simplify_coords_vw_idx(coords,epsilon),dtype=int)
            if np.array_equal(a,b):vw_count+=1
            else:failures.append({'trial':trial,'epsilon':epsilon,'ours':a.tolist(),'native':b.tolist()})
        peak=int(np.argmax(abs(f)))
        for method in (rdp_indices,vw_indices):
            for k in (3,9,17,33,64):
                ids=method(x,f,k,anchors=[peak])
                assert len(ids)==k and ids[0]==0 and ids[-1]==63 and peak in ids and np.all(np.diff(ids)>0)
    report={'rdp_native_tolerance_agreements':rdp_count,'vw_native_tolerance_agreements':vw_count,
            'comparisons_per_native_method':80,'vw_disagreements':failures,
            'native_versions':{n:importlib.metadata.version(n) for n in ('rdp','simplification')},
            'fixed_budget_endpoint_peak_checks':20*2*5,
            'scope':'Native tolerance mode cross-checks; fixed-budget RDP is explicitly a best-first adaptation'}
    out=ROOT/'validation/results_v02';out.mkdir(exist_ok=True)
    (out/'third_party_validation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print({k:v for k,v in report.items() if k!='vw_disagreements'})
    print('VW disagreements:',len(failures))

if __name__=='__main__':main()
