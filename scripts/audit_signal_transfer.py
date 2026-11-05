"""Check whether root-height suppression offers comparable edits across clips."""
from pathlib import Path
import json
import numpy as np
R=Path(__file__).resolve().parents[1];O=R/'outputs/social-signal-review'
rows=[]
for c in json.loads((O/'clips.json').read_text())[1:]:
 p=np.array(c['positions']);y=p[:,c['names'].index('b_root'),1]
 # For w in [0,1] and an in-clip reference, |(reference-y)*w| <= ptp(y).
 rows.append({'clip':c['name'],'root_range_cm':float(np.ptp(y)*100),'max_possible_suppression_bound_cm':float(np.ptp(y)*100)})
report={'question':'Does identical source-height suppression yield comparable contraction strength?', 'formula':'dy(t)=(root_y(onset)-root_y(t))*smoothstep(phase)', 'rows':rows,'finding':'C full-clip root range is below 0.75cm; no in-clip onset choice can produce the approximately 2.06cm downward correction used on D under this rule. Signs can differ: source falling causes upward correction.', 'limitations':['Full-clip geometric bound, not a perceptual result.','C has no confirmed greeting event annotation in repository.','Fixed downward displacement would be a NEW operator, not unchanged transfer of the previous one.','Original variable segment lengths and IK feasibility remain relevant.'], 'next':'Separate preservation/suppression of source motion from explicitly controlled contraction. If testing a fixed displacement operator, rerun D as well as C with same settings and independently confirm events; do not inherit previous D feedback as validation.'}
(O/'transfer-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
assert next(r for r in rows if r['clip']=='C')['root_range_cm']<.75
print(json.dumps(report,ensure_ascii=False,indent=2))
