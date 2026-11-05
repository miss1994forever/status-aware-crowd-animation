"""Distance-driven gait and analytic paths; no navigation, interactions or status.

Pose provider is deliberately injectable: source BVH import conventions must be
confirmed independently of this locomotion layer. All display scaling is global.
"""
from dataclasses import dataclass
import math
import statistics


def source_positions(motion, frame):
    """Replace this boundary when the dataset's BVH translation convention changes."""
    return motion.positions(frame, translation_mode="channels_replace_offset")


def norm(v):
    return math.sqrt(sum(x*x for x in v))


def rms(vectors):
    return math.sqrt(sum(sum(x*x for x in v) for v in vectors) / len(vectors))


def hermite(a, b, va, vb, t, step=1.):
    return [(2*t**3-3*t*t+1)*x + (t**3-2*t*t+t)*step*vx
            + (-2*t**3+3*t*t)*y + (t**3-t*t)*step*vy
            for x, y, vx, vy in zip(a, b, va, vb)]


@dataclass
class Cycle:
    poses: list
    tangents: list
    stride: float
    evidence: dict
    parents: list
    bone_lengths: list

    def sample(self, distance):
        phase = (distance / self.stride) % 1
        last = len(self.poses)-1
        x = phase*last
        i = min(int(x), last-1)
        points = [hermite(a,b,va,vb,x-i,1/last)
                  for a,b,va,vb in zip(self.poses[i], self.poses[i+1], self.tangents[i], self.tangents[i+1])]
        # Rebuild using source median bone lengths. Hips retains its residual motion.
        result=[]
        for j,p in enumerate(points):
            parent=self.parents[j]
            if parent is None:
                result.append(p)
            else:
                v=[p[a]-points[parent][a] for a in range(3)]
                length=norm(v)
                if length<1e-10 and self.bone_lengths[j]>1e-8:
                    raise ValueError('Collapsed interpolated bone')
                result.append([result[parent][a]+v[a]*self.bone_lengths[j]/max(length,1e-10) for a in range(3)])
        return result


