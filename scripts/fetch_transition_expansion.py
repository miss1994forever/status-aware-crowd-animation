"""Resumable official CMU/LAFAN1 archives, with ZIP/hash/skeleton checks.
No code from downloaded repositories is executed.
"""
from pathlib import Path
import argparse, hashlib, json, os, re, shutil, subprocess, time, zipfile, urllib.request
ROOT=Path('/Volumes/Samsung-SSD/AnimationLab/motion-expansion/transition')
JOBS={
 'cmu':dict(folder='CMU',name='allasfamc.zip',url='https://mocap.cs.cmu.edu/allasfamc.zip',bytes=1083549385,sha256=None),
 'lafan1':dict(folder='LAFAN1',name='lafan1.zip',url='https://media.githubusercontent.com/media/ubisoft/ubisoft-laforge-animation-dataset/94084601bacdf9cc3764b5c73daaeccae6035fac/lafan1/lafan1.zip',bytes=144051503,sha256='ea918082b500a5d158e9d3aa39039df04cd42e25f5c02fe8f7e88e8e9365a977')}
def run(which):
 job=JOBS[which];out=ROOT/job['folder'];out.mkdir(parents=True,exist_ok=True);archive=out/job['name'];partial=out/(job['name']+'.part');state=out/'download-status.json'
 def status(stage,**kw):
  tmp=state.with_suffix('.tmp');tmp.write_text(json.dumps(dict(dataset=which,state=stage,pid=os.getpid(),updated_unix=time.time(),archive=str(archive),partial=str(partial),partial_bytes=partial.stat().st_size if partial.exists() else 0,expected_bytes=job['bytes'],**kw),indent=2)+'\n');tmp.replace(state)
 try:
  if not archive.exists():
   status('downloading')
   url=job['url']
   if which=='lafan1':
    # Official anonymous Git LFS endpoint; preserve TLS verification.
    req=urllib.request.Request('https://github.com/ubisoft/ubisoft-laforge-animation-dataset.git/info/lfs/objects/batch',data=json.dumps({'operation':'download','transfers':['basic'],'objects':[{'oid':job['sha256'],'size':job['bytes']}]}).encode(),headers={'Content-Type':'application/vnd.git-lfs+json','Accept':'application/vnd.git-lfs+json'})
    with urllib.request.urlopen(req,timeout=30) as r:url=json.load(r)['objects'][0]['actions']['download']['href']
   cmd=['curl' ,'--http1.1','-L','--fail','--retry','6','--retry-all-errors','--retry-delay','10','--connect-timeout','30','--max-time','43200','--max-filesize',str(job['bytes']+1024),'-C','-','-o',str(partial),url]
   proc=subprocess.Popen(cmd)
   while proc.poll() is None:
    status('downloading');time.sleep(5)
   if proc.returncode:raise RuntimeError('curl exit '+str(proc.returncode)+'; rerun same command to resume')
   if partial.stat().st_size!=job['bytes']:raise ValueError('archive size mismatch')
   partial.replace(archive)
  status('validating')
  digest=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()
  if job['sha256'] and digest!=job['sha256']:raise ValueError('SHA256 mismatch')
  with zipfile.ZipFile(archive) as z:
   bad=z.testzip()
   if bad:raise ValueError('ZIP CRC failure '+bad)
   members=[i for i in z.infolist() if Path(i.filename).suffix.lower() in {'.bvh','.asf','.amc'} and not i.filename.startswith('__MACOSX/')]
   expanded=sum(i.file_size for i in members)
   if expanded>20*1024**3 or shutil.disk_usage(out).free<expanded+20*1024**3:raise ValueError('archive valid but extraction exceeds free-space reserve')
   dest=out/'motions';dest.mkdir(exist_ok=True);records=[]
   for i in members:
    path=dest/i.filename
    if not path.resolve().is_relative_to(dest.resolve()):raise ValueError('unsafe archive path')
    data=z.read(i);text=data.decode('utf-8',errors='replace');kind=path.suffix.lower();record={'name':i.filename,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    if kind=='.bvh':
     assert 'HIERARCHY' in text and 'MOTION' in text
     nf=int(re.search(r'Frames:\s*(\d+)',text).group(1));dt=float(re.search(r'Frame Time:\s*([\d.eE+-]+)',text).group(1));channels=sum(map(int,re.findall(r'CHANNELS\s+(\d+)',text)));frames=text.split('Frame Time:',1)[1].splitlines()[1:];frames=[r for r in frames if r.strip()]
     assert len(frames)==nf and all(len(r.split())==channels for r in frames)
     record.update(frames=nf,frame_time=dt,channels=channels,validation='ZIP CRC, BVH hierarchy and declared frame/channel matrix')
    elif kind=='.asf':
     assert ':bonedata' in text and ':hierarchy' in text
     record['validation']='ZIP CRC and ASF bone/hierarchy sections'
    else:
     assert ':DEGREES' in text or ':RADIANS' in text
     frames=[int(r) for r in text.splitlines() if r.strip().isdigit()]
     assert frames and frames==list(range(frames[0],frames[0]+len(frames))) and re.search(r'^root\s',text,re.M)
     record.update(frames=len(frames),validation='ZIP CRC, AMC angle declaration, contiguous frame IDs, root channel presence')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);record['path']=str(path);records.append(record)
   (out/'file-manifest.json').write_text(json.dumps({'archive_sha256':digest,'files':records,'extracted_bytes':expanded,'scope':'Complete skeleton members in official archive; other modality archives omitted','naturalness_verified':False},indent=2)+'\n')
  status('complete_verified',archive_sha256=digest,skeleton_files=len(records),extracted_bytes=expanded)
 except Exception as e:
  status('failed_resumable',error=repr(e));raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('dataset',choices=JOBS);run(p.parse_args().dataset)
