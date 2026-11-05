"""Fixed-motion expression diagnostic, NOT a closed-loop controller.

Decode each .2s execution block from its saved .05s phases, clips and speeds.
Resynthesize only pose with the original inertial-offset / fixed-bone routine.
Root motion, phase, speed, actions, holds and arrivals are copied unchanged.
Changing the body after planning invalidates the original collision guarantee.
"""
import copy
import numpy as np
from src.expression_layer import personal_library, upper_mask
from src.predictive_motion_lab.controller import initial
from src.predictive_motion_lab.motion import rebuild


def resynthesize(base, source, strength):
    if not 0 <= strength <= 1:
        raise ValueError('Strength must be in [0, 1]')
    frames = source['frames']
    if (len(frames)-1) % 4 or len(frames) < 5:
        raise ValueError('Expected complete .2s blocks at 20Hz')
    np.testing.assert_allclose([f['t'] for f in frames], np.arange(len(frames))*.05, atol=1e-8)
    states = initial(base, source['spec'])
    if len(states) != len(frames[0]['agents']):
        raise ValueError('Agent count mismatch')
    libraries = {s.reference: personal_library(base, s.reference, strength) for s in states}
    poses = [s.pose.copy() for s in states]
    velocities = [s.pose_velocity.copy() for s in states]
    out = copy.deepcopy(source)
    out['decisions'] = []  # Prior safety/selection logs do not describe the new body.
    out['mode'] = 'fixed_motion_expression_diagnostic'
    out['layer_strength'] = strength
    out['runtime'] = {k: v for k, v in source['runtime'].items() if not k.startswith('planning_')}
    out['limitations'] = ['Not replanned; copied arrival times are not a new navigation result.',
                          'Body occupancy changes; collision audit must be recomputed.',
                          'No status labels, perceived-rank calibration or neighbor estimation.']
    for start in range(0, len(frames)-1, 4):
        for i, s in enumerate(states):
            a = frames[start]['agents'][i]
            next_agents = [frames[start+j]['agents'][i] for j in range(1, 5)]
            if any(x['id'] != s.id for x in [a, *next_agents]):
                raise ValueError('Agent ordering changed')
            # Holds / terminal states retain their last synthesized pose exactly.
            if a['arrived'] or next_agents[0]['hold']:
                block = [poses[i].copy() for _ in range(4)]
                velocities[i] = np.zeros_like(poses[i])
            else:
                lib = libraries[s.reference]
                clip = base.ids.index(next_agents[0]['clip'])
                if any(x['clip'] != next_agents[0]['clip'] for x in next_agents):
                    raise ValueError('Action changes inside an execution block')
                # Invert the first integration step, including its phase wrap.
                first = next_agents[0]
                entry_phase = (first['phase'] - first['speed']/lib.speeds[clip]/lib.periods[clip]*.05) % 1
                rate = a['speed']/lib.speeds[clip]/lib.periods[clip]
                delta = poses[i]-lib.sample(clip, entry_phase)
                dv = velocities[i]-lib.velocity(clip, entry_phase, rate)
                block = []
                for j, x in enumerate(next_agents, 1):
                    t = j*.05
                    u = t/.4
                    fade = 1-10*u**3+15*u**4-6*u**5
                    source_pose = lib.sample(clip, x['phase'])
                    block.append(rebuild(source_pose+(delta+dv*t)*fade, lib.parents, lib.lengths))
                velocities[i] = (block[-1]-block[-2])/.05
            poses[i] = block[-1]
            for j, p in enumerate(block, 1):
                out['frames'][start+j]['agents'][i]['pose'] = p.round(6).tolist()
    return out


def compare_contract(base, source, result):
    root_fields = ['id', 'pos', 'yaw', 'travel', 'speed', 'clip', 'phase', 'hold', 'arrived']
    assert len(source['frames']) == len(result['frames'])
    for fa, fb in zip(source['frames'], result['frames']):
        assert fa['t'] == fb['t']
        for a, b in zip(fa['agents'], fb['agents']):
            assert all(a[k] == b[k] for k in root_fields)
    pa = np.array([[a['pose'] for a in f['agents']] for f in source['frames']])
    pb = np.array([[a['pose'] for a in f['agents']] for f in result['frames']])
    errors = [np.max(np.abs(np.linalg.norm(pb[..., j, :]-pb[..., p, :], axis=-1)-base.lengths[j]))
              for j, p in enumerate(base.parents) if p is not None]
    return {'root_motion_actions_phase_flags_exactly_equal': True,
            'pose_node_difference_max': float(np.linalg.norm(pa-pb, axis=-1).max()),
            'non_upper_node_difference_max': float(np.abs(pa[..., ~upper_mask(base), :]-pb[..., ~upper_mask(base), :]).max()),
            'rounded_bone_length_error_max': float(max(errors)),
            'frame_count': len(pa), 'agent_count': pa.shape[1]}
