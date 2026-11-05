"""Nine fixed exploratory conditions; original frozen files remain read-only."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab import controller
from src.predictive_motion_lab.evaluate import audit
from src.expression_layer import layered_controller, personal_library, upper_mask


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'))+'\n')


def layer_metrics(run, lib, strength):
    n = len(run['frames'][0]['agents'])
    refs = [lib.ids.index(run['spec'].get('reference', 'M02')) if n == 1
            else lib.ids.index(['M01', 'M02', 'M03'][i%3]) for i in range(n)]
    libraries = {r: personal_library(lib, r, strength) for r in set(refs)}
    directions, residuals = [], []
    upper = np.flatnonzero(upper_mask(lib))
    for f in run['frames']:
        for i, a in enumerate(f['agents']):
            pose = np.array(a['pose'])
            ref = lib.sample(refs[i], a['phase'])
            sample = libraries[refs[i]].sample(lib.ids.index(a['clip']), a['phase'])
            residuals.append(float(np.linalg.norm(pose-sample, axis=-1).max()))
            for j in upper:
                p = lib.parents[j]
                if lib.lengths[j] > 1e-6:
                    directions.append(float(np.sum(((pose[j]-pose[p])-(ref[j]-ref[p]))**2)/lib.lengths[j]**2))
    return {'upper_reference_direction_rms': float(np.sqrt(np.mean(directions))),
            'synthesized_source_residual_max': max(residuals),
            'reference_clip_ids': [lib.ids[r] for r in refs]}


def page(out):
    for name in ['index.html', 'ui.js']:
        source = ROOT/'expression-layer-lab'/name
        if source.exists():
            (out/name).write_bytes(source.read_bytes())
    (out/'LICENSE.txt').write_bytes((ROOT/'data/raw/bandai-pilot/LICENSE').read_bytes())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--page', action='store_true')
    args = parser.parse_args()
    out = ROOT/'outputs/expression-layer-lab';out.mkdir(parents=True, exist_ok=True)
    if args.page:
        page(out);return
    data = ROOT/'data/predictive-motion-lab'
    frozen = json.loads((data/'frozen-v4.json').read_text())
    checks = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == h for p, h in frozen['sha256'].items()}
    if not all(checks.values()):
        raise ValueError('Frozen input changed')
    lib = Library(json.loads((data/'library.json').read_text()))
    cfg = json.loads((data/'configs.json').read_text())
    scenes = [next(s for s in cfg['train'] if s.get('width') == w) for w in [.46, .62]]
    scenes.append(next(s for s in cfg['train'] if len(s['starts']) == 10))
    code_hashes = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                   for p in ['src/expression_layer.py', 'scripts/build_expression_layer_lab.py']}
    plan = {'classification': 'exploratory_training_only_v1', 'scenes': scenes,
            'strengths': [0., .5, 1.], 'frozen_hash_checks': checks, 'code_hashes': code_hashes,
            'notes': ['No phase-matching B, no old P penalty, no status labels.',
                      'All strengths use same candidate clip IDs and controls, but synthesized poses differ.',
                      'Layered pose is used for both prediction and execution, not replay cosmetics.',
                      'Original candidate speed/direction metadata unchanged; selected trajectories may differ.',
                      'Reference closeness is expected by construction, NOT perceptual validation.',
                      'Same body-frame phase does not guarantee physically coordinated gait.',
                      'Train scenes only; retain dense-crowd failures.']}
    plan_path = ROOT/'data/main-review/expression-layer/plan.json'
    if plan_path.exists() and json.loads(plan_path.read_text()) != plan:
        raise ValueError('Existing experiment differs; create new version instead of overwriting')
    save(plan_path, plan)
    results = []
    for spec in scenes:
        for strength in plan['strengths']:
            key = f'{spec["name"]}-layer{strength:g}'
            metric_path = ROOT/'data/main-review/expression-layer'/f'{key}.json'
            if metric_path.exists():
                results.append(json.loads(metric_path.read_text()));continue
            started = time.perf_counter()
            if strength == 0:
                original = ROOT/'outputs/predictive-motion-lab/runs'/f'train_{spec["name"]}_G_0.json'
                run = json.loads(original.read_text())
                origin = {'type': 'frozen_existing_G_replay', 'file': str(original.relative_to(ROOT)),
                          'sha256': hashlib.sha256(original.read_bytes()).hexdigest()}
            else:
                print('START', key, flush=True)
                with layered_controller(lib, strength):
                    run = controller.simulate(lib, copy.deepcopy(spec), 'G')
                origin = {'type': 'new_layered_controller_simulation'}
            measured = audit(run, lib)
            # Original clip-only proxy does not describe synthesized output.
            measured.pop('expression_drift_mean', None)
            measured.update(layer_metrics(run, lib, strength))
            replay = {k: run[k] for k in ['spec', 'frames', 'runtime']}
            replay['strength'] = strength
            replay['metrics'] = measured
            replay['reference_clip_ids'] = measured['reference_clip_ids']
            save(out/'runs'/f'{key}.json', replay)
            row = {'key': key, 'scene': spec['name'], 'count': len(spec['starts']),
                   'strength': strength, 'file': f'runs/{key}.json', 'metrics': measured,
                   'origin': origin, 'wall_seconds': time.perf_counter()-started}
            save(metric_path, row);results.append(row)
            save(out/'catalog.json', results)
            print('DONE', key, 'arrived', measured['arrived_fraction'], 'penetration',
                  round(measured['max_proxy_penetration'], 5), 'upper distance',
                  round(measured['upper_reference_direction_rms'], 4), flush=True)
    save(out/'catalog.json', results)
    save(out/'skeleton.json', {'parents': lib.parents, 'names': lib.names})
    save(out/'plan.json', plan)
    save(ROOT/'data/main-review/expression-layer/summary.json', {'plan': plan, 'results': results})
    page(out)
    print(out/'index.html', flush=True)


if __name__ == '__main__':
    main()
