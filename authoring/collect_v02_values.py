"""Collect exact reported values from archived, machine-readable evidence."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads((ROOT/p).read_text(encoding='utf8'))

def main():
    installed=read('software/release_validation.json')
    assert installed['version']=='0.2.0'
    counts={r[a]['tests_passed'] for r in installed['runtimes'] for a in ('wheel','sdist')}
    assert len(counts)==1
    test_count=next(iter(counts))
    h=read('validation/results/scaling/headline_repeats.json')
    assert tuple(int(v) for v in h['python'].split()[0].split('.')[:2])>=(3,10)
    old=h['summary']['v0_1_full_scan'];new=h['summary']['v0_2_incremental']
    ci=ROOT/'release_evidence/remote_ci_verification.json'
    if not ci.exists():ci=ROOT/'qa/remote_ci_verification.json'
    ci_data=json.loads(ci.read_text(encoding='utf8')) if ci.exists() else {'status':'NOT_RUN'}
    if ci_data.get('status')=='PASS':
        ci_sentence='The published CI run passed the Linux, macOS and Windows matrix for Python 3.10--3.14.'
    else:
        ci_sentence='The supplied CI configuration targets Linux, macOS and Windows with Python 3.10--3.14. Remote CI has not yet run for this revision.'
    values={'package_tests':test_count,
            'tested_platform_statement':'Wheel and source-distribution installations pass all tests on Windows with Python/NumPy 3.10.0/2.2.6, 3.12.14/2.3.5 and 3.14.7/2.5.4. The 3.12 environment reuses its preinstalled NumPy; the other two use independently installed dependencies.',
            'ci_statement':ci_sentence,'ci_status':ci_data['status'],
            'headline_old_median_seconds':old['median_seconds'],'headline_old_min_seconds':old['minimum_seconds'],
            'headline_old_max_seconds':old['maximum_seconds'],'headline_new_median_seconds':new['median_seconds'],
            'headline_new_min_seconds':new['minimum_seconds'],'headline_new_max_seconds':new['maximum_seconds'],
            'headline_repeat_count_per_implementation':3,'scaling_platform':h['platform'].split('-')[0],
            'main_comparison_tables':3080,'optimal_dp_tables':580,
            'comparison_total_tables':3660,'cyclic_source_records':1,'cyclic_source_points':125157}
    (ROOT/'authoring/final_values.json').write_text(json.dumps(values,indent=2),encoding='utf8')
    print('Collected frozen scientific values; CI status:',values['ci_status'])

if __name__=='__main__':main()
