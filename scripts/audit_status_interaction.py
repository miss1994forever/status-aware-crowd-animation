"""Replay-only audit; metrics never infer naturalness/status success."""
import argparse,json,hashlib,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.build_status_interaction_lab import library,DATA,OUT,save
from src.crowd_mobility_lab.evaluate import evaluate
from src.status_interaction_lab.motion import MAX_RATE,TOE_RATE


def extra(run,lib):
    fs=run['frames'];p=np.array([[a['pose'] for a in f['agents']] for f in fs]);pos=np.array([[a['pos'] for a in f['agents']] for f in fs])
    ix=np.array([j for j,parent in enumerate(lib.parents) if parent is not None and lib.lengths[j]>1e-8]);parents=[lib.parents[j] for j in ix]
    bones=p[:,:,ix]-p[:,:,parents];length=np.linalg.norm(bones,axis=-1);unit=bones/length[...,None]
    rate=np.arccos(np.clip((unit[1:]*unit[:-1]).sum(-1),-1,1))/.05
    limits=np.array([TOE_RATE if 'Toes' in lib.names[j] else MAX_RATE for j in ix]);goals=np.array(run['spec']['goals'])
    ds=run['decisions'];social=np.array([d['response']['social'] for d in ds]);applied=np.array([d['control_after'] for d in ds]);obs=[o for d in ds for o in d['response']['observations']]
    edges={i:set() for i in range(len(pos[0]))}
    for d in ds:
        for o in d['response']['observations']:edges[d['id']].add(o['id'])
    actual_feature=[]
    # Verify saved observation fields equal independently extracted executed poses.
    names=lib.names
    for d in ds:
        f=fs[round(d['t']/.05)]
        for o in d['response']['observations']:
            q=np.array(f['agents'][o['id']]['pose']);v=q[names.index('Chest')]-q[names.index('Hips')]
            actual_feature.append(abs(np.arctan2(v[2],v[1])-o['feature']))
    delays=[];variation=[];signchanges=[]
    for i in edges:
        rows=[d for d in ds if d['id']==i];signal=np.array([d['response']['social'] for d in rows])
        variation.append(float(np.abs(np.diff(signal)).sum()))
        nonzero=signal[abs(signal)>.001];signchanges.append(int(np.sum(nonzero[1:]*nonzero[:-1]<0)))
        # Operational onset latency: first confident inference versus first observation.
        seen={}
        for d in rows:
            for o in d['response']['observations']:
                seen.setdefault(o['id'],d['t'])
                if o['confidence']>0 and not isinstance(seen[o['id']],tuple):
                    delays.append(d['t']-seen[o['id']]);seen[o['id']]=(seen[o['id']],d['t'])
    return dict(arrived_from_final_positions=int(np.sum(np.linalg.norm(pos[-1]-goals,axis=-1)<.22)),agent_count=len(pos[0]),
       raw_bone_absolute_error_max=float(abs(length-lib.lengths[ix]).max()),minimum_joint_height=float(p[:,:,:,1].min()),
       angular_rate_max=float(rate.max()),angular_rate_excess_max=float(np.maximum(rate-limits,0).max()),
       social_rms=float(np.sqrt(np.mean(social**2))),social_peak=float(abs(social).max()),social_absolute_integral=float(abs(social).sum()*.2),
       executed_control_rms=float(np.sqrt(np.mean(applied**2))),rejected_social_absolute_integral=float(sum(abs(d['response']['social'])*.2 for d in ds if not d['executed'])),
       social_sign_changes_per_agent=signchanges,social_total_variation_per_agent=variation,
       max_simultaneous_observed_neighbors=max([len(d['response']['observations']) for d in ds],default=0),
       unique_observed_neighbors={i:len(v) for i,v in edges.items()},actual_feature_reobservation_error_max=max(actual_feature,default=0),
       confidence_onset_latency_seconds=delays,confidence_mean=float(np.mean([o['confidence'] for o in obs])) if obs else 0.,
       floor_correction_peak=max([d.get('floor_lift_max',0) for d in ds],default=0),motion_constraint_correction_peak=max([d.get('constraint_correction_max',0) for d in ds],default=0),
       note='Saved pose observation agreement tests execution feedback, not psychological inference. Latency is engineering onset, not human response time.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--full',action='store_true');p.add_argument('--key');a=p.parse_args();lib=library();rows=[]
    files=[OUT/'runs'/f'{a.key}.json'] if a.key else sorted((OUT/'runs').glob('*.json'))
    for path in files:
        r=json.loads(path.read_text());m=extra(r,lib);m['key']=path.stem
        if a.full:
            recomputed=evaluate(r,lib);original=json.loads((DATA/'metrics'/path.name).read_text())
            m['independent_evaluator_match']=all(recomputed[k]==original[k] for k in recomputed)
        rows.append(m)
    save(DATA/(('independent-'+a.key+'.json') if a.full and a.key else ('independent-full.json' if a.full else 'replay-audit.json')),rows)
    print(json.dumps([{k:r[k] for k in ['key','arrived_from_final_positions','minimum_joint_height','angular_rate_excess_max','social_peak','max_simultaneous_observed_neighbors']} for r in rows],ensure_ascii=False),flush=True)
if __name__=='__main__':main()
