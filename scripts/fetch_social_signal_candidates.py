from pathlib import Path
import json,hashlib,subprocess,concurrent.futures
ROOT=Path(__file__).resolve().parents[1];m=json.loads((ROOT/'data/stymo-pilot/social-signal-candidates.json').read_text());out=Path('/Volumes/Samsung-SSD/AnimationLab/social-signal-originals');out.mkdir(exist_ok=True)
def fetch(e):
 name=e['path'].split('dom-shy_')[1].rsplit('_',1)[0];p=out/(name+'.fbx')
 if not p.exists() or p.stat().st_size!=e['size']:
  subprocess.run(['curl','-L','--fail','--max-time','120','-sS','https://raw.githubusercontent.com/facebookresearch/MotionIsTheMessageDataset/'+m['tree_sha']+'/'+e['path'],'-o',str(p)],check=True)
 b=p.read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==e['sha']
 return dict(**e,local_path=str(p),sha256=hashlib.sha256(b).hexdigest(),verified_git_blob=True)
# Neutral is being fetched separately; avoid competing writes.
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:r=list(pool.map(fetch,[e for e in m['files'] if '_Neutral_' not in e['path']]))
(ROOT/'data/stymo-pilot/social-signal-fetch-partial.json').write_text(json.dumps(r,indent=2));print('verified',len(r))
