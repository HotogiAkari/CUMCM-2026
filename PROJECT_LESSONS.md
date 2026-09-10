# PROJECT_LESSONS — CUMCM-2026 A 题 药材烘干

> 本项目经验已同步整理到工作区经验系统：`PROJECT_LESSONS.md`（P-009~P-018）
> 与 `KNOWLEDGE.md`（K-001~K-007 候选泛用经验）。本文件为项目内副本。

## 文档冲突：问题2的起始状态
type: fact
status: to-review

content: `解题指导/工作指导.md` 与 `题目.md` 称问题2应“承接问题1结束时状态”；而 `四问统一建模与Claw执行规范.md`（schema v2.0，标注为最终框架）与 `解题指导书_Claw执行版.md` 明确要求“问题2从初始场重新计算，不使用问题1末态”。
conclusion: 采用后者（两份最详尽的规范一致），问题2/3 使用附录3物性自 t=0 起算。
evidence: 规范原文 “问题2从初始场重新计算，不使用问题1末态”；解题指导书 “强制规则：Q2不得接续Q1在1800 s的状态”。
scope: 本题实现。
limits: 若命题方以“两阶段接力”为准，需改 Q2 起点；对 Q3 终点影响极小（预热仅占 0.5 h）。
refs: 解题指导/四问统一建模与Claw执行规范.md, 解题指导书_Claw执行版.md

## 附件2 实际记录数
type: fact
status: verified

content: `附件2.xlsx` 实际为 145 条数据记录（t=0..259200 s，R=2→1.198 cm），而非部分说明中的 146。
conclusion: 数据读取校验按 145 条编写。
evidence: openpyxl dims=A1:B146（含表头）。
scope: 本题。
limits: —

## pyyaml 不可用 → 使用 JSON 配置
type: environment
status: verified

content: 运行环境 Python 3.12.3 受 PEP668 保护，`pip install pyyaml` 被拒；numpy/scipy/pandas/openpyxl/matplotlib 均已存在。
conclusion: 配置改用 `configs/main.json`，避免改动系统环境。
evidence: `pip install pyyaml` 报 externally-managed-environment。
scope: 本机 Linux(WSL) 环境。
limits: 若需 YAML，可建 venv 或 --break-system-packages。

## 圆柱径向守恒有限体积 + BDF 的可靠性
type: success
status: verified

content: 环形控制体（A_{−1/2}=0），界面 k/D 调和平均，BDF(rtol=1e-8) 积分。
conclusion: 与圆柱 Dirichlet 解析解最大偏差 7.4e-6；Q4 材料坐标模型在 R(t)≡R0 极限下与固定域一致（5.6e-16）；N=64/160/320 终点变化 <0.001%。
evidence: tests/test_benchmarks.py；网格收敛试算。
scope: 一维径向扩散（导热/传质）。
limits: 强非线性或移动边界剧烈时需重新验证网格/容差。

## 模型结果与题目背景表述的差异
type: fact
status: verified

content: 按指定模型（附录3/4 物性与 h_C=8e-7）算得 Q3 ≈ 16.4684 h、Q4 ≈ 19.6555 h；题面背景称烘干“一般持续 2–3 天”。
conclusion: 已由用户确认：保留理论主结果不改参数；另做 h_C / D / 边界平衡含水率敏感性，并在论文中说明“2–3 天”是实际工艺背景，当前有效扩散模型未含蒸发潜热与吸附平衡，故理论临界时间偏短。
evidence: 事件时间对网格(160/320/640)与容差(rtol 1e-7~1e-9)均稳定；“表面—内部”梯度与 Bi≈1.1 准稳态解析一致。
scope: 本题简化有效扩散模型。
limits: 若命题方要求 2–3 天，需补充相变潜热/吸附等温线或修改系数口径。
refs: outputs/diagnostics/sensitivity_*.csv, validation_report.md

## 有限元/体积术语：区间 vs 节点 vs 控制体
类型: pitfall
状态: verified

content: 节点中心有限体积中，N 通常指“径向区间数”，对应 N+1 个节点与 N+1 个节点中心控制体（首末为半控制体）。若文档写“N 个控制体”会被反向验证判为不一致。
conclusion: 配置项统一用 `radial_intervals`（旧名 `grid_cells` 兼容），运行记录同时写明 intervals/nodes/control_volumes。
evidence: 反向验证报告第 7.1 条。
scope: 一维径向有限体积实现与文档。
limits: 换用 (i+1/2)Δr 单元中心网格时需另加半网格阻力项。

## 事件复核必须建立异号区间
类型: pitfall
状态: verified

content: 用 brentq 复核 solve_ivp 事件时，若只用 [t_event-window, t_event] 作括号，事件端点 g(t_event) 常为 ~1e-17 的正数，brentq 根本不执行，却看起来“复核了”。
conclusion: 先向事件后多积分一小段，用 g>0 与 g<0 的严格异号区间再调 brentq，并显式输出 `brent_executed`。
evidence: 反向验证报告第 7.3 条；修正后 brent_executed=True，g_left>0>g_right。
scope: 所有带终止事件的 ODE 求解。
limits: —

## Q4 收缩域的水分收支要用材料坐标
类型: pitfall
状态: verified

content: 收缩域中用当前物理体积 R(t)²V_i^ξ 积分含水率会把几何收缩误判为水分流失。
conclusion: 用材料坐标度量 M_ξ(t)=ΣV_i^ξ c_i(t)，其收支为 dM_ξ/dt=-(2πh_C/R(t))(c_s-C_a)。
evidence: 反向验证报告第 7.4 条；修正后 Q3/Q4 相对残差分别为 4e-6/3e-6 量级。
scope: 移动边界/收缩域质量守恒检查。
limits: —

## 敏感性主导因素（Q3/Q4）
type: success
status: verified

content: h_C×0.5~4 → t*₃ 由 27.55 h 降到 8.37 h；D×0.5~2 → 21.73 h 降到 13.85 h；C_a×0.5~2 → 15.49 h 升到 19.54 h。Q4 纯几何收缩把时间从固定半径的 39.21 h 砍到 19.66 h（Δt=−70403 s）。
conclusion: 终点对 h_C 与 D 最敏感，对边界平衡含水率中等敏感；收缩显著缩短干燥时间。
evidence: sensitivity_mass_transfer / _diffusivity / _equilibrium_moisture / _radius.csv。
scope: 本题参数区间。
limits: 极端参数下事件可能落在预热阶段，需重验。
