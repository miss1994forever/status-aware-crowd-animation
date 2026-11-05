"""R1 material audit. Sample Assimp FBX hierarchy without retargeting or style edits."""
from pathlib import Path
import json,subprocess,hashlib
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
ROOT=Path(__file__).resolve().parents[1];base=Path('/Volumes/Samsung-SSD/AnimationLab/social-signal-originals');out=ROOT/'outputs/social-signal-review';out.mkdir(exist_ok=True)
manifest=json.loads((ROOT/'data/stymo-pilot/social-signal-candidates.json').read_text())
order=['Shy','Very_Dominant','Neutral','Dominant','VeryShy'];clips=[];reports=[]
for num,label in enumerate(order):
 src=base/(label+'.fbx');e=next(e for e in manifest['files'] if e['path'].split('dom-shy_')[1].rsplit('_',1)[0]==label)
 raw=src.read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==e['sha']
 dest=base/(label+'.assjson')
 if not dest.exists():subprocess.run(['assimp','export',str(src),str(dest),'-fassjson'],stdout=subprocess.DEVNULL,check=True)
 d=json.loads(dest.read_text());assert len(d['animations'])==1;a=d['animations'][0];rate=a['tickspersecond'];times=np.arange(int(a['duration'])+1,dtype=float);count=len(times)
 chans={c['name']:c for c in a['channels']};nodes=[];parents=[]
 def flatten(n,p=-1):
  i=len(nodes);nodes.append(n);parents.append(p)
  for ch in n.get('children',[]):flatten(ch,i)
 flatten(d['rootnode']);world=[]
 for i,n in enumerate(nodes):
  m=np.tile(np.array(n['transformation']).reshape(4,4),(count,1,1));ch=chans.get(n['name'])
  if ch:
   # Assimp channels provide local TRS; helper nodes retain FBX pivots/pre/post rotations.
   def sample(k):
    keys=ch[k];tt=np.array([v[0] for v in keys]);vv=np.array([v[1] for v in keys]);t=np.clip(times,tt[0],tt[-1])
    if len(keys)==1:return np.tile(vv[0],(count,1))
    if k=='rotationkeys':return Slerp(tt,Rotation.from_quat(vv[:,[1,2,3,0]]))(t).as_quat()[:,[3,0,1,2]]
    return np.stack([np.interp(t,tt,vv[:,j]) for j in range(vv.shape[1])],axis=-1)
   pos=sample('positionkeys');q=sample('rotationkeys');sc=sample('scalingkeys')
   m=np.tile(np.eye(4),(count,1,1));m[:,:3,:3]=Rotation.from_quat(q[:,[1,2,3,0]]).as_matrix()*sc[:,None,:];m[:,:3,3]=pos
  world.append(m if parents[i]<0 else world[parents[i]]@m)
 keep=[i for i,n in enumerate(nodes) if n['name'].startswith('b_') and '$' not in n['name'] and not any(t in n['name'] for t in ['eye','tongue','jaw','teeth','null','twist','talocrural','subtalar','transversetarsal'])]
 indices={old:j for j,old in enumerate(keep)};ps=[]
 for old in keep:
  parent=parents[old]
  while parent>=0 and parent not in indices:parent=parents[parent]
  ps.append(indices.get(parent,-1))
 names=[nodes[i]['name'] for i in keep];pos=np.stack([world[i][:,:3,3] for i in keep],axis=1)*.01
 assert np.isfinite(pos).all();assert names[0]=='b_root'
 # No per-clip recentering, floor fitting, scale fitting or speed changes in exported data.
 horiz=pos[:,0][:,[0,2]];extent=np.ptp(horiz,axis=0);path=float(np.linalg.norm(np.diff(horiz,axis=0),axis=1).sum())
 bone=np.stack([np.linalg.norm(pos[:,j]-pos[:,p],axis=1) for j,p in enumerate(ps) if p>=0],axis=1)
 report=dict(id=chr(65+num),source_label=label,file=str(src),sha256=hashlib.sha256(raw).hexdigest(),git_blob_verified=True,duration_seconds=float(a['duration']/rate),samples=count,sample_rate=rate,root_horizontal_extent_m=extent.tolist(),root_path_length_m=path,max_bone_length_range_m=float(np.ptp(bone,axis=0).max()),finite=True,scene_nodes=len(nodes),shown_joints=len(keep),translation_scale=.01,interpretation='Path length includes swaying; not walking distance or step count.',status_verified=False)
 reports.append(report);clips.append(dict(name=chr(65+num),dt=1/rate,names=['Head' if n=='b_head' else n for n in names],parents=ps,positions=pos.round(6).tolist()))
(out/'clips.json').write_text(json.dumps([clips[0]]+clips,separators=(',',':')));(out/'audit.json').write_text(json.dumps(reports,indent=2))
print(json.dumps(reports,indent=2))
