"""Development acceptance for all four full EMM sources, not perception testing."""
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.bvh import load
from src.finite_motion import FiniteSequence, Cursor
from src.motion_coverage import positions


def audit():
    spec = json.loads((ROOT/'data/main-review/motion-coverage/preview-plan.json').read_text())
    provenance = json.loads((ROOT/'outputs/motion-coverage/evidence.json').read_text())
    expected = {row['id']: row['sha256'] for row in provenance['reports']}
    rows = []
    for entry in spec['clips']:
        path = ROOT/entry['path']; before = hashlib.sha256(path.read_bytes()).hexdigest()
        assert before == expected[entry['id']], 'Source differs from inspected preview'
        began = time.perf_counter(); motion = load(path); seq = FiniteSequence(motion)
        reference = positions(motion)
        native = seq.sample(np.arange(len(motion.frames))*seq.dt)
        fk_error = float(np.max(np.abs(native-reference)))
        # Half frames stress interpolation, including all source transitions.
        half = seq.sample((np.arange(len(motion.frames)-1)+.5)*seq.dt)
        bone_error = max(float(np.max(np.abs(np.linalg.norm(half[:, j]-half[:, p], axis=-1)
                            -np.linalg.norm(seq.offsets[j])))) for j, p in enumerate(seq.parents) if p is not None)
        starts = seq.eligible_starts(1., stride_frames=12)
        assert np.all(starts+1 <= seq.duration)
        # Nonzero entry, rotation and translation: displacement must telescope.
        cursor = Cursor(seq, start=max(0, seq.duration-2), origin_xz=(3, -2), yaw=.7)
        initial = seq.placed(cursor.time, **cursor.placement)
        accumulated = np.zeros(3); steps = 0
        while True:
            result = cursor.advance(.037); accumulated += result.root_delta; steps += 1
            if result.exhausted: break
        delta_error = float(np.max(np.abs(accumulated-(result.pose[0]-initial[0]))))
        rejected = False
        try: cursor.advance(.037)
        except RuntimeError: rejected = True
        after = hashlib.sha256(path.read_bytes()).hexdigest()
        assert before == after and fk_error < 1e-9 and bone_error < 1e-9 and delta_error < 1e-9 and rejected
        rows.append(dict(id=entry['id'],source=entry['path'],sha256=before,
                         frames=len(motion.frames),duration_last_sample=seq.duration,
                         sample_fk_max_error=fk_error,half_frame_bone_length_max_error=bone_error,
                         eligible_one_second_windows=len(starts),root_delta_accumulation_error=delta_error,
                         cursor_tail_steps=steps,tail_unconsumed_seconds=result.remaining,
                         post_end_rejected=rejected,elapsed_seconds=time.perf_counter()-began))
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    output = ROOT/'data/main-review/finite-motion/audit.json'; output.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(scope='Engineering checks, all four full source files. Not a controller, transition or status result.',
                   interpolation='Local quaternion shortest-arc SLERP then FK; linear root translation',
                   units='Original source units, not asserted metres',
                   code_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                                ['src/finite_motion.py','scripts/audit_finite_motion.py']},reports=rows)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__': audit()
