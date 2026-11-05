from pathlib import Path
import re
root=Path(__file__).resolve().parents[1];folder=root/'outputs/social-signal-review'
s=(folder/'index.html').read_text();head=s.split('<main>')[0];body=s.split('<main>')[1].split('<details>')[0];js=re.search(r'<script>([\s\S]*?)</script>',s).group(1)
head=head.replace('R1 · 社会表达原片审查','R1 · 原片与事件对齐')
body=body.replace('五段表达，先看动作再看标签','把动作时刻与身体变化对齐').replace('<p><a href="extraction.html">查看多 agent 核验结果与时间曲线 →</a></p>','<p><a href="extraction.html">核验结果</a> · <a href="index.html">原片审查</a></p>')
body=body.replace('A–E 不是地位排名；先描述你看到了什么，再展开来源标签。','A–E 不是地位排名；本页核对动作时间与身体变化。')
# Keep same original motion renderer; new page has its own event records.
body+='''<section style="background:white;padding:18px;border:1px solid #c9d7e2;border-radius:8px"><h2>随播放同步的曲线</h2><label>测量 <select id="measure"><option value="l_wrist_outward_from_midline_m">左腕侧向距离（m）</option><option value="r_knee_flexion_deg">右膝弯曲角（°）</option><option value="pelvis_height_m">骨盆高度（m）</option><option value="left_hand">左手相对前臂角（°）</option></select></label><svg id="trace" viewBox="0 0 1000 210" role="img" aria-label="当前原片测量曲线与播放时间"></svg><p id="measureReadout"></p><p>竖线只表示当前时间。曲线峰值不是互动起点；绝对高度不宜直接跨人物比较。</p><div class="bar"><button id="prevFrame">上一帧</button><button id="nextFrame">下一帧</button><button data-case="D">定位 D：左腕展开峰值附近</button><button data-case="A">定位 A：尾段</button><button data-case="E">定位 E：左手变化峰值附近</button></div></section>
<section style="margin-top:24px"><h2>事件标注 · 不确定可以留空</h2><p>“起抬”是该次招呼可辨认运动的开始；“主要手势”是招呼最清楚的时刻；“结束”是招呼手势结束，不要求恢复原姿态。E需观察左手局部，不能用抬手高度代替判断。准备姿态变化可能早于起抬。</p><div class="bar"><label>事件 <select id="eventType"><option value="onset">招呼运动开始</option><option value="gesture">主要手势时刻</option><option value="offset">招呼手势结束</option></select></label><button id="markEvent">记录当前时间</button><button id="clearEvent">清除此项标注</button><button id="exportEvents">导出全部标注</button></div><p id="eventList" aria-live="polite"></p><label>这段的判断或不确定处<br><textarea id="eventNote" rows="3" style="width:100%;max-width:900px;font:inherit;padding:10px"></textarea></label><p id="eventStatus" role="status"></p><p>标注仅保存在当前浏览器，不自动回写项目或通知主聊天。保存前会检查时间顺序；记录不代表已完成正式感知评价。</p></section>'''
js=js.replace("+' 秒'}","+' 秒';drawTrace();renderEvents()}")
(folder/'event-review.html').write_text(head+'<main>'+body+'</main><script>'+js+'\n</script><script src="event-review.js"></script></html>')
