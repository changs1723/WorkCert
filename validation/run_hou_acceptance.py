"""Run original installation checks and independent Hou-role acceptance separately.

Use an installed WorkCert 0.2.0 environment; never inject src into sys.path.
Outputs are a new auditable run directory. Does not rebuild benchmark results.
"""
import argparse
import csv
import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ['test_workcert.py','test_revision.py','test_interop.py','test_round2.py']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AuditResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.cases=[]

    def addSuccess(self,test):
        super().addSuccess(test)
        self.cases.append(dict(test=test.id(),status='PASS',detail=''))

    def addFailure(self,test,err):
        super().addFailure(test,err)
        self.cases.append(dict(test=test.id(),status='FAIL',detail=self._exc_info_to_string(err,test)))

    def addError(self,test,err):
        super().addError(test,err)
        self.cases.append(dict(test=test.id(),status='ERROR',detail=self._exc_info_to_string(err,test)))

    def addSkip(self,test,reason):
        super().addSkip(test,reason)
        self.cases.append(dict(test=test.id(),status='SKIP',detail=reason))

    def addSubTest(self,test,subtest,err):
        super().addSubTest(test,subtest,err)
        if err is not None:
            status='FAIL' if issubclass(err[0],test.failureException) else 'ERROR'
            self.cases.append(dict(test=subtest.id(),status=status,detail=self._exc_info_to_string(err,test)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['baseline','independent','all'],default='all')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    if (out/'summary.json').exists() or (out/'results.jsonl').exists():
        parser.error('Choose a new output directory; existing audit runs are immutable')
    import numpy
    import workcert
    meta=dict(timestamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
              command=[sys.executable,*sys.argv],python=sys.version,python_executable=sys.executable,
              platform=platform.platform(),numpy=numpy.__version__,numpy_path=numpy.__file__,
              workcert=workcert.__version__,distribution_version=importlib.metadata.version('workcert'),
              import_path=workcert.__file__,research_root=str(ROOT),source_hashes={},test_hashes={})
    for source in (ROOT/'software/src/workcert').glob('*.py'):
        installed=Path(workcert.__file__).with_name(source.name)
        meta['source_hashes'][source.name]=dict(workspace=sha(source),installed=sha(installed))
    for source in sorted((ROOT/'software/tests').glob('*.py')):
        meta['test_hashes'][source.name]=sha(source)
    for path in ['validation/run_hou_acceptance.py','examples/query_exchange.py','examples/compose_branch_errors.py']:
        meta['test_hashes'][path]=sha(ROOT/path)
    (out/'environment.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8')
    if 'site-packages' not in workcert.__file__ or any(v['workspace']!=v['installed'] for v in meta['source_hashes'].values()):
        raise RuntimeError('Acceptance requires installed package matching all workspace runtime files')
    os.environ['WORKCERT_RESEARCH_ROOT']=str(ROOT)
    os.environ['HOU_RESULTS_JSONL']=str(out/'results.jsonl')
    phases=['baseline','independent'] if args.phase=='all' else [args.phase]
    summary=dict(status='PASS',authorship='Codex acting in the Hou acceptance role; human sign-off not asserted',
                 remote_ci='NOT_RUN_LOCALLY',tests_run=0,total_checks=0,failed_checks=0)
    cases=[]
    for phase in phases:
        suite=unittest.TestSuite()
        patterns=BASELINE if phase=='baseline' else ['test_hou_*.py']
        for pattern in patterns:
            suite.addTests(unittest.TestLoader().discover(str(ROOT/'software/tests'),pattern=pattern))
        count=suite.countTestCases()
        if (phase=='baseline' and count!=39) or (phase=='independent' and count==0):
            raise RuntimeError('Unexpected '+phase+' discovery count: '+str(count))
        with (out/(phase+'.log')).open('w',encoding='utf8') as log:
            log.write(json.dumps(meta,indent=2)+'\n');log.flush()
            result=unittest.TextTestRunner(stream=log,verbosity=2,resultclass=AuditResult).run(suite)
        status='PASS' if result.wasSuccessful() and not result.skipped else 'FAIL'
        summary[phase]=dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),status=status)
        summary['tests_run']+=result.testsRun
        if status!='PASS':summary['status']='FAIL'
        # Surface the actual traceback in CI, as well as keeping the full
        # immutable log artifact. A bare exit code hides the failing assertion.
        if status!='PASS':
            for case in result.cases:
                if case['status']!='PASS':
                    print(case['status']+': '+case['test']+'\n'+case['detail'],flush=True)
        cases.extend(dict(phase=phase,**row) for row in result.cases)
        print(phase+': '+json.dumps(summary[phase]),flush=True)
    with (out/'case_summary.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=['phase','test','status','detail'])
        writer.writeheader();writer.writerows(cases)
    if (out/'results.jsonl').exists():
        rows=[json.loads(line) for line in (out/'results.jsonl').read_text(encoding='utf8').splitlines()]
        with (out/'results.csv').open('w',newline='',encoding='utf-8-sig') as stream:
            writer=csv.DictWriter(stream,fieldnames=['test','check','expected','actual','difference','atol','rtol','tolerance','status'])
            writer.writeheader();writer.writerows(rows)
        summary['total_checks']=len(rows)
        summary['failed_checks']=sum(row['status']!='PASS' for row in rows)
        if summary['failed_checks']:summary['status']='FAIL'
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    print(json.dumps(summary,indent=2))
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':
    sys.exit(main())
