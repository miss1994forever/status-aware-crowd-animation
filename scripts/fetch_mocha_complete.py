"""Resume official MOCHA BVH archive; verify every BVH and preserve provenance."""
from pathlib import Path
import json,subprocess,zipfile,zlib,hashlib,re,os,time,collections
import numpy as np
R=Path(__file__).resolve().parents[1]
BASE=Path('/Volumes/Samsung-SSD/AnimationLab/mocha-data');OUT=BASE/'full';OUT.mkdir(exist_ok=True)
MAN=R/'data/research/motion-expansion/mocha.json';URL='https://www.dropbox.com/scl/fi/debqr38g2yzh92wvw75lz/bvh.zip?rlkey=lau6sc9yzab0ojdfx1elccizc&dl=1'
ROWS=[r for r in json.loads((R/'data/stymo-pilot/mocha-archive-manifest.json').read_text()) if r['name'].startswith('bvh/') and r['name'].endswith('.bvh')]
STYLES={'Angry','Happy','Neutral','Sad','Scared'};CHARACTERS={'AverageJoe','Clown','Ogre','Princess','Robot','Zombie'}
def labels(name):
 toks=Path(name).stem.split('_');i=next((i for i,x in enumerate(toks) if x in STYLES),None)
 return {'action':'_'.join(toks[:i]) if i is not None else Path(name).stem,'style':toks[i] if i is not None else None,'character':next((x for x in toks if x in CHARACTERS),None)}
report={'dataset':'MOCHA raw BVH','source_url':'https://github.com/DK-Jang/MOCHA_SIGASIA2023','download_source_url':'https://raw.githubusercontent.com/DK-Jang/MOCHA_SIGASIA2023/main/download.sh','archive_url':URL,'license':{'name':'CC BY-NC 4.0','source_url':'https://github.com/DK-Jang/MOCHA_SIGASIA2023/blob/main/LICENSE','commercial_use':False},'scope':'All 403 raw BVH entries in official bvh.zip; excludes __MACOSX metadata and pretrained models/features. Existing 10 candidate files reused by hardlink where valid.','has_status_labels':False,'real_multi_person_interactions':False,'limitations':['Emotion and character-archetype labels are not status ground truth.','Push/fall actions do not establish synchronized actor pairs.','Raw file validation is not perceptual naturalness or retargeting acceptance.','Fantasy characters/body proportions may confound social impression.'],'expected_files':len(ROWS),'expected_uncompressed_bytes':sum(r['bytes'] for r in ROWS),'expected_compressed_bvh_bytes':sum(r['compressed'] for r in ROWS),'local_path':str(OUT),'resume_command':f'/Users/haojun/anaconda3/envs/py311/bin/python "{R}/scripts/fetch_mocha_complete.py"','log_path':str(BASE/'complete-download.log'),'pid':os.getpid(),'files':[]}
def save(stage,**extra):
 report.update(stage=stage,updated=time.strftime('%Y-%m-%d %H:%M:%S'),**extra);tmp=MAN.with_suffix('.tmp');tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');tmp.replace(MAN)
def validate(data,r,path,reused):
 assert len(data)==r['bytes'] and (zlib.crc32(data)&0xffffffff)==r['crc32']
 text=data.decode('utf-8-sig');header,body=text.split('MOTION',1);n=int(re.search(r'Frames:\s*(\d+)',body).group(1));dt=float(re.search(r'Frame Time:\s*([^\s]+)',body).group(1));ch=sum(map(int,re.findall(r'CHANNELS\s+(\d+)',header)));payload=re.split(r'Frame Time:\s*[^\s]+',body,maxsplit=1)[1];matrix=np.fromstring(payload,sep=' ')
 assert n>0 and dt>0 and matrix.size==n*ch and np.isfinite(matrix).all()
 return dict(name=r['name'],path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),crc_verified=True,frames=n,frame_time=dt,seconds=n*dt,channels=ch,finite=True,reused_existing=reused,status='verified',**labels(r['name']))
# Publish complete scope and reusable files before the potentially slow download.
for r in ROWS:
 dest=OUT/Path(r['name']).name;existing=BASE/'candidates'/dest.name
 if not dest.exists() and existing.exists() and len(existing.read_bytes())==r['bytes'] and zlib.crc32(existing.read_bytes())&0xffffffff==r['crc32']:os.link(existing,dest)
 if dest.exists():report['files'].append(validate(dest.read_bytes(),r,dest,existing.exists() and os.path.samefile(dest,existing)))
save('downloading_archive',verified_files=len(report['files']))
archive=BASE/'bvh.zip';part=BASE/'bvh.zip.part'
if not archive.exists():
 ok=False
 for attempt in range(3):
  save('downloading_archive',attempt=attempt+1,archive_partial_bytes=part.stat().st_size if part.exists() else 0)
  proc=subprocess.run(['curl','-L','--fail','--retry','3','--retry-delay','5','--connect-timeout','30','--max-time','1800','--max-filesize','300000000','-C','-','-o',str(part),URL])
  if proc.returncode==0:ok=True;break
 if not ok:save('download_incomplete',error='curl download exhausted retries; rerun resume command');raise SystemExit(1)
 with zipfile.ZipFile(part) as z:
  for r in ROWS:
   i=z.getinfo(r['name']);assert i.file_size==r['bytes'] and i.CRC==r['crc32']
 part.replace(archive)
save('extracting_and_validating')
report['files']=[]
with zipfile.ZipFile(archive) as z:
 for i,r in enumerate(ROWS):
  dest=OUT/Path(r['name']).name;existing=BASE/'candidates'/dest.name
  data=dest.read_bytes() if dest.exists() else z.read(r['name'])
  info=validate(data,r,dest,existing.exists() and dest.exists() and os.path.samefile(dest,existing))
  if not dest.exists():dest.write_bytes(data)
  report['files'].append(info)
  if i%20==0:save('extracting_and_validating',verified_files=len(report['files']))
groups={field:dict(collections.Counter(str(f[field]) for f in report['files'])) for field in ['action','style','character']}
save('complete_verified',verified_files=len(report['files']),archive_bytes=archive.stat().st_size,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),groups=groups)
print('MOCHA verified',len(report['files']),'BVH files',flush=True)
