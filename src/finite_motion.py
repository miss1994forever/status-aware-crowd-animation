"""Finite EMM sequence adapter. No cycles, retargeting, status, or clip transitions.

Local rotation SLERP + FK preserves fixed source bones at fractional times.
Source time ends at the LAST SAMPLE, not n*dt. Out-of-range requests fail;
Cursor reports exhaustion instead of silently freezing or wrapping.
"""
from dataclasses import dataclass
import math
import numpy as np


def multiply(a, b):
    """Hamilton product; scalar-first unit quaternions, broadcastable."""
    aw, av = a[..., :1], a[..., 1:]
    bw, bv = b[..., :1], b[..., 1:]
    return np.concatenate((aw*bw-np.sum(av*bv, axis=-1, keepdims=True),
                           aw*bv+bw*av+np.cross(av, bv)), axis=-1)


def rotate(q, v):
    t = 2*np.cross(q[..., 1:], v)
    return v+q[..., :1]*t+np.cross(q[..., 1:], t)


def slerp(a, b, weight):
    dot = np.sum(a*b, axis=-1, keepdims=True)
    b = np.where(dot < 0, -b, b)
    dot = np.clip(np.abs(dot), 0, 1)
    angle = np.arccos(dot)
    denom = np.maximum(np.sin(angle), 1e-12)
    spherical = (np.sin((1-weight)*angle)*a+np.sin(weight*angle)*b)/denom
    linear = (1-weight)*a+weight*b
    q = np.where(dot > .9995, linear, spherical)
    return q/np.linalg.norm(q, axis=-1, keepdims=True)


class FiniteSequence:
    """Strict root-translation / fixed-offset skeleton; rejects Bandai conventions.

    All coordinates remain source units. start/end are inclusive source-frame
    indices. The adapter owns copies and never modifies the supplied Motion.
    """
    def __init__(self, motion, start=0, end=None):
        end = len(motion.frames)-1 if end is None else end
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end < len(motion.frames):
            raise ValueError('Need at least two valid inclusive source frames')
        if not math.isfinite(motion.frame_time) or motion.frame_time <= 0:
            raise ValueError('Invalid frame time')
        self.dt = motion.frame_time
        self.start_frame, self.end_frame = start, end
        self.duration = (end-start)*self.dt
        self.names = [j.name for j in motion.joints]
        self.parents = [j.parent for j in motion.joints]
        if not self.parents or self.parents[0] is not None:
            raise ValueError('Root must be first')
        self.offsets = np.array([j.offset for j in motion.joints], dtype=float)
        values = np.array(motion.frames[start:end+1], dtype=float)
        if not np.isfinite(values).all() or not np.isfinite(self.offsets).all():
            raise ValueError('Non-finite source')
        self.root = np.broadcast_to(self.offsets[0], (len(values), 3)).copy()
        self.rotations = np.zeros((len(values), len(self.names), 4))
        self.rotations[..., 0] = 1
        for j, joint in enumerate(motion.joints):
            if j and (joint.parent is None or not 0 <= joint.parent < j):
                raise ValueError('Need topologically ordered skeleton')
            rotated = False
            for k, channel in enumerate(joint.channels):
                axis = 'XYZ'.index(channel[0])
                value = values[:, joint.channel_start+k]
                if channel.endswith('position'):
                    if j or rotated:
                        raise ValueError('Only root translations before rotations supported')
                    self.root[:, axis] += value
                elif channel.endswith('rotation'):
                    rotated = True
                    half = np.deg2rad(value)/2
                    q = np.zeros((len(values), 4)); q[:, 0] = np.cos(half)
                    q[:, axis+1] = np.sin(half)
                    self.rotations[:, j] = multiply(self.rotations[:, j], q)
                else:
                    raise ValueError('Unknown BVH channel')
        self.rotations /= np.linalg.norm(self.rotations, axis=-1, keepdims=True)
        for array in (self.root, self.offsets, self.rotations):
            array.setflags(write=False)

    def sample(self, seconds):
        """Scalar or 1D times -> (..., joints, xyz), strict finite bounds."""
        root, local = self.local_sample(seconds)
        return self.forward(root, local)

    def local_sample(self, seconds):
        """Root translation and local rotations for bone-preserving transitions."""
        times = np.asarray(seconds, dtype=float)
        if times.ndim > 1 or not np.isfinite(times).all():
            raise ValueError('Expected finite scalar/1D times')
        if np.any(times < 0) or np.any(times > self.duration):
            raise ValueError('Outside finite sequence; replan instead of loop/hold')
        x = times/self.dt
        i = np.minimum(np.floor(x).astype(int), len(self.root)-1)
        k = np.minimum(i+1, len(self.root)-1)
        f = (x-i)[..., None]
        root = self.root[i]*(1-f)+self.root[k]*f
        local = slerp(self.rotations[i], self.rotations[k], f[..., None])
        return root, local

    def forward(self, root, local):
        pose = np.empty(root.shape[:-1]+(len(self.names), 3))
        world = np.empty_like(local)
        pose[..., 0, :] = root; world[..., 0, :] = local[..., 0, :]
        for j in range(1, len(self.names)):
            p = self.parents[j]
            world[..., j, :] = multiply(world[..., p, :], local[..., j, :])
            pose[..., j, :] = pose[..., p, :]+rotate(world[..., p, :], self.offsets[j])
        return pose

    def eligible_starts(self, horizon, stride_frames=1):
        """Candidate frame times with a full real future, never padded frames."""
        if not math.isfinite(horizon) or horizon < 0:
            raise ValueError('Invalid horizon')
        if not isinstance(stride_frames, int) or stride_frames < 1:
            raise ValueError('Invalid stride')
        t = np.arange(0, len(self.root), stride_frames)*self.dt
        return t[t+horizon <= self.duration]

    def placed(self, seconds, *, entry=0., origin_xz=(0., 0.), yaw=0.):
        """Rigid yaw + horizontal placement about the entry root; preserve floor Y.

        yaw is a rotation DELTA in radians, not inferred facing or travel heading.
        No frame-by-frame path warping or time scaling is applied.
        """
        if not math.isfinite(yaw):
            raise ValueError('Invalid yaw')
        origin = np.asarray(origin_xz, dtype=float)
        if origin.shape != (2,) or not np.isfinite(origin).all():
            raise ValueError('Invalid placement')
        anchor = self.sample(entry)[0].copy(); anchor[1] = 0
        q = np.array([np.cos(yaw/2), 0., np.sin(yaw/2), 0.])
        return rotate(q, self.sample(seconds)-anchor)+np.array([origin[0], 0., origin[1]])


@dataclass(frozen=True)
class Advance:
    time: float
    pose: np.ndarray
    root_delta: np.ndarray
    consumed: float
    remaining: float
    exhausted: bool


class Cursor:
    """Owns source time only, not a navigation policy or an idle animation."""
    def __init__(self, sequence, start=0., **placement):
        sequence.sample(start)  # Validate before storing state.
        self.sequence, self.time = sequence, float(start)
        self.placement = dict(entry=start, **placement)

    def advance(self, dt):
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError('Advance requires positive finite dt')
        if self.time >= self.sequence.duration:
            raise RuntimeError('Sequence exhausted: caller must select a successor')
        old = self.sequence.placed(self.time, **self.placement)
        consumed = min(dt, self.sequence.duration-self.time)
        self.time = min(self.sequence.duration, self.time+consumed)
        pose = self.sequence.placed(self.time, **self.placement)
        return Advance(self.time, pose, pose[0]-old[0], consumed, max(0., dt-consumed),
                       self.time >= self.sequence.duration)
