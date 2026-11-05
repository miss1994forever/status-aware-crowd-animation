"""R1 descriptive posture extraction; no inferred interaction events or status labels."""
from pathlib import Path
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'outputs/social-signal-review'

def summarize(values, times, reference):
    baseline = float(np.mean(values[reference]))
    minimum, maximum = int(np.argmin(values)), int(np.argmax(values))
    return {
        'initial_0_5s_mean': round(baseline, 6),
        'min': round(float(values[minimum]), 6),
        'max': round(float(values[maximum]), 6),
        'range': round(float(np.ptp(values)), 6),
        'min_time_s': round(float(times[minimum]), 6),
        'max_time_s': round(float(times[maximum]), 6),
        'min_change_from_initial_mean': round(float(values[minimum]-baseline), 6),
        'max_change_from_initial_mean': round(float(values[maximum]-baseline), 6),
        'last_0_5s_mean_change': round(float(np.mean(values[times > times[-1]-.5])-baseline), 6),
        'series': values.round(6).tolist(),
    }

def extract(clip):
    p = np.asarray(clip['positions'], dtype=float)
    times = np.arange(len(p)) * clip['dt']
    reference = times < .5
    names = clip['names']
    def joint(name):
        return p[:, names.index(name)]
    measures = {}
    bones = {}
    for side in ('l','r'):
        hip, knee, ankle = [joint(f'b_{side}_{part}') for part in ('upleg','leg','foot')]
        # Anatomical knee location is b_*_leg; ankle is b_*_foot.
        thigh = knee - hip
        shank = ankle - knee
        thigh_length = np.linalg.norm(thigh,axis=1)
        shank_length = np.linalg.norm(shank,axis=1)
        assert np.all(thigh_length > 1e-5) and np.all(shank_length > 1e-5)
        cosine = np.sum(thigh*shank,axis=1)/(thigh_length*shank_length)
        flexion = np.degrees(np.arccos(np.clip(cosine,-1,1)))
        # Zero denotes straight collinear thigh and shank, not 180 degrees.
        measures[f'{side}_knee_flexion_deg'] = summarize(flexion,times,reference)
        bones[side] = {
            'thigh_length_median_m': round(float(np.median(thigh_length)),6),
            'thigh_length_range_m': round(float(np.ptp(thigh_length)),6),
            'shank_length_median_m': round(float(np.median(shank_length)),6),
            'shank_length_range_m': round(float(np.ptp(shank_length)),6),
        }
    pelvis, head, neck = joint('b_root'), joint('Head'), joint('b_neck0')
    trunk = neck-pelvis
    tilt = np.degrees(np.arctan2(np.linalg.norm(trunk[:,[0,2]],axis=1),trunk[:,1]))
    measures['pelvis_height_m'] = summarize(pelvis[:,1],times,reference)
    measures['head_joint_height_m'] = summarize(head[:,1],times,reference)
    measures['root_neck_tilt_deg'] = summarize(tilt,times,reference)
    assert all(np.isfinite(m['series']).all() for m in measures.values())
    return {'id':clip['name'], 'duration_s':round(float(times[-1]),6),
            'reference_frame_count':int(reference.sum()),
            'times_s':times.round(6).tolist(),'metrics':measures,'leg_bone_lengths':bones}

def main():
    clips = json.loads((FOLDER/'clips.json').read_text())[1:]
    audit = json.loads((FOLDER/'audit.json').read_text())
    assert [c['name'] for c in clips] == list('ABCDE')
    rows = [extract(c) for c in clips]
    output = {
        'source':'clips.json indices 1–5; duplicate A at index 0 excluded',
        'source_audit':'audit.json',
        'method':{
            'sampling':'Original 24 Hz sample positions; no smoothing or retiming.',
            'reference':'Mean of samples 0 <= t < 0.5 seconds, only a numerical reference. It is NOT an annotated pre-interaction baseline; preparations may already be underway.',
            'knees':'Angle between hip-to-knee and knee-to-ankle vectors. 0 degrees means straight; unsigned flexion proxy, not full anatomical joint rotation or signed sagittal flexion.',
            'heights':'World Y of pelvis and head joint; head joint is not skull top or standing stature. Original imported coordinates and 0.01 scale retained. No floor fitting.',
            'trunk':'Unsigned deviation of root-to-neck vector from world vertical; does not measure spinal curvature, chest openness, shoulder rotation, or forward/backward direction.',
            'normalization':'No stature normalization. Absolute differences across clips can include rig/actor/pose differences. Initial-reference subtraction does not remove all these confounds.',
            'uncertainty':'Original animated translations make some bone lengths vary. FK conversion has not been independently checked against vendor-rendered mesh. Metrics are descriptive; extrema are not interaction onset or offset.',
            'interpretation':'No status score, observer validation, interaction-stage inference, muscle tension inference or causal claim.'
        },
        'source_import_bone_range_m':{r['id']:r['max_bone_length_range_m'] for r in audit},
        'rows':rows,
    }
    (FOLDER/'posture-analysis.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    for r in rows:
        print(r['id'],{k:{v:m[v] for v in ['initial_0_5s_mean','min_change_from_initial_mean','max_change_from_initial_mean','last_0_5s_mean_change']} for k,m in r['metrics'].items()})

if __name__ == '__main__':
    main()