def build_cycle(motion, pose_provider=source_positions):
    poses = [pose_provider(motion, i) for i in range(len(motion.frames))]
    names = [j.name for j in motion.joints]
    hips, head = names.index('Hips'), names.index('Head')
    left, right = names.index('Shoulder_L'), names.index('Shoulder_R')
    toes = [names.index('Toes_L'), names.index('Toes_R')]
    body = range(1, len(names))
    height = statistics.median(p[head][1]-min(p[k][1] for k in toes) for p in poses)
    if height <= 0:
        raise ValueError('Expected Y-up source body; verify source coordinates')
    # Constant anatomical forward from average shoulder lateral, checked against travel.
    lateral = [statistics.mean(p[left][a]-p[right][a] for p in poses) for a in (0,2)]
    forward = [-lateral[1], lateral[0]]
    forward = [v/norm(forward) for v in forward]
    total_travel = [poses[-1][hips][a]-poses[0][hips][a] for a in (0,2)]
    facing_dot = sum(a*b for a,b in zip(forward,total_travel))/norm(total_travel)
    if facing_dot < .8:
        raise ValueError('M01 is not travelling along inferred anatomical forward')
    heading = math.atan2(forward[0], forward[1])
    co, si = math.cos(heading), math.sin(heading)
    floor = min(p[k][1] for p in poses for k in toes)

    def velocity(f,k):
        return [(poses[f+1][k][a]-poses[f-1][k][a])/2 for a in range(3)]

    candidates = []
    # Search one full stride, not half-stride or the entire recording.
    for start in range(8, len(poses)-30):
        for period in range(24, 43):
            end = start+period
            if end >= len(poses)-8:
                continue
            drift = [(poses[end][hips][a]-poses[start][hips][a])/period if a!=1 else 0 for a in range(3)]
            delta = [[poses[end][k][a]-poses[start][k][a]-period*drift[a] for a in range(3)] for k in body]
            dv = [[velocity(end,k)[a]-velocity(start,k)[a] for a in range(3)] for k in body]
            pose_error, velocity_error = rms(delta), rms(dv)/motion.frame_time
            score = (pose_error + .08*velocity_error)/height
            candidates.append((score,start,end,pose_error,velocity_error))
    score,start,end,raw_error,raw_velocity = min(candidates)
    period = end-start
    origin = poses[start][hips]
    drift = [(poses[end][hips][a]-origin[a])/period if a!=1 else 0 for a in range(3)]
    stride = norm([period*drift[a] for a in (0,2)])/height

    def rotate_scale(p):
        return [(co*p[0]-si*p[2])/height,p[1]/height,(si*p[0]+co*p[2])/height]

    local, tangents = [], []
    for f in range(start,end+1):
        local.append([rotate_scale([poses[f][k][a]-(floor if a==1 else origin[a]+(f-start)*drift[a]) for a in range(3)]) for k in body])
        tangents.append([rotate_scale([(velocity(f,k)[a]-drift[a])*period for a in range(3)]) for k in body])
    raw_local = [[v[:] for v in p] for p in local]
    # Cubic correction closes both position and first derivative at chosen matching phases.
    max_correction = 0
    for k in range(len(body)):
        d = [b-a for a,b in zip(local[0][k],local[-1][k])]
        dv = [a-b for a,b in zip(tangents[0][k],tangents[-1][k])]
        A,B = [v+2*x for v,x in zip(dv,d)],[-v-3*x for v,x in zip(dv,d)]
        for f in range(period+1):
            u=f/period
            c=[a*u**3+b*u*u for a,b in zip(A,B)]
            dc=[3*a*u*u+2*b*u for a,b in zip(A,B)]
            max_correction=max(max_correction,norm(c))
            local[f][k]=[v+x for v,x in zip(local[f][k],c)]
            tangents[f][k]=[v+x for v,x in zip(tangents[f][k],dc)]
    # Quantify Cartesian interpolation/correction rather than claim rigid-bone preservation.
    max_bone_error=0
    for f in range(period+1):
        for k,joint in enumerate(motion.joints[1:]):
            if joint.parent in (None,0):
                continue
            parent=joint.parent-1
            old=norm([raw_local[f][k][a]-raw_local[f][parent][a] for a in range(3)])
            new=norm([local[f][k][a]-local[f][parent][a] for a in range(3)])
            if old>1e-5:
                max_bone_error=max(max_bone_error,abs(new/old-1))
    evidence=dict(start_frame_zero_based=start,end_frame_zero_based=end,period_frames=period,
                  period_seconds=period*motion.frame_time,stride_body_heights=stride,
                  source_body_height=height,source_floor=floor,source_forward_xz=forward,
                  forward_travel_cosine=facing_dot,source_heading_radians=heading,
                  candidate_count=len(candidates),score=score,raw_endpoint_rms_body_heights=raw_error/height,
                  raw_endpoint_velocity_rms_body_heights_per_second=raw_velocity/height,
                  max_correction_body_heights=max_correction,
                  max_sampled_bone_length_relative_change=max_bone_error,
                  closed_endpoint_rms=rms([[b-a for a,b in zip(x,y)] for x,y in zip(local[0],local[-1])]),
                  closed_endpoint_tangent_rms=rms([[b-a for a,b in zip(x,y)] for x,y in zip(tangents[0],tangents[-1])]))
    parents=[None if j.parent in (None,0) else j.parent-1 for j in motion.joints[1:]]
    lengths=[0 if parent is None else statistics.median(norm([p[k+1][a]-p[parent+1][a] for a in range(3)])/height for p in poses)
             for k,parent in enumerate(parents)]
    cycle=Cycle(local,tangents,stride,evidence,parents,lengths)
    max_output_correction=0
    for f in range(period):
        output=cycle.sample(stride*f/period)
        max_output_correction=max(max_output_correction,max(norm([a-b for a,b in zip(x,y)]) for x,y in zip(output,raw_local[f])))
    evidence['max_final_position_correction_body_heights']=max_output_correction
    # Contact is a height heuristic, not a labelled support phase or verified contact.
    speeds=[]
    nominal_speed=stride/evidence['period_seconds']
    dt=1/300
    foot_indices=[k-1 for k in toes]
    foot_floor=min(cycle.sample(stride*f/300)[k][1] for f in range(300) for k in foot_indices)
    for f in range(300):
        d=stride*f/300
        before=cycle.sample(d-nominal_speed*dt)
        after=cycle.sample(d+nominal_speed*dt)
        for k in foot_indices:
            if cycle.sample(d)[k][1]<foot_floor+.025:
                v=[(after[k][a]-before[k][a])/(2*dt)+(nominal_speed if a==2 else 0) for a in (0,2)]
                speeds.append(norm(v))
    evidence['contact_heuristic_straight_foot_speed_body_heights_per_second']={
        'samples':len(speeds),'median':statistics.median(speeds) if speeds else None,
        'max':max(speeds) if speeds else None,'height_threshold':.025}
    return cycle


def path_at(distance, kind='curve', index=0, count=1):
    """Unbounded straight lanes or evenly spaced same-direction ring traffic."""
    if kind=='straight':
        return [(index-(count-1)/2)*.85,0,distance], 0.
    if kind!='curve':
        raise ValueError('Unknown path')
    radius=3.2
    theta=distance/radius+2*math.pi*index/count
    return [radius*math.sin(theta),0,radius*math.cos(theta)], math.pi/2+theta


def place_pose(pose, position, heading):
    c,s=math.cos(heading),math.sin(heading)
    return [[position[0]+c*x+s*z,position[1]+y,position[2]-s*x+c*z] for x,y,z in pose]
