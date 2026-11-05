"""Read-only audit of M01-M03: explicit BVH convention and descriptive geometry.

No status inference, no pose editing, no implicit conversion to metres.
Quaternion recursion is independently implemented to check matrix FK arithmetic;
it is NOT an independent execution of Blender or the author's renderer.
"""
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.bvh import load


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def qmul(a, b):
    w, x, y, z = a
    v, i, j, k = b
    return (w*v-x*i-y*j-z*k, w*i+x*v+y*k-z*j,
            w*j-x*k+y*v+z*i, w*k+x*j-y*i+z*v)


def qrotate(q, point):
    return qmul(qmul(q, (0., *point)), (q[0], -q[1], -q[2], -q[3]))[1:]


def quaternion_positions(motion, frame):
    """Local position channels replace OFFSET; rotation order retained."""
    positions, rotations = [], []
    for joint in motion.joints:
        position, q = list(joint.offset), (1., 0., 0., 0.)
        rotation_seen = False
        for offset, channel in enumerate(joint.channels):
            value = motion.frames[frame][joint.channel_start + offset]
            axis = 'XYZ'.index(channel[0])
            if channel.endswith('position'):
                if rotation_seen:
                    raise ValueError('Position after rotation is unsupported by this reference')
                position[axis] = value
            else:
                rotation_seen = True
                half = math.radians(value) / 2
                rotation = [math.cos(half), 0., 0., 0.]
                rotation[axis + 1] = math.sin(half)
                q = qmul(q, rotation)
        if joint.parent is not None:
            position = add(positions[joint.parent], qrotate(rotations[joint.parent], position))
            q = qmul(rotations[joint.parent], q)
        positions.append(tuple(position))
        rotations.append(q)
    return positions


def percentile(values, fraction):
    ordered = sorted(values)
    index = fraction * (len(ordered) - 1)
    lo, hi = math.floor(index), math.ceil(index)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def summary(values):
    return {name: round(percentile(values, fraction), 6) for name, fraction in [('p05', .05), ('median', .5), ('p95', .95)]}


def describe(poses, names):
    idx = {name: i for i, name in enumerate(names)}
    hips = idx['Hips']
    travel = sub(poses[-1][hips], poses[0][hips])
    distance = math.hypot(travel[0], travel[2])
    if distance < 1e-6:
        raise ValueError('No horizontal net travel; forward axis cannot be inferred')
    forward = (travel[0]/distance, 0., travel[2]/distance)
    # Whole-clip median height: a fixed descriptive normalizer, never applied to animation.
    height = statistics.median(p[idx['Head']][1] - min(p[idx[n]][1] for n in ['Foot_L', 'Foot_R', 'Toes_L', 'Toes_R']) for p in poses)
    if height <= 0:
        raise ValueError('Nonpositive body height')
    metrics = {'torso_forward_tilt_deg': []}
    for side in ('L', 'R'):
        for key in ('hand_forward_height_ratio', 'hand_above_hips_height_ratio', 'elbow_flexion_deg'):
            metrics[f'{side}_{key}'] = []
    for pose in poses:
        torso = sub(pose[idx['Neck']], pose[hips])
        metrics['torso_forward_tilt_deg'].append(math.degrees(math.atan2(dot(torso, forward), torso[1])))
        for side in ('L', 'R'):
            hand = sub(pose[idx[f'Hand_{side}']], pose[hips])
            upper = sub(pose[idx[f'UpperArm_{side}']], pose[idx[f'LowerArm_{side}']])
            lower = sub(pose[idx[f'Hand_{side}']], pose[idx[f'LowerArm_{side}']])
            cosine = dot(upper, lower) / (math.sqrt(dot(upper, upper)) * math.sqrt(dot(lower, lower)))
            metrics[f'{side}_elbow_flexion_deg'].append(180 - math.degrees(math.acos(max(-1., min(1., cosine)))))
            metrics[f'{side}_hand_forward_height_ratio'].append(dot(hand, forward) / height)
            metrics[f'{side}_hand_above_hips_height_ratio'].append(hand[1] / height)
    return {'height_normalizer_source_units': height, 'forward_from_net_travel': forward,
            'net_travel_source_units': distance, 'metrics': {key: summary(values) for key, values in metrics.items()}}


def audit():
    manifest = json.loads((ROOT / 'data/pilot_manifest.json').read_text())
    result = {'translation_mode': 'channels_replace_offset', 'comparison': 'legacy offset_plus_channels',
              'scope': 'M01-M03, all frames plus middle 80%; geometric descriptions, not status labels', 'clips': []}
    for number, entry in enumerate(manifest['entries'][:3], 1):
        path = ROOT / entry['file']
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry['sha256']:
            raise ValueError(f'Source changed: {path.name}')
        motion = load(path)
        corrected = [motion.positions(i, translation_mode='channels_replace_offset') for i in range(len(motion.frames))]
        legacy = [motion.positions(i) for i in range(len(motion.frames))]
        quaternion = [quaternion_positions(motion, i) for i in range(len(motion.frames))]
        max_error = max(abs(x-y) for a,b in zip(corrected, quaternion) for p,q in zip(a,b) for x,y in zip(p,q))
        if max_error > 1e-7:
            raise ValueError(f'Independent recursion mismatch: {max_error}')
        names = [joint.name for joint in motion.joints]
        lo, hi = int(len(corrected)*.1), int(len(corrected)*.9)
        ratios = []
        for a, b in zip(legacy, corrected):
            for j, joint in enumerate(motion.joints):
                if joint.parent in (None, 0) or not joint.channels:
                    continue
                length = math.dist(b[j], b[joint.parent])
                if length > 1e-8:
                    ratios.append(math.dist(a[j], a[joint.parent]) / length)
        result['clips'].append(dict(id=f'M{number:02}', source=path.name, sha256=digest,
                                   frames=len(corrected), max_quaternion_matrix_difference=max_error,
                                   legacy_to_corrected_bone_length_ratio=summary(ratios),
                                   corrected=describe(corrected, names), legacy=describe(legacy, names),
                                   corrected_middle_80_percent=describe(corrected[lo:hi], names)))
    output = ROOT / 'outputs/posture-audit'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    for clip in result['clips']:
        print(clip['id'], 'FK discrepancy', clip['max_quaternion_matrix_difference'], 'old/new bone ratios', clip['legacy_to_corrected_bone_length_ratio'])
        print(json.dumps(clip['corrected']['metrics'], ensure_ascii=False))
    return result


if __name__ == '__main__':
    audit()
