"""Eight predeclared post-hoc training cases, no tuning or frozen-file writes."""
import hashlib
import json
from pathlib import Path
import sys
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.predictive_motion_lab import controller
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab.evaluate import audit
from src.transition_diagnostic import bounded_controller


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase-matching', action='store_true',
                        help='Separate four-case follow-up; does not overwrite first diagnostic')
    args = parser.parse_args()
    data = ROOT/'data/predictive-motion-lab'
    frozen = json.loads((data/'frozen-v4.json').read_text())
    checks = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == h
              for p, h in frozen['sha256'].items()}
    if not all(checks.values()):
        raise ValueError('Frozen input mismatch')
    lib = Library(json.loads((data/'library.json').read_text()))
    cfg = json.loads((data/'configs.json').read_text())
    plan = [(w, limit, family) for w in [.46, .62]
            for limit, family in [(.4, False), (.1, False), (.05, False), (.1, True)]]
    if args.phase_matching:
        plan = [(w, limit, False) for w in [.46, .62] for limit in [.1, .05]]
    output = ROOT/'data/main-review'/('transition-phase-matching' if args.phase_matching else 'transition-bounds')
    output.mkdir(parents=True, exist_ok=True)
    report = {'classification': 'post_hoc_training_diagnostic',
              'frozen_hash_checks': checks, 'plan': plan,
              'phase_matching': args.phase_matching,
              'source_hashes': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                                for p in ['src/transition_diagnostic.py',
                                          'scripts/main_audit_transition_bounds.py']},
              'limitations': ['Bounds are engineering probes, not naturalness thresholds.',
                              'Source-pose discrepancy includes legitimate transitions.',
                              'Same-family filtering confounds speed and motion coverage.',
                              'Two training scenes, not held-out generalization or status validation.'],
              'results': []}
    for width, limit, family in plan:
        spec = next(s for s in cfg['train'] if s.get('width') == width)
        with bounded_controller(lib, limit, family, args.phase_matching):
            run = controller.simulate(lib, spec, 'G')
        metrics = audit(run, lib)
        name = f'door{width}-bound{limit}-family{int(family)}'
        # Save actual poses so a later inspection need not reconstruct from clips.
        replay = {k: run[k] for k in ['spec', 'mode', 'p_weight', 'frames', 'runtime']}
        (output/f'{name}.json').write_text(json.dumps(replay, separators=(',', ':'))+'\n')
        decisions = run['decisions']
        selected = [c for d in decisions for c in d['candidates'] if c['selected']]
        row = {'name': name, 'width': width, 'bound': limit, 'own_source_style': family,
               'metrics': metrics,
               'used_clips': sorted({a['clip'] for f in run['frames'] for a in f['agents']}),
               'selected_prediction_discrepancy_max': max((c['deformation'] for c in selected), default=0),
               'decisions_losing_all_frozen_safe_candidates': sum(
                   d['frozen_safe_count'] > 0 and d['safe_count'] == 0 for d in decisions),
               'replay': str((output/f'{name}.json').relative_to(ROOT))}
        report['results'].append(row)
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print(name, 'arrived', metrics['arrived_fraction'], 'max source offset',
              round(metrics['source_pose_modification_max'], 5), 'clips', row['used_clips'], flush=True)
    print(output/'summary.json', flush=True)


if __name__ == '__main__':
    main()
