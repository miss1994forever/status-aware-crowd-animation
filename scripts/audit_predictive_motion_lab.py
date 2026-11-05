"""Re-evaluate saved trajectories independently of planning and export acceptance evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab.evaluate import audit


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',action='append');p.add_argument('--all',action='store_true');args=p.parse_args()
    data=ROOT/'data/predictive-motion-lab';out=ROOT/'outputs/predictive-motion-lab'
    lib=Library(json.loads((data/'library.json').read_text()))
    files=[Path(f).resolve() for f in args.run] if args.run else sorted((out/'runs').glob('*.json'))
    if not args.all and not args.run:files=files[:1]
    report=[]
    for f in files:
        m=audit(json.loads(f.read_text()),lib)
        report.append({'file':str(f.relative_to(ROOT)),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'independent_metrics':m})
        print(f.name,m['arrived_fraction'],m['max_proxy_penetration'],flush=True)
    (data/'independent-recheck.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
