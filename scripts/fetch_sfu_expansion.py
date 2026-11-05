from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin,urlparse
from concurrent.futures import ThreadPoolExecutor
import requests,json,hashlib,re,numpy as np,time,subprocess
out=Path('/Volumes/Samsung-SSD/AnimationLab/motion-expansion/locomotion/SFU');html=(out/'source-index.html').read_text();(out/'source-index.html').write_text(html);b=BeautifulSoup(html,'html.parser');links={}
for a in b.find_all('a'):
 href=a.get('href','');path=urlparse(href).path
 if not path.lower().endswith(('.bvh','.vsk')):continue
 tr=a.find_parent('tr');links[href]={'url':urljoin('https://mocap.cs.sfu.ca/',href),'description':tr.get_text(' ',strip=True)[:1500] if tr else a.text}
print('FILES',len(links),flush=True)
def fetch(item):
 href,meta=item;url=meta['url'];dst=out/Path(urlparse(url).path).name;result={**meta,'path':str(dst)}
 try:
  if not dst.exists():
   part=dst.with_suffix(dst.suffix+'.part')
   subprocess.run(['curl','-L','--fail','--retry','2','--retry-delay','2','--connect-timeout','20','--max-time','300','-C','-','-o',str(part),url],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   part.rename(dst)
  raw=dst.read_bytes();result.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
  if dst.suffix.lower()=='.bvh':
   s=raw.decode();assert s.lstrip().startswith('HIERARCHY');head,body=s.split('MOTION',1);frames=int(re.search(r'Frames:\s*(\d+)',body).group(1));dt=float(re.search(r'Frame Time:\s*([\d.eE+-]+)',body).group(1));channels=sum(map(int,re.findall(r'CHANNELS\s+(\d+)',head)));numeric=body.split('Frame Time:',1)[1].strip().splitlines()[1:];arr=np.fromstring(' '.join(numeric),sep=' ');assert arr.size==frames*channels and np.isfinite(arr).all();result.update(format='BVH',frames=frames,frame_time=dt,duration_seconds=frames*dt,channels=channels,joints=len(re.findall(r'\b(?:ROOT|JOINT)\s+',head)),validation='hierarchy + complete declared finite frame matrix')
  else:
   assert b'<' in raw[:100];result.update(format='VSK',validation='XML header present')
  result['status']='downloaded_verified'
 except Exception as e:result.update(status='failed',error=str(e))
 print(dst.name,result['status'],result.get('bytes'),flush=True);return result
with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(fetch,links.items()))
report={'dataset':'SFU Motion Capture Database','source_url':'https://mocap.cs.sfu.ca/','retrieved_date':'2026-11-02','license':{'source_url':'https://mocap.cs.sfu.ca/','research_use':'free for research purposes','commercial_use':'not permitted','redistribution':'resale not permitted; preserve original terms','acknowledgment_requested':True},'scope':'All unique BVH and VSK links on official index, not raw HDF/C3D/FBX alternate encodings. Any unavailable/unlinked motions explicitly excluded.','has_status_labels':False,'real_multi_person_interactions':False,'categories':['walking forward/backward','swaggering and normal walking','catwalk hands on hips','increasing stride length','side skipping','jogging','balance','fall/crawl','obstacle vault/bench/jump','dance','martial arts'],'priority_clips':['0008_Walking001.bvh','0008_Walking002.bvh','0007_Walking001.bvh','0018_Walking001.bvh','0018_Catwalk001.bvh','0005_BackwardsWalk001.bvh','0005_SideSkip001.bvh'],'files':rows,'total_bytes':sum(x.get('bytes',0) for x in rows),'verified_bvh':sum(x.get('format')=='BVH' and x['status']=='downloaded_verified' for x in rows),'limitations':['No status labels; swagger/catwalk are movement descriptions, not dominance ground truth.','Single actor clips, not recorded social response.','Format completeness checks do not establish motion naturalness or clean contacts.','Research license unsuitable for commercial NPC/film delivery without separate permission.','Complete skeletal representations do not include raw capture or alternate FBX files.']}
Path('data/research/motion-expansion/locomotion.json').write_text(json.dumps({'task':'locomotion_sources','datasets':[report],'pending_sources':[{'dataset':'CMU','url':'https://mocap.cs.cmu.edu/','reason':'Official FAQ and HEAD verified with system curl. Full ASF/AMC archive: https://mocap.cs.cmu.edu/allasfamc.zip ; 1083549385 bytes. Parent coordinating download separately; no per-file crawling performed.','candidate_subjects':[69,76,77,78,91],'license_facts':'Free research and inclusion in products, no direct resale; hand/toe noisy and fingers/thumb not actually captured.'},{'dataset':'HDM05','url':'https://resources.mpi-inf.mpg.de/HDM05/','reason':'Official landing page returned403 in web fetch; not downloaded or license accepted.'}]},ensure_ascii=False,indent=2)+'\n')
print('TOTAL',report['total_bytes'],'BVH',report['verified_bvh'],flush=True)
