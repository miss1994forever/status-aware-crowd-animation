# EMM 图形运行验收（2026-10-27）

主示例与无第三方付费资产的走廊人群示例均已在图形 Editor Play 模式运行至少 72 秒，并已正常退出、重新打开后再次完成 72 秒人群复现。四项技术验收完成。未实现 status 模型，也没有评定动作自然性或课程原创性合规。

## 环境与启动

- Editor：`/Volumes/Samsung-SSD/Applications/Unity/Unity/Unity.app`，6000.2.7f2，ARM64，Metal；未升级。
- 工程：`/Volumes/Samsung-SSD/AnimationLab/Unity/Projects/Environment-aware-Motion-Matching/Unity`。
- EMM 作者提交：`273928addc94ddf4a3bd7b8bf1ef17c360b0000e`。
- 核心 Motion Matching 0.3.1，锁定提交：`95f903c7bc45b983b1984497029ea13c36a8be27`，未换成最新版。
- [启动脚本](../outputs/emm-validation/launch_emm.sh) 会检查现有实例，避免重复打开。也可在 Unity Hub 添加上述工程目录并使用已安装的 6000.2.7f2。

手动复现：

1. 打开工程，在 Project 面板进入 `Assets/EnvironmentMotionMatching/Scenes/EMM_NoDependencies`。
2. 双击 `00_Environment_MainDemo`，按顶部 Play。W/A/S/D 移动；F 切换固定朝向；空格切换当前控制器的半速/原速。退出 Play 后不会保存测试输入。
3. 停止 Play，再打开同目录 `10_Crowds_Corridor` 并 Play；人群由官方脚本自动生成和行走，无需键盘输入。
4. 正常退出 Unity，再打开工程和场景即可复现。首次运行可能生成数据库及编译着色器，应等待真实人物与环境出现。

独立验收脚本位于 `Assets/EMMValidation/Editor/EMMValidationRunner.cs`，[留档副本](../outputs/emm-validation/EMMValidationRunner.cs)。默认不接管手动 Play；只有显式写入一次性测试命令才启动。可用 `python3 outputs/emm-validation/reproduce_test.py main main-new-name` 或 `crowd crowd-new-name` 排入一次 72 秒测试，然后启动 Editor。命名必须唯一；不要在正在编辑未保存场景时排队。

## 实际运行证据

以下 FPS 用 `Time.frameCount` 的增量除以真实墙钟时间，包含本次自动采集负担；不是目标 FPS、构建版性能或人工前台流畅度认证。脚本每约 0.5 秒记录各角色根位置、全身关节世界坐标与局部旋转、数据库帧、障碍位置和半径。

| 运行 | 采样覆盖游戏时间 | 采样覆盖墙钟时间 | 实测平均 FPS | 结果 |
|---|---:|---:|---:|---|
| main-01，首次启动诊断 | 71.68 秒 | 73.41 秒 | 6.12 | 早期青色画面，40 秒截图才正常，不计完整视觉通过 |
| main-02，缓存后复测 | 71.79 秒 | 71.96 秒 | 9.99 | 人物、环境正常，姿态与位置持续变化 |
| crowd-01，首次人群运行 | 71.90 秒 | 97.61 秒 | 5.28 | 包含数据库首次生成；10–70 游戏秒区间平均 6.82 FPS；峰值 67 人 |
| crowd-02-restart，正常退出后复现 | 71.97 秒 | 75.37 秒 | 8.31 | 峰值 58 人；126 条至少 5 秒的轨迹全部有位移和关节变化；无缓存重建警告 |

每轮完成文件记录实际停止时 `Time.time >= 72`；表内时间是首尾遥测采样覆盖范围。主示例 main-02 单角色累计采样路径长约 123.21 m，检测到 2,398 个关节相邻样本旋转变化（四元数分量绝对差之和 > 0.01）。人群首轮有 124 条观察至少 5 秒的轨迹，全部路径长 > 1 m 且关节变化样本 > 20；角色持续生成和销毁，因此轨迹总数不等于同时人数。这些是运行证据，不是感知评分。

正常退出由会话77501返回退出码0确认；重新启动会话99836使用相同Editor/工程路径，日志为 `emm-validation-reproduce.log`。复现轮72秒结束后留在走廊场景的编辑状态，已清除测试命令，不会继续自动驱动。

可视证据：

