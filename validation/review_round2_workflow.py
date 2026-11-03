"""Specimen-aware table exchange and independent published-indicator checks.

The existing workflow_results directory remains the preceding numerical case.
This revision distinguishes configurations from replicate specimens, compares
reconstruction with observed replicate scatter, and uses tighter peak bounds.
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
from workcert import ReducedResponse, reduce_response, __version__
from user_workflow import primitive, prefix_peak

OUT=ROOT/'validation/workflow_results_round2'
STROKES=(10.,20.,30.,40.)
GROUPS=('STWC','N-SCMC')
TOLERANCE=1.
CAP=129


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def numpy_json(value):
    if isinstance(value,np.generic):return value.item()
    raise TypeError('Unsupported JSON value: '+type(value).__name__)


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False,default=numpy_json)+'\n',encoding='utf8')


def consumer():
    spec=importlib.util.spec_from_file_location('workcert_round2_client',ROOT/'examples/query_exchange.py')
    client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
    return client.query_metrics


def configuration(specimen):
    for name in GROUPS:
        if specimen.startswith(name+'-'):return name
    assert specimen in {'%02d'%i for i in range(1,41)},specimen
    return specimen


def source_rows():
    path=ROOT/'data/raw/pla_v7p6y654ft_v4/Mass_and_Crash_Indicators.xlsx'
    w=openpyxl.load_workbook(path,read_only=True,data_only=True)
    rows=[r for r in w.active.values if isinstance(r[1],(int,float))]
    w.close();assert len(rows)==46
    metadata=json.loads((ROOT/'data/metadata/mendeley_v7p6y654ft_v4.json').read_text(encoding='utf8'))
    assert '40' in metadata['description'] and 'Latin Hypercube' in metadata['description']
    return path,rows


def independent_reference(x,f,q,mass):
    """Trapezoidal integral clipped exactly at q, independent of query routine."""
    j=np.searchsorted(x,q,side='left')
    xx=np.r_[x[:j],q];ff=np.r_[f[:j],np.interp(q,x,f)]
    work=float(np.sum(np.diff(xx)*(ff[1:]+ff[:-1])*.5))
    peak=float(np.max(ff));span=q-x[0]
    return {'EA_J':work,'SEA_kJ_kg':work/mass,'MCF_kN':work/span,
            'PCF_kN':peak,'CFE':work/span/peak}


def check_intervals(client,reference):
    for key in ('EA_J','SEA_kJ_kg','MCF_kN','PCF_kN','CFE'):
        stem=key.split('_',1)[0]
        unit=key[len(stem):]
        lower=client[stem+'_lower'+unit];upper=client[stem+'_upper'+unit]
        if lower is None or upper is None:raise AssertionError('Expected finite '+key+' bounds')
        assert lower-1e-9<=reference[key]<=upper+1e-9,(key,reference[key],lower,upper)


def comparisons(records,grouped=False):
    results=[]
    for stroke in STROKES:
        entries=[r for r in records if r['stroke_mm']==stroke]
        for i,a in enumerate(entries):
            for b in entries[i+1:]:
                difference=a['reference_SEA_kJ_kg']-b['reference_SEA_kJ_kg']
                lo=a['SEA_lower_kJ_kg']-b['SEA_upper_kJ_kg']
                hi=a['SEA_upper_kJ_kg']-b['SEA_lower_kJ_kg']
                direction=1 if lo>0 else (-1 if hi<0 else 0)
                if direction:assert direction==int(np.sign(difference))
                results.append({'stroke_mm':stroke,'id_a':a['configuration' if grouped else 'specimen'],
                                'id_b':b['configuration' if grouped else 'specimen'],
                                'same_configuration':a['configuration']==b['configuration'],
                                'reference_SEA_difference_kJ_kg':difference,'difference_lower':lo,
                                'difference_upper':hi,'resolved_direction':direction,
                                'interpretation':'Numerical reference comparison at fixed reported masses'})
    return results


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    mass_path,published=source_rows();query_metrics=consumer()
    queries=[];external=[];manifest=[];sources=[];old_width=[]
    references={};tables={};mass_map={}
    for row in published:
        specimen=str(row[0]);group=configuration(specimen);mass=float(row[1]);stroke=float(row[2])
        path=ROOT/'data/prepared'/('PLA_'+specimen+'.csv')
        d=pd.read_csv(path,float_precision='round_trip');x=d.x_mm.to_numpy();f=d.force_kN.to_numpy()
        assert max(STROKES)<=stroke<=x[-1]
        references[specimen]=(x,f);mass_map[specimen]=mass
        table=reduce_response(x,f,max_points=CAP,tolerance=TOLERANCE,certificate='window',relative=False,
            method='work',peak_mode='absolute',x_unit='mm',force_unit='kN',
            provenance={'specimen':specimen,'configuration':group,'source_doi':'10.17632/v7p6y654ft.4',
                        'prepared_csv_sha256':sha(path),'mass_workbook_sha256':sha(mass_path),'mass_g':mass})
        p=OUT/'tables'/(specimen+'.json');p.parent.mkdir(parents=True,exist_ok=True);table.save(p)
        table=ReducedResponse.load(p);assert table.verify_reference(x,f);tables[specimen]=table
        manifest.append({'specimen':specimen,'configuration':group,'points':len(table.x),
                         'tolerance_met':table.metadata['tolerance_met'],'table':p.relative_to(ROOT).as_posix(),
                         'sha256':sha(p),'reference_sha256':sha(path)})
        received=query_metrics(table,mass,STROKES)
        for q in received:
            truth=independent_reference(x,f,q['stroke_mm'],mass);check_intervals(q,truth)
            old_p=table.certificate.delta
            q['old_CFE_lower']=(q['EA_J']-table.certificate.prefix)/q['stroke_mm']/(q['PCF_kN']+old_p)
            q['old_CFE_upper']=(q['EA_J']+table.certificate.prefix)/q['stroke_mm']/(q['PCF_kN']-old_p)
            old_width.append((q['old_CFE_upper']-q['old_CFE_lower'],q['CFE_upper']-q['CFE_lower']))
            queries.append({'specimen':specimen,'configuration':group,'mass_g':mass,**q,
                            **{'reference_'+k:v for k,v in truth.items()},
                            'EA_error_J':abs(q['EA_J']-truth['EA_J']),
                            'prefix_bound_J':table.certificate.prefix,
                            'rounding_SEA_lower_kJ_kg':q['EA_lower_J']/(mass+.05),
                            'rounding_SEA_upper_kJ_kg':q['EA_upper_J']/(mass-.05),
                            'mass_rounding_halfwidth_g':.05})
        q=query_metrics(table,mass,[stroke])[0];truth=independent_reference(x,f,stroke,mass)
        check_intervals(q,truth)
        source={'EA_J':float(row[4])*1000.,'PCF_kN':float(row[5]),'MCF_kN':float(row[6]),
                'SEA_kJ_kg':float(row[7]),'CFE':float(row[8])}
        endpoint_ea=independent_reference(x,f,float(x[-1]),mass)['EA_J']
        entry={'specimen':specimen,'configuration':group,'reported_stroke_mm':stroke,
               'archived_endpoint_mm':float(x[-1]),'endpoint_offset_mm':float(x[-1])-stroke,
               'source_PL_EA_at_archived_endpoint_J':endpoint_ea,
               'published_EA_minus_endpoint_EA_J':source['EA_J']-endpoint_ea,
               'published_EA_matches_stated_stroke':abs(source['EA_J']-truth['EA_J'])<1e-8,
               'published_EA_matches_archived_endpoint':abs(source['EA_J']-endpoint_ea)<1e-8,
               'mass_g':mass,'peak_exact':q['peak_exact'],'prefix_bound_J':table.certificate.prefix}
        for key,value in source.items():
            stem=key.split('_',1)[0];unit=key[len(stem):]
            lower=q[stem+'_lower'+unit];upper=q[stem+'_upper'+unit]
            entry.update({'published_'+key:value,'source_PL_'+key:truth[key],'reduced_'+key:q[key],
                          key+'_lower':lower,key+'_upper':upper,
                          key+'_source_minus_published':truth[key]-value,
                          key+'_published_in_interval':lower-1e-9<=value<=upper+1e-9})
        external.append(entry)
        sources.append({'specimen':specimen,'configuration':group,'mass_g':mass,'assessment_stroke_mm':stroke,
                        'archived_endpoint_mm':float(x[-1]),'source_csv_sha256':sha(path)})

    groups=[];scatter=[]
    for stroke in STROKES:
        at=[r for r in queries if r['stroke_mm']==stroke]
        for group in sorted({r['configuration'] for r in at}):
            members=[r for r in at if r['configuration']==group]
            groups.append({'configuration':group,'stroke_mm':stroke,'specimens':len(members),
                           'reference_SEA_kJ_kg':float(np.mean([r['reference_SEA_kJ_kg'] for r in members])),
                           'reduced_SEA_kJ_kg':float(np.mean([r['SEA_kJ_kg'] for r in members])),
                           'SEA_lower_kJ_kg':float(np.mean([r['SEA_lower_kJ_kg'] for r in members])),
                           'SEA_upper_kJ_kg':float(np.mean([r['SEA_upper_kJ_kg'] for r in members])),
                           'sample_SD_SEA_kJ_kg':float(np.std([r['reference_SEA_kJ_kg'] for r in members],ddof=1)) if len(members)>1 else None})
            if len(members)>1:
                ea=np.array([r['reference_EA_J'] for r in members]);sea=np.array([r['reference_SEA_kJ_kg'] for r in members])
                sd=float(np.std(ea,ddof=1));bound=max(r['prefix_bound_J'] for r in members)
                scatter.append({'configuration':group,'stroke_mm':stroke,'n':len(members),
                                'EA_mean_J':float(np.mean(ea)),'EA_sample_SD_J':sd,
                                'EA_sample_CV_percent':sd/float(np.mean(ea))*100.,
                                'EA_sample_range_J':float(np.ptp(ea)),
                                'SEA_mean_kJ_kg':float(np.mean(sea)),
                                'SEA_sample_SD_kJ_kg':float(np.std(sea,ddof=1)),
                                'maximum_prefix_bound_J':bound,
                                'maximum_actual_EA_error_J':max(r['EA_error_J'] for r in members),
                                'bound_to_sample_SD_ratio':bound/sd,
                                'bound_below_sample_SD':bound<sd,
                                'actual_error_below_sample_SD':max(r['EA_error_J'] for r in members)<sd})
    specimen_pairs=comparisons(queries);group_pairs=comparisons(groups,grouped=True)
    rounded=[dict(r,SEA_lower_kJ_kg=r['rounding_SEA_lower_kJ_kg'],SEA_upper_kJ_kg=r['rounding_SEA_upper_kJ_kg']) for r in queries]
    rounded_pairs=comparisons(rounded)
    assert len(specimen_pairs)==4140 and len(group_pairs)==3444
    assert sum(r['same_configuration'] for r in specimen_pairs)==24
    for name,rows in [('queries',queries),('configuration_queries',groups),('repeat_scatter',scatter),
                      ('published_indicator_comparison',external),('source_mapping',sources),
                      ('specimen_pairs',specimen_pairs),('configuration_pairs',group_pairs),
                      ('rounding_sensitivity_pairs',rounded_pairs)]:
        pd.DataFrame(rows).to_csv(OUT/(name+'.csv'),index=False)
    source_diffs={key:{'maximum_absolute_difference':max(abs(v[key+'_source_minus_published']) for v in external),
                       'median_absolute_difference':float(np.median([abs(v[key+'_source_minus_published']) for v in external])),
                       'published_covered':sum(v[key+'_published_in_interval'] for v in external),'cases':len(external)}
                  for key in ('EA_J','SEA_kJ_kg','PCF_kN','MCF_kN','CFE')}
    widths=np.array(old_width)
    endpoint_cases=[r for r in external if not r['published_EA_matches_stated_stroke']]
    assert len(endpoint_cases)==13
    assert all(r['reported_stroke_mm']==50. and r['published_EA_matches_archived_endpoint'] for r in endpoint_cases)
    summary={'software_version':__version__,'core_sha256':sha(ROOT/'software/src/workcert/core.py'),
             'client_sha256':sha(ROOT/'examples/query_exchange.py'),
             'source_workbook':mass_path.relative_to(ROOT).as_posix(),'source_workbook_sha256':sha(mass_path),
             'source_dataset_doi':'10.17632/v7p6y654ft.4','associated_paper_doi':'10.1515/mt-2026-0038',
             'source_description_url':'https://data.mendeley.com/datasets/v7p6y654ft/4',
             'specimens':46,'configurations':42,'singleton_LHS_configurations':40,
             'triplicate_configurations':['STWC','N-SCMC'],'reference_nodes':46000,
             'interval_budget_J':TOLERANCE,'point_cap':CAP,'retained_nodes':sum(r['points'] for r in manifest),
             'median_retained_nodes':float(np.median([r['points'] for r in manifest])),
             'tables_unmet_tolerance':sum(not r['tolerance_met'] for r in manifest),'table_manifest':manifest,
             'client_queries':len(queries),'queries_with_exact_preserved_positive_peak':sum(r['peak_exact'] for r in queries),
             'maximum_actual_EA_error_J':max(r['EA_error_J'] for r in queries),
             'all_reconstruction_intervals_contain_reference':True,
             'published_indicator_crosscheck':source_diffs,
             'published_indicator_queries_with_exact_peak':sum(r['peak_exact'] for r in external),
             'published_endpoint_diagnostic':{'cases_with_nonzero_nominal_stroke_EA_discrepancy':len(endpoint_cases),
                 'specimens':[r['specimen'] for r in endpoint_cases],
                 'reported_stroke_mm':50.,
                 'archived_endpoint_range_mm':[min(r['archived_endpoint_mm'] for r in endpoint_cases),max(r['archived_endpoint_mm'] for r in endpoint_cases)],
                 'maximum_published_minus_archived_endpoint_EA_absolute_J':max(abs(r['published_EA_minus_endpoint_EA_J']) for r in endpoint_cases),
                 'remaining_cases_match_stated_delta_max':46-len(endpoint_cases),
                 'interpretation':'All thirteen nominal-50mm EA discrepancies reproduce the integral to the archived endpoint. Strict reported-stroke coverage is retained without substituting the query endpoint or changing the workbook MCF denominator.'},
             'specimen_comparisons':{'all_pairs':len(specimen_pairs),'same_configuration_pairs':24,
                                     'numerically_resolved':sum(r['resolved_direction']!=0 for r in specimen_pairs),
                                     'interpretation':'Comparisons of supplied numerical specimen records, not 46 distinct designs'},
             'configuration_comparisons':{'pairs':len(group_pairs),'numerically_resolved':sum(r['resolved_direction']!=0 for r in group_pairs),
                                          'aggregation':'Arithmetic means for the two triplicate controls; singleton values for 40 LHS configurations',
                                          'statistical_claim':'Reference reconstruction only; no uncertainty is estimated for singleton designs'},
             'repeat_scatter':{'rows':scatter,'bound_below_sample_SD_cases':sum(r['bound_below_sample_SD'] for r in scatter),
                               'actual_error_below_sample_SD_cases':sum(r['actual_error_below_sample_SD'] for r in scatter),
                               'scope':'Descriptive sample SD at each common stroke for two n=3 control configurations; no population confidence claim or transfer to singleton designs'},
             'mass_rounding_sensitivity':{'halfwidth_g':.05,'assumption':'Rounding to the nearest 0.1 g, inferred only as a sensitivity scenario from reported decimals; not an instrument-uncertainty model',
                                           'numerically_resolved_pairs_with_rounding':sum(r['resolved_direction']!=0 for r in rounded_pairs),
                                           'maximum_relative_SEA_halfwidth_percent':max(.05/(r['mass_g']-.05)*100 for r in queries)},
             'CFE_interval_refinement':{'exact_peak_queries':sum(r['peak_exact'] for r in queries),
                                         'median_old_width':float(np.median(widths[:,0])),
                                         'median_new_width':float(np.median(widths[:,1])),
                                         'all_new_widths_at_most_old':bool(np.all(widths[:,1]<=widths[:,0]+1e-14))},
             'interpretation':'A documented public-dataset reuse workflow. No external software adoption or experimentally meaningful ordering of arbitrarily close specimens is claimed.'}
    write_json(OUT/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('table_manifest','repeat_scatter')},indent=2,default=numpy_json))


if __name__=='__main__':main()
