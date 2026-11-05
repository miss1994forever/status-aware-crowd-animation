# 多风格动作实验数据（2026-10-24）

本目录不含新下载或人工评分。`audit.json` / `candidates.csv` 为现有12个BVH的来源、哈希、采样范围、实测移动方向、原生速度、脚部重复峰、周期候选、闭环尝试及采用理由。原始标签只来自上游，不是status真值。

- `audit.json`：完整审查、统一M01身高标尺、源低脚高足速代理、环境版本、代码SHA-256、工程门槛。`measurements` 为数值计算；`gaps_inferred` 为尚未验证的覆盖缺口。
- `candidates.csv`：12行可筛选摘要，含每条原始URL和SHA-256。
- `scenario-metrics.json`：48个单人条件，以及2/10/30人稀疏相遇。区分步态提取版本、原生/匹配速度和独立的step/smooth调速消融。时间、单位及指标定义内置。
- `browser-checks.json`：实际浏览器操作和证据索引；性能原始读数在`outputs/motion-candidate-lab/performance-*.json`。
- `acceptance.json`：交付包完整性门槛结果；明确不包含自然性/status/密集群组/全身碰撞认证。

复现（在项目根目录；使用已有Python、NumPy与Node）：

```sh
python3 scripts/build_motion_candidate_lab.py
node scripts/audit_motion_candidate_lab.js
python3 -m unittest discover -s tests -p 'test_motion_candidate*.py' -v
node tests/test_motion_candidate_runtime.js
```

页面为`outputs/motion-candidate-lab/index.html`。完整原始FK与循环序列另保存在同目录`lab.json`。页面全部内嵌，无CDN、外部字体或运行时加载；本次通过现有8769服务检查，未单独验收file协议。

固定源revision `74ead3ba1ae4696404e6086233779f60de8bf9ef`；作者Bandai Namco Research Inc.；动作素材CC BY-NC 4.0。原文件和许可证在`data/raw/bandai-pilot/`，未修改；派生页面附许可证。源URL与归属沿用本地已核查清单，本轮未增加外部资料或借用第三方算法实现。

本目录的“接受”只表示通过事先设定的工程门槛：相关峰≥0.65，源接缝位置RMS≤0.025参考身高，最大最终节点改动≤0.05，最终接缝速度差≤0.015参考身高/秒，并有至少两个观察周期及边界余量。不是自然性、心理表达或人体碰撞认证。报告见`docs/多风格连续控制验收.md`。
