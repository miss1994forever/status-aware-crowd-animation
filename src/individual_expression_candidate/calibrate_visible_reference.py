"""Geometry-only normalization from existing unlabeled reference clips; not status calibration."""
from pathlib import Path
import json,math,hashlib,statistics
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'outputs/individual-expression-candidate'
def sub(a,b):return [x-y for x,y in zip(a,b)]
def norm(v):return math.sqrt(sum(x*x for x in v))
def features(p,names):
    idx={name:i for i,name in enumerate(names)}
    l=p[idx['UpperArm_L']];r=p[idx['UpperArm_R']];e=p[idx['LowerArm_L']]
    shoulder=sub(r,l);width2=sum(x*x for x in shoulder)
    expansion=sum(x*y for x,y in zip(sub(l,e),shoulder))/width2
    legs=sum(norm(sub(p[idx['LowerLeg_'+s]],p[idx['UpperLeg_'+s]]))+norm(sub(p[idx['Foot_'+s]],p[idx['LowerLeg_'+s]])) for s in ['L','R'])/2
    height=(p[idx['Hips']][1]-(p[idx['Foot_L']][1]+p[idx['Foot_R']][1])/2)/legs
    return [expansion,height]
def quantile(values,q):
    a=sorted(values);x=(len(a)-1)*q;i=int(x);return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(x-i)
def main():
    raw=json.loads((OUT/'raw-replay.json').read_text());combined=json.loads((OUT/'combination-replay.json').read_text())
    combinations={c['id']:c for c in combined['clips']};clips=[];filtered=[]
    for c in raw['clips']:
        variants={name:[features(p,c['names']) for p in c['variants'][name]] for name in ['source','half','full']}
        variants['combination']=[features(p,c['names']) for p in combinations[c['id']]['variants']['target']]
        values=variants['source'];state=values[0][:];alpha=1-math.exp(-c['dt']/.45)
        for frame,v in enumerate(values):
            state=[state[j]+(v[j]-state[j])*alpha for j in range(2)]
            if frame*c['dt']>=.5:filtered.append(state[:])
        clips.append({'id':c['id'],'dt':c['dt'],'variants':variants})
    es=[x[0] for x in filtered];hs=[x[1] for x in filtered]
    reference={'expansionCenter':statistics.median(es),'expansionScale':max(.10,quantile(es,.90)-quantile(es,.10)),
               'heightCenter':statistics.median(hs),'heightScale':max(.04,quantile(hs,.90)-quantile(hs,.10))}
    report={'kind':'unlabeled neutral-geometry normalization; not status/observer calibration','reference':reference,
            'observation_filter_seconds':.45,'calibration_startup_excluded_seconds':.5,'calibration_frames':len(filtered),
            'scale_rule':'max(p90-p10, floor); floors expansion .10, height .04',
            'calibration_clips':['M01 source','M07 source'],'input_sha256':hashlib.sha256((ROOT/'data/expression-space-lab/input-cycles.json').read_bytes()).hexdigest(),
            'limits':['same source clips used for normalization and diagnostics; no held-out inference claim','neutral means reference movement, not neutral social status','height uses visible ankle reference, not floor contact or body stature']}
    (OUT/'visible-reference.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'observable-inputs.json').write_text(json.dumps({'reference':reference,'clips':clips},separators=(',',':')))
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