- 主示例：[4秒](../outputs/emm-validation/main-02-4s.png)、[5秒绕过圆柱](../outputs/emm-validation/main-02-5s.png)、[7秒](../outputs/emm-validation/main-02-7s.png)、[12秒墙前](../outputs/emm-validation/main-02-12s.png)、[40秒](../outputs/emm-validation/main-02-40s.png)、[65秒](../outputs/emm-validation/main-02-65s.png)。
- 人群：[8秒](../outputs/emm-validation/crowd-01-8s.png)、[20秒](../outputs/emm-validation/crowd-01-20s.png)、[65秒](../outputs/emm-validation/crowd-01-65s.png)。俯视镜头沿用官方场景。
- 重启复现：[20秒](../outputs/emm-validation/crowd-02-restart-20s.png)、[65秒](../outputs/emm-validation/crowd-02-restart-65s.png)、[完整统计](../outputs/emm-validation/crowd-02-restart-telemetry-summary.json)。
- [主示例统计](../outputs/emm-validation/main-02-telemetry-summary.json)、[人群统计](../outputs/emm-validation/crowd-01-telemetry-summary.json)、[避让记录](../outputs/emm-validation/main-02-avoidance.json)。

主示例测试通过官方 `InputCharacterController.OnMovementDirectionChanged` 输入方向，不修改角色 Transform、检索参数或动画数据。日程是 0–3 秒无输入、3–18 秒向前、18–22 秒停止、22–34 秒向右、34–48 秒向后、48–60 秒向左、60–72 秒向前；不是此前 Python 的 12 秒对照实验。屏幕左下键盘图标仍为黑色，因为测试直接调用输入接口而非合成按键。

避让的具体证据：前方圆柱中心约 (-0.153, 2.416)，半径 0.3 m，初始 x=0 的直线输入会穿过其圆形占地；持续向前输入时根位置在 4.89 秒达到 (0.592, 2.792)，从右侧绕过。该阶段采样根点距圆柱边缘最小约 0.534 m。12–17.5 秒仍要求向前，但角色停在红墙前，根位置 x 范围仅约 0.00385 m、z 范围约 0.00150 m。截图与坐标相符。这里证明具体环境响应，不能推广为所有障碍、所有身体部位均无穿透，也未做关闭避让的因果对照。

## 导入、修复与边界

- 官方 `Examples` 的 100 个文件完整导入 `Assets/Samples/Motion Matching/0.3.1/Examples`，保留原 `.meta` GUID，复制时逐文件 SHA-256 与包内源文件一致；导入完成后，Unity仅重生成了PlayerInput.cs的两处注释路径（0.2.0改为0.3.1），可执行内容一致，见[导入校验](../outputs/emm-validation/sample-import.json)。解决主场景引用的 InputCharacterController、InputManager、FollowCamera 缺失。
- 第一次运行本地缺少生成后的动作数据库。核心包按作者现有代码现场生成并保存到 `Assets/StreamingAssets/MMDatabases`；没有重写生成算法或下载额外动作数据。
- 首轮着色器编译期间截到青色画面，保留失败记录；缓存后重新完整运行，未修改渲染管线设置。
- 一次重启遇到 `HandleDanglingSceneBackups` 恢复提示。该测试备份完整移到 SSD `Validation/preserved-scene-backups-main01/0.backup`，未删除用户文件；之后通过 `EditorApplication.Exit(0)` 正常退出。
- 原生UI工具曾持续返回过时的条款窗口；用户提供的真实 Editor 截图纠正了判断。运行证据来自图形 Editor 的 `ScreenCapture` 输出和实际对象遥测，不以旧UI画面、headless编译或帧计数单独判定成功。
- 原官方受版本控制文件未改动，新增仅为样例、自动生成缓存和隔离验收脚本；没有改 Python 主线、购买资源、升级引擎、提交 Git、绕过安全检查或代接受协议。

日志：SSD `/Volumes/Samsung-SSD/AnimationLab/Unity/Downloads/emm-validation-01.log`、`emm-validation-02b.log`、`emm-validation-reproduce.log`。完整遥测/原始PNG在同级 `../Validation/`。本仓库保留精选截图、统计、测试脚本和消息日志。启动日志存在许可 token 更新失败后成功解析 entitlement 的诊断，以及 Metal memoryless attachment 提示；不能称整个日志完全没有 Error 字样。主示例复测运行消息无 Error/Exception/Assert；人群首次运行只有两条数据库生成 Warning，非持续错误刷屏；重启复现轮无 Warning/Error/Exception/Assert。

## 后续接入点

- `MotionMatchingSearch` 的 `ShouldSearch`、`FindBestFrame`、`OnSearchCompleted`、`OnUpdateEnvironmentFeatureWeight` 是实际检索扩展入口。后续可添加个人表达与即时响应候选评分，需区分个人代码和作者底层。
- `MotionMatchingController.SkeletonTransforms`、`OnSkeletonTransformUpdated`、`CurrentFrame` 提供可见动作观察入口；邻人决策应从可见骨骼/运动特征计算，不直接读取他人的隐藏 status。
- `CrowdCharacterController.SetMovementDirection` 是期望运动输入；仅改速度、避让半径或路径不等于实现 status。当前复用的是环境感知动画底层，表达保留、互动感与自然性都需后续独立实验及用户观看评价。
- 本次人群运行有聚集、迂回，且实测帧率偏低。未验证高密度完全无碰撞、所有人持续通过或实时帧率目标；不能将可运行宣称为最终研究已完成。
