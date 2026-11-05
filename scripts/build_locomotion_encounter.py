"""Build a self-contained local encounter prototype using the unchanged M01 gait."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.bvh import load
from src.locomotion import build_cycle


def build(destination=ROOT/'outputs/locomotion-encounter'):
    manifest=json.loads((ROOT/'data/pilot_manifest.json').read_text())
    entry=manifest['entries'][0]
    source=ROOT/entry['file']
    if hashlib.sha256(source.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('M01 hash mismatch')
    motion=load(source);cycle=build_cycle(motion)
    data=dict(poses=cycle.poses,tangents=cycle.tangents,stride=cycle.stride,parents=cycle.parents,
              bone_lengths=cycle.bone_lengths,names=[j.name for j in motion.joints[1:]],source=entry,
              revision=manifest['revision'],license=manifest['license'],translation_mode='channels_replace_offset',
              purpose='M01 engineering trial only; no final motion choice or status labels; foot IK disabled')
    html=(ROOT/'locomotion/encounter.html').read_text()
    html=html.replace('/*__GAIT__*/',(ROOT/'locomotion/runtime.js').read_text())
    html=html.replace('/*__ENCOUNTER__*/',(ROOT/'src/locomotion_encounter.js').read_text())
    html=html.replace('/*__DATA__*/',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
    destination.mkdir(parents=True,exist_ok=True)
    (destination/'index.html').write_text(html)
    (destination/'gait.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    (destination/'LICENSE.txt').write_bytes((ROOT/'data/raw/bandai-pilot/LICENSE').read_bytes())
    print(destination/'index.html')
    return data


if __name__=='__main__':build()
