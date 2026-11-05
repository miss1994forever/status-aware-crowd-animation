"""Fetch selected official MOCHA ZIP entries by byte range, verify CRC, preserve raw BVHs."""
from pathlib import Path
import concurrent.futures,hashlib,json,struct,subprocess,zlib
ROOT=Path(__file__).resolve().parents[1]
URL='https://www.dropbox.com/scl/fi/debqr38g2yzh92wvw75lz/bvh.zip?rlkey=lau6sc9yzab0ojdfx1elccizc&dl=1'
OUT=Path('/Volumes/Samsung-SSD/AnimationLab/mocha-data/candidates');OUT.mkdir(exist_ok=True)
rows=json.loads((ROOT/'data/stymo-pilot/mocha-archive-manifest.json').read_text())
selected=[r for r in rows if r['name'].startswith(('bvh/Loco_Walk_','bvh/Loco_Run_')) and 'AverageJoe' in r['name']]
def fetch(r):
 name=Path(r['name']).name; dest=OUT/name;tmp=OUT/(name+'.range')
 if dest.exists() and (zlib.crc32(dest.read_bytes())&0xffffffff)==r['crc32']: data=dest.read_bytes()
 else:
  end=r['offset']+r['compressed']+4095
  subprocess.run(['curl','-L','--fail','--retry','1','--max-time','90','--range',f"{r['offset']}-{end}",URL,'-o',str(tmp),'-sS'],check=True)
  buf=tmp.read_bytes();v=struct.unpack_from('<4s5H3I2H',buf,0)
  assert v[0]==b'PK\x03\x04';n,e=v[-2:];stored=buf[30:30+n].decode();assert stored==r['name'],stored
  compressed=buf[30+n+e:30+n+e+r['compressed']]
  data=zlib.decompress(compressed,-15) if r['method']==8 else compressed
  assert len(data)==r['bytes'] and zlib.crc32(data)&0xffffffff==r['crc32']
  dest.write_bytes(data);tmp.unlink()
 return dict(**r,path=str(dest),sha256=hashlib.sha256(data).hexdigest(),crc_verified=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 results=list(pool.map(fetch,selected))
(ROOT/'data/stymo-pilot/mocha-candidates.json').write_text(json.dumps(dict(archive_url=URL,files=results,paired=False,status_labels=False),indent=2))
print('Verified',len(results),'BVHs;',sum(x['bytes'] for x in results),'bytes')
