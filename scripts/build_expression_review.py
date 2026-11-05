"""Build a fixed-motion, ten-person expression diagnostic, plus fresh body audit."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.predictive_motion_lab.motion import Library
from src.crowd_mobility_lab.evaluate import evaluate
from src.expression_replay import resynthesize, compare_contract


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'))+'\n')


def build():
    frozen = json.loads((ROOT/'data/crowd-mobility-lab/frozen-v1.json').read_text())['sha256']
    hashes = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == h for p, h in frozen.items()}
    assert all(hashes.values()), hashes
    source_path = ROOT/'outputs/crowd-mobility-lab/runs/train_shared-10-None-13_R0.json'
    source = json.loads(source_path.read_text())
    lib = Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()))
    out = ROOT/'outputs/expression-review'
    record = ROOT/'data/main-review/expression-review'
    plan = {'source': str(source_path.relative_to(ROOT)), 'source_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
            'strengths': [0, .5, 1], 'duration': 26, 'agents': 10,
            'classification': 'post_hoc_fixed_motion_training_scene_diagnostic',
            'defaults': {'agent': 1, 'strength': 1, 't': 0},
            'scope': 'All ten people and full 26 seconds, not hand-picked favorable snippets. No new heldout or human study.',
            'limits': ['Root, speed, heading, phase and selected clips fixed to R0.',
                       'Recompute body metrics; copied arrival flags are not success evidence.',
                       'Original reference gait is an in-place native-tempo visual reference, not a matched condition.'],
            'frozen_hash_checks': hashes,
            'code_hashes': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['src/expression_replay.py', 'scripts/build_expression_review.py']}}
    save(record/'plan.json', plan)  # Save choices before computing any new outcome.
    rows = []
    for strength in plan['strengths']:
        run = resynthesize(lib, source, strength)
        contract = compare_contract(lib, source, run)
        assert contract['non_upper_node_difference_max'] < 3e-6, contract
        assert contract['rounded_bone_length_error_max'] < 3e-6, contract
        if strength == 0:
            assert contract['pose_node_difference_max'] < 3e-6, contract
        file = f'run-{strength:g}.json'
        save(out/file, run)
        print('Synthesized', strength, contract, flush=True)
        metrics = evaluate(run, lib)
        row = {'strength': strength, 'file': file, 'contract': contract, 'metrics': metrics}
        save(record/f'metrics-{strength:g}.json', row)
        rows.append(row)
        print('Audited', strength, 'proxy penetration', metrics['max_proxy_penetration'], flush=True)
    save(out/'data.json', {'plan': plan, 'rows': rows, 'parents': lib.parents, 'names': lib.names,
                            'lengths': lib.lengths.tolist(),
                            'references': [{'id': lib.ids[i], 'poses': lib.poses[i].tolist(), 'period': float(lib.periods[i])}
                                           for i in [lib.ids.index(x) for x in ['M01', 'M02', 'M03']]]})
    save(record/'summary.json', {'plan': plan, 'rows': rows})
    for name in ['index.html', 'ui.js']:
        (out/name).write_bytes((ROOT/'expression-review'/name).read_bytes())
    (out/'LICENSE.txt').write_bytes((ROOT/'data/raw/bandai-pilot/LICENSE').read_bytes())
    print('Built', out, flush=True)


if __name__ == '__main__':
    build()
