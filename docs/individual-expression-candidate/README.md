# 个体表达算法 · 独立探索记录

最新IE-05：[实时预览](http://127.0.0.1:8790/) · [25.5秒加强组合视频](../../outputs/individual-expression-candidate/round5-review.html) · [实现与验证范围](实时预览与加强组合-IE05.md)。新增躯干、头颈与显式互动余量；旧版测试结论不自动继承，尚未接入Unity或完成感知验收。

[观看23秒示例动画](../../outputs/individual-expression-candidate/video-review.html) · [MP4](../../outputs/individual-expression-candidate/example-animation.mp4) · [来源和重建说明](示例动画视频说明.md)。包含行走、侧移、双向反馈和端点诊断；离线骨架预览，非Unity录屏。

2026-11-05。当前为独立实现与离线审查版，未合入Unity，不占用空间线编辑器。用户已确认作业聚焦：在保留基础运动的同时，通过可控身体表达与情境回应，探索群组人物相对地位的可读性。“高地位可以配合”是约束/诊断，不是首要独立主题。


## 最新：IE-04 互动表达具体函数

已将个人基底、可见线索、相遇权重、有界回应和时间更新写成[五函数规格](互动表达函数规格-IE04.md)及独立C#原型。通过3441项检查及M01/M07真实可见骨点单向回放。初始参数已经明确，回应方向及地位语义仍是待测假设。

后续继续推进到[双向离线骨点反馈检查](双向骨点反馈检查-IE04.md)：18种场景通过数值判据，但status=0/1的端点场景最终互动偏移被完全裁掉，属于表达缺陷，不能算功能验收通过。[图](../../outputs/individual-expression-candidate/body-feedback-review.png)并列展示收敛、退出、原动作周期变化与端点饱和。Unity运行、导航反馈、自然度和人物印象仍未验收。

## 互动参数稳定性（IE-04之前的结构探索）

针对用户提出的“自身设定＋对方可见动作＋距离”与反馈震荡问题，已形成[稳定性方案](互动表达稳定性方案.md)、独立人工标量压力模型及[结果图](../../outputs/individual-expression-candidate/feedback-review.png)。模型复现滤波下的震荡/极端分化，并检查完整敏感度预算、退出回归、噪声和10人总权重预算。不是Unity或status感知验证；未新增生产互动模块。

## 最新：IE-03 身体组合探索

用户反馈IE-02手臂页面未感觉差别，并要求探索更有效组合、追问status调节是否应更合理。新增[身体组合探索规格](身体组合探索-IE03.md)与[同输入组合页](../../outputs/individual-expression-candidate/combination-review.html)。IE-03真正执行离线高度修改，比较直接组合与目标＋约束组合；不改空间线、不请求合入。status目标映射仍未标定；非线性几何求解不等于地位语义已经合理。

新组合浏览器连接不可用，未完成视觉验收。膝部叠加帧间变化仍有风险，不能继承旧手臂页的自然度或交互检查结论。下文IE-02信息保留为前一轮记录。

## 从哪里开始

- [算法规格](算法规格-IE02.md)：表达映射、协调策略、局部姿态约束、依据与否证条件。
- [同输入真实原片对照](../../outputs/individual-expression-candidate/raw-review.html)：M01向前行走与M07侧移，原始FK逐帧播放；三个栏为原片、旧固定上臂规则、新上臂算法。高度只记录请求、没有应用。不是Unity录制或完整组合。
- [接入说明](接入说明-IE02.md)：基于reference的精确局部修改、开关、回退及串行验收队列；不是整文件覆盖或自动合入请求。
- [设计依据审查与历史决策](设计依据审查.md)。

## 当前实现

`ExpressionProfile`提供明确的status创作控制到身体目标映射；`ExpressionPolicy`根据自己的设定、尺度、真实根速度和dt，输出平滑手臂权重及高度请求；`ExpressionOverlay`只消费命令，不读取status，操作新鲜源骨架中的双上臂；`ExpressionMath`实现局部定长目标。均在独立命名空间IndividualExpressionCandidate。

首个profile仍是SourceToCompact假设，不声称已解决地位语义。Profile与几何解耦是实现边界改善，不意味着映射本身已有新感知证据。使用线性创作控制不代表真实地位等级等距。

世界坐标使用Unity米制宿主约定；手臂局部坐标为外侧/向上/向前，单位向量与几何目标不依赖均匀尺度；真实速度除固定bodyScale。上臂保留前后分量，固定骨长，向下/向外姿态才处理，大摆动时减弱，最大9°；左/右增益1/.75。没有新注视模块，不读别人隐藏值，不修改导航、脚膝或原动作节奏。

高度以bodyScale*.0125*w提出请求，但仅宿主能决定可执行预算和腿IK。`BoundedLowering`只裁剪标量，不能证明可达性或连续性。默认预算0；不能把只应用了手臂的结果说成完整表达组合。

## 语义兼容

当前ObservedExpansion读取最终左肘展开/肩宽。新算法改变其分布，也会改变旧belief/response分支输入；即使导航代码没改，闭环行为仍可能不同。本地两段原片最大观测变化约.177，不能沿用旧实验结论。观测公式、`.05/.7`映射与空间阈值保持不动，交空间线审核。AppliedArmAngle接入后应注明为实际修正角，不能混用旧目标角语义。

## 验证与重建

```sh
dotnet run --project tests/test_individual_expression_candidate/Checks.csproj -- outputs/individual-expression-candidate/synthetic-walk.csv
dotnet run --no-restore --project tests/test_individual_expression_candidate/Checks.csproj -- --replay data/expression-space-lab/input-cycles.json outputs/individual-expression-candidate/raw-replay.json
python3 src/individual_expression_candidate/build_review.py
```

测试工程只使用本机SDK、UnityEngine DLL静态引用，输出在独占tests目录，UseSharedCompilation=false，不触发Unity刷新或共享工程编译。更换机器需调整csproj的UnityEngine引用路径。

已通过：508203项数学/策略检查；100000组单位向量约束；编译真实策略、数学核与Unity适配器；两段原始骨架回放的骨长、非手臂不动和前后分量约束；源BVH哈希一致；浏览器布局、前/侧视、切片段、拖时间、强度切换和重播检查。无控制台错误/警告。浏览器检查是显示/交互审查，不是用户感知验收。

未验证：Unity接线/运行、完整高度＋手臂组合、脚膝、人体网格/手腕接触、自然度与status可读性、交会及群组。原片物理单位未确认；离线回放明确使用冻结参考身高单位，不能混作米。没有等幅度因果消融，没有正式盲评/统计验证。

先前限制：IE-01只有上臂技术候选且耦合ownStatus；IE-02已拆分策略和编辑，但SourceToCompact仍是待测假设。旧固定12°在合成向量中可能越过肩内侧，这只是机制反例，不证明Unity已穿模。新上臂角较小也会带来约.053参考身高的最大手腕位移，不能当成接触安全保证。

通过顺序：独立上臂画面→空间线认可的高度组合→固定空间版本开回应→十人验收。自然度或表达失败就关候选，不进行无休止角度扫描。录屏、报告、打包优先。
