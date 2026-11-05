"""Create a timestamped disk inventory; not a perception-quality or download-completion claim."""
from pathlib import Path
from datetime import datetime
import json,html
R=Path(__file__).resolve().parents[1]; S=Path('/Volumes/Samsung-SSD/AnimationLab'); O=R/'outputs/motion-expansion';O.mkdir(parents=True,exist_ok=True)
sets=[('SFU','motion-expansion/locomotion/SFU','locomotion.json','完整官方骨架链接集','普通/夸张步行、后退、步幅与姿态变化'),('MOCHA','mocha-data/full','mocha.json','403 BVH，含已有10段','走跑、侧走、蹲行、推、跌倒、拾物、坐下'),('100STYLE','motion-expansion/expression','expression.json','完整原始BVH ZIP，不取特征包','多风格前后行走、侧移、静止与转换'),('Bandai','motion-expansion/expression','expression.json','固定版本两库：3077 BVH','同行为跨风格：行走、鞠躬、引导、转向'),('InterAct','motion-expansion/dyadic/InterAct','dyadic.json','482 BVH＝241双人录制场景','真实配对日常互动；排除音频面部评判'),('ShakeFive2','motion-expansion/dyadic/ShakeFive2','dyadic.json','完整骨架元数据；非高精度动捕','传物、解释等；使用前需按作者要求联系'),('Multi-TPC','motion-expansion/group/Multi-TPC','group.json','69动作＋69注视＋23会话标注','三人身体回应；尚需骨架映射'),('CMU/LAFAN1','motion-expansion/transition','transition.json','以独立清单为准','通用动作与转换；许可分别核查')]
rows=[]
for name,rel,manifest,scope,use in sets:
 root=S/rel;files=list(root.rglob('*')) if root.exists() else [];raw=[p for p in files if p.is_file() and p.suffix.lower() in ['.bvh','.amc','.asf']];partial=[p for p in files if p.is_file() and p.name.endswith('.part')]
 # expression root shared by two archives; do not double-attribute raw files.
 if name in ['100STYLE','Bandai']:count='见专门状态文件（共享目录不重复计数）'
 elif name=='Multi-TPC':count=str(sum(p.is_file() and p.suffix.lower() in ['.txt','.csv'] for p in files))+' 个TXT/CSV成品文件'
 elif name=='ShakeFive2':count='XML骨架及归档包状态见清单'
 else:count=f'{len(raw)} 个BVH/ASF/AMC成品文件（其他格式见清单）'
 status_paths={'100STYLE':[S/'motion-expansion/expression/100style-download-status.json'],'Bandai':[S/'motion-expansion/expression/bandai-download-status.json'],'Multi-TPC':[root/'download-status.json'],'CMU/LAFAN1':[root/'CMU/download-status.json',root/'LAFAN1/download-status.json']}
 states=[]
 for sp in status_paths.get(name,[]):
  if sp.exists():
   sd=json.loads(sp.read_text());states.append((sp.parent.name+': ' if name=='CMU/LAFAN1' else '')+str(sd.get('state',sd.get('status','见清单'))))
 if states:count+='；状态：'+', '.join(map(str,states))
 rows.append({'name':name,'root':str(root),'manifest':manifest,'scope':scope,'purpose':use,'disk_observation':count,'partial_bytes_shared_root':sum(p.stat().st_size for p in partial)})
snap={'checked_at':datetime.now().astimezone().isoformat(),'warning':'Static snapshot; file presence is not full integrity, naturalness, or status validation. See per-source manifest/logs for download completion.','datasets':rows}
(O/'inventory.json').write_text(json.dumps(snap,ensure_ascii=False,indent=2)+'\n')
e=html.escape
trs=''.join('<tr>'+''.join('<td>'+v+'</td>' for v in [e(x['name']),e(x['scope']),e(x['purpose']),e(x['disk_observation']),f'<a href="../../data/research/motion-expansion/{x["manifest"]}">来源与状态清单</a>' if (R/'data/research/motion-expansion'/x['manifest']).exists() else '该方向仍在核验'])+'</tr>' for x in rows)
s='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>跨情景动作数据扩充</title><style>body{margin:32px auto;padding:0 24px;max-width:1300px;background:#edf3f8;color:#19334e;font:16px/1.7 system-ui}h1{font-family:serif}table{border-collapse:collapse;background:white;width:100%}td,th{padding:14px;text-align:left;border-bottom:1px solid #cad6e0;vertical-align:top}a{color:#176eaf}.scroll{overflow:auto}p{max-width:1000px}code{overflow-wrap:anywhere}</style><a href="../../progress/index.html#research-route">返回研究路线</a><h1>跨情景动作数据扩充</h1>'''
s+=f'<p>盘点时间：{e(snap["checked_at"])}。这是静态快照，下载在SSD后台继续；重新打开此页不会自动重新扫描磁盘。</p>'
s+='<p><strong>完整原片优先，感知结论另验。</strong>情绪、风格或角色关系标签均不是“只看动作即可读出的status”真值。原始库保留完整，后续预览再筛选自然、相关的片段。</p><div class="scroll"><table><thead><tr><th>数据集</th><th>获取范围</th><th>研究用途</th><th>磁盘观察（非完成认证）</th><th>核验记录</th></tr></thead><tbody>'+trs+'</tbody></table></div>'
s+='<h2>下一轮优先看什么</h2><ol><li>Bandai/MOCHA：同一种非招呼动作的不同表达，区分羞怯、情绪与地位印象。</li><li>SFU/100STYLE：行走、起停和侧移，检验修改后的连续性与自然度。</li><li>InterAct：保持真实双人同步，观察接近、等待和回应；先确认实际动作，再按情境筛选。</li></ol><p>InterAct有970条候选情境文本，但只有241组实际录制，已核对文件映射；实际boss/subordinate仅2组。角色设定不是感知标签，也不将项目改成关系分类。</p><p>后台下载支持恢复与完成后校验。大包尚在传输时不能称为“整库已获取”。需要申请或联系作者的库保持单独标识。</p>'
(O/'index.html').write_text(s)
print(json.dumps(snap,ensure_ascii=False,indent=2))
