"""Main-chat replay and integrity check; do not overwrite delegated evidence."""
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.predictive_motion_lab.motion import Library
from src.crowd_mobility_lab.controller import simulate
from src.crowd_mobility_lab.evaluate import evaluate
import numpy as np


def main():
    start = time.perf_counter()
    data = ROOT / 'data/crowd-mobility-lab'
    out = ROOT / 'outputs/crowd-mobility-lab/runs'
    frozen = json.loads((data / 'frozen-v1.json').read_text())['sha256']
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
              for p, h in frozen.items()}
    assert all(hashes.values()), hashes
    lib = Library(json.loads((ROOT / 'data/predictive-motion-lab/library.json').read_text()))
    source = json.loads((out / 'train_shared-10-None-13_R0.json').read_text())
    repeated = simulate(lib, source['spec'], 'long_cv', 0)
    equality = {'frames_equal': repeated['frames'] == source['frames'],
                'decisions_equal': repeated['decisions'] == source['decisions'],
                'frames': len(repeated['frames'])}
    assert equality['frames_equal'] and equality['decisions_equal'], equality
    print('Full 26-second R0 reproduced:', equality, flush=True)
    checks = []
    for key in ['train_shared-10-None-13_R0', 'heldout_shared-10-new-14293_R1',
                'diagnostics_corridor-10-new-41017_R1']:
        run = json.loads((out / (key + '.json')).read_text())
        actual = evaluate(run, lib)
        prior = json.loads((data / 'formal-metrics' / (key + '.json')).read_text())
        match = all(prior.get(k) == v for k, v in actual.items())
        final = np.array([a['pos'] for a in run['frames'][-1]['agents']])
        distances = np.linalg.norm(final - np.array(run['spec']['goals']), axis=1)
        arrival_ids = {int(i) for i in run['runtime']['arrival_times']}
        geometric_ids = {int(i) for i in np.where(distances < .22)[0]}
        assert match and arrival_ids == geometric_ids, (key, arrival_ids, geometric_ids)
        checks.append({'key': key, 'all_metrics_match': match,
                       'final_goal_distances': distances.tolist(),
                       'arrival_count': len(arrival_ids),
                       'arrivals_match_final_geometry': True,
                       'recomputed': actual})
        print(key, len(arrival_ids), 'arrived; metrics match', flush=True)
    report = {'frozen_hashes_match': hashes, 'full_reproduction': equality,
              'rechecks': checks, 'elapsed_seconds': time.perf_counter() - start,
              'scope': 'One full re-simulation and three saved-run metric rechecks; not all 23 re-simulated. No human perception validation.'}
    target = ROOT / 'data/main-review/crowd-mobility.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('Saved', target, flush=True)


if __name__ == '__main__':
    main()
