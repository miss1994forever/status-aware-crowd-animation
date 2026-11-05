"""Small finite motion-matching baseline. No status, obstacles or hidden labels.

World target velocity + facing -> trajectory/pose/velocity score. Every candidate
has one second of real future. Continue is explicit, never modulo. Fixed heuristic
weights are development settings, not a learned or validated behavior model.
"""
from dataclasses import dataclass
import numpy as np
from src.finite_motion import multiply, rotate, slerp


def yaw_quaternion(angle):
    angle = np.asarray(angle)
    q = np.zeros(angle.shape+(4,))
    q[..., 0] = np.cos(angle/2); q[..., 2] = np.sin(angle/2)
    return q


def heading(q):
    forward = rotate(q, np.array([0., 0., 1.]))
    return np.arctan2(forward[..., 0], forward[..., 2])


def wrap(angle):
    return (angle+np.pi) % (2*np.pi)-np.pi


@dataclass
class Segment:
    sequence: object
    source_id: int
    source_time: float
    clock: float
    origin: np.ndarray
    yaw: float

    def local(self, clock):
        t = self.source_time+clock-self.clock
        root, q = self.sequence.local_sample(t)
        anchor = self.sequence.local_sample(self.source_time)[0].copy(); anchor[1] = 0
        rotation = yaw_quaternion(self.yaw)
        root = rotate(rotation, root-anchor)+np.array([self.origin[0], 0., self.origin[1]])
        q = q.copy(); q[..., 0, :] = multiply(rotation, q[..., 0, :])
        return root, q


class Database:
    horizons = np.array([.33, .66, 1.])

    def __init__(self, sequences, stride=12):
        self.sequences = sequences; base = sequences[0]
        for seq in sequences:
            if seq.names != base.names or seq.parents != base.parents or not np.allclose(seq.offsets, base.offsets, atol=1e-8):
                raise ValueError('Cannot mix incompatible skeletons')
        self.ids = []; self.times = []; self.poses = []; self.velocity = []
        self.future = []; self.facing = []; self.yaws = []
        for index, seq in enumerate(sequences):
            t = seq.eligible_starts(1., stride)
            p = seq.sample(t); later = seq.sample(t+seq.dt)
            root, q = seq.local_sample(t); yaw = heading(q[:, 0]); inv = yaw_quaternion(-yaw)
            self.ids.extend([index]*len(t)); self.times.extend(t)
            self.yaws.extend(yaw)
            self.poses.extend(rotate(inv[:, None], p-root[:, None]))
            self.velocity.extend(rotate(inv[:, None], (later-p)/seq.dt))
            futures = []; faces = []
            for horizon in self.horizons:
                r, fq = seq.local_sample(t+horizon)
                futures.append(rotate(inv, r-root)[:, [0, 2]])
                faces.append(wrap(heading(fq[:, 0])-yaw))
            self.future.extend(np.stack(futures, axis=1))
            self.facing.extend(np.stack(faces, axis=1))
        for name in ['ids', 'times', 'poses', 'velocity', 'future', 'facing', 'yaws']:
            setattr(self, name, np.asarray(getattr(self, name)))
        # Reference head-to-lowest-node height; not an assertion of SI units.
        p = base.sample(np.arange(0, min(10., base.duration), .1))
        self.height = float(np.median(p[:, base.names.index('Head'), 1]-p[:, :, 1].min(axis=1)))
        self.feet = [base.names.index(n) for n in ['LeftAnkle', 'RightAnkle', 'LeftToe', 'RightToe']]

    def costs(self, pose, velocity, yaw, target_velocity, target_facing):
        inv = yaw_quaternion(-yaw)
        query_pose = rotate(inv, pose-pose[0]); query_vel = rotate(inv, velocity)
        local_target = rotate(inv, np.array([target_velocity[0], 0., target_velocity[1]]))[[0, 2]]
        trajectory = np.mean(((self.future-self.horizons[None, :, None]*local_target)/self.height)**2, axis=(1, 2))
        posture = np.mean(((self.poses-query_pose)/self.height)**2, axis=(1, 2))
        feet = np.mean(((self.poses[:, self.feet]-query_pose[self.feet])/self.height)**2, axis=(1, 2))
        speed = np.mean(((self.velocity-query_vel)/self.height)**2, axis=(1, 2))
        face = np.mean(wrap(self.facing-(target_facing-yaw))**2, axis=1)
        return dict(trajectory=trajectory, posture=posture, feet=feet, speed=speed, facing=face)


class Matcher:
    weights = dict(trajectory=5., posture=2., feet=3., speed=.12, facing=.08)
    blend_seconds = .25
    switch_penalty = .012

    def __init__(self, database, source_id=0, source_time=1.):
        self.db = database; seq = database.sequences[source_id]
        _, q = seq.local_sample(source_time)
        self.active = Segment(seq, source_id, source_time, 0., np.zeros(2), -float(heading(q[0])))
        self.outgoing = None; self.last_change = -100.; self.log = []

    def local(self, clock, blend=True):
        root, q = self.active.local(clock)
        age = clock-self.last_change
        if blend and self.outgoing is not None and 0 <= age < self.blend_seconds:
            old_root, old_q = self.outgoing.local(clock)
            u = age/self.blend_seconds; w = u*u*(3-2*u)
            root = (1-w)*old_root+w*root
            q = slerp(old_q, q, w)
        return root, q

    def pose(self, clock, blend=True):
        return self.active.sequence.forward(*self.local(clock, blend))

    def choose(self, clock, target_velocity, target_facing):
        if clock-self.last_change < self.blend_seconds:
            raise ValueError('Do not replan during an unfinished transition')
        pose = self.pose(clock); _, q = self.local(clock)
        yaw = float(heading(q[0])); dt = 1/120
        velocity = (self.pose(clock+dt)-pose)/dt
        costs = self.db.costs(pose, velocity, yaw, target_velocity, target_facing)
        scores = sum(self.weights[key]*value for key, value in costs.items())+self.switch_penalty
        index = int(np.argmin(scores)); best = float(scores[index])
        # Score continuation with the same features/weights and no switch penalty.
        seq = self.active.sequence; source_time = self.active.source_time+clock-self.active.clock
        continuation_score = None
        if source_time+1 <= seq.duration:
            inv = yaw_quaternion(-yaw); root = pose[0]
            future = []; facing = []
            for h in self.db.horizons:
                r, fq = self.active.local(clock+h)
                future.append(rotate(inv, r-root)[[0, 2]])
                facing.append(wrap(heading(fq[0])-yaw))
            local_target = rotate(inv, np.array([target_velocity[0], 0., target_velocity[1]]))[[0, 2]]
            trajectory = np.mean(((np.array(future)-self.db.horizons[:, None]*local_target)/self.db.height)**2)
            face = np.mean(wrap(np.array(facing)-(target_facing-yaw))**2)
            continuation_score = float(self.weights['trajectory']*trajectory+self.weights['facing']*face)
        switched = continuation_score is None or best < continuation_score
        row = dict(time=clock, target_velocity=list(target_velocity), target_facing=target_facing,
                   best_score=best, continuation_score=continuation_score, switched=switched,
                   best_terms={k:float(v[index]) for k,v in costs.items()})
        if switched:
            source = int(self.db.ids[index]); start = float(self.db.times[index])
            self.outgoing = self.active
            self.active = Segment(self.db.sequences[source], source, start, clock,
                                  pose[0, [0, 2]].copy(), yaw-float(self.db.yaws[index]))
            self.last_change = clock
        row.update(source_id=self.active.source_id,
                   source_time=self.active.source_time+clock-self.active.clock)
        self.log.append(row)
        return row
