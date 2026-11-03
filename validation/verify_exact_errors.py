"""Read-only numerical audit with exact rational quadrature and path coverage."""
from pathlib import Path
from fractions import Fraction as Q
import hashlib
import itertools
import json
import os
import subprocess
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'software/src'))
from workcert import certify,reduce_response,from_indices,split_monotone_branches
from workcert import core


def exact_errors(x,f,ids):
    """Rational independent cell integration, including interior stationary points."""
    x=list(map(Q,x));f=list(map(Q,f));ids=list(ids)
    residual=[];j=0
    for i,t in enumerate(x):
        while j+1<len(ids)-1 and i>ids[j+1]:j+=1
        a,b=ids[j],ids[j+1]
        chord=f[a]+(t-x[a])*(f[b]-f[a])/(x[b]-x[a])
        residual.append(f[i]-chord)
    d=Q(0);areas=Q(0);extrema=[Q(0)]
    for i in range(len(x)-1):
        a,b=residual[i:i+2];h=x[i+1]-x[i]
        if a*b<0:
            t=-a/(b-a)
            extrema.append(d+h*t*a/2)
            areas+=h*(abs(a)*t+abs(b)*(1-t))/2
        else:areas+=h*(abs(a)+abs(b))/2
        d+=h*(a+b)/2;extrema.append(d)
    lo,hi=min(extrema),max(extrema)
    return [float(v) for v in [areas,(areas+abs(d))/2,max(abs(lo),abs(hi)),hi-lo,max(map(abs,residual)),d,lo,hi]]


def check_tree(node):
    if node is None:return 0,[],core._ZERO
    hl,kl,sl=check_tree(node.left);hr,kr,sr=check_tree(node.right)
    assert abs(hl-hr)<=1 and node.height==1+max(hl,hr)
    assert (not kl or max(kl)<node.key) and (not kr or min(kr)>node.key)
    flat=core._concatenate(core._concatenate(sl,node.value),sr)
    np.testing.assert_allclose(node.total,flat,atol=1e-12,rtol=1e-12)
    return node.height,kl+[node.key]+kr,flat


