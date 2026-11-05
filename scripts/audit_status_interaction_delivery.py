"""Consolidate all frozen results and preserve a hash-indexed handoff."""
import csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.build_status_interaction_lab import DATA,OUT,save

def main():
    frozen=json.loads((DATA/'frozen.json').read_text());assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in frozen['sha256'].items())
    rows=[json.loads(p.read_text()) for p in sorted((DATA/'metrics').glob('*.json'))]
    formal=[r for r in rows if r['key'].startswith('eval_')];assert len(formal)==16,len(formal)
    save(DATA/'results.json',rows)
    keys=['key','mode','arrived_fraction','max_proxy_penetration','emergency_hold_agent_seconds','stagnant_agents','completed_arrival_time_mean','completed_path_stretch_mean','active_joint_velocity_change_p99','active_joint_velocity_change_max','planning_seconds','cpu_seconds']
    with (DATA/'results.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:r.get(k) for k in keys} for r in rows)
    text=['# 冻结评价结果','', '|场景/条件|到达|代理穿透|保持人秒|已到达者平均秒|路径伸长|活动关节速度变化p99|', '|---|---:|---:|---:|---:|---:|---:|']
    for r in formal+[x for x in rows if x['key'].startswith('stress-')]:
        n=r['agent_count'];text.append(f"|{r['key']}|{round(r['arrived_fraction']*n)}/{n}|{r['max_proxy_penetration']:.6f}|{r['emergency_hold_agent_seconds']:.2f}|{(r['completed_arrival_time_mean'] or 0):.2f}|{(r['completed_path_stretch_mean'] or 0):.3f}|{(r['active_joint_velocity_change_p99'] or 0):.3f}|")
    (DATA/'tables.md').write_text('\n'.join(text)+'\n')
    inputs={}
    for directory in ['src/status_interaction_lab','status-interaction-lab','data/status-interaction-lab','outputs/status-interaction-lab']:
        for p in (ROOT/directory).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.name!='delivery-manifest.json':inputs[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    for pattern in ['scripts/*status_interaction*','tests/test_status_interaction*']:
        for p in ROOT.glob(pattern):inputs[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    report=ROOT/'docs/status互动原型验收.md';inputs[str(report.relative_to(ROOT))]=hashlib.sha256(report.read_bytes()).hexdigest()
    save(DATA/'delivery-manifest.json',dict(core_freeze_sha256=hashlib.sha256((DATA/'frozen.json').read_bytes()).hexdigest(),formal_count=16,
         artifact_sha256=inputs,human_perception_validated=False,scope='technical prototype; local-only; no Git commit or publishing'))
    print('Consolidated',len(rows),'runs;',len(inputs),'artifact hashes')
if __name__=='__main__':main()
