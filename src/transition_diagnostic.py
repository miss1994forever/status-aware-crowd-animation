"""Post-hoc admissibility experiment; does not alter the frozen controller.

The bound measures discrepancy from the destination source pose, NOT perceived
naturalness, anatomical validity or status. It can reject a valid style blend.
"""
from contextlib import contextmanager
import numpy as np
from src.predictive_motion_lab import controller


def matched_phase_offsets(lib, state, clip):
    """Three lowest pose/velocity costs from a 32-phase bank plus old offsets.

This is a motion-matching heuristic, not a new research contribution. Candidate
count is held fixed, but preprocessing costs more and future shape diversity may
be lost. Source style labels do not enter this search.
    """
    offsets = np.unique(np.concatenate([np.arange(32)/32-.5, [-.08, 0, .08]]))
    phases = (state.phase+offsets) % 1
    rate = state.speed/max(lib.speeds[clip], 1e-6)/lib.periods[clip]
    poses = lib.sample(clip, phases)
    velocities = lib.velocity(clip, phases, rate)
    costs = 2*np.sqrt(np.mean((poses-state.pose)**2, axis=(1, 2)))
    costs += .08*np.sqrt(np.mean((velocities-state.pose_velocity)**2, axis=(1, 2)))
    return offsets[np.argsort(costs, kind='stable')[:3]]


def select_bounded(lib, original_choose, state, snapshot, walls, mode='G',
                   p_weight=0, log=False, limit=.1):
    if not 0 <= limit <= .4:
        raise ValueError('Diagnostic bound must be between zero and frozen .4')
    _, decision = original_choose(lib, state, snapshot, walls, mode, p_weight, True)
    entries = decision['candidates']
    eligible = [i for i, c in enumerate(entries)
                if c['feasible'] and c['deformation'] <= limit]
    selected = min(eligible, key=lambda i: entries[i]['score']) if eligible else None
    decision['frozen_safe_count'] = decision['safe_count']
    decision['safe_count'] = len(eligible)
    decision['source_discrepancy_limit'] = limit
    for i, c in enumerate(entries):
        c['selected'] = i == selected
        if c['deformation'] > limit:
            c['feasible'] = False
            c['reason'] = 'diagnostic_source_discrepancy_limit'
    # Frozen traces show the old winner; do not mislabel them after re-selection.
    decision['traces'] = []
    if selected is None:
        return None, decision
    c = entries[selected]
    return np.array([[lib.ids.index(c['clip']), c['scale'], c['steer'],
                      c['phase_offset']]]), decision


@contextmanager
def bounded_controller(lib, limit, own_source_style=False, phase_matching=False):
    """Single-process diagnostic scope; restores globals even on exceptions."""
    original_choose, original_options = controller.choose, controller.options
    styles = np.array([c['source']['source_style'] for c in lib.clips])

    def choose(library, state, snapshot, walls, mode='G', p_weight=0, log=False):
        return select_bounded(library, original_choose, state, snapshot, walls,
                              mode, p_weight, log, limit)

    def options(library, state, mode):
        rows = original_options(library, state, mode)
        if own_source_style:
            rows = rows[styles[rows[:, 0].astype(int)] == styles[state.reference]]
        if phase_matching:
            rows = rows.copy()
            for clip in np.unique(rows[:, 0].astype(int)):
                if clip == state.clip:
                    continue
                offsets = matched_phase_offsets(library, state, clip)
                indices = np.flatnonzero(rows[:, 0] == clip)
                # Do not let one replacement get replaced a second time.
                old_offsets = rows[indices, 3].copy()
                for old, new in zip([-.08, 0, .08], offsets):
                    rows[indices[old_offsets == old], 3] = new
        return rows

    try:
        controller.choose, controller.options = choose, options
        yield
    finally:
        controller.choose, controller.options = original_choose, original_options
