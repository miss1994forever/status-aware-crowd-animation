"""Post-hoc main-chat diagnostic, not a new held-out result or production fix.

Compare fixed M02, G, and G restricted to the reference source-style family.
The original frozen controller and artifacts remain unchanged. Source-style
labels are filtering metadata here, never validated status labels.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab.evaluate import audit
import src.predictive_motion_lab.controller as controller


def main():
    data = ROOT / 'data/predictive-motion-lab'
    frozen = json.loads((data / 'frozen-v4.json').read_text())
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == digest
              for p, digest in frozen['sha256'].items()}
    if not all(hashes.values()):
        raise ValueError('Frozen inputs changed; do not silently compare versions')
    lib = Library(json.loads((data / 'library.json').read_text()))
    config = json.loads((data / 'configs.json').read_text())
    spec = next(s for s in config['train'] if s.get('width') == .46)
    original = controller.options
    styles = np.array([c['source']['source_style'] for c in lib.clips])

    def own_style(library, state, mode):
        candidates = original(library, state, mode)
        return candidates[styles[candidates[:, 0].astype(int)] == styles[state.reference]]

    results = []
    try:
        for name, mode, options in [('F', 'F', original),
                                    ('G_all_styles', 'G', original),
                                    ('G_own_source_style', 'G', own_style)]:
            controller.options = options
            run = controller.simulate(lib, spec, mode)
            result = {'condition': name, 'metrics': audit(run, lib),
                      'used_clips': sorted({a['clip'] for f in run['frames'] for a in f['agents']})}
            results.append(result)
            print(name, result['metrics']['arrived_fraction'], result['used_clips'], flush=True)
    finally:
        controller.options = original
    report = {'classification': 'post_hoc_training_case_diagnostic',
              'scenario': spec, 'frozen_hash_checks': hashes,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'limitations': ['One training scene, not a new held-out test.',
                              'Restricting source-style also changes motion coverage and speed distribution.',
                              'Failure does not prove no same-style solution exists.',
                              'Source-style and kinematic distances do not establish perceived status.'],
              'results': results}
    output = ROOT / 'data/main-review/predictive-style-diagnostic.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(output)


if __name__ == '__main__':
    main()
