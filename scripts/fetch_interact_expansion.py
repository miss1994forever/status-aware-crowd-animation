"""Resume official complete original-body InterAct modality; no login or gated sources.
Run with python3 scripts/fetch_interact_expansion.py. Logs/manifests live on SSD.
"""
from pathlib import Path
import urllib.request,json,hashlib,concurrent.futures,subprocess,time
p=Path('/Volumes/Samsung-SSD/AnimationLab/motion-expansion/dyadic/InterAct')
rows=json.loads((p/'listing-bvhs.json').read_text());roots=json.loads((p/'listing-root.json').read_text())
rows=sorted(rows,key=lambda r:(r['path'].split('/')[-1].split('_')[0],r['path'].split('_')[-1],r['path']))
rows=[r for r in roots if r['type']=='file' and r['size']<1000000]+rows
assert sum(x['size'] for x in rows)<2.1e9
revision='152ba832f379c465f5b1e10c67166d646014d675'
base='https://huggingface.co/datasets/leohocs/interact/resolve/'+revision+'/'
def fetch(r):
 f=p/r['path'];f.parent.mkdir(parents=True,exist_ok=True);u=base+r['path'];tmp=f.with_suffix(f.suffix+'.part')
 try:
  if not (f.exists() and f.stat().st_size==r['size']):
   cmd=['curl','--fail','--location','--silent','--show-error','--retry','3','--retry-delay','3','--connect-timeout','30','--max-time','900','--continue-at','-','--output',str(tmp),u]
   run=subprocess.run(cmd,capture_output=True,text=True)
   if run.returncode:raise ValueError(run.stderr[-600:])
   if tmp.stat().st_size!=r['size']:raise ValueError('size mismatch')
   tmp.rename(f)
  data=f.read_bytes();sha=hashlib.sha256(data).hexdigest();lfs=r.get('lfs',{}).get('oid');git=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  if lfs and sha!=lfs:raise ValueError('LFS hash mismatch')
  if not lfs and git!=r['oid']:raise ValueError('Git blob hash mismatch')
  return {'path':r['path'],'bytes':len(data),'sha256':sha,'upstream_hash_verified':True,'revision':revision}
 except Exception as e:return {'path':r['path'],'error':str(e)}
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
 futures={ex.submit(fetch,r):r for r in rows}
 for future in concurrent.futures.as_completed(futures):
  results.append(future.result())
  temp=p/'download-progress.tmp';temp.write_text(json.dumps(results,indent=2));temp.replace(p/'download-progress.json')
  if len(results)%10==0:print(len(results),len(rows),'errors',sum('error' in x for x in results),flush=True)
(p/'download-manifest.json').write_text(json.dumps(results,indent=2));print('DONE',len(results),'errors',sum('error' in x for x in results),flush=True)
