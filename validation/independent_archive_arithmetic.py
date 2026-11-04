"""Independent scalar PL arithmetic for all saved comparison tables.

Adapted from the independent 2026-11-03 archive audit. This validator imports
no WorkCert implementation; tolerances describe scalar binary64 comparisons.
"""
from pathlib import Path
import csv,json,math,time
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT
OUTPUT=ROOT/'verification_reports'

def curve(path):
    with path.open(encoding='utf8',newline='') as s:
        rows=list(csv.reader(s))[1:]
    return [float(v[0]) for v in rows],[float(v[1]) for v in rows]

def primitive(x,f):
    values=[0.0];total=correction=0.0
    for a,b,u,v in zip(x,x[1:],f,f[1:]):
        term=(b-a)*(u+v)/2-correction
        updated=total+term;correction=(updated-total)-term;total=updated
        values.append(total)
    return values

def force_errors(x,f,ids):
    residual=[];segment=0
    for i,q in enumerate(x):
        while segment+1<len(ids)-1 and i>ids[segment+1]:segment+=1
        a,b=ids[segment:segment+2]
        reconstructed=f[a]+(f[b]-f[a])*(q-x[a])/(x[b]-x[a])
        residual.append(f[i]-reconstructed)
    d=primitive(x,residual);candidates=list(d);absolute=[]
    for i,(a,b,u,v) in enumerate(zip(x,x[1:],residual,residual[1:])):
        h=b-a
        if u*v<0:
            distance=-u*h/(v-u)
            candidates.append(d[i]+u*distance/2)
            absolute.append(abs(u)*distance/2+abs(v)*(h-distance)/2)
        else:absolute.append((abs(u)+abs(v))*h/2)
    eta=math.fsum(absolute);lo=min(candidates);hi=max(candidates)
    return dict(eta=eta,xi=(eta+abs(d[-1]))/2,prefix=max(abs(lo),abs(hi)),window=hi-lo,
                delta=max(map(abs,residual)),signed_terminal_error=d[-1],
                min_cumulative_error=lo,max_cumulative_error=hi,
                reference_work=math.fsum((b-a)*(u+v)/2 for a,b,u,v in zip(x,x[1:],f,f[1:])))

def work_only_errors(x,f,w,ids,stored):
    candidates=[];segment=0
    for i,q in enumerate(x):
        # A work-knot has two derivative limits. Use its right segment for the
        # following source cell, so an interior extremum just after the knot
        # cannot be silently omitted.
        while segment+1<len(ids)-1 and i>=ids[segment+1]:segment+=1
        a,b=ids[segment:segment+2]
        slope=(stored[segment+1]-stored[segment])/(x[b]-x[a])
        difference=w[i]-(stored[segment]+slope*(q-x[a]))
        candidates.append(difference)
        if i<len(x)-1 and i<ids[segment+1]:
            u,v=f[i]-slope,f[i+1]-slope
            if u*v<0:
                distance=-u*(x[i+1]-x[i])/(v-u)
                candidates.append(difference+u*distance/2)
    return dict(prefix_error_J=max(map(abs,candidates)),window_error_J=max(candidates)-min(candidates))

def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    started=time.monotonic();sources={};counts={'force_tables':0,'work_only_tables':0,'terminal_scalars':0}
    rows=[];worst={};failures=[]
    for filename in ('table_manifest.json','dp_table_manifest.json'):
        manifest=json.loads((SOURCE/'validation/results_v02'/filename).read_text(encoding='utf8'))['tables']
        for entry in manifest:
            ref=entry['reference']
            if ref not in sources:
                x,f=curve(SOURCE/ref);sources[ref]=(x,f,primitive(x,f))
            x,f,w=sources[ref]
            obj=json.loads((SOURCE/entry['table']).read_text(encoding='utf8'))
            if 'payload' in obj:
                p=obj['payload'];ids=p['indices'];counts['force_tables']+=1
                assert p['x']==[x[i] for i in ids] and p['force']==[f[i] for i in ids]
                expected=force_errors(x,f,ids);actual=p['certificate']
            elif 'prefix_error_J' in obj:
                counts['work_only_tables']+=1
                expected=work_only_errors(x,f,w,obj['indices'],obj['work']);actual=obj
            else:
                counts['terminal_scalars']+=1
                expected={'work_J':w[-1]};actual=obj
            for field,wanted in expected.items():
                measured=actual[field];difference=measured-wanted
                tolerance=1e-10 if field=='delta' else 1e-8
                passed=math.isfinite(measured) and abs(difference)<=tolerance
                row={'table':entry['table'],'field':field,'expected':wanted,'actual':measured,'difference':difference,'absolute_tolerance':tolerance,'status':'PASS' if passed else 'FAIL'}
                rows.append(row)
                if abs(difference)>worst.get(field,{}).get('absolute_difference',-1):worst[field]={'absolute_difference':abs(difference),'table':entry['table']}
                if not passed:failures.append(row)
    assert counts=={'force_tables':3240,'work_only_tables':350,'terminal_scalars':70}
    with (OUTPUT/'independent_arithmetic_results.csv').open('w',encoding='utf-8-sig',newline='') as s:
        writer=csv.DictWriter(s,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    report=dict(status='PASS' if not failures else 'FAIL',counts=counts,source_count=len(sources),checks=len(rows),failed_checks=len(failures),failures=failures[:30],maximum_difference_by_field=worst,seconds=time.monotonic()-started,
                oracle='Python scalar interpolation, clipped trapezoids, compensated prefix sums and internal derivative zeros; no WorkCert import; original inputs preserved',
                tolerance='Absolute 1e-8 J for real-data integral quantities and 1e-10 kN for force residual; no relative tolerance')
    (OUTPUT/'independent_arithmetic_summary.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report,indent=2))
    assert not failures, 'Independent reconstruction arithmetic did not match the frozen tables'

if __name__=='__main__':main()
