# 验证报告 — 药材烘干 (A题)

生成时间: 2026-09-11 03:25:22
模型版本: drying_model 1.0.0

## 关键结果

| 项目 | 数值 |
|---|---|
| 问题3 烘干终点 t* | 59286.1751 s = 16.4684 h |
| 问题4 烘干终点 t* | 70759.9787 s = 19.6555 h |
| 网格 | 径向区间 N=320，节点 321，节点中心控制体 321（首末半控制体） |

## 终点原始值（未舍入，供反验证）

- q3_event_time_s_raw = 59286.175088758 s -> 16.468381969 h
- q4_event_time_s_raw = 70759.978749528 s -> 19.655549653 h
- 舍入校验：59286.175088758/3600 = 16.468382 -> 16.4684 h；70759.978749528/3600 = 19.655550 -> 19.6555 h（因未舍入秒数 < 70759.98 s）。

## 检查项

- grid geometry: OK
- finite trajectories: OK
- result matrices finite: OK
- physical ranges: OK
- Q3 critical state: max_i C_i = 0.150000000000 at t = 59286.175089 s
-    integer safe time with max C strictly < 0.15: 59287 s
- Q4 critical state: max_i c_i = 0.150000000000 at t = 70759.978750 s
-    integer safe time with max C strictly < 0.15: 70760 s
- Q3 safe integer time 59287 s: max C = 0.149994820 (strictly < 0.15)
- Q4 safe integer time 70760 s: max C = 0.149999862 (strictly < 0.15)
- centre moisture non-increasing: checked
- excel result1.xlsx: sheets/cols/rows/finiteness OK
- excel result2.xlsx: sheets/cols/rows/finiteness OK
- excel result3.xlsx: sheets/cols/rows/finiteness OK
- excel result3.xlsx: critical-row max C = 0.150000 (expected approximately 0.15)
- excel result3.xlsx: row before critical max C = 0.150039 (> 0.15, crossing confirmed)
- excel result4.xlsx: sheets/cols/rows/finiteness OK
- excel result4.xlsx: critical-row max C = 0.150000 (expected approximately 0.15)
- excel result4.xlsx: row before critical max C = 0.150130 (> 0.15, crossing confirmed)

## 说明

- 扩散系数温度项采用 exp(-3850/T_K)（绝对温度倒数形式）。
- 问题2/3 使用附录3物性、固定半径；问题4 使用附录4物性、材料坐标收缩模型。
- 4 h 之后环境取附件1末1 h均值 (Ta=49.998934 C, Ca=0.04998754)。
- 终点由全域最大含水率事件 max C = 0.15 判定（使用未舍入值）。

## 主结果与工艺背景

严格按题设简化模型（已按规范冻结，未调整参数）得到：

- 问题3 临界烘干时间 t*3 = 16.4684 h（= 59286.2 s）
- 问题4 临界烘干时间 t*4 = 19.6555 h（= 70760.0 s）

题面所述烘干'一般持续 2-3 天'属于**实际工艺背景**。当前有效扩散模型
未包含蒸发潜热（温度方程无相变汇项）与吸附/解吸平衡（以空气含湿量近似
表面平衡含水率），因此预测的**理论临界时间短于实际工艺时长**，属于模型
简化的系统性偏差，而非数值错误。

敏感性结论：

- 表面传质系数 h_C 与扩散系数 D 的主导影响见 sensitivity_*.csv；
- 纯几何收缩相对固定半径的时间变化 dt_shrink = -70402.8 s（Q4 主模型 70760.0 s vs 固定半径 141162.7 s）。
- 水分收支相对残差：Q1 = 3.831e-09，Q3 = 2.972e-06，Q4（材料参考域）= 5.535e-06。