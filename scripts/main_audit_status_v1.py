"""Read-only audit of the delivered v1 interaction; never alters frozen runs."""
import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab.controller import initial
from src.status_interaction_lab.social import CONFIG, respond, visible, transform


def main():
    sources = [ROOT / 'src/status_interaction_lab/social.py',
               ROOT / 'src/status_interaction_lab/simulation.py']
    rows = []
    for key in ('dev-v3-ten', 'eval_shared-10-62011', 'eval_shared-10-62017',
                'eval_shared-10-62003', 'dev-role'):
        paths = [ROOT / f'outputs/status-interaction-lab/runs/{key}_{mode}.json'
                 for mode in ('C1', 'C2')]
        if not paths[0].exists():
            paths = [ROOT / f'outputs/status-interaction-lab/runs/{key}-{mode}.json'
                     for mode in ('C1', 'C2')]
        a, b = [json.loads(p.read_text()) for p in paths]
        sources.extend(paths)
        pa, pb = [np.array([[v['pose'] for v in f['agents']] for f in r['frames']])
                  for r in (a, b)]
        ra, rb = [np.array([[v['pos'] for v in f['agents']] for f in r['frames']])
                  for r in (a, b)]
        # RMS is per active agent/frame over joints; either condition moving.
        moving = np.array([[v['speed'] > .05 for v in f['agents']] for f in a['frames']])
        moving |= np.array([[v['speed'] > .05 for v in f['agents']] for f in b['frames']])
        distances = np.linalg.norm(pa - pb, axis=-1)
        rms = np.sqrt(np.mean(distances**2, axis=-1))[moving]
        requested = np.array([abs(d['response']['social']) for d in b['decisions']])
        rows.append(dict(pair=key, root_max=float(np.linalg.norm(ra-rb, axis=-1).max()),
                         joint_max=float(distances.max()), active_pose_rms_p50=float(np.median(rms)),
                         active_pose_rms_p95=float(np.quantile(rms, .95)),
                         social_request_degrees_p95=float(np.degrees(np.quantile(requested, .95))),
                         social_request_degrees_max=float(np.degrees(requested.max())),
                         note='Height-normalized local pose; route/clip divergence confounds large differences.'))

    lib = Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()))
    states = initial(lib, dict(seed=1, starts=[[0, 0], [0, 1.25]], goals=[[0, 3], [0, -3]]))
    own = replace(visible(states[0]), yaw=0.)
    other = replace(visible(states[1]), yaw=math.pi)
    # Synthetic stationary observations isolate algebra, not realistic motion.
    def response(observer, others):
        history = {}
        for _ in range(5):
            result = respond(observer, others, lib.names, history, 0., 'C2', CONFIG)
        return result
    head_on = response(own, [other])
    side = replace(other, pos=np.array([.6, 1.25]))
    lateral = response(own, [side])
    own_changed = replace(own, pose=transform(lib, own.pose, .2, .2))
    changed = response(own_changed, [side])
    left = replace(side, id=2, pos=np.array([-.6, 1.25]))
    symmetric = response(own, [left, side])
    controlled = dict(head_on_social=head_on.social,
                      head_on_confidence=head_on.observations[0]['confidence'],
                      off_axis_social=lateral.social,
                      own_pose_change_response_equal=lateral == changed,
                      symmetric_identical_neighbor_social=symmetric.social,
                      note='Controlled counterexamples show structure, not population prevalence or perception.')
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    result = dict(pairs=rows, controlled=controlled, source_sha256=hashes,
                  limitation='No human evaluation; no algorithm changes or fresh held-out experiment.')
    destination = ROOT/'data/main-review/status-v1-audit.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(pairs=rows, controlled=controlled), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
