# 面向地位差异表达的群组角色动画

计算机动画课程项目。以开源 Environment-aware Motion Matching（EMM）作为基础运动层，自主实现群组空间回应与可解释的身体表达控制。

**[观看视频展示](https://miss1994forever.github.io/status-aware-crowd-animation/)** · [最终版本配置](data/final-submission-selection.json) · [自主源码](src/unity_submission/)

## 最终实现

- 十人固定场景中，预测邻居接近情况，从有限速度/方向候选中选择运动，并考虑安全、舒适距离、目标进度和连续性。
- 角色不读取他人的隐藏 status；从可见身体线索形成响应输入。
- 自身 status 调节手臂、身体高度、躯干与头部姿态，并使用平滑、头部角速度限制和腿部 IK 保持连续性。
- 最终选择为 ExpressionVersion 2、SpatialPolicy 10、HeadFilterLevel 2，种子 806。历史失败候选保留，不代表最终采用方案。

固定录制中 10/10 角色到达出口、最小中心距离约 0.667 m。已在 M2 macOS 上验证独立播放器正常运行。尚未完成正式多人地位感识别实验，不能把运行成功或调试标签当成 status 感知有效性的证据。

## 代码与运行

完整 Unity 工程、macOS 程序及课程报告随课程提交包提供。此仓库主要保存自主源码、研究记录、配置和补丁；不包含所有第三方动作素材，也不能只克隆本仓库就直接运行 Unity 场景。

- `src/unity_submission/`：自主 C# 控制器与运行界面。
- `patches/`：EMM 与 Motion Matching 的 Editor-only 调试代码构建兼容修正。
- `data/final-submission-selection.json`：最终录制配置与证据位置。
- `docs/`、`data/research-route.json`：研究过程与路线记录。
- `showcase/index.html`：公开展示页源文件；发布媒体保存在 `gh-pages` 分支。

完整工程使用 Unity 6000.2.7f2，打开 `Assets/SubmissionSprint/FinalSubmission.unity` 后运行。菜单 `Submission/Build macOS package` 可重新构建。编辑器批处理工具默认输出到工程内 `SubmissionRuns` / `SubmissionPackage`，可用 `UNITY_SUBMISSION_RUNS` / `UNITY_SUBMISSION_PACKAGE` 环境变量覆盖。

## 来源与贡献边界

基础行走、动作匹配、衔接与角色运动采用 [Environment-aware Motion Matching](https://github.com/UPC-ViRVIG/Environment-aware-Motion-Matching)（Ponton 等，2025）。保留原作者署名及[原始许可](src/unity_submission/EMM-LICENSE.txt)。第三方素材各自遵循原许可；本仓库不声称拥有这些素材。

自主部分为群组空间候选选择、可见线索驱动的回应、个体表达与稳定化整合。课程报告说明了工具辅助及形成性反馈的局限。早期研究记录中的计划、统计和实验版本须结合日期阅读，以最终配置为准。
