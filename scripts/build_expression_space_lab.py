"""Offline deterministic builder. Writes only expression-space-lab directories."""
import sys,json,hashlib,platform
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.locomotion import Cycle
from src.expression_space_lab.model import quality,phase_map,aligned_blend
OUT=ROOT/'outputs/expression-space-lab';META=ROOT/'data/expression-space-lab'


def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
def load_cycle(c):
    z=c['methods']['improved'];return Cycle(z['poses'],z['tangents'],z['stride'],z['evidence'],z['parents'],z['bone_lengths'])
def sample(c,u):return np.array(c.sample(c.stride*u))
def offset(c):return c.evidence['phase_offset']

def metrics(poses,original,parents,lengths,dt,names):
    p=np.array(poses);o=np.array(original);err=[]
    for j,k in enumerate(parents):
        if k is not None and lengths[j]>1e-7:err.extend(abs(np.linalg.norm(p[:,j]-p[:,k],axis=1)-lengths[j]))
    foot=[names.index(n) for n in ['Foot_L','Toes_L','Foot_R','Toes_R']]
    velocities=np.diff(p,axis=0)/dt
    return dict(max_bone_absolute_error=float(max(err)),max_frame_displacement=float(np.linalg.norm(np.diff(p,axis=0),axis=2).max()),
        max_foot_change_from_same_source_phase=float(np.linalg.norm(p[:,foot]-o[:,foot],axis=2).max()),
        minimum_toe_height=float(p[:,[names.index('Toes_L'),names.index('Toes_R')],1].min()),
        maximum_joint_speed=float(np.linalg.norm(velocities,axis=2).max()),
        all_finite=bool(np.isfinite(p).all()))

def build():
    OUT.mkdir(exist_ok=True,parents=True);META.mkdir(exist_ok=True,parents=True)
    oldpath=ROOT/'data/expression-space-lab/input-cycles.json';old=json.loads(oldpath.read_text());entries=[];allmetrics=[]
    for clip in old['clips']:
        src=clip['review']['source']
        if hashlib.sha256((ROOT/src['file']).read_bytes()).hexdigest()!=src['sha256']:
            raise ValueError('Frozen source identity mismatch: '+src['file'])
    for bi,di in [(0,1),(2,3)]:
        b,d=old['clips'][bi],old['clips'][di];c,donor=load_cycle(b),load_cycle(d)
        names=b['names'];parents=c.parents;lengths=np.array(c.bone_lengths);T=c.evidence['period_seconds'];N=240
        variants={};rows=[]
        # Determine donor phase shift with labelled feet; test shifts independent of upper body.
        us=np.arange(96)/96; feet=[names.index('Toes_L'),names.index('Toes_R')]
        def relative(p):return p[feet]-p[0]
        costs=[]
        for sh in range(96):
            costs.append(float(np.mean([(relative(sample(c,u))-relative(sample(donor,u+sh/96)))**2 for u in us])))
        shift=int(np.argmin(costs))/96
        specs=[('original',0,'B',3,True,True),('B_050',.5,'B',3,True,True),('B_100',1,'B',3,True,True),
          ('no_timing',1,'B',3,False,True),('no_shape',1,'B',3,True,False),('first_round',1,'B',1,True,True),('before_knee_fix',1,'B',2,True,True),
          ('old_upper',1,'upper',2,False,False),('A_050',.5,'A',2,False,False),('A_100',1,'A',2,False,False)]
        for key,s,route,ver,timing,shape in specs:
            poses=[];same=[];times=[]
            for n in range(N+1):
                u=n/N;v=float(phase_map(u,s,.68 if ver==1 else .32)) if route=='B' and timing else u
                # Native anatomical phase for B; donor alignment always label-aware.
                p=sample(c,v);ref=sample(donor,v+shift)
                result=quality(p,names,parents,lengths,v,s,shape=shape,version=ver) if route=='B' else aligned_blend(p,ref,parents,lengths,s,route=='upper',names)
                poses.append(result.tolist());same.append(p.tolist());times.append(v*T)
            m=metrics(poses,same,parents,lengths,T/N,names)
            m.update(id=key,strength=s,route=route,source_time_rate_bounds=[1-s*(.68 if ver==1 else .32),1+s*(.68 if ver==1 else .32)] if timing else [1,1])
            variants[key]=dict(poses=np.round(poses,8).tolist(),source_times=times,metrics=m)
            rows.append(m)
        # Exact source interval for user reference: no closure or bone projection.
        ev=c.evidence;raw=np.array(b['raw'][ev['start']:ev['end']+1]);raw-=raw[0,0]*np.array([1,0,1]);raw-=np.arange(len(raw))[:,None,None]/(len(raw)-1)*(raw[-1,0]-raw[0,0])*np.array([1,0,1])
        variants['raw']=dict(poses=raw.round(8).tolist(),source_times=np.linspace(0,T,len(raw)).tolist(),metrics={'id':'raw'})
        # Real unmodified frame window, root-centred in display, no repeating seam.
        source=b['review']['source'];sourcepath=ROOT/source['file']
        row=dict(id=b['id'],label='向前行走' if bi==0 else '向左侧移',names=names,parents=parents,lengths=lengths.tolist(),
            cycle=b['methods']['improved'],duration=T,stride=c.stride,dt=b['dt'],variants=variants,source=source,source_sha256=hashlib.sha256(sourcepath.read_bytes()).hexdigest(),
            extraction=ev,donor=d['id'],donor_source=d['review']['source'],donor_phase_shift=shift,phase_cost_min=min(costs),phase_cost_max=max(costs))
        entries.append(row);allmetrics.append(dict(base=b['id'],variants=rows))
    payload=dict(schema=1,source_cycle_sha256=hashlib.sha256(oldpath.read_bytes()).hexdigest(),clips=entries)
    dump(OUT/'experiment.json',payload);dump(META/'metrics.json',allmetrics)
    dump(META/'build.json',dict(python=platform.python_version(),numpy=np.__version__,code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'src/expression_space_lab/model.py',ROOT/'src/expression_space_lab/ui.js',ROOT/'src/expression_space_lab/index.html',ROOT/'src/locomotion.py',ROOT/'locomotion/runtime.js',ROOT/'src/expression_layer.py']},human_ratings=[]))
    html=(ROOT/'src/expression_space_lab/index.html').read_text().replace('/*__DATA__*/',json.dumps(payload,ensure_ascii=False).replace('</','<\\/')).replace('/*__KERNEL__*/',(ROOT/'locomotion/runtime.js').read_text()).replace('/*__UI__*/',(ROOT/'src/expression_space_lab/ui.js').read_text())
    (OUT/'index.html').write_text(html)
    print(OUT/'index.html');print(json.dumps(allmetrics,ensure_ascii=False,indent=2))
if __name__=='__main__':build()
