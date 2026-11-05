"""R1 body-relative space diagnostics; not occupancy, status, or event labels."""
from pathlib import Path
import json
import hashlib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'outputs/social-signal-review'
SOURCE = FOLDER / 'clips.json'


def unit(v):
    length = np.linalg.norm(v, axis=-1, keepdims=True)
    if np.any(length < 1e-8):
        raise ValueError('Degenerate body coordinate axis')
    return v / length


def rounded(v):
    return np.round(v, 6).tolist()


def describe(v, times):
    base = float(np.mean(v[times < .5]))
    imin, imax = int(np.argmin(v)), int(np.argmax(v))
    return dict(first_half_second_mean=round(base, 6),
                min=round(float(v[imin]), 6), max=round(float(v[imax]), 6),
                median=round(float(np.median(v)), 6),
                min_time_s=round(float(times[imin]), 6), max_time_s=round(float(times[imax]), 6),
                max_change_from_reference=round(float(v[imax]-base), 6),
                min_change_from_reference=round(float(v[imin]-base), 6))


def duration_info(mask, dt):
    # Adjacent endpoints inside the interval define a fully supported interval.
    both = mask[:-1] & mask[1:]
    runs = []
    start = None
    for i, yes in enumerate(mask):
        if yes and start is None:
            start = i
        if start is not None and (not yes or i == len(mask)-1):
            end = i if yes else i-1
            runs.append(dict(start_s=round(start*dt, 6), end_s=round(end*dt, 6),
                             duration_s=round((end-start)*dt, 6)))
            start = None
    return dict(total_fully_supported_s=round(float(both.sum()*dt), 6),
                longest_continuous_s=max((r['duration_s'] for r in runs), default=0),
                intervals=runs)


def main():
    raw = SOURCE.read_bytes()
    all_clips = json.loads(raw)
    assert all_clips[0] == all_clips[1], 'Expected duplicate first A'
    clips = all_clips[1:]
    assert [c['name'] for c in clips] == list('ABCDE')
    rows = []
    for c in clips:
        p = np.asarray(c['positions'], dtype=float)
        assert np.isfinite(p).all()
        names = c['names']; dt = c['dt']; times = np.arange(len(p))*dt
        joint = lambda n: p[:, names.index(n)]
        pelvis, neck = joint('b_root'), joint('b_neck0')
        left, right = joint('b_l_arm'), joint('b_r_arm')
        origin = (left+right)/2
        up = unit(neck-pelvis)
        raw_lateral = right-left
        lateral = unit(raw_lateral - np.sum(raw_lateral*up, axis=1)[:, None]*up)
        # This is right x up; its sign is geometric, not a claimed gaze direction.
        third = unit(np.cross(lateral, up))
        series = {}
        for side, sign in [('l', -1), ('r', 1)]:
            shoulder = joint('b_'+side+'_arm')
            elbow = joint('b_'+side+'_forearm')
            wrist = joint('b_'+side+'_wrist')
            arm = unit(elbow-shoulder)
            series[side+'_upperarm_angle_from_torso_down_deg'] = np.degrees(np.arccos(np.clip(np.sum(arm*(-up), axis=1), -1, 1)))
            # Signed outward component, not a clinical abduction angle.
            series[side+'_upperarm_outward_component'] = sign*np.sum(arm*lateral, axis=1)
            for part, point in [('elbow', elbow), ('wrist', wrist)]:
                relative = point-origin
                series[side+'_'+part+'_outward_from_midline_m'] = sign*np.sum(relative*lateral, axis=1)
                series[side+'_'+part+'_vertical_from_shoulders_m'] = np.sum(relative*up, axis=1)
                series[side+'_'+part+'_third_axis_from_shoulders_m'] = np.sum(relative*third, axis=1)
                series[side+'_'+part+'_outward_from_shoulder_m'] = sign*np.sum((point-shoulder)*lateral, axis=1)
        series['elbow_lateral_span_m'] = series['l_elbow_outward_from_midline_m']+series['r_elbow_outward_from_midline_m']
        series['wrist_lateral_span_m'] = series['l_wrist_outward_from_midline_m']+series['r_wrist_outward_from_midline_m']
        holds = {}
        for threshold in [25, 35, 45]:
            mask = ((series['l_upperarm_angle_from_torso_down_deg'] > threshold)
                    & (series['r_upperarm_angle_from_torso_down_deg'] > threshold))
            holds[str(threshold)] = duration_info(mask, dt)
        assert all(np.isfinite(v).all() for v in series.values())
        assert np.allclose(np.sum(up*lateral, axis=1), 0, atol=1e-7)
        rows.append(dict(id=c['name'],samples=len(p),duration_s=round(float(times[-1]),6),
                         time_s=rounded(times), summary={k:describe(v,times) for k,v in series.items()},
                         series={k:rounded(v) for k,v in series.items()},
                         bilateral_upperarm_threshold_holds_deg=holds))
    result = dict(source=str(SOURCE.relative_to(ROOT)), source_sha256=hashlib.sha256(raw).hexdigest(),
        method=dict(frame='Origin: midpoint of upper-arm origins. Up: pelvis-to-neck. Right: right-minus-left upper-arm origins orthogonalized against up. Third axis = right cross up; not gaze.',
            reference='Mean of samples at 0 <= t < 0.5 s, only a reference window, NOT an annotated pre-interaction baseline.',
            upperarm_angle='Elbow-minus-upper-arm-origin direction against negative torso up. Includes forward/backward as well as sideways elevation; not pure abduction.',
            distances='Signed outward lateral distances. Negative means across center/reference toward the other side. Not mesh occupancy, area or volume.',
            duration='Sum of adjacent frame intervals with both endpoints above threshold. Longest contiguous run; no smoothing, thresholds 25/35/45 degrees.',
            units='Imported positions in meters; angles degrees. Root/skeleton scale follows existing import, no height fitting.',
            limitations=['No interaction event labels; peaks are not event onset.',
                'Both sides measured for every clip. B must not be assigned an inactive left hand.',
                'No hand-to-hip contact or intention inferred.',
                'Single selected take per label; no causal, statistical or status claim.',
                'Body axes change with torso/shoulder posture; retain absolute animation for interpretation.',
                'The first duplicated A is skipped; five independent files, not six samples.']), rows=rows)
    (FOLDER/'space-analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    for row in rows:
        s=row['summary']
        print(row['id'], 'L elbow', s['l_elbow_outward_from_midline_m'], 'bilateral35', row['bilateral_upperarm_threshold_holds_deg']['35']['total_fully_supported_s'])

if __name__ == '__main__':
    main()