def main():
    rng=np.random.default_rng(20261031)
    counts={};maxdiff=0.0
    for _ in range(40):
        x=np.r_[0,np.cumsum(rng.integers(1,5,6))]
        f=rng.integers(-20,21,7)
        for mask in range(1<<5):
            ids=[0]+[i+1 for i in range(5) if mask>>i&1]+[6]
            c=certify(x,f,ids)
            got=np.asarray([c.eta,c.xi,c.prefix,c.window,c.delta,c.signed_terminal_error,c.min_cumulative_error,c.max_cumulative_error])
            wanted=np.asarray(exact_errors(x.tolist(),f.tolist(),ids))
            maxdiff=max(maxdiff,float(np.max(np.abs(got-wanted))))
            np.testing.assert_allclose(got,wanted,rtol=2e-13,atol=2e-12)
    counts['exact_rational_vertex_subsets']=40*32
    # Independent flat left-fold checks during randomized AVL insertions and deletions.
    tree=None;values={};ops=0
    for key in rng.permutation(500):
        endpoint=float(rng.normal());lo=min(0.,endpoint)-float(rng.random());hi=max(0.,endpoint)+float(rng.random())
        value=(float(rng.uniform(1,5)),endpoint,lo,hi,float(rng.random()))
        values[int(key)]=value;tree=core._put(tree,int(key),value);check_tree(tree)
        expected=core._ZERO
        for k in sorted(values):expected=core._concatenate(expected,values[k])
        np.testing.assert_allclose(tree.total,expected,atol=2e-12,rtol=2e-12);ops+=1
    for key in rng.permutation(500):
        del values[int(key)];tree=core._delete(tree,int(key));check_tree(tree)
        expected=core._ZERO
        for k in sorted(values):expected=core._concatenate(expected,values[k])
        np.testing.assert_allclose(tree.total if tree else core._ZERO,expected,atol=2e-12,rtol=2e-12);ops+=1
    counts['AVL_insert_delete_and_flat_fold_checks']=ops
    # Compare tolerance stopping with the full fixed-budget sequence, preserving
    # the actual greedy tie conventions but evaluating stopping independently.
    stopping=0
    for _ in range(16):
        n=int(rng.integers(8,29));x=np.cumsum(rng.uniform(.05,2,n));f=rng.normal(0,4,n)
        for method in ('work','vertical'):
            sequence=[reduce_response(x,f,method=method,max_points=k,preserve_peak=False) for k in range(2,n+1)]
            for kind in ('eta','xi','prefix','window'):
                candidates=np.asarray([t.certificate.bound(kind) for t in sequence])
                positive=candidates[candidates>1e-10]
                tolerance=float(np.median(positive)*.71)
                first=next(i+2 for i,c in enumerate(candidates) if c<=tolerance)
                t=reduce_response(x,f,method=method,max_points=n,preserve_peak=False,tolerance=tolerance,certificate=kind)
                assert len(t.x)==first and t.metadata['tolerance_met']
                assert t.certificate==certify(x,f,t.indices);stopping+=1
    counts['independent_full_sequence_stopping_checks']=stopping
    # Random integer walks include exact dwells, reversals and both force signs.
    branch_cases=0;covered_edges=0;max_pathdiff=0.
    for _ in range(100):
        dx=rng.integers(-3,4,60);x=np.r_[0,np.cumsum(dx)];f=rng.integers(-15,16,len(x))
        series=split_monotone_branches(x,f)
        seen=np.zeros(len(x)-1,dtype=int);branch_work=0.
        for b in series.branches:
            ids=b.source_indices
            assert np.all(np.diff(b.x)>0)
            for a,z in zip(ids[:-1],ids[1:]):seen[min(a,z)]+=1
            t=from_indices(b.x,b.force,np.arange(len(b.x)))
            branch_work+=b.directed_work(t)
            if len(b.x)>2:
                reduced=reduce_response(b.x,b.force,method='work',max_points=2,preserve_peak=False)
                for q in np.linspace(b.x[0],b.x[-1],11):
                    error=b.directed_work(t,q)-b.directed_work(reduced,q)
                    assert abs(error)<=reduced.certificate.window+1e-11
        for e in series.events:
            assert e.source_end==e.source_start+1 and x[e.source_start]==x[e.source_end]
            seen[e.source_start]+=1
        assert np.all(seen==1)
        wanted=float(sum(Q(int(dx[i]))*Q(int(f[i]+f[i+1]),2) for i in range(len(dx))))
        assert branch_work==wanted==series.reference_work
        max_pathdiff=max(max_pathdiff,abs(branch_work-wanted));branch_cases+=1;covered_edges+=len(dx)
    counts['random_chronological_paths']=branch_cases;counts['chronological_edges_checked']=covered_edges
    # Magnitude/positive/negative peak choices, with no sign conversion.
    x=np.arange(8.);f=np.array([0,-11,3,-5,8,-1,2,0.])
    for mode,index in [('absolute',1),('positive',4),('negative',1)]:
        t=reduce_response(x,f,method='work',max_points=3,peak_mode=mode)
        assert index in t.indices and t.x_unit==t.force_unit=='unspecified'
        np.testing.assert_array_equal(t.force,f[t.indices])
    counts['signed_peak_modes']=3
    env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'software/src')
    # This audit checks the original installation baseline separately. Additional
    # installed-package acceptance is run by run_hou_acceptance.py; unrestricted
    # discovery here would silently change the historical baseline count.
    baseline_code=("import sys, unittest; "
                   "loader=unittest.TestLoader(); suite=unittest.TestSuite(); "
                   "[suite.addTests(loader.discover('tests', pattern=p)) for p in "
                   "('test_workcert.py','test_revision.py','test_interop.py','test_round2.py')]; "
                   "r=unittest.TextTestRunner(verbosity=2).run(suite); "
                   "sys.exit(0 if r.wasSuccessful() and not r.skipped else 1)")
    tests=subprocess.run([sys.executable,'-c',baseline_code],cwd=ROOT/'software',env=env,capture_output=True,text=True)
    expected_tests=json.loads((ROOT/'software/release_validation.json').read_text(encoding='utf8'))['runtimes'][0]['wheel']['tests_passed']
    assert tests.returncode==0 and ('Ran %d tests'%expected_tests) in tests.stderr
    (ROOT/'validation/results_v02/independent_package_tests.log').write_text(tests.stdout+'\n'+tests.stderr,encoding='utf8')
    report={'status':'PASS','python':sys.version,'numpy':np.__version__,'reviewed_core_sha256':hashlib.sha256((ROOT/'software/src/workcert/core.py').read_bytes()).hexdigest(),
            'counts':counts,'package_tests_passed':expected_tests,'maximum_rational_oracle_absolute_difference':maxdiff,
            'maximum_integer_path_work_difference':max_pathdiff,
            'scope':'Independent rational integration, AVL structural/aggregate checks, full-sequence stopping and directed chronological path coverage; source files not altered.'}
    (ROOT/'validation/results_v02/reconstruction_verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
