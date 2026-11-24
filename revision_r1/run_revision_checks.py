"""Read-only verification of the R1 overlay and its fixed original inputs.

    python -B revision_r1/run_revision_checks.py --output ../r1_checks

The output must be outside the source root and must not already contain files.
All recomputation uses a temporary copy inside that output. Source hashes are
checked again even after failure. --remeasure explicitly repeats timing work;
otherwise recorded durations are checked arithmetically without new timings.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import datetime
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
from statistics import median
import subprocess
import sys
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE_MANIFEST_SHA256 = '763e4ce0f340c5b57bd16fd12a8bf3f50153c7aa65369183ea66db7290e4963e'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                  allow_nan=False) + '\n', encoding='utf8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def read_csv(path):
    with Path(path).open(encoding='utf8', newline='') as stream:
        return list(csv.DictReader(stream))


def snapshot(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symbolic links are outside this archive contract: ' + str(path))
        if path.is_file():
            result[path.relative_to(root).as_posix()] = {'bytes': path.stat().st_size,
                                                       'sha256': sha(path)}
    return result


def manifest_entries(path):
    entries = {}
    for line in path.read_text(encoding='utf8').splitlines():
        if not line.strip():
            continue
        if len(line) < 67 or line[64:66] != '  ':
            raise ValueError('Invalid SHA256 manifest line in ' + str(path))
        digest, name = line[:64], line[66:]
        relative = PurePosixPath(name)
        if (not re.fullmatch(r'[0-9a-f]{64}', digest) or relative.is_absolute()
                or '..' in relative.parts or '\\' in name or ':' in name
                or name in entries or str(relative) != name):
            raise ValueError('Unsafe or duplicate manifest path: ' + name)
        entries[name] = digest
    if not entries:
        raise ValueError('Empty manifest: ' + str(path))
    return entries


def validate_manifests(before, development):
    base_path = ROOT / 'MANIFEST.sha256'
    if sha(base_path) != BASE_MANIFEST_SHA256:
        raise ValueError('The fixed original article manifest has changed')
    base = manifest_entries(base_path)
    original_actual = {name for name in before
                       if name != 'MANIFEST.sha256' and not name.startswith('revision_r1/')}
    if set(base) != original_actual:
        raise ValueError('Original input file set differs: missing=' +
                         repr(sorted(set(base)-original_actual)[:10]) + ' extra=' +
                         repr(sorted(original_actual-set(base))[:10]))
    for name, expected in base.items():
        if before[name]['sha256'] != expected:
            raise ValueError('Original source file changed: ' + name)
    revision_path = HERE / 'MANIFEST.sha256'
    result = {'original': {'status': 'PASS', 'payload_files': len(base),
                          'manifest_sha256': BASE_MANIFEST_SHA256}}
    if not revision_path.exists():
        if not development:
            raise ValueError('Missing revision_r1/MANIFEST.sha256; --development is only for an unsealed candidate')
        result['revision'] = {'status': 'UNSEALED_DEVELOPMENT_ONLY',
                              'reason': 'R1 manifest not yet generated'}
        return result
    revision = manifest_entries(revision_path)
    # All executed R1 code and every compared scientific result must be sealed.
    # Unlisted local correspondence may coexist, but cannot supply audit inputs.
    required = {
        'run_revision_checks.py', 'checked_cyclic_path.py',
        'test_checked_cyclic_path.py', 'test_exchange_benchmark.py',
        'recompute_cyclic_recovery.py', 'audit_protocols.py', 'benchmark_exchange.py',
        'README_reproduction.txt', 'requirements-r1.txt',
        'results/exchange_summary.json', 'results/exchange_per_curve.csv',
        'results/exchange_individual_timings.csv',
        'results/exchange_worker_1.json', 'results/exchange_worker_2.json',
        'results/exchange_worker_3.json', 'results/protocol_audit.json',
        'results/protocol_workbook_aligned.csv', 'results/protocol_stopping_cases.csv',
        'results/cyclic_recovery_summary.json',
        'results/cyclic_checked_manifest_before.json', 'results/cyclic_checked_manifest_after.json',
        'results/cyclic_path_assessment_before.json', 'results/cyclic_path_assessment_after.json',
        'results/cyclic_branch_2533_recovered.json',
    }
    if required - set(revision):
        raise ValueError('R1 manifest must cover all executed code and compared data: ' +
                         repr(sorted(required - set(revision))))
    actual = {name[len('revision_r1/'):] for name in before
              if name.startswith('revision_r1/') and name != 'revision_r1/MANIFEST.sha256'}
    if set(revision)-actual:
        raise ValueError('R1 manifest member missing: ' + repr(sorted(set(revision)-actual)[:10]))
    for name, expected in revision.items():
        if before['revision_r1/' + name]['sha256'] != expected:
            raise ValueError('R1 file differs from its manifest: ' + name)
    result['revision'] = {'status': 'PASS', 'payload_files': len(revision),
                          'manifest_sha256': sha(revision_path),
                          'coverage_mode': 'listed_scientific_files_only',
                          'required_execution_and_comparison_members': len(required),
                          'unlisted_files': sorted(actual-set(revision)),
                          'scope': 'Every listed scientific member is verified. Local editorial extras are reported, not covered by this manifest. All actual files remain in the before/after identity check.'}
    return result


def equal_number(actual, expected, label):
    if not math.isfinite(float(actual)) or not math.isfinite(float(expected)):
        raise ValueError('Nonfinite saved value: ' + label)
    if float(actual) != float(expected):
        raise ValueError('Saved arithmetic mismatch: ' + label)


def validate_saved_timings(root):
    """Independent arithmetic on saved measurements, with no clocks or writes."""
    results = root / 'revision_r1/results'
    summary = read_json(results / 'exchange_summary.json')
    workers = [read_json(results / f'exchange_worker_{i}.json') for i in (1, 2, 3)]
    cases = read_csv(results / 'exchange_per_curve.csv')
    timings = read_csv(results / 'exchange_individual_timings.csv')
    inventory = read_json(root / 'data/metadata/reference_audit.json')['curves']
    expected_names = {entry['curve'] for entry in inventory}
    if len(cases) != 70 or {r['curve'] for r in cases} != expected_names:
        raise ValueError('Exchange cases do not cover the 70 reference records exactly')
    if len(timings) != summary['timing_samples']:
        raise ValueError('Saved timing row count differs')
    expected_runtime = {p.relative_to(root).as_posix(): sha(p)
                        for p in sorted((root / 'software/src/workcert').glob('*.py'))}
    duration_index = {}
    for row in timings:
        key = (row['curve'], row['representation'], row['operation'], int(row['worker']))
        value = float(row['milliseconds'])
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Nonpositive or nonfinite saved duration')
        duration_index.setdefault(key, []).append(value)
    for i, worker in enumerate(workers, 1):
        if worker['worker'] != i or worker['runtime_sha256'] != expected_runtime:
            raise ValueError('Worker identity or runtime fingerprint mismatch')
        if worker['script_sha256'] != sha(root / 'revision_r1/benchmark_exchange.py'):
            raise ValueError('Measurement script fingerprint mismatch')
        if len(worker['curves']) != 70 or {r['curve'] for r in worker['curves']} != expected_names:
            raise ValueError('Incomplete or duplicate worker population')
    if summary['runtime_sha256'] != expected_runtime:
        raise ValueError('Summary runtime fingerprint mismatch')
    if summary['script_sha256'] != sha(root / 'revision_r1/benchmark_exchange.py'):
        raise ValueError('Summary measurement-script fingerprint mismatch')
    stages = 0
    for case in cases:
        originals = [next(r for r in worker['curves'] if r['curve'] == case['curve']) for worker in workers]
        entry = next(e for e in inventory if e['curve'] == case['curve'])
        if case['dataset'] != entry['dataset'] or int(case['reference_points']) != entry['points']:
            raise ValueError('Reference cohort or length mismatch')
        if int(case['retained_points']) != 33:
            raise ValueError('The fixed-count exchange comparison must retain 33 nodes')
        if case['prepared_sha256'] != sha(root / entry['prepared']):
            raise ValueError('Prepared source fingerprint mismatch')
        for key in ('reduced_json_sha256', 'dense_schema_json_sha256', 'dense_minimal_json_sha256'):
            if {row[key] for row in originals} != {case[key]}:
                raise ValueError('Serialized identity changes between workers')
        for representation, operation in (('reduced','load'),('full_schema','load'),('raw_dense','load'),
                ('reduced','prefix'),('full_schema','prefix'),('reduced','window'),('full_schema','window')):
            per_process = []
            suffix = operation if operation == 'load' else operation + '_10000'
            key = representation + '_' + suffix + '_median_ms'
            for i, original in enumerate(originals, 1):
                samples = duration_index[(case['curve'], representation, operation, i)]
                if len(samples) != 5:
                    raise ValueError('Expected five timed samples per main operation')
                value = median(samples)
                equal_number(value, original[key], 'worker median ' + key)
                per_process.append(value)
            equal_number(median(per_process), case[key], 'case median ' + key)
            equal_number(min(per_process), case[key.replace('_median_ms', '_process_min_ms')], 'case minimum')
            equal_number(max(per_process), case[key.replace('_median_ms', '_process_max_ms')], 'case maximum')
            stages += 1
        for operation in ('load', 'prefix_10000', 'window_10000'):
            ratio = float(case['full_schema_' + operation + '_median_ms']) / float(case['reduced_' + operation + '_median_ms'])
            equal_number(ratio, case['dense_to_reduced_' + operation + '_time_ratio'], 'within-curve ratio')
    cohort_checks = 0
    for cohort, group in summary['cohorts'].items():
        selected = cases if cohort == 'ALL' else [case for case in cases if case['dataset'] == cohort]
        if len(selected) != group['curves']:
            raise ValueError('Cohort population differs')
        for name, metrics in group['metrics'].items():
            values = [float(case[name]) for case in selected]
            for statistic, value in [('median',median(values)),('minimum',min(values)),('maximum',max(values))]:
                equal_number(value, metrics[statistic], cohort + '/' + name + '/' + statistic)
                cohort_checks += 1
    for representation in ('reduced', 'full_schema'):
        for key, column in [('query_locations',representation + '_observed_queries'),
                            ('fallback_queries',representation + '_fallback_queries')]:
            equal_number(sum(int(case[column]) for case in cases), summary['natural_fallback'][representation][key], key)
    for case in summary['fallback_stress']:
        points = case['retained_points']
        originals = [next(row for row in worker['fallback'] if row['retained_points'] == points) for worker in workers]
        if (case['fallback_queries'] != case['queries_in_batch'] or case['actual_work_J'] != 2e-100
                or case['diagnostic_fallback_bypassed_work_J'] != 0. or case['reconstruction_window_error_J'] != 0.):
            raise ValueError('Fallback diagnostic result differs')
        for metric, repetitions in [('enabled_median_ms','enabled_repeats_ms'),
                                    ('diagnostic_bypassed_median_ms','diagnostic_bypassed_repeats_ms')]:
            values = []
            for original in originals:
                if len(original[repetitions]) != 3:
                    raise ValueError('Fallback timing must contain three repetitions')
                equal_number(median(original[repetitions]), original[metric], 'fallback worker median')
                values.append(original[metric])
            for statistic, value in [('median',median(values)),('minimum',min(values)),('maximum',max(values))]:
                equal_number(value, case[metric][statistic], 'fallback aggregate')
    return {'status':'PASS', 'measurement_mode':'verify saved duration arithmetic; no remeasurement',
            'source_records':len(cases),'individual_timing_rows':len(timings),
            'case_median_chains':stages,'cohort_statistic_checks':cohort_checks,
            'fallback_fixture_sizes':[row['retained_points'] for row in summary['fallback_stress']]}


def run_script(script, root, output, label, arguments=()):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    command = [sys.executable, '-B', str(script), *map(str, arguments)]
    process = subprocess.run(command, cwd=root, env=env, capture_output=True)
    (output / (label + '.log')).write_bytes(process.stdout + process.stderr)
    if process.returncode:
        raise RuntimeError(label + ' failed; see ' + str(output / (label + '.log')))
    text = (process.stdout + process.stderr).decode('utf8', errors='replace')
    match = re.search(r'Ran (\d+) tests? in', text)
    result = {'status':'PASS','exit_code':process.returncode,'log':label + '.log'}
    if match:
        if re.search(r'OK\s*\(skipped=', text):
            raise RuntimeError('Skipped tests are not accepted for ' + label)
        result['test_methods_run'] = int(match.group(1))
    return result


def compare_recomputation(source, copy, output):
    results = source / 'revision_r1/results'
    recomputed = copy / 'revision_r1/results'
    protocol = read_json(recomputed / 'protocol_audit.json')
    saved = read_json(results / 'protocol_audit.json')
    for document in (protocol, saved):
        for key in ('python', 'openpyxl'):
            document.pop(key, None)
    if protocol != saved:
        raise ValueError('Protocol recomputation differs from saved scientific results')
    cyclic = read_json(recomputed / 'cyclic_recovery_summary.json')
    saved_cyclic = read_json(results / 'cyclic_recovery_summary.json')
    for document in (cyclic, saved_cyclic):
        for key in ('python','numpy'):
            document.pop(key, None)
    if cyclic != saved_cyclic:
        raise ValueError('Cyclic recovery differs from saved scientific results')
    for name in ('protocol_workbook_aligned.csv','protocol_stopping_cases.csv',
                 'cyclic_checked_manifest_before.json','cyclic_checked_manifest_after.json',
                 'cyclic_path_assessment_before.json','cyclic_path_assessment_after.json',
                 'cyclic_branch_2533_recovered.json'):
        if sha(results / name) != sha(recomputed / name):
            raise ValueError('Recomputed case file differs: ' + name)
    destination = output / 'recomputed_results'
    destination.mkdir()
    for name in ('protocol_audit.json', 'protocol_workbook_aligned.csv',
                 'protocol_stopping_cases.csv', 'cyclic_recovery_summary.json',
                 'cyclic_checked_manifest_before.json', 'cyclic_checked_manifest_after.json',
                 'cyclic_path_assessment_before.json', 'cyclic_path_assessment_after.json',
                 'cyclic_branch_2533_recovered.json'):
        shutil.copy2(recomputed / name, destination / name)
    return {'status':'PASS','protocol_scientific_fields_match':True,
            'workbook_metric_rows':len(read_csv(recomputed/'protocol_workbook_aligned.csv')),
            'stopping_cases':len(read_csv(recomputed/'protocol_stopping_cases.csv')),
            'independent_scalar_field_checks':protocol['stopping']['independent_scalar_field_checks'],
            'stopping_failures':protocol['stopping']['failures'],
            'cyclic_source_reference_verifications':cyclic['source_reference_verifications'],
            'cyclic_all_local_budgets_met':cyclic['after']['tolerance_met'],
            'cyclic_recovered_total_nodes':cyclic['after']['retained_nodes']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--development', action='store_true', help='Explicitly allow only a missing R1 manifest; not a release pass')
    parser.add_argument('--remeasure', action='store_true', help='Repeat performance measurements in the disposable copy')
    parser.add_argument('--keep-work-copy', action='store_true', help='Keep the isolated copy for a later document build')
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or output.is_relative_to(ROOT) or ROOT.is_relative_to(output):
        parser.error('Choose an output directory outside, and not an ancestor of, the source root')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error('Output already exists and is not an empty directory')
    output.mkdir(parents=True, exist_ok=True)
    report = {'status':'RUNNING','source_root':str(ROOT),'output_root':str(output),
              'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'python':sys.version,'remeasure_requested':args.remeasure,
              'development_requested':args.development,'steps':{}}
    before = None
    work = output / 'working_copy' / 'source'
    try:
        before = snapshot(ROOT)
        dump(output / 'source_identity_before.json', before)
        report['manifests'] = validate_manifests(before, args.development)
        report['steps']['saved_measurement_arithmetic'] = validate_saved_timings(ROOT)
        shutil.copytree(ROOT, work)
        copied = snapshot(work)
        if copied != before:
            raise ValueError('Isolated working copy differs from the source snapshot')
        report['working_copy_identity'] = 'PASS'
        r1 = work / 'revision_r1'
        report['steps']['cyclic_policy_tests'] = run_script(r1/'test_checked_cyclic_path.py',work,output,'cyclic_policy_tests')
        report['steps']['exchange_diagnostic_tests'] = run_script(r1/'test_exchange_benchmark.py',work,output,'exchange_diagnostic_tests')
        report['steps']['protocol_recomputation'] = run_script(r1/'audit_protocols.py',work,output,'protocol_recomputation')
        report['steps']['cyclic_recovery'] = run_script(r1/'recompute_cyclic_recovery.py',work,output,'cyclic_recovery')
        report['steps']['saved_science_comparison'] = compare_recomputation(ROOT,work,output)
        if args.remeasure:
            report['steps']['remeasurement'] = run_script(r1/'benchmark_exchange.py',work,output,'exchange_remeasurement')
            fresh = output / 'fresh_timing_measurements'
            fresh.mkdir()
            for path in (r1/'results').glob('exchange_*'):
                if path.is_file():
                    shutil.copy2(path,fresh/path.name)
            report['steps']['remeasurement_arithmetic'] = validate_saved_timings(work)
            report['timing_interpretation'] = 'New host/load-dependent durations retained separately; equality to archived timings is not required'
        else:
            report['timing_interpretation'] = 'Archived durations were checked arithmetically; no new speed measurement is claimed'
        unsealed = report['manifests']['revision']['status'] != 'PASS'
        report['status'] = 'DEVELOPMENT_PASS' if unsealed else 'PASS'
        report['new_test_methods'] = sum(report['steps'][key]['test_methods_run']
            for key in ('cyclic_policy_tests','exchange_diagnostic_tests'))
    except Exception as error:
        report['status'] = 'FAIL'
        report['error'] = type(error).__name__ + ': ' + str(error)
        (output/'failure_traceback.txt').write_text(traceback.format_exc(),encoding='utf8')
    finally:
        # Only the exact disposable copy created inside this new output may be
        # removed. Never recurse into an inferred or pre-existing source path.
        if not args.keep_work_copy and work.exists():
            try:
                checked = work.resolve()
                if (checked != output/'working_copy'/'source' or not checked.is_relative_to(output)
                        or checked == ROOT or ROOT.is_relative_to(checked)):
                    raise ValueError('Refusing unsafe work-copy cleanup')
                shutil.rmtree(checked)
                checked.parent.rmdir()
                report['temporary_work_copy_removed'] = True
            except Exception as cleanup_error:
                report['status'] = 'FAIL'
                report['cleanup_error'] = str(cleanup_error)
        else:
            report['temporary_work_copy_removed'] = not work.exists()
        try:
            after = snapshot(ROOT)
            dump(output/'source_identity_after.json',after)
            unchanged = before is not None and before == after
            report['source_unchanged'] = unchanged
            if not unchanged:
                report['status'] = 'FAIL'
                if before is not None:
                    report['changed_source_paths'] = [name for name in sorted(set(before)|set(after))
                        if before.get(name) != after.get(name)]
        except Exception as identity_error:
            report['status'] = 'FAIL'
            report['source_unchanged'] = False
            report['source_recheck_error'] = str(identity_error)
        report['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        dump(output/'check_report.json',report)
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0 if report['status'] in ('PASS','DEVELOPMENT_PASS') else 1


if __name__ == '__main__':
    raise SystemExit(main())
