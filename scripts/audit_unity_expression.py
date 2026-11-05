"""Integration evidence, not a perceptual status assessment."""
import csv,json,math,statistics,sys
from pathlib import Path

def audit(path):
    rows=list(csv.DictReader((path/'expression.csv').open()))
    telemetry=list(csv.DictReader((path/'telemetry.csv').open()))
    assert (path/'finished.txt').exists(), 'Run incomplete'
    assert rows, 'No expression samples'
    for r in rows:
        assert all(math.isfinite(float(v)) for v in r.values()), 'Nonfinite sample'
        if int(r['version']):
            assert float(r['feasible'])==1, 'Pose constraint failure'
            assert float(r['knee'])<=12.01 and float(r['arm'])<=18.01
            assert abs(float(r['offset']))<=.15001
            assert 0<=float(r['target'])<=1
    final={r['id']:r for r in telemetry}
    def span(k):return [min(float(r[k]) for r in rows),max(float(r[k]) for r in rows)]
    return dict(run=path.name,samples=len(rows),finished=True,all_exited=all(float(r['journey_phase'])==2 for r in final.values()),min_centre_gap=float(telemetry[-1]['min_frame_gap']),max_foot_error=max(float(r['foot_error']) for r in telemetry),raw_e=span('raw_e'),raw_h=span('raw_h'),final_e=span('final_e'),final_h=span('final_h'),offset=span('offset'),arm=span('arm'),lowering=span('lowering'),target=span('target'),max_neighbors=max(int(r['neighbors']) for r in rows),raw_e_median=statistics.median(float(r['raw_e']) for r in rows),raw_h_median=statistics.median(float(r['raw_h']) for r in rows))
if __name__=='__main__':
    p=Path(sys.argv[1]);result=audit(p);(p/'expression-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
