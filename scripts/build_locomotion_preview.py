"""Build the local M01 path-following prototype, stdlib only; never edits raw BVH."""
import hashlib
import json
from pathlib import Path
import sys
import subprocess

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.bvh import load
from src.locomotion import build_cycle
from src.locomotion_contact import infer_contacts


def build(destination=ROOT/'outputs/locomotion'):
    manifest=json.loads((ROOT/'data/pilot_manifest.json').read_text())
    entry=manifest['entries'][0]
    source=ROOT/entry['file']
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if digest!=entry['sha256']:
        raise ValueError('M01 source hash mismatch')
    motion=load(source)
    cycle=build_cycle(motion)
    data=dict(poses=cycle.poses,tangents=cycle.tangents,stride=cycle.stride,parents=cycle.parents,
              bone_lengths=cycle.bone_lengths,names=[j.name for j in motion.joints[1:]],
              evidence=cycle.evidence,source=entry,revision=manifest['revision'],
              contacts=infer_contacts(motion,cycle),translation_mode='channels_replace_offset',license=manifest['license'],creator=manifest['creator'])
    template=(ROOT/'locomotion/index.html').read_text()
    template=template.replace('/*__RUNTIME__*/',(ROOT/'locomotion/runtime.js').read_text())
    template=template.replace('/*__CONTACT__*/',(ROOT/'locomotion/contact.js').read_text())
    html=template.replace('/*__DATA__*/',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
    destination.mkdir(parents=True,exist_ok=True)
    (destination/'index.html').write_text(html,encoding='utf-8')
    (destination/'evidence.json').write_text(json.dumps({k:v for k,v in data.items() if k not in ('poses','tangents')},ensure_ascii=False,indent=2)+'\n')
    (destination/'cycle.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    (destination/'LICENSE.txt').write_bytes((ROOT/'data/raw/bandai-pilot/LICENSE').read_bytes())
    subprocess.run(['node',str(ROOT/'locomotion/diagnose.js'),str(destination/'cycle.json'),str(destination/'contact-diagnostics.json')],check=True)
    print(json.dumps(cycle.evidence,ensure_ascii=False,indent=2))
    print(destination/'index.html')
    return data


if __name__=='__main__':
    build()
