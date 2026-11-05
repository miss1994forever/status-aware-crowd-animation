"""Fetch complete Multi-TPC motion/gaze/interaction-label modalities via official ZIP ranges.
No audio/video. ZIP64 central-directory manifest previously captured from official archive.
"""
from pathlib import Path
import json,subprocess,struct,zlib,hashlib,concurrent.futures,threading,os,time
ROOT=Path(__file__).resolve().parents[1];BASE=Path('/Volumes/Samsung-SSD/AnimationLab/motion-expansion/group');DEST=BASE/'Multi-TPC';DEST.mkdir(exist_ok=True)
URL='https://zenodo.org/records/17935560/files/Dataset.zip?download=1'
rows=[r for r in json.loads((BASE/'tpc-archive-manifest.json').read_text()) if r['bytes'] and r['name'].startswith(('Data/Mocap/','Data/Gaze/','Data/AudioGazeGBack/'))]
state={'dataset':'Multi-TPC','expected_files':len(rows),'selected_uncompressed_bytes':sum(r['bytes'] for r in rows),'status':'downloading','files':[]};lock=threading.Lock();status=DEST/'download-status.json'
def save():
 tmp=status.with_suffix('.json.tmp');tmp.write_text(json.dumps(state,indent=2));tmp.replace(status)
def valid(path,r):return path.exists() and path.stat().st_size==r['bytes'] and (zlib.crc32(path.read_bytes())&0xffffffff)==r['crc32']
def fetch(r):
 dest=DEST/r['name'];dest.parent.mkdir(parents=True,exist_ok=True);part=dest.with_suffix(dest.suffix+'.range')
 try:
  if not valid(dest,r):
   end=r['offset']+r['compressed']+2047
   subprocess.run(['curl','-L','--fail','--retry','2','--retry-delay','5','--connect-timeout','30','--max-time','1800','--max-filesize',str(r['compressed']+8192),'--range',f"{r['offset']}-{end}",URL,'-o',str(part),'-sS'],check=True)
   b=part.read_bytes();v=struct.unpack_from('<4s5H3I2H',b,0);assert v[0]==b'PK\x03\x04';n,e=v[-2:];assert b[30:30+n].decode()==r['name'];payload=b[30+n+e:30+n+e+r['compressed']];data=zlib.decompress(payload,-15) if r['method']==8 else payload;assert len(data)==r['bytes'] and (zlib.crc32(data)&0xffffffff)==r['crc32'];dest.write_bytes(data);part.unlink()
  data=dest.read_bytes();text=data.decode('utf-8-sig');lines=text.splitlines();row=dict(r,path=str(dest),sha256=hashlib.sha256(data).hexdigest(),crc_verified=True,line_count=len(lines),first_line=lines[0][:180] if lines else '',status='downloaded_verified')
 except Exception as e:row=dict(r,path=str(dest),status='failed',error=str(e))
 with lock:
  state['files'].append(row);state['completed_files']=sum(x['status']=='downloaded_verified' for x in state['files']);state['updated_unix']=time.time();save()
 return row
save()
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(fetch,rows))
state['status']='complete_verified' if state.get('completed_files')==len(rows) else 'incomplete_with_errors';save()
