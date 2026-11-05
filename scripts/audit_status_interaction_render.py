"""Independent dense bone-rebuilt replay with the UI's vertical floor projection."""
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.build_status_interaction_lab import library,OUT,DATA,save
from src.predictive_motion_lab.motion import rebuild
from src.status_interaction_lab.social import torso_heading

def main():
    lib=library();rows=[]
    for path in sorted((OUT/'runs').glob('*.json')):
        if 'v1-' in path.name or 'v2-' in path.name:continue
        run=json.loads(path.read_text());p=np.array([[a['pose'] for a in f['agents']] for f in run['frames']]);worst=10.;corrected=10.;liftmax=0;display=[]
        roots=np.array([[a['pos'] for a in f['agents']] for f in run['frames']]);yaw=np.array([[a['yaw'] for a in f['agents']] for f in run['frames']])
        for u in np.arange(6)/6:
            q=rebuild(p[:-1]*(1-u)+p[1:]*u,lib.parents,lib.lengths)
            worst=min(worst,float(q[:,:,:,1].min()));lift=np.maximum(0.,-q[:,:,:,1].min(axis=-1));liftmax=max(liftmax,float(lift.max()))
            q[:,:,:,1]+=lift[:,:,None];corrected=min(corrected,float(q[:,:,:,1].min()))
            from src.predictive_motion_lab.geometry import world_pose
            display.append(world_pose(q,roots[:-1]*(1-u)+roots[1:]*u,yaw[:-1]*(1-u)+yaw[1:]*u))
        displayed=np.stack(display,axis=1).reshape((-1,)+p.shape[1:]);v=np.diff(displayed,axis=0)*120;dv=np.diff(v,axis=0)
        rows.append(dict(display_joint_speed_p99=float(np.quantile(np.linalg.norm(v,axis=-1),.99)),display_joint_velocity_change_max=float(np.linalg.norm(dv,axis=-1).max()),key=path.stem,original_interpolation_min_y=worst,projected_interpolation_min_y=corrected,projection_max=liftmax,hz=120,
          note='Whole skeleton vertical lift only; lengths/bone directions and xz safety footprints unchanged. Derivative at floor contact may be nonsmooth.'))
    save(DATA/'render-audit.json',rows);print('Dense display floor audited:',len(rows))
if __name__=='__main__':main()
