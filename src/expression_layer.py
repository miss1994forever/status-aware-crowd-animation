"""Upper-body reference layering INSIDE the frozen predictive chooser.

Own-reference local bone directions are blended into each candidate, with root
and leg samples unchanged. This is a procedural synthesis hypothesis, not a
status model or physical character controller. No neighbor reference is read.
"""
from contextlib import contextmanager
import copy
import numpy as np
from src.predictive_motion_lab import controller


def unit_slerp(a, b, weight):
    """Unit-direction interpolation, including deterministic antipodal handling."""
    if weight == 0:
        return a.copy()
    if weight == 1:
        return b.copy()
    dot = np.clip(np.sum(a*b, axis=-1, keepdims=True), -1., 1.)
    tangent = b-dot*a
    norm = np.linalg.norm(tangent, axis=-1, keepdims=True)
    axis = np.eye(3)[np.argmin(np.abs(a), axis=-1)]
    fallback = axis-np.sum(axis*a, axis=-1, keepdims=True)*a
    fallback /= np.maximum(np.linalg.norm(fallback, axis=-1, keepdims=True), 1e-12)
    tangent = np.where(norm > 1e-8, tangent/np.maximum(norm, 1e-12), fallback)
    angle = np.arccos(dot)*weight
    out = np.cos(angle)*a+np.sin(angle)*tangent
    return out/np.maximum(np.linalg.norm(out, axis=-1, keepdims=True), 1e-12)


def upper_mask(lib):
    # Whole Spine subtree, not pelvis or legs; derive descendants from skeleton.
    spine = lib.names.index('Spine')
    mask = []
    for j, parent in enumerate(lib.parents):
        mask.append(j == spine or (parent is not None and mask[parent]))
    return np.array(mask)


def layer_pose(lib, base, reference, weight):
    if not 0 <= weight <= 1:
        raise ValueError('Layer strength must lie in [0, 1]')
    if weight == 0:
        return base.copy()
    mask = upper_mask(lib)
    result = base.copy()
    for j, parent in enumerate(lib.parents):
        if parent is None or not mask[j]:
            continue
        va = base[..., j, :]-base[..., parent, :]
        vb = reference[..., j, :]-reference[..., parent, :]
        na = np.linalg.norm(va, axis=-1, keepdims=True)
        nb = np.linalg.norm(vb, axis=-1, keepdims=True)
        fallback = np.zeros_like(va);fallback[..., 1] = 1
        ua = np.where(na > 1e-12, va/np.maximum(na, 1e-12), fallback)
        ub = np.where(nb > 1e-12, vb/np.maximum(nb, 1e-12), ua)
        direction = unit_slerp(ua, ub, weight)
        result[..., j, :] = result[..., parent, :]+direction*lib.lengths[j]
    return result


def personal_library(base, reference, strength):
    """Precompute a personal candidate library; no new data or training."""
    if strength == 0:
        return base
    lib = copy.copy(base)
    ref = np.broadcast_to(base.poses[reference], base.poses.shape)
    lib.poses = layer_pose(base, base.poses, ref, strength)
    # Own source is identity, including numerical precision.
    lib.poses[reference] = base.poses[reference]
    # The original clip-profile expression penalty is NOT used in this experiment.
    # Original features remain archival metadata only; all runs force p_weight=0.
    return lib


@contextmanager
def layered_controller(base, strength):
    if not 0 <= strength <= 1:
        raise ValueError('Layer strength must lie in [0, 1]')
    original_choose, original_rollout = controller.choose, controller.rollout
    libraries = {}

    def own(state):
        if state.reference not in libraries:
            libraries[state.reference] = personal_library(base, state.reference, strength)
        return libraries[state.reference]

    def rollout(lib, state, opts, times):
        return original_rollout(own(state), state, opts, times)

    def choose(lib, state, snapshot, walls, mode='G', p_weight=0, log=False):
        if p_weight != 0:
            raise ValueError('Archival clip-expression P is invalid for layered candidates')
        opt, decision = original_choose(own(state), state, snapshot, walls, mode, 0, log)
        decision['layer_strength'] = strength
        for entry in decision['candidates']:
            entry.pop('expression', None)
        return opt, decision

    try:
        controller.choose, controller.rollout = choose, rollout
        yield
    finally:
        controller.choose, controller.rollout = original_choose, original_rollout
