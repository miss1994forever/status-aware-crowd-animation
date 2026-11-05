"""Download all public ShakeFive2 skeleton metadata plus renderer source/background.
Research-only source asks authors be contacted if using data in work; no contact made.
Videos deliberately deferred; source archives remain untouched, no executable run.
"""
from pathlib import Path
import subprocess,json,hashlib,tarfile
p=Path('/Volumes/Samsung-SSD/AnimationLab/motion-expansion/dyadic/ShakeFive2');rows=[]
for name in ['ShakeFive2.metadata.tar.bz2','ShakeFive2.code.tar.gz','ShakeFive2.background.tar.bz2']:
 f=p/name;tmp=p/(name+'.part');u='https://www2.projects.science.uu.nl/shakefive/data/'+name
 try:
  if not f.exists():
   subprocess.run(['curl','--fail','--location','--silent','--show-error','--retry','3','--connect-timeout','30','--max-time','1800','--continue-at','-','--output',str(tmp),u],check=True);tmp.rename(f)
  with tarfile.open(f) as tar:members=[m.name for m in tar.getmembers() if m.isfile()]
  rows.append({'file':name,'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'archive_files':len(members),'xml_files':sum(m.endswith('.xml') for m in members),'url':u})
 except Exception as e:rows.append({'file':name,'error':str(e)})
 (p/'download-manifest.json').write_text(json.dumps(rows,indent=2))
 print(rows[-1],flush=True)
