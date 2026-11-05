"""Read-only adapters and batched, bone-preserving pose synthesis."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from src.bvh import load
from src.motion_candidate_lab.cycles import audit


def wrap(a):
    return (a+np.pi) % (2*np.pi)-np.pi


def rebuild(p, parents, lengths):
    out=p.copy()
    for j,parent in enumerate(parents):
        if parent is None: continue
        v=p[...,j,:]-p[...,parent,:]
        out[...,j,:]=out[...,parent,:]+v*(lengths[j]/np.maximum(np.linalg.norm(v,axis=-1),1e-12))[...,None]
    return out


class Library:
    def __init__(self, payload):
        self.payload=payload
        self.clips=payload['clips']; self.ids=[c['id'] for c in self.clips]
        self.parents=self.clips[0]['parents'];self.names=payload['names']
        self.lengths=np.array(self.clips[0]['lengths'])
        self.poses=np.array([c['samples'] for c in self.clips])
        self.speeds=np.array([c['speed'] for c in self.clips])
        self.angles=np.array([c['angle'] for c in self.clips])
        self.periods=np.array([c['period'] for c in self.clips])
        # Features deliberately exclude root speed and labels. Replaceable interface.
        self.features=np.array([c['features'] for c in self.clips])
        self.feature_scale=np.maximum(self.features.std(axis=0),.015)
        self.features_scaled=self.features/self.feature_scale

    def sample(self, clip, phase):
        x=(np.asarray(phase)%1)*128
        i=np.floor(x).astype(int); f=(x-i)[...,None,None]
        return rebuild(self.poses[clip,i]*(1-f)+self.poses[clip,(i+1)%128]*f,
                       self.parents,self.lengths)

    def velocity(self, clip, phase, rate):
        return (self.sample(clip,phase+rate*.001)-self.sample(clip,phase-rate*.001))/.002

    def expression(self, clip, reference):
        return np.mean((self.features_scaled[clip]-self.features_scaled[reference])**2,axis=-1)


def prepare(root):
    """Rebuild cycles directly from verified BVHs; never depend on an old output."""
    root=Path(root);manifest=json.loads((root/'data/pilot_manifest.json').read_text())
    clips=[];coverage=[];height=None
    for i,e in enumerate(manifest['entries']):
        path=root/e['file']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=e['sha256']: raise ValueError('Source hash mismatch')
        info,methods,cycles=audit(load(path),height)
        height=height or info['height'];key=f'M{i+1:02}'
        row={'id':key,'accepted':methods['improved']['accepted'],'source':e,
             'measurements':info['metadata'],'cycle':methods['improved']}
        coverage.append(row)
        if not row['accepted']: continue
        cycle=cycles['improved'];ev=cycle.evidence
        # Canonical phase is left toe forward. Same labels and source lengths throughout.
        samples=np.array([cycle.sample(cycle.stride*(f/128+ev['phase_offset'])) for f in range(128)])
        names=info['names'];hips=names.index('Hips')
        selected=[names.index(n) for n in ['Chest','Head','UpperArm_L','LowerArm_L','Hand_L','UpperArm_R','LowerArm_R','Hand_R']]
        rel=samples[:,selected]-samples[:,hips:hips+1]
        features=np.concatenate([rel.mean(axis=0).flatten(),rel.std(axis=0).flatten()])
        angle=ev['travel_heading_relative_body']
        lateral=np.array([math.cos(angle),0,-math.sin(angle)])
        widths=np.ptp(samples@lateral,axis=1)+.08
        row['width_travel_q05_q50_q95']=np.quantile(widths,[.05,.5,.95]).tolist()
        clips.append({'id':key,'samples':samples.round(8).tolist(),'parents':info['parents'],
                      'lengths':info['lengths'],'speed':ev['native_speed'],'period':ev['period_seconds'],
                      'angle':angle,'features':features.tolist(),'source':e,'closure':ev})
        print('coverage',key,'width',row['width_travel_q05_q50_q95'],flush=True)
    payload={'schema':1,'names':names,'clips':clips,'coverage':coverage,'manifest_sha256':hashlib.sha256((root/'data/pilot_manifest.json').read_bytes()).hexdigest(),
             'units':'fixed M01 reference head-to-toe height','thickness_radius':.04,'new_download_bytes':0}
    lib=Library(payload)
    # This table exposes direction reachability and pose/velocity distances, not naturalness labels.
    transitions=[]
    for a in range(len(clips)):
        for b in range(len(clips)):
            pa=lib.sample(a,np.arange(16)/16);pb=lib.sample(b,np.arange(16)/16)
            va=lib.velocity(a,np.arange(16)/16,1/lib.periods[a]);vb=lib.velocity(b,np.arange(16)/16,1/lib.periods[b])
            transitions.append({'from':lib.ids[a],'to':lib.ids[b],'direction_edge':bool(abs(wrap(lib.angles[a]-lib.angles[b]))<=.7),
                                'pose_rms':float(np.sqrt(np.mean((pa-pb)**2))),'velocity_rms':float(np.sqrt(np.mean((va-vb)**2)))})
    payload['transitions']=transitions
    return payload
