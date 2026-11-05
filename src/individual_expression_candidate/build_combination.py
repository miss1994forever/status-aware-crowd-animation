"""Package the compiled offline combination replay. No shared-source writes."""
from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[2]
out=root/'outputs/individual-expression-candidate'
d=json.loads((out/'combination-replay.json').read_text())
(out/'combination-review.html').write_text((root/'src/individual_expression_candidate/combination_viewer.html').read_text().replace('REPLAY_DATA',json.dumps(d,separators=(',',':'))))
audit={'kind':d['type'],'virtual_avatar_height_metres':1.65,'coordinate_units':'frozen reference heights','knee_snapshot_sha256':hashlib.sha256((root/'src/individual_expression_candidate/reference/SprintLegIK.cs').read_bytes()).hexdigest(),'input_sha256':hashlib.sha256((root/'data/expression-space-lab/input-cycles.json').read_bytes()).hexdigest(),'clips':[{ 'id':c['id'],**c['audit']} for c in d['clips']],'limits':['managed Unity math shim not engine equivalence','no Unity runtime','no mesh/contact guarantees','overlay step threshold only catches gross jumps','status target mapping uncalibrated','naturalness and status not endorsed']}
(out/'combination-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps(audit,indent=2))
