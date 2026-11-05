"""Headless adapter to official STyMo prediction, scaling and contact optimization.
Upstream model and motion functions are reused, not a new style algorithm.
Outputs are movement-style candidates; no status semantics are assumed.
"""
import argparse, json, sys, time, hashlib
from pathlib import Path
import numpy as np
import torch
from scipy.signal import savgol_filter
UP = Path('/Volumes/Samsung-SSD/AnimationLab/STyMo-official')
sys.path.insert(0, str(UP / 'src'))
from pymotion.io.bvh import BVH
from pymotion.ops.skeleton import fk
from model_temporal import ModelTransformer
from model_static import AveragePoseModel
from model_gating import GatingModel
from motion_loss import ContactLoss
from utils import resample_bvh
from utils_training_data import preprocess_source_input_data
from stylizer_inference import predict, optimize
from utils_inference import load_average_deltas, extract_Y_k, add_scaled_style_rots, add_scaled_style_pos
from features import set_bvh_from_full_body_target_kinematics, get_feet_indices


def positions(b):
    r,p,parents,o,_,_=b.get_data()
    offsets=np.tile(o,(len(p),1,1)); offsets[:,1]=p[:,1]
    return fk(r,p[:,0],offsets,parents)[0]


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('model',type=Path); ap.add_argument('input',type=Path)
    ap.add_argument('out',type=Path); ap.add_argument('--frames',type=int,default=360)
    ap.add_argument('--start-frame',type=int,default=0)
    ap.add_argument('--predict-root',action='store_true',help='Use predicted root motion instead of pinning the source trajectory')
    ap.add_argument('--contact-epochs',type=int,default=100); args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True); start=time.monotonic(); torch.set_num_threads(4)
    c=torch.load(args.model/'model.pt',map_location='cpu',weights_only=False)
    model=ModelTransformer(input_dim=c['n_in_features'],output_dim=c['n_out_features'],window_size=len(c['delta_indices']))
    avg=AveragePoseModel(input_dim=c['n_in_features_avg_pose'],output_dim=c['n_out_features_avg_pose'])
    gate=GatingModel(input_dim=c['n_in_features_gating'],always_one=c['gating_model_always_one'])
    for m,k in [(model,'model'),(avg,'avg_pose_model'),(gate,'gating_model')]:
        m.load_state_dict(c[k]); m.eval()
    b=BVH(); b.load(str(args.input)); b=resample_bvh(b,c['target_frame_time'])
    a=args.start_frame; z=a+args.frames
    if a<0 or z>len(b.data['positions']): raise ValueError('Requested window outside source')
    b.data['positions']=b.data['positions'][a:z]; b.data['rotations']=b.data['rotations'][a:z]
    b.save(str(args.out/'source.bvh'))
    sources,_=preprocess_source_input_data([b],c['x_k_standardize'],c['x_p_standardize'],c['Y_k_standardize'],c['delta_indices'],c['feet_velocity_contact_th'],None,'cpu',None)
    inputs=[sources[b.data['filename']]]
    dr,dp,_=load_average_deltas(str(args.model))
    raw=predict(inputs,model,avg,dr,dp,c['Y_k_standardize'],gating_model=gate)
    score=raw[4][0].detach().numpy()
    score=np.clip(savgol_filter(score,61,2,axis=0),0,1) if len(score)>=61 else score
    n=raw[0][0].shape[0]
    score=np.pad(score,((0,max(0,n-len(score))),(0,0)),mode='edge')[:n]
    base=positions(b); feet=get_feet_indices(b)
    # Same contact mask for all variants, inferred from source speed; diagnostic only.
    dt=float(c['target_frame_time']); speed=np.linalg.norm(np.diff(base[:,feet],axis=0),axis=-1)/dt
    mask=speed<c['feet_velocity_contact_th']
    variants=[]; clips=[]
    def add_clip(name,motion):
        pos=positions(motion); r,p,parents,o,_,_=motion.get_data()
        assert np.isfinite(pos).all() and np.isfinite(r).all()
        fvel=np.linalg.norm(np.diff(pos[:,feet],axis=0),axis=-1)/dt
        metrics={'name':name,'frames':len(pos),'mean_joint_displacement_m':float(np.linalg.norm(pos-base,axis=-1).mean()),'source_contact_foot_speed_m_s':float(fvel[mask].mean()) if mask.any() else None,'min_foot_height_m':float(pos[:,feet,1].min()),'offsets_unchanged':bool(np.allclose(o,b.get_data()[3]))}
        variants.append(metrics)
        clips.append({'name':name,'dt':dt,'names':list(map(str,motion.data['names'])),'parents':parents.tolist(),'positions':pos.round(5).tolist()})
    add_clip('source',b)
    for strength,contact in [(0.,0),(.5,args.contact_epochs),(1.,0),(1.,args.contact_epochs)]:
        label=f'style-{strength:g}-contact-{contact}'
        scales={'dynamic':score[:,:,None]*strength,'static':score[:,:,None]*strength,'dynamic_pelvis':score*strength,'static_pelvis':score*strength}
        loss=ContactLoss(source_bvh=b,Y_k_standardize=c['Y_k_standardize'],body_parts_indices=c['body_parts_indices'],target_frame_time=dt,lambda_contacts=100.,lambda_smooth=.01) if contact else None
        ys,rs,ps,_=optimize(*raw[:4],input_sources=inputs,contact_loss_fn=loss,contact_epochs=contact,window_size=len(c['delta_indices']),Y_k_standardize=c['Y_k_standardize'],gated_scales_per_source=[scales])
        trans,pelvis,rot,deltas=extract_Y_k(ys[0])
        rots=add_scaled_style_rots(deltas,rs[0][...,0,:,:],scales['dynamic'],scales['static'])
        pp=add_scaled_style_pos(pelvis,ps[0][...,0,:],scales['dynamic_pelvis'],scales['static_pelvis'])
        result=set_bvh_from_full_body_target_kinematics(b,trans,pp,rot,rots,fix_root=not args.predict_root)
        result.save(str(args.out/(label+'.bvh'))); add_clip(label,result)
        print(label,variants[-1],flush=True)
    # Upstream intentionally leaves static pelvis rotation unscaled, even at zero.
    # Validate reconstruction separately using actual identity deltas.
    identity=np.zeros_like(b.get_data()[0][:,1:]); identity[...,0]=1
    root_identity=np.zeros((len(base),4)); root_identity[:,0]=1
    zero=np.zeros((len(base),3))
    reconstructed=set_bvh_from_full_body_target_kinematics(b,zero,zero,root_identity,identity,fix_root=True)
    assert np.max(np.abs(positions(reconstructed)-base))<1e-6
    report={'start_frame':args.start_frame,'frame_count':args.frames,'zero_strength_is_identity':False,'identity_reconstruction_verified':True,'checkpoint':str(args.model),'input':str(args.input),'input_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest(),'elapsed_seconds':time.monotonic()-start,'gating_always_one':c['gating_model_always_one'],'gate_mean':float(score.mean()),'gate_range':[float(score.min()),float(score.max())],'fix_root':not args.predict_root,'variants':variants,'visual_verified':False,'status_verified':False,'notes':'Contact diagnostic uses source velocity mask, not measured ground truth contacts. Root mode is recorded in fix_root. Gate smoothing clips to [0,1].'}
    (args.out/'report.json').write_text(json.dumps(report,indent=2)); (args.out/'clips.json').write_text(json.dumps(clips,separators=(',',':')))
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
