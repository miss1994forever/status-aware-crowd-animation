"""Isolated, paired transition review. No collision or status claims.

Three predeclared destinations x eight initial phases. Both switching methods
use identical root control, target clip, speed request and blend; only the
entry phase differs. The M02 continuation is context, not a matched-path arm.
"""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab.controller import initial, rollout, State, frame
from src.transition_diagnostic import matched_phase_offsets

SWITCH = 1.2
DURATION = 4.0


def entry_offset(lib, state, clip, method):
    if method == 'matched':
        return float(matched_phase_offsets(lib, state, clip)[0])
    offsets = np.array([-.08, 0, .08])
    phases = (state.phase+offsets) % 1
    rate = state.speed/lib.speeds[clip]/lib.periods[clip]
    costs = 2*np.sqrt(np.mean((lib.sample(clip, phases)-state.pose)**2, axis=(1, 2)))
    costs += .08*np.sqrt(np.mean((lib.velocity(clip, phases, rate)-state.pose_velocity)**2, axis=(1, 2)))
    return float(offsets[np.argmin(costs)])


def sequence(lib, target, phase, method):
    spec = {'starts': [[0, 0]], 'goals': [[0, 100]], 'reference': 'M02',
            'seed': 0, 'walls': [], 'duration': DURATION}
    s = initial(lib, spec)[0]
    s.phase = phase
    s.pose = lib.sample(s.clip, phase)
    s.pose_velocity = lib.velocity(s.clip, phase, 1/lib.periods[s.clip])
    frames = [frame([s], lib, 0)]
    offsets = []
    target_index = lib.ids.index(target)
    for step in range(20):
        is_switch = step == 6 and method != 'continue'
        clip = s.clip if step < 6 or method == 'continue' else target_index
        offset = entry_offset(lib, s, clip, method) if is_switch else 0.
        if is_switch:
            chosen_offset = offset
        path = rollout(lib, s, np.array([[clip, 1., 0., offset]]), np.arange(1, 5)*.05)
        for j in range(4):
            previous = s.pose if j == 0 else path['pose'][j-1, 0]
            current = State(s.id, path['pos'][j, 0], s.goal, float(path['yaw'][j, 0]),
                            float(path['travel'][j, 0]), float(path['speed'][j, 0]),
                            clip, s.reference, float(path['phase'][j, 0]),
                            path['pose'][j, 0], (path['pose'][j, 0]-previous)/.05)
            frames.append(frame([current], lib, step*.2+(j+1)*.05))
            offsets.append(float(np.linalg.norm(path['pose'][j, 0]-path['source'][j, 0], axis=-1).max()))
        s = current
    local = np.array([f['agents'][0]['pose'] for f in frames])
    # Frame differences are sampling diagnostics, not physical accelerations.
    velocity = np.diff(local, axis=0)/.05
    acceleration = np.diff(velocity, axis=0)/.05
    return {'method': method, 'frames': frames,
            'entry_offset': None if method == 'continue' else chosen_offset,
            'metrics': {'post_switch_source_discrepancy_max': max(offsets[24:]),
                        'local_joint_speed_p95': float(np.quantile(np.linalg.norm(velocity[24:], axis=-1), .95)),
                        'local_joint_acceleration_p95': float(np.quantile(np.linalg.norm(acceleration[23:], axis=-1), .95))}}


def build():
    data = ROOT/'data/predictive-motion-lab'
    frozen = json.loads((data/'frozen-v4.json').read_text())
    checks = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == h
              for p, h in frozen['sha256'].items()}
    if not all(checks.values()):
        raise ValueError('Frozen inputs changed')
    lib = Library(json.loads((data/'library.json').read_text()))
    cases = []
    for target in ['M11', 'M01', 'M03']:
        for phase in np.arange(8)/8:
            variants = [sequence(lib, target, float(phase), m)
                        for m in ['continue', 'local', 'matched']]
            a, b = variants[1:]
            for fa, fb in zip(a['frames'], b['frames']):
                aa, bb = fa['agents'][0], fb['agents'][0]
                for key in ['pos', 'yaw', 'speed', 'travel']:
                    np.testing.assert_array_equal(aa[key], bb[key])
            cases.append({'id': f'M02-{target}-phase{phase:g}', 'target': target,
                          'initial_phase': float(phase), 'root_pair_identical': True,
                          'variants': variants})
    payload = {'switch_time': SWITCH, 'duration': DURATION, 'dt': .05,
               'parents': lib.parents, 'names': lib.names, 'cases': cases,
               'classification': 'isolated_post_hoc_transition_diagnostic',
               'frozen_hash_checks': checks,
               'source_hashes': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                                 for p in ['scripts/build_transition_review.py', 'src/transition_diagnostic.py']},
               'limitations': ['Not obstacle success, contact validity, naturalness or status evaluation.',
                               'A/B share root controls; the continuation reference does not.',
                               'Different target native speeds confound comparisons across destinations.',
                               'Same .4s fade restarted each .2s replanning step as frozen controller.',
                               'All eight phases retained; initial default is phase zero, not best case.']}
    out = ROOT/'outputs/transition-review'
    out.mkdir(parents=True, exist_ok=True)
    (out/'data.json').write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':'))+'\n')
    for name in ['index.html', 'ui.js']:
        (out/name).write_bytes((ROOT/'transition-review'/name).read_bytes())
    (out/'LICENSE.txt').write_bytes((ROOT/'data/raw/bandai-pilot/LICENSE').read_bytes())
    summary = {**payload, 'cases': [{**c, 'variants': [{k:v for k,v in r.items() if k != 'frames'} for r in c['variants']]} for c in cases]}
    (ROOT/'data/main-review/isolated-transitions.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(f'Built {len(cases)} paired cases, 3 variants each; identical A/B roots verified.')
    return payload


if __name__ == '__main__':
    build()
