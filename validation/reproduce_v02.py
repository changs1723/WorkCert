"""Verify frozen evidence or recompute the complete v0.2 scientific workflow."""
from pathlib import Path
import argparse
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def run(relative,*args):
    print('Running',relative,*args,flush=True)
    subprocess.run([sys.executable,str(ROOT/relative),*args],cwd=ROOT,check=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--recompute',action='store_true',help='Regenerate numerical tables and case studies')
    mode.add_argument('--verify-only',action='store_true',help='Verify the supplied frozen outputs (the default)')
    p.add_argument('--include-scaling',action='store_true',help='Also rerun all scaling cases and paired repeats')
    p.add_argument('--figures',action='store_true',help='Regenerate figures from current numerical outputs')
    a=p.parse_args()
    if a.include_scaling and not a.recompute:p.error('--include-scaling requires --recompute')
    if a.recompute:
        run('validation/acquire_pla_data.py')
        run('validation/prepare_data.py')
        run('validation/check_baselines.py')
        run('validation/extended_benchmark.py')
        run('validation/optimal_dp.py')
        run('validation/extended_benchmark.py','--finish-dp')
        run('validation/user_workflow.py','--case','all')
        if a.include_scaling:
            run('validation/benchmark_scaling.py')
            run('validation/benchmark_scaling.py','--headline')
    run('data/source_context/verify_preparation.py')
    run('validation/verify_extended_benchmark.py')
    run('validation/verify_exact_errors.py')
    run('validation/verify_workflow.py')
    if a.figures:run('authoring/build_v02_figures.py')
    print('Completed. Recomputed host timings may differ from the archived runs.',flush=True)

if __name__=='__main__':main()
