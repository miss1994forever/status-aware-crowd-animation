"""Repeat original training R0 exactly; timing excluded from equality."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.predictive_motion_lab.motion import Library
from src.crowd_mobility_lab.controller import simulate


if __name__=='__main__':
    path=ROOT/'outputs/crowd-mobility-lab/runs/train_shared-10-None-13_R0.json'
    original=json.loads(path.read_text());lib=Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()))
    repeated=simulate(lib,original['spec'],'long_cv',0)
    report={'source':str(path.relative_to(ROOT)),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'all_replay_frames_exactly_equal':original['frames']==repeated['frames'],'frame_count':len(repeated['frames']),
        'decisions_exactly_equal':original['decisions']==repeated['decisions'],'scope':'Repeat full 26 seconds; excludes runtime timing only.'}
    (ROOT/'data/crowd-mobility-lab/reproducibility.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
