"""Measure head-relative-chest orientation increments; not perceptual validation."""
import csv,json,math,sys
from pathlib import Path

def audit(path):
    rows=list(csv.DictReader((path/'motion.csv').open()));prev={};rates={'raw':[],'final':[]}
    for row in rows:
        if any(v is None for v in row.values()):continue
        key=row['id']
        if key in prev:
            a=prev[key]
            for label,prefix in [('raw','headchest_'),('final','headout_')]:
                qa=[float(a[prefix+c]) for c in 'xyzw'];qb=[float(row[prefix+c]) for c in 'xyzw']
                dot=abs(sum(x*y for x,y in zip(qa,qb)))/math.sqrt(sum(x*x for x in qa)*sum(y*y for y in qb))
                rates[label].append(2*math.degrees(math.acos(min(1,dot)))/float(row['dt']))
        prev[key]=row
    return {label:{'peak_deg_s':max(v),'p99_deg_s':sorted(v)[int(.99*(len(v)-1))]} for label,v in rates.items()}
if __name__=='__main__':
    path=Path(sys.argv[1]);result=audit(path);(path/'head-filter-audit.json').write_text(json.dumps(result,indent=2));print(result)
