"""Reproduce selector, matched-query stopping and exact-objective comparisons."""
from pathlib import Path
import csv
import hashlib
import json
import platform
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'software/src'))
from workcert import ReducedResponse,certify,reduce_response
from baselines import rdp_indices,vw_indices

OUT=ROOT/'validation/results_v02'
TABLES=OUT/'tables'
BUDGETS=(9,17,33,65,129)
METHODS=('work','vertical','uniform_peak','uniform','rdp','vw')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf8')
def write_csv(path,rows):
    fields=list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w',newline='',encoding='utf8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
def read_reference(entry):
    p=ROOT/entry['prepared'];assert sha(p)==entry['prepared_sha256']
    with p.open(newline='',encoding='utf8') as stream:rows=list(csv.DictReader(stream))
    return np.asarray([float(r['x_mm']) for r in rows]),np.asarray([float(r['force_kN']) for r in rows])

def make_response(x,f,method,budget):
    if method not in ('rdp','vw'):
        return reduce_response(x,f,method=method,max_points=budget,preserve_peak=method!='uniform',
                               peak_mode='absolute',x_unit='mm',force_unit='kN')
    peak=int(np.argmax(np.abs(f)))
    ids=(rdp_indices if method=='rdp' else vw_indices)(x,f,budget,anchors=[peak])
    return ReducedResponse(x[ids],f[ids],ids,certify(x,f,ids),x_unit='mm',force_unit='kN',
                           metadata={'selection_method':method,'peak_mode':'absolute','preserve_peak':True,
                                     'coordinate_normalization':'unit range on each axis',
                                     'benchmark_selector':True,'requested_max_points':budget})

def primitive(x,f,q):
    h=np.diff(x);node=np.r_[0.,np.cumsum(h*(f[:-1]+f[1:])*.5)]
    j=np.clip(np.searchsorted(x,q,side='right')-1,0,len(x)-2);t=np.asarray(q)-x[j]
    return node[j]+f[j]*t+(f[j+1]-f[j])/h[j]*t*t*.5

def work_only(x,f,ids,reference_hash):
    w=np.r_[0.,np.cumsum(np.diff(x)*(f[:-1]+f[1:])*.5)]
    qx=x[ids];qw=w[ids];r=w-np.interp(x,qx,qw)
    lo=float(np.min(r));hi=float(np.max(r))
    cell=np.clip(np.searchsorted(qx,x[:-1],side='right')-1,0,len(qx)-2)
    slope=np.diff(qw)[cell]/np.diff(qx)[cell]
    for j in range(len(x)-1):
        df=f[j+1]-f[j]
        if df:
            t=(slope[j]-f[j])/df
            if 0<t<1:
                value=r[j]+(x[j+1]-x[j])*(t*(f[j]-slope[j])+.5*df*t*t)
                lo=min(lo,float(value));hi=max(hi,float(value))
    payload={'schema':'workcert.benchmark-work-only/2.0','x':qx.tolist(),'work':qw.tolist(),
             'indices':ids.tolist(),'units':{'x':'mm','work':'J'},'reference_sha256':reference_hash,
             'prefix_error_J':max(abs(lo),abs(hi)),'window_error_J':hi-lo,
             'capability':'work_queries_only'}
    return payload,qx,qw

