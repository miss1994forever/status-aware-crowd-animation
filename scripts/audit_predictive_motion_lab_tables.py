"""Generate literal result tables from metrics; no significance or perception claims."""
import csv
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data/predictive-motion-lab'
CONDITIONS=[('F',0),('G',0),('G+P',.12),('G+P',.6),('G+P',2.),('no_prediction',0),('circle',0),('no_continuity',0)]
LABELS=['F','G','P=.12','P=.6','P=2','短几何预测','固定圆','无连续项']


def main():
    rows=[json.loads(p.read_text()) for p in sorted((DATA/'metrics').glob('*.json'))]
    text=['# 冻结 v4 结果表','',f'已完成 {len(rows)} / 104 次。完整原始指标见 results.json / results.csv；缺失标为 NA，不填零。','',
          '## 门宽：到达率（单人）','','|分组 / 门宽|'+'|'.join(LABELS)+'|','|---|'+'---:|'*8]
    for split in ['train','heldout']:
        for width in sorted({r['width'] for r in rows if r['split']==split and r['scene']=='door'}):
            line=[]
            for mode,p in CONDITIONS:
                m=next((r for r in rows if r['split']==split and r['scene']=='door' and r['width']==width and r['mode']==mode and r['p_weight']==p),None)
                line.append(f"{m['arrived_fraction']:.0%}" if m else 'NA')
            text.append(f'|{split} / {width:.2f}|'+'|'.join(line)+'|')
    text.extend(['','## 多人共享区：全部条件','','|分组 / 人数|条件|到达|停滞人数|最大代理穿透|hold 人秒|切换|实际参考姿态 RMS|','|---|---|---:|---:|---:|---:|---:|---:|'])
    for split,count in [('train',10),('heldout',10),('heldout',30)]:
        for (mode,p),label in zip(CONDITIONS,LABELS):
            m=next((r for r in rows if r['split']==split and r['agent_count']==count and r['mode']==mode and r['p_weight']==p),None)
            if m:text.append(f"|{split} / {count}|{label}|{m['arrived_fraction']:.0%}|{m['stagnant_agents']}|{m['max_proxy_penetration']:.5f}|{m['emergency_hold_agent_seconds']:.2f}|{m['switches']}|{m['actual_reference_pose_rms']:.5f}|")
            else:text.append(f'|{split} / {count}|{label}|NA|NA|NA|NA|NA|NA|')
    text.extend(['','## 连续性与形变边界（每条件跨场景最大或累计）','','|条件|源姿态最大改动|实际速度倍率最小 / 最大|行进角偏离最大 rad|根加速度最大|ABA 次数合计|','|---|---:|---:|---:|---:|---:|'])
    for (mode,p),label in zip(CONDITIONS,LABELS):
        group=[r for r in rows if r['mode']==mode and r['p_weight']==p]
        if group:text.append(f"|{label}|{max(r['source_pose_modification_max'] for r in group):.4f}|{min(r['actual_speed_ratio_min'] for r in group):.3f} / {max(r['actual_speed_ratio_max'] for r in group):.3f}|{max(r['travel_angle_warp_max_radians'] for r in group):.3f}|{max(r['root_acceleration_max'] for r in group):.2f}|{sum(r['aba_clip_reversals'] for r in group)}|")
    text.extend(['','速度倍率包含切换和从 emergency hold 恢复的瞬态，目标倍率仍为 .8–1.15；骨长投影与突停不保证自然性。根加速度来自 120Hz 重采样回放，包含 hold / 到达后的突停。源姿态与表达量采样为 20Hz，身体碰撞为 120Hz。',''])
    (DATA/'tables.md').write_text('\n'.join(text))
    preferred=['key','split','scene','seed','width','agent_count','mode','p_weight']
    scalar={k for r in rows for k,v in r.items() if not isinstance(v,(dict,list))}
    fields=preferred+sorted(scalar-set(preferred))
    with (DATA/'results.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    (ROOT/'outputs/predictive-motion-lab/results.csv').write_bytes((DATA/'results.csv').read_bytes())
    print('Tables generated for',len(rows),'runs')


if __name__=='__main__':main()
