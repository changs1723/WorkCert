"""Exact fixed-vertex dynamic programming for two specified objectives.

Edge areas are continuous absolute residual integrals in the original units.
The additive-area objective is NOT a global prefix-work objective. The second
objective is the maximum vertical residual. Runtime is O(n^3 + K n^2), memory
O(n^2 + K n), with Numba used only as an optional benchmark accelerator.
"""
from pathlib import Path
import csv
import hashlib
import itertools
import json
import platform
import time
import numpy as np
try:
    from numba import njit
except ImportError:
    def njit(*args,**kwargs):
        return args[0] if args and callable(args[0]) else lambda f:f

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/results_v02'
BUDGETS=(9,17,33,65,129)


@njit(cache=True)
def edge_costs(x,f):
    n=len(x);area=np.full((n,n),np.inf);vertical=np.full((n,n),np.inf)
    for a in range(n-1):
        area[a,a+1]=0.;vertical[a,a+1]=0.
        for b in range(a+2,n):
            slope=(f[b]-f[a])/(x[b]-x[a]);s=0.;v=0.;left=0.
            for j in range(a,b):
                right=0. if j+1==b else f[j+1]-f[a]-slope*(x[j+1]-x[a])
                aa=abs(left);bb=abs(right);h=x[j+1]-x[j]
                if (left<0 and right>0) or (left>0 and right<0):
                    scale=max(aa,bb);u=aa/scale;w=bb/scale
                    s+=.5*h*scale*(u*u+w*w)/(u+w)
                else:s+=.5*h*(aa+bb)
                v=max(v,aa,bb);left=right
            area[a,b]=s;vertical[a,b]=v
    return area,vertical


@njit(cache=True)
def solve_dp(cost,max_points,peak,additive):
    n=len(cost);maximum=min(max_points,n)
    values=np.full((maximum+1,n),np.inf)
    parents=np.full((maximum+1,n),-1,dtype=np.int32);values[1,0]=0.
    for k in range(2,maximum+1):
        for b in range(k-1,n):
            best=np.inf;arg=-1
            for a in range(k-2,b):
                if a<peak and peak<b:continue
                candidate=values[k-1,a]+cost[a,b] if additive else max(values[k-1,a],cost[a,b])
                if candidate<best:best=candidate;arg=a
            values[k,b]=best;parents[k,b]=arg
    return values,parents


def recover(parents,budget):
    path=[parents.shape[1]-1]
    for k in range(budget,1,-1):
        point=int(parents[k,path[-1]])
        if point<0:raise ValueError('Infeasible vertex budget')
        path.append(point)
    return list(reversed(path))


def brute_force_check():
    rng=np.random.RandomState(741)
    checked=0
    for trial in range(8):
        x=np.r_[0.,np.cumsum(rng.uniform(.1,2.,7))];f=rng.normal(size=8)
        peak=int(np.argmax(np.abs(f)));a,v=edge_costs(x,f)
        for objective,cost,additive in [('eta',a,True),('vertical',v,False)]:
            values,parents=solve_dp(cost,6,peak,additive)
            for k in range(max(2,3 if 0<peak<len(x)-1 else 2),7):
                alternatives=[]
                for inside in itertools.combinations(range(1,len(x)-1),k-2):
                    ids=[0,*inside,len(x)-1]
                    if peak not in ids:continue
                    edges=[cost[i,j] for i,j in zip(ids[:-1],ids[1:])]
                    alternatives.append(sum(edges) if additive else max(edges))
                assert np.isclose(values[k,-1],min(alternatives),rtol=2e-12,atol=2e-12)
                ids=recover(parents,k);assert len(ids)==k and peak in ids
                checked+=1
    return checked


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    checked=brute_force_check();print('Brute-force DP comparisons:',checked,flush=True)
    inventory=json.loads((ROOT/'data/metadata/reference_audit.json').read_text())['curves']
    rows=[];eligible=[];excluded=[]
    for record in inventory:
        if record['points']>1000:
            excluded.append({'curve':record['curve'],'points':record['points'],'reason':'Original reference exceeds predefined n<=1000 exact-DP ceiling'})
            continue
        path=ROOT/record['prepared']
        with path.open(newline='',encoding='utf8') as stream:
            data=list(csv.DictReader(stream))
        x=np.asarray([float(r['x_mm']) for r in data]);f=np.asarray([float(r['force_kN']) for r in data])
        start=time.perf_counter();a,v=edge_costs(x,f);edge_seconds=time.perf_counter()-start
        peak=int(np.argmax(np.abs(f)))
        solutions={}
        for objective,cost,additive in [('eta',a,True),('vertical',v,False)]:
            start=time.perf_counter();values,parents=solve_dp(cost,max(BUDGETS),peak,additive);dp_seconds=time.perf_counter()-start
            for budget in BUDGETS:
                ids=recover(parents,budget)
                rows.append({'curve':record['curve'],'dataset':record['dataset'],'reference_points':len(x),
                             'objective':objective,'budget':budget,'optimal_cost':float(values[budget,-1]),
                             'indices':ids,'edge_cost_seconds':edge_seconds,'dp_all_budgets_seconds':dp_seconds,
                             'reference_csv_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        eligible.append({'curve':record['curve'],'dataset':record['dataset'],'points':len(x),'edge_cost_seconds':edge_seconds})
        print(record['curve'],len(x),'edges %.3fs'%edge_seconds,flush=True)
        (OUT/'dp_solutions.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
    import numba
    report={'status':'PASS','objective_scope':['minimum continuous absolute-area residual eta','minimum maximum vertical residual'],
            'prefix_or_window_global_optimality_claimed':False,'budgets':list(BUDGETS),'eligibility_ceiling':1000,
            'eligible_records':eligible,'excluded_records':excluded,'brute_force_comparisons':checked,
            'python':platform.python_version(),'numpy':np.__version__,'numba':numba.__version__,
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'dp_verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('Completed DP records:',len(eligible),'solutions:',len(rows),flush=True)

if __name__=='__main__':main()
