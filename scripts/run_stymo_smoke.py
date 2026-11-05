"""Bounded CPU smoke test of an unmodified, pinned upstream STyMo checkout.

One temporal epoch tests the pipeline, NOT paper quality or status expression.
Upstream static/gating epochs remain 100/30. No paid compute is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = Path('/Volumes/Samsung-SSD/AnimationLab/STyMo-official')
PYTHON = Path('/Volumes/Samsung-SSD/AnimationLab/stymo-py311/bin/python')
REVISION = '1b9a1b064063369f275111addce424e8337f04b8'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--epochs', type=int, default=1)
    parser.add_argument('--inputs', type=Path, help='Optional unpaired input folder for gating samples')
    parser.add_argument('--python', type=Path, default=PYTHON,
                        help='Existing interpreter or isolated overlay with STyMo dependencies')
    args = parser.parse_args()
    revision = subprocess.check_output(['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != REVISION:
        raise RuntimeError('Upstream revision changed; audit before proceeding')
    out = ROOT / 'outputs/stymo-pilot'
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    work = Path('/Volumes/Samsung-SSD/AnimationLab/stymo-runs') / stamp
    work.mkdir(parents=True, exist_ok=False)
    source = UPSTREAM / 'motion/mocha/angry'
    shutil.copytree(source / 'source', work / 'source')
    shutil.copytree(source / 'target', work / 'target')
    inputs = {str(p.relative_to(work)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in work.rglob('*.bvh')}
    # Reconstruct the training source first; held-out generalization comes later.
    input_file = args.inputs.resolve() if args.inputs else work / 'source/neutral_to_angry.bvh'
    cmd = [str(args.python), '-u', str(UPSTREAM / 'src/stylizer_train.py'),
           str(work), str(input_file), '--epochs', str(args.epochs), '--name', 'smoke' if args.epochs == 1 else 'pilot']
    env = dict(os.environ, MPLBACKEND='Agg', OMP_NUM_THREADS='4',
               OPENBLAS_NUM_THREADS='4', PYTHONUNBUFFERED='1')
    log_path = out / f'{stamp}.log'
    start = time.monotonic()
    timed_out = False
    with log_path.open('w') as log:
        process = subprocess.Popen(cmd, cwd=UPSTREAM, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            try:
                code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                code = process.wait()
    checkpoints = list(work.rglob('model.pt'))
    result = dict(revision=revision, command=cmd, input_sha256=inputs,
                  work=str(work), log=str(log_path), exit_code=code,
                  timed_out=timed_out, elapsed_seconds=time.monotonic()-start,
                  checkpoints=[str(p) for p in checkpoints],
                  checkpoint_saved=bool(checkpoints), temporal_epochs=args.epochs,
                  held_out_evaluation=False, visual_verified=False,
                  status_verified=False, paid_compute_used=False)
    (out / 'latest-run.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if code == 0 and checkpoints else 1)


if __name__ == '__main__':
    main()
