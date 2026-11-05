"""Fetch official EMM motion data and inventory it, without executing archive content.

Read-only upstream; never overwrites a downloaded archive or extracted source.
Only selected BVH files are extracted with --extract; no code/assets are run.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'data/raw/emm-pilot'
REPORT = ROOT / 'data/main-review/motion-coverage'
URL = 'https://zenodo.org/api/records/17220516'


def main():
    p=argparse.ArgumentParser();p.add_argument('--extract',action='append',default=[]);args=p.parse_args()
    metadata=json.load(urllib.request.urlopen(URL,timeout=60))
    assert metadata['metadata']['license']['id']=='cc-by-4.0'
    entry=next(f for f in metadata['files'] if f['key']=='DataEMM.zip')
    assert entry['size']<60_000_000
    DEST.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
    target=DEST/'DataEMM.zip'
    if not target.exists():
        # Download to exclusive partial file; keep interrupted files for inspection.
        partial=DEST/'DataEMM.zip.partial'
        with urllib.request.urlopen(entry['links']['self'],timeout=60) as r,partial.open('xb') as w:
            size=0
            while chunk:=r.read(1024*1024):
                size+=len(chunk)
                if size>entry['size']:raise ValueError('Unexpected download size')
                w.write(chunk)
        assert partial.stat().st_size==entry['size']
        assert 'md5:'+hashlib.md5(partial.read_bytes()).hexdigest()==entry['checksum']
        partial.rename(target)
    assert 'md5:'+hashlib.md5(target.read_bytes()).hexdigest()==entry['checksum']
    with zipfile.ZipFile(target) as z:
        inventory=[dict(path=i.filename,bytes=i.file_size,compressed_bytes=i.compress_size)
                   for i in z.infolist() if not i.is_dir()]
        for name in args.extract:
            path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or path.suffix.lower()!='.bvh':raise ValueError(name)
            info=z.getinfo(name)
            if info.file_size>150_000_000:raise ValueError('Single clip too large')
            output=DEST/'selected'/path
            output.parent.mkdir(parents=True,exist_ok=True)
            content=z.read(name)
            if output.exists():assert output.read_bytes()==content
            else:output.write_bytes(content)
        record=dict(source_page='https://zenodo.org/records/17220516',api=URL,
                    license='CC BY 4.0',creator=metadata['metadata']['creators'],
                    upstream_checksum=entry['checksum'],archive_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                    archive_bytes=target.stat().st_size,files=inventory,
                    status_labels=None,note='Source inventory only; filenames are not verified action annotations.')
        (REPORT/'emm-source.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(inventory,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
