# CUMCM-2026 A 题：药材烘干问题

径向守恒型有限体积 + BDF 隐式积分的完整实现，生成 `result1.xlsx` ~ `result4.xlsx`。

## 目录

```
├─ 附件1.xlsx / 附件2.xlsx      # 原始附件（只读）
├─ 附件3/result1..4.xlsx        # 结果模板（只读）
├─ 解题指导/                    # 题目与建模/执行规范
├─ configs/
│  ├─ main.yaml                 # 主配置（唯一权威参数源）
│  └─ sensitivity.yaml          # 敏感性/收敛扫描参数
├─ src/drying_model/            # 模型实现（见下）
├─ solution/                    # 单题独立程序（一题一文件，可单独运行）
├─ tests/test_benchmarks.py     # 解析/极限基准测试
├─ inputs/                      # 输入副本：附件1/附件2 + 模板（配置指向此处）
├─ outputs/
│  ├─ tables/                   # 论文用表 1–6 (CSV)
│  └─ diagnostics/              # 收敛/敏感性/事件轨迹/验证报告
├─ result/                      # 最终交付 result1..4.xlsx
├─ figures/                     # 论文插图（6 张）
├─ paper/                       # 论文生成与绘图脚本
├─ matlab/plot_results.m        # 等价 MATLAB 绘图脚本
├─ skills/                      # 本项目沉淀的可复用技能
├─ 论文_药材烘干问题.md/.docx     # 论文（Markdown + Word）
├─ IMPLEMENTATION_QA.md         # 逐条实现细节问答（反验证用）
├─ PROJECT_LESSONS.md
├─ requirements.txt             # 运行时依赖
├─ requirements-dev.txt         # 开发/验证依赖
└─ requirements-lock.txt
```

## 模块对应（与验证清单的对照）

| 功能 | 本实现文件 |
|---|---|
| 物性（附录2/3/4） | `properties.py` |
| 环境 T_a(t), C_a(t) | `environment.py` |
| 半径 R(t) | `radius.py` |
| 有限体积网格（固定域 + 材料域） | `grid.py` |
| 问题2/3 右端 + 问题4 移动域右端 + Robin 边界 + 调和平均 | `rhs.py` |
| 事件函数 | `rhs.make_drying_event` |
| 求解器调用（BDF、分段时间步、事件复核） | `solve.py` |
| 采样到输出网格 | `sampling.py` |
| Excel 写入 | `export_excel.py` |
| 诊断/守恒/收敛 | `diagnostics.py`、`cli.run_sensitivity` |
| CLI | `cli.py` |

## 模型（四问统一）

- **几何**：均匀圆柱，只保留径向传递，R₀ = 0.02 m。网格约定（与验证清单第 7.1 条一致）：
  `radial_intervals = N` 表示 **N 个径向区间**；**节点数 = N+1**；**节点中心控制体 = N+1**
  （首、末为半控制体）。网格为节点中心 `r_i = iΔr, i=0..N`，界面取节点中点，
  `r_{-½}=0`、`r_{N+½}=R₀`。
- **离散**：守恒型环形有限体积，界面 k/D 取**调和平均**，中心面 A=0（无需虚拟节点），
  表面节点落在 `r=R₀` 上（无额外半网格阻力）。
- **时间**：SciPy `solve_ivp` BDF，`rtol=1e-8`，`atol_T=1e-8`，`atol_C=1e-10`。
- **问题 1**：附录 2 常物性，固定半径，0–1800 s。
- **问题 2/3**：附录 3 变物性，固定半径，自初场起算；Q3 以事件 `max_i C_i = 0.15`
  （`terminal=True, direction=-1`）判终点；事件时刻由 BDF 求解器内部事件定位获得，
  再用 brentq 在事件前后异号区间上独立复核（`brent_executed=true`）。
- **问题 4**：附录 4 变物性，材料坐标 `ξ=r/R(t)`，附件 2 半径（PCHIP）；同为材料坐标全域事件。

临界时间的表述：以**全域最大含水率首次降至 0.15 kg/kg 的时刻**作为理论临界烘干时间；
在该时刻之后药材全域含水率**严格低于** 0.15 kg/kg。若需整数秒的安全操作时间，另取
`t₃,safe = 59287 s`、`t₄,safe = 70760 s`（不得用其替代理论临界时间）。

关键约定：扩散系数温度项取 `exp(-3850/T_K)`（`T_K=T_°C+273.15`）；4 h 后环境取
附件 1 末 1 h 均值（Ta=49.998934 °C, Ca=0.04998754）；终点判定使用未舍入数值。

## 运行

