"""Artifact acceptance gate; does not replace motion review or human judgment."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def check():
    audit=json.loads((ROOT/'data/motion-candidate-lab/audit.json').read_text())
    metrics=json.loads((ROOT/'data/motion-candidate-lab/scenario-metrics.json').read_text())
    assert len(audit['entries'])==12
    for e in audit['entries']:
        s=e['source'];assert hashlib.sha256((ROOT/s['file']).read_bytes()).hexdigest()==s['sha256']
        assert s['status_label'] is None
    assert all(e['methods']['improved']['accepted'] for e in audit['entries'][:3])
    assert not audit['entries'][3]['methods']['improved']['accepted']
    assert audit['entries'][7]['methods']['improved']['evidence']['selected_rank']==1
    for p,digest in audit['code_sha256'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest,p
    assert len(metrics['matrix'])==48
    for row in metrics['matrix']:
        assert row['speed']['samples']==1081
        assert row['low_toe_height_horizontal_speed_proxy']['samples']>0
        assert row['final_cycle_seam_velocity_rms']<.001
    assert [e['count'] for e in metrics['encounters']]==[2,10,30]
    assert all(e['finite'] and e['min_speed']>0 and e['center_circle_overlap_samples']==0 for e in metrics['encounters'])
    for count in [10,30]:
        perf=json.loads((ROOT/f'outputs/motion-candidate-lab/performance-{count}-final.json').read_text())
        assert perf['count']==count and perf['time']==9 and perf['raf_interval_ms']['samples']>=300
        assert perf['effective_condition']=='matched_encounter_nominal_0.8'
    required=['M02-seam-before.png','M02-seam-after.png','single-slow-side-3.5.png','single-turn-front-5.png',
              'ten-encounter-oblique-4.4.png','thirty-encounter-oblique-4.4.png','M04-rejected.png','M08-fallback.png']
    for p in required:assert (ROOT/'outputs/motion-candidate-lab'/p).stat().st_size>1000
    assert (ROOT/'data/motion-candidate-lab/browser-checks.json').is_file()
    full=(ROOT/'outputs/motion-candidate-lab/regression-python.txt').read_text()
    assert 'Ran 48 tests' in full and '\nOK\n' in full
    assert '6065 candidate runtime assertions passed' in (ROOT/'outputs/motion-candidate-lab/javascript-tests.txt').read_text()
    result={'artifact_gate':'passed','source_hashes_verified':12,'primary_candidates':['M01','M02','M03'],
            'matrix_conditions':48,'python_regression_tests':48,'new_runtime_assertions':6065,
            'human_naturalness_validation':False,'status_validation':False,'dense_crowd_validation':False,
            'full_body_collision_validation':False}
    (ROOT/'data/motion-candidate-lab/acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':check()