def main():
    OUT.mkdir(exist_ok=True)
    for category in ('fixed','tolerance','terminal','optimal'):(TABLES/category).mkdir(parents=True,exist_ok=True)
    core_start=sha(ROOT/'software/src/workcert/core.py')
    inventory=json.loads((ROOT/'data/metadata/reference_audit.json').read_text())['curves']
    fixed=[];tol=[];terminal=[];manifest=[]
    for entry in inventory:
        x,f=read_reference(entry);n=len(x);full=certify(x,f,np.arange(n))
        work=abs(full.reference_work);assert work>0
        q=np.linspace(x[0],x[-1],501);rng=np.random.RandomState(741)
        ab=np.sort(rng.uniform(x[0],x[-1],(1000,2)),axis=1)
        truth=primitive(x,f,q);truth_window=primitive(x,f,ab[:,1])-primitive(x,f,ab[:,0])
        for budget in BUDGETS:
            uniform_ids=None
            for method in METHODS:
                start=time.perf_counter();rep=make_response(x,f,method,budget);seconds=time.perf_counter()-start
                c=rep.certificate;slack=work*1e-10+1e-10
                assert np.max(abs(rep.work(q)-truth))<=c.prefix+slack
                assert np.max(abs(rep.window_work(ab[:,0],ab[:,1])-truth_window))<=c.window+slack
                assert c.prefix<=c.window+slack and c.window<=c.xi+slack and c.xi<=c.eta+slack
                if method!='uniform':assert int(np.argmax(abs(f))) in rep.indices
                p=TABLES/'fixed'/(entry['curve']+'__'+method+'__'+str(budget)+'.json');rep.save(p)
                row={'curve':entry['curve'],'dataset':entry['dataset'],'method':method,'budget':budget,
                     'points':len(rep.x),'reference_points':n,'reference_work_J':work,'eta_J':c.eta,'xi_J':c.xi,
                     'prefix_error_J':c.prefix,'window_error_J':c.window,'delta_kN':c.delta,
                     'eta_percent':100*c.eta/work,'prefix_error_percent':100*c.prefix/work,
                     'window_error_percent':100*c.window/work,'signed_terminal_error_J':c.signed_terminal_error,
                     'peak_magnitude_error_kN':float(abs(np.max(abs(f))-np.max(abs(rep.force)))),
                     'force_queries_supported':True,'serialized_bytes':p.stat().st_size,'build_seconds_descriptive':seconds,
                     'table':p.relative_to(ROOT).as_posix(),'sha256':sha(p)}
                fixed.append(row)
                manifest.append({'table':row['table'],'sha256':row['sha256'],'reference':entry['prepared'],'reference_sha256':entry['prepared_sha256']})
                if method=='uniform':uniform_ids=rep.indices
            payload,qx,qw=work_only(x,f,uniform_ids,full.reference_sha256)
            p=TABLES/'fixed'/(entry['curve']+'__work_only__'+str(budget)+'.json');p.write_bytes(dump(payload))
            assert np.max(abs(np.interp(q,qx,qw)-truth))<=payload['prefix_error_J']+slack
            assert np.max(abs((np.interp(ab[:,1],qx,qw)-np.interp(ab[:,0],qx,qw))-truth_window))<=payload['window_error_J']+slack
            fixed.append({'curve':entry['curve'],'dataset':entry['dataset'],'method':'work_only','budget':budget,'points':len(qx),
                          'reference_points':n,'reference_work_J':work,'prefix_error_J':payload['prefix_error_J'],
                          'window_error_J':payload['window_error_J'],'prefix_error_percent':100*payload['prefix_error_J']/work,
                          'window_error_percent':100*payload['window_error_J']/work,'force_queries_supported':False,
                          'serialized_bytes':p.stat().st_size,'table':p.relative_to(ROOT).as_posix(),'sha256':sha(p)})
            manifest.append({'table':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'reference':entry['prepared'],'reference_sha256':entry['prepared_sha256']})
        for method in ('work','vertical'):
            for measure in ('eta','xi','prefix','window'):
                rep=reduce_response(x,f,method=method,max_points=n,tolerance=.01,certificate=measure,relative=True,
                                    peak_mode='absolute',x_unit='mm',force_unit='kN')
                assert rep.metadata['tolerance_met'] and rep.certificate.bound(measure,True)<=.01
                p=TABLES/'tolerance'/(entry['curve']+'__'+method+'__'+measure+'.json');rep.save(p)
                tol.append({'curve':entry['curve'],'dataset':entry['dataset'],'method':method,'measure':measure,
                            'relative_tolerance':.01,'points':len(rep.x),'eta_percent':rep.certificate.bound('eta',True)*100,
                            'prefix_error_percent':rep.certificate.bound('prefix',True)*100,
                            'window_error_percent':rep.certificate.bound('window',True)*100,'tolerance_met':True,
                            'table':p.relative_to(ROOT).as_posix(),'sha256':sha(p)})
                manifest.append({'table':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'reference':entry['prepared'],'reference_sha256':entry['prepared_sha256']})
        p=TABLES/'terminal'/(entry['curve']+'.json')
        p.write_bytes(dump({'kind':'terminal_work_scalar','domain_mm':[float(x[0]),float(x[-1])],'work_J':full.reference_work,
                            'capability':'one_terminal_work_query_only','reference_sha256':full.reference_sha256}))
        terminal.append({'curve':entry['curve'],'dataset':entry['dataset'],'work_J':full.reference_work,'serialized_bytes':p.stat().st_size})
        manifest.append({'table':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'reference':entry['prepared'],'reference_sha256':entry['prepared_sha256']})
        print('Selectors/stopping:',entry['curve'],flush=True)
    assert sha(ROOT/'software/src/workcert/core.py')==core_start,'Core changed during benchmark'
    write_csv(OUT/'selector_metrics.csv',fixed);write_csv(OUT/'stopping_metrics.csv',tol);write_csv(OUT/'terminal_controls.csv',terminal)
    (OUT/'table_manifest.json').write_text(json.dumps({'tables':manifest},indent=2),encoding='utf8')
    summary=summarize(fixed,tol)
    summary.update(core_sha256=core_start,protocol_sha256=sha(ROOT/'validation/baselines_protocol.txt'),
                   python=platform.python_version(),numpy=np.__version__,fixed_force_cases=2100,work_only_cases=350,
                   tolerance_cases=len(tol),terminal_controls=len(terminal),actual_tables=len(manifest),all_bound_checks_pass=True)
    (OUT/'comparative_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    if (OUT/'dp_solutions.json').exists():finish_dp(fixed,manifest)
    print(json.dumps(summary['ALL'],indent=2),flush=True)

def summarize(fixed,tol):
    summary={}
    for dataset in ['ALL','CX_steel','EDAH','PLA_plus']:
        rows=[r for r in fixed if dataset=='ALL' or r['dataset']==dataset]
        at33=[r for r in rows if r['budget']==33]
        item={'records':len({r['curve'] for r in rows}),'at33':{},'stopping_1percent':{}}
        for method in (*METHODS,'work_only'):
            these=[r for r in at33 if r['method']==method]
            item['at33'][method]={key:float(np.median([r[key] for r in these])) for key in ('prefix_error_percent','window_error_percent','serialized_bytes')}
            if method!='work_only':item['at33'][method]['eta_percent']=float(np.median([r['eta_percent'] for r in these]))
        paired={}
        curves=sorted({r['curve'] for r in at33})
        for left,right in [('work','vertical'),('work','rdp'),('work','vw'),('vertical','rdp'),('vertical','vw'),('work','uniform_peak')]:
            lookup={(r['curve'],r['method']):r for r in at33}
            a=np.asarray([lookup[c,left]['prefix_error_percent'] for c in curves]);b=np.asarray([lookup[c,right]['prefix_error_percent'] for c in curves])
            paired[left+'_vs_'+right]={'lower_prefix_error':int(np.sum(a<b)),'equal_within_1e_12_percent':int(np.sum(abs(a-b)<1e-12)),
                                     'records':len(a),'median_prefix_error_ratio':float(np.median(a/b))}
        item['paired']=paired
        for method in ('work','vertical'):
            item['stopping_1percent'][method]={measure:{'median':float(np.median([r['points'] for r in tol if r['method']==method and r['measure']==measure and (dataset=='ALL' or r['dataset']==dataset)])),
                                                      'min':min(r['points'] for r in tol if r['method']==method and r['measure']==measure and (dataset=='ALL' or r['dataset']==dataset)),
                                                      'max':max(r['points'] for r in tol if r['method']==method and r['measure']==measure and (dataset=='ALL' or r['dataset']==dataset))} for measure in ('eta','xi','prefix','window')}
        summary[dataset]=item
    return summary

def finish_dp(fixed=None,manifest=None):
    if fixed is None:
        with (OUT/'selector_metrics.csv').open(newline='',encoding='utf8') as stream:fixed=list(csv.DictReader(stream))
        fixed=[{k:(int(v) if k=='budget' else float(v) if k in ('eta_J','delta_kN') and v else v) for k,v in r.items()} for r in fixed]
    solutions=json.loads((OUT/'dp_solutions.json').read_text(encoding='utf8'))
    inventory={r['curve']:r for r in json.loads((ROOT/'data/metadata/reference_audit.json').read_text())['curves']}
    bycurve={};rows=[];gaps=[];paths=[]
    for solution in solutions:
        name=solution['curve'];entry=inventory[name]
        if name not in bycurve:bycurve[name]=read_reference(entry)
        x,f=bycurve[name];ids=np.asarray(solution['indices'],dtype=np.int64);c=certify(x,f,ids)
        actual=c.eta if solution['objective']=='eta' else c.delta
        assert abs(actual-solution['optimal_cost'])<=max(1.,actual)*1e-10
        rep=ReducedResponse(x[ids],f[ids],ids,c,x_unit='mm',force_unit='kN',metadata={'selection_method':'exact_dp_'+solution['objective'],'peak_mode':'absolute'})
        p=TABLES/'optimal'/(name+'__'+solution['objective']+'__'+str(solution['budget'])+'.json');rep.save(p)
        rows.append({k:v for k,v in solution.items() if k!='indices'}|{'eta_J':c.eta,'delta_kN':c.delta,'prefix_error_percent':100*c.prefix/abs(c.reference_work),
                    'window_error_percent':100*c.window/abs(c.reference_work),'table':p.relative_to(ROOT).as_posix(),'sha256':sha(p)})
        paths.append({'table':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'reference':entry['prepared'],'reference_sha256':entry['prepared_sha256']})
        key='eta_J' if solution['objective']=='eta' else 'delta_kN'
        for r in fixed:
            if r['curve']==name and r['budget']==solution['budget'] and r['method'] in ('work','vertical','rdp','vw','uniform_peak'):
                numerator=float(r[key]);denominator=solution['optimal_cost']
                assert numerator+max(1.,denominator)*1e-10>=denominator
                gaps.append({'curve':name,'dataset':entry['dataset'],'objective':solution['objective'],'method':r['method'],'budget':solution['budget'],
                             'greedy_cost':numerator,'optimal_cost':denominator,'ratio':numerator/denominator if denominator else None})
    write_csv(OUT/'dp_metrics.csv',rows);write_csv(OUT/'optimality_gaps.csv',gaps)
    (OUT/'dp_table_manifest.json').write_text(json.dumps({'tables':paths},indent=2),encoding='utf8')
    summary={}
    for objective in ('eta','vertical'):
        summary[objective]={}
        for budget in BUDGETS:
            summary[objective][str(budget)]={}
            for method in ('work','vertical','rdp','vw','uniform_peak'):
                a=[r['ratio'] for r in gaps if r['objective']==objective and r['budget']==budget and r['method']==method and r['ratio'] is not None]
                summary[objective][str(budget)][method]={'records':len(a),'median_ratio':float(np.median(a)),'maximum_ratio':float(np.max(a))}
    (OUT/'dp_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    cohorts={}
    for dataset in ('CX_steel','PLA_plus'):
        cohorts[dataset]={}
        for objective in ('eta','vertical'):
            cohorts[dataset][objective]={}
            for budget in BUDGETS:
                cohorts[dataset][objective][str(budget)]={}
                for method in ('work','vertical','rdp','vw','uniform_peak'):
                    a=[r['ratio'] for r in gaps if r['dataset']==dataset and r['objective']==objective and r['budget']==budget and r['method']==method and r['ratio'] is not None]
                    cohorts[dataset][objective][str(budget)][method]={'records':len(a),'median_ratio':float(np.median(a)),'maximum_ratio':float(np.max(a))}
    (OUT/'dp_cohort_summary.json').write_text(json.dumps(cohorts,indent=2),encoding='utf8')
    print('DP objective checks/tables:',len(rows),'matched greedy objective ratios:',len(gaps),flush=True)

if __name__=='__main__':
    if '--finish-dp' in sys.argv:finish_dp()
    else:main()