```bash
PYTHONPATH=src python -m drying_model.cli inspect --config configs/main.yaml
PYTHONPATH=src python -m drying_model.cli solve  --question 2-3 --config configs/main.yaml
PYTHONPATH=src python -m drying_model.cli solve  --question 4   --config configs/main.yaml
PYTHONPATH=src python -m drying_model.cli verify --all
PYTHONPATH=src python -m drying_model.cli sens   --config configs/sensitivity.yaml
PYTHONPATH=src python -m drying_model.cli all    --intervals 320   # 完整流程
pytest -q                                                          # 基准测试
```

`--intervals` 即径向区间数 N（旧参数名 `--cells` 仍兼容）。

结果写入 `result/`，并生成论文表、收敛/敏感性表、事件轨迹与验证报告。

## 关键结果

| 项目 | 数值 |
|---|---|
| 问题 3 烘干终点 t* | 59286.175088758 s = **16.4684 h** |
| 问题 4 烘干终点 t* | 70759.978749528 s = **19.6555 h** |

## 结果解读：为何理论临界时间短于“2–3 天”

题面“烘干一般持续 2–3 天”属于**实际工艺背景**。本模型是题设给定的简化有效扩散模型，
其预测的临界时间必然短于真实工艺时长，原因是模型未包含以下物理：

1. **蒸发潜热**：温度方程无相变潜热汇项，水分蒸发带走的热量未计入，药材升温偏快、
   扩散系数偏大；
2. **吸附/解吸平衡**：以空气含湿量直接作为表面平衡含水率，缺少吸附等温线；
3. **环境与表面传质处理**：4 h 后按约 50 °C 恒定环境外推，传质系数取 8e-7 m/s；
4. **收缩效应**：问题 4 半径由 2 cm 收缩到约 1.21 cm，扩散距离显著缩短。

因此论文中应把 **16.4684 h（Q3）与 19.6555 h（Q4）作为“严格按题设简化模型”的理论主结果**
保留，并将“2–3 天”作为工艺背景说明，而不是去人为修改模型参数。

## 敏感性分析

| 文件 | 变化因素 |
|---|---|
| `sensitivity_mass_transfer.csv` | 表面传质系数 h_C ×0.5/1/2/4 |
| `sensitivity_diffusivity.csv` | 扩散系数 D ×0.5/1/2 |
| `sensitivity_equilibrium_moisture.csv` | 边界平衡含水率 C_a ×0.5/1/2 |
| `sensitivity_environment.csv` | 4 h 后环境三种取法 |
| `sensitivity_radius.csv` | Q4 半径：PCHIP / 线性 / 固定 R₀ |
| `space.csv` / `convergence_time.csv` | 网格 160/320/640 的终点收敛 |
| `tolerance.csv` / `convergence_tolerance.csv` | 时间容差 1e-7/1e-8/1e-9 |
| `convergence_space.csv` | Q1 场量的空间网格收敛 |
| `conservation_residuals.csv` | 水分收支残差（Q1 固定域 / Q3 固定域 / Q4 材料参考域） |
| `event_trace_q3.csv` / `event_trace_q4.csv` | 终点前后 ±120 s、每 1 s 未舍入轨迹 |
| `event_raw.json` | 终点原始秒数（未舍入） |

## 依赖

- 运行时：`numpy`、`scipy`、`openpyxl`、`PyYAML`（见 `requirements.txt`）
- 开发/验证：`pytest`、`pandas`（见 `requirements-dev.txt`）
- `pytest` 仅用于测试；不装也能用 `python tests/test_benchmarks.py` 直接跑基准。
- `requirements-lock.txt` 是**顶层依赖版本快照**（不含传递依赖与哈希），不是完整锁文件；
  环境已足够复现本题。交付流程不使用 Matplotlib，故未列入依赖。

## 验证

- 网格收敛：N = 64/160/320/640，终点变化 < 0.1 s；空间收敛阶 p₃≈1.98、p₄≈1.89。
- 时间积分误差 < 0.002 s；综合空间离散后，N=320 的 t* 不确定度约 **< 0.04 s**。
- 有限体积 vs 圆柱 Dirichlet 解析解：最大偏差 7.4e-6。
- 问题 4 固定半径极限 vs 固定域：偏差 5.6e-16。
- 水分收支相对残差：Q1、Q3、Q4 均写入 `conservation_residuals.csv`（量级 1e-6~1e-8）。
- 四个 Excel 回读校验：工作表/行列/有限性/临界值 `max C = 0.150000` 全部通过。

详见 `IMPLEMENTATION_QA.md` 与 `outputs/diagnostics/validation_report.md`。
