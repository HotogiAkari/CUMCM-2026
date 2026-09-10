---
document_type: implementation_guide
schema_version: "1.0"
language: zh-CN
problem: A题_药材烘干
runtime: Python_3.12
target_executor: Claw
questions: [Q1, Q2, Q3, Q4]
numerical_method: conservative_radial_finite_volume_plus_BDF
required_outputs:
  - result1.xlsx
  - result2.xlsx
  - result3.xlsx
  - result4.xlsx
  - run_summary.json
  - validation_report.md
status: ready_for_implementation
---

# A题药材烘干 Python 3.12 解题指导书

## 1. 指导书目标

本指导书用于指导Claw完成从附件读取、数学模型实现、数值求解、结果验证、Excel输出到论文数据整理的全过程。

最终代码必须达到以下目标：

1. 使用Python 3.12运行；
2. 独立求解问题1、问题2/3和问题4；
3. 使用守恒型径向有限体积法离散空间；
4. 使用SciPy的BDF隐式积分器求解；
5. 自动定位问题3和问题4的全域含水率终点；
6. 保持官方Excel模板结构并写入四位小数结果；
7. 给出守恒、极值、网格、容差和敏感性验证；
8. 保存完整运行配置，使数值结果可复现；
9. 不把未经运行或未经验证的数字填入论文。

## 2. 必须冻结的建模决策

### 2.1 四问计算关系

~~~mermaid
flowchart TD
    A["读取附件并校验单位"] --> B["共同初始场：T=28 ℃，C=2.55"]
    B --> Q1["Q1：附录2，固定R，0–1800 s"]
    B --> Q23["Q2/3：附录3，固定R，从0开始"]
    B --> Q4["Q4：附录4，R(t)，从0开始"]
    Q23 --> E3["Q3：max C=0.15事件"]
    Q4 --> E4["Q4：max C=0.15事件"]
~~~

强制规则：

- Q2不得接续Q1在1800 s的状态；
- Q4不得接续Q3的状态；
- Q2和Q3可以共用同一次从零开始的长时积分；
- Q4使用附录4并独立从零开始。

### 2.2 扩散系数温度项

题面附录3、附录4写成 \(\exp(-3850T)\)，其中 \(T\) 为K。严格代入初温会导致指数约为 \(-1.159\times10^6\)，扩散系数下溢为0。主计算采用以下显式解释：

\[
D=D_0\exp(-aC)\exp\left(-\frac{3850}{T_K}\right),
\qquad T_K=T_{\rm Celsius}+273.15.
\tag{DEC-01}
\]

程序必须实现两种模式：

| 模式 | 公式 | 用途 |
|---|---|---|
| arrhenius_inverse_T | \(\exp(-3850/T_K)\) | 正式计算 |
| strict_problem_text | \(\exp(-3850T_K)\) | 量级诊断，不作为正式结果 |

程序日志和run_summary.json必须记录当前模式。不得静默改式。

### 2.3 空气水分列的解释

药材中的 \(C\) 是干基含水率，空气水分列与其物理基准未必相同。由于题目没有提供吸附等温线，主模型采用

\[
C_e(t)\approx C_a(t)
\]

作为等效边界势。代码变量建议使用 ambient_moisture_potential，而不是容易误导的 air_dry_basis_moisture。

### 2.4 4 h后的环境

附件1在14400 s结束。Q3、Q4主方案采用附件1末1 h均值：

\[
T_{a,\rm tail}=49.998934\ ^\circ{\rm C},
\qquad
C_{a,\rm tail}=0.04998754.
\]

另运行两组敏感性：

- constant_setpoint：\(50^\circ{\rm C},0.05\)；
- last_value_hold：\(50.165^\circ{\rm C},0.04986\)。

Q2只要求前三小时结果时，不涉及数据外推。

### 2.5 Q4半径

Q4采用固定材料坐标

\[
\xi=\frac r{R(t)}\in[0,1].
\]

半径主插值为PCHIP，敏感性插值为分段线性。PCHIP保形、保单调且不对不光滑数据产生过冲，适合附件2的单调平台型半径数据。[^7]

## 3. Python 3.12运行环境

### 3.1 为什么使用CPU双精度

本题每个模型通常只有数百至约一千多个状态变量，主要瓶颈是刚性ODE的稀疏线性代数和函数调用，而不是大规模矩阵乘法。推荐：

- NumPy float64；
- SciPy BDF；
- 稀疏Jacobian模式；
- 单进程完成正式结果；
- 敏感性场景确认正确后，可用2至4个独立进程并行。

不推荐在第一版中使用CuPy、CUDA或32/64线程。它们会增加环境和数据传输复杂度，却不一定加速这类中小规模隐式积分。

### 3.2 创建虚拟环境

Python官方文档建议用venv创建相互隔离、可重建的项目环境。[^1]

Windows PowerShell：

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
~~~

Windows cmd：

~~~bat
py -3.12 -m venv .venv
.\.venv\Scripts\activate.bat
python -m pip install --upgrade pip
~~~

Linux或macOS：

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
~~~

### 3.3 建议依赖

第一版requirements.txt建议：

~~~text
numpy>=1.26,<3
scipy>=1.11,<2
pandas>=2.1,<4
openpyxl>=3.1,<4
matplotlib>=3.8,<4
pyyaml>=6,<7
pytest>=8,<10
~~~

安装：

~~~bash
python -m pip install -r requirements.txt
python -c "import sys,numpy,scipy,pandas,openpyxl; print(sys.version); print(numpy.__version__,scipy.__version__,pandas.__version__,openpyxl.__version__)"
~~~

首次得到可信结果后保存精确环境：

~~~bash
python -m pip freeze > requirements-lock.txt
~~~

禁止只记录“Python 3”，必须在run_summary.json中保存完整Python、NumPy、SciPy、pandas和openpyxl版本。

## 4. 项目目录

建议Claw建立以下结构：

~~~text
drying_project/
├─ data/
│  ├─ raw/
│  │  ├─ attachment1.xlsx
│  │  ├─ attachment2.xlsx
│  │  └─ templates/
│  │     ├─ result1.xlsx
│  │     ├─ result2.xlsx
│  │     ├─ result3.xlsx
│  │     └─ result4.xlsx
│  └─ processed/
├─ src/
│  └─ drying_model/
│     ├─ __init__.py
│     ├─ config.py
│     ├─ data_io.py
│     ├─ environment.py
│     ├─ properties.py
│     ├─ radius.py
│     ├─ grid.py
│     ├─ rhs_fixed.py
│     ├─ rhs_shrink.py
│     ├─ events.py
│     ├─ solve.py
│     ├─ sampling.py
│     ├─ export_excel.py
│     ├─ diagnostics.py
│     ├─ plots.py
│     └─ cli.py
├─ tests/
│  ├─ test_data_io.py
│  ├─ test_properties.py
│  ├─ test_environment.py
│  ├─ test_grid.py
│  ├─ test_flux_balance.py
│  ├─ test_fixed_benchmarks.py
│  ├─ test_shrink_limits.py
│  ├─ test_events.py
│  └─ test_excel_contract.py
├─ configs/
│  ├─ main.yaml
│  └─ sensitivity.yaml
├─ outputs/
│  ├─ official/
│  ├─ diagnostics/
│  ├─ figures/
│  └─ tables/
├─ requirements.txt
├─ requirements-lock.txt
├─ pyproject.toml
└─ README.md
~~~

原始附件必须只读。程序把模板复制到outputs/official后再写入，不得直接覆盖data/raw。

## 5. 配置文件规范

configs/main.yaml建议采用以下结构：

~~~yaml
runtime:
  python_required: "3.12"
  dtype: float64

geometry:
  initial_radius_m: 0.02
  length_m: 0.25

initial:
  temperature_C: 28.0
  moisture_dry_basis: 2.55

boundary:
  heat_transfer_W_m2K: 25.0
  mass_transfer_m_s: 8.0e-7

diffusivity:
  temperature_mode: arrhenius_inverse_T

environment:
  interpolation: linear
  post_4h_mode: tail_1h_mean

radius_q4:
  interpolation: pchip
  post_72h_mode: last_value_hold

solver:
  method: BDF
  rtol: 1.0e-8
  atol_temperature: 1.0e-8
  atol_moisture: 1.0e-10
  dense_output: true
  grid_cells: 320
  event_threshold: 0.15

verification:
  grids: [160, 320, 640]
  rtols: [1.0e-7, 1.0e-8, 1.0e-9]

output:
  decimals: 4
  preserve_templates: true
~~~

所有参数只在配置或专门常量模块中定义一次。禁止在不同问题脚本里重复硬编码同一参数。

## 6. 数据读取与输入验收

### 6.1 附件1

读取后转换为三个float64数组：

\[
\boldsymbol t_a,\quad \boldsymbol T_a,\quad \boldsymbol C_a.
\]

强制检查：

- 恰有三列有效数值；
- 时间单位为s；
- 时间严格递增；
- 首时刻为0，末时刻为14400；
- 数据共241条；
- 温度和水分列无空值、NaN或Inf；
- 温度应在合理烘干范围；
- 水分势非负。

在数据范围内使用numpy.interp或scipy.interpolate.interp1d的线性模式。对数据范围外禁止默认线性外推，必须走明确的post_4h_mode。

### 6.2 附件2

读取为

\[
\boldsymbol t_R,\quad \boldsymbol R_{\rm cm},
\]

立即执行

\[
R_{\rm m}=0.01R_{\rm cm}.
\]

强制检查：

- 时间严格递增；
- 首点为 \((0,2.0\ {\rm cm})\)；
- 末点为 \((259200\ {\rm s},1.198\ {\rm cm})\)；
- 半径始终为正；
- 半径单调不增，允许平台；
- 插值结果不能超出观测半径的局部范围。

### 6.3 Excel模板

启动计算前打印：

- 文件名；
- 工作表名；
- 每个工作表的最大行、最大列；
- 第一行全部列头；
- A列前10个和最后10个非空时间；
- 是否存在合并单元格、公式、隐藏表或特殊格式。

模板是题意歧义的最终校验依据。例如result2的时间范围应优先根据模板行数判断。

openpyxl的load_workbook可读取现有xlsx并返回可修改工作簿；read_only模式不可编辑，因此正式写模板时使用read_only=False。[^9]

### 6.4 输入哈希

使用SHA-256记录所有原始附件和模板的哈希。run_summary.json中保存：

~~~json
{
  "inputs": {
    "attachment1.xlsx": "sha256:...",
    "attachment2.xlsx": "sha256:...",
    "result1_template.xlsx": "sha256:..."
  }
}
~~~

这样可以防止比赛过程中附件被误改后仍以为结果来自同一数据。

## 7. 四问数学模型速查

### 7.1 共同初值与中心边界

\[
T(r,0)=28,\qquad C(r,0)=2.55,
\]

\[
T_r(0,t)=0,\qquad C_r(0,t)=0.
\]

### 7.2 固定半径表面边界

\[
-kT_r(R,t)=h_T(T_s-T_a),
\]

\[
-DC_r(R,t)=h_C(C_s-C_a).
\]

### 7.3 Q1

\[
\rho c_pT_t=\frac1r\partial_r(rkT_r),
\]

\[
C_t=\frac1r\partial_r[rD(C)C_r],
\qquad D=7\times10^{-9}e^{-0.89C}.
\]

\[
\rho=820,\quad c_p=2600,\quad k=0.36.
\]

### 7.4 Q2与Q3

\[
\rho(C)c_p(C)T_t=
\frac1r\partial_r[rk(C)T_r],
\]

\[
C_t=
\frac1r\partial_r[rD(C,T_K)C_r].
\]

附录3：

\[
\rho=650+128C,
\]

\[
c_p=1450+2736\frac C{C+1},
\]

\[
k=0.21+0.38\frac C{C+1},
\]

\[
D=2.4\times10^{-3}e^{-0.45C}e^{-3850/T_K}.
\]

Q3终止事件：

\[
g_3(t)=\max_i C_i(t)-0.15.
\]

### 7.5 Q4

材料坐标 \(\xi=r/R(t)\) 上：

\[
\rho(c)c_p(c)\theta_t=
\frac1{R(t)^2\xi}\partial_\xi[\xi k(c)\theta_\xi],
\]

\[
c_t=
\frac1{R(t)^2\xi}\partial_\xi[\xi D(c,\theta_K)c_\xi].
\]

表面条件：

\[
-\frac{k}{R}\theta_\xi(1,t)=h_T(\theta_s-T_a),
\]

\[
-\frac D R c_\xi(1,t)=h_C(c_s-C_a).
\]

附录4：

\[
\rho=760+90c,\qquad
c_p=1850+2150\frac c{c+1},
\]

\[
k=0.12+0.20\frac c{c+1},
\]

\[
D=4.2\times10^{-4}e^{-0.30c}e^{-3850/\theta_K}.
\]

Q4事件：

\[
g_4(t)=\max_i c_i(t)-0.15.
\]

## 8. 核心程序接口

### 8.1 配置数据类

建议在config.py中使用不可变数据类，避免求解过程中意外修改参数：

~~~python
from dataclasses import dataclass

@dataclass(frozen=True)
class BoundaryConfig:
    h_heat: float
    h_mass: float

@dataclass(frozen=True)
class SolverConfig:
    method: str
    rtol: float
    atol_temperature: float
    atol_moisture: float
    n_intervals: int
    event_threshold: float

@dataclass(frozen=True)
class GeometryConfig:
    radius0_m: float
    length_m: float
~~~

统一规定：

- N表示径向区间数；
- 节点数恒为N+1；
- 所有内部距离单位为m；
- 所有内部时间单位为s；
- 温度状态用摄氏度；
- 只有扩散系数计算时转换为K；
- 所有数组使用numpy.float64。

### 8.2 环境对象

environment.py建议接口：

~~~python
class Environment:
    def __init__(self, time_s, temperature_C, moisture_potential, post_mode):
        ...

    def evaluate(self, t_s: float) -> tuple[float, float]:
        """返回环境温度和等效水分势。"""
        ...
~~~

单元测试必须覆盖：

- 每一个原始采样点处返回原值；
- 任意相邻点中点等于线性平均；
- 14400 s左右连续；
- 三种post_mode返回预期常量；
- 负时间直接报错，不允许悄悄外推。

### 8.3 物性函数

properties.py中每套物性独立命名：

~~~python
def appendix2_diffusivity(C):
    ...

def appendix3_properties(T_C, C, temperature_mode):
    """返回rho, cp, k, D。"""
    ...

def appendix4_properties(T_C, C, temperature_mode):
    """返回rho, cp, k, D。"""
    ...
~~~

建议通过对数形式计算扩散系数：

~~~python
T_K = T_C + 273.15
log_D = np.log(D_prefactor) - moisture_factor * C - 3850.0 / T_K
D = np.exp(log_D)
~~~

在正式计算前强制检查：

~~~python
if np.any(T_K <= 0.0):
    raise ValueError("absolute temperature must be positive")
if np.any(C <= -1.0):
    raise ValueError("C + 1 appears in material properties")
if not np.all(np.isfinite(D)) or np.any(D <= 0.0):
    raise FloatingPointError("invalid diffusivity")
~~~

strict_problem_text模式不要直接依靠下溢后的0来解释，应同时输出

\[
\log D=\log D_0-aC-3850T_K,
\]

这样能够明确说明异常来自指数，而不是程序错误。

### 8.4 半径对象

radius.py建议接口：

~~~python
class RadiusLaw:
    def __init__(self, time_s, radius_cm, method, post_mode):
        ...

    def evaluate_m(self, t_s):
        """返回以m为单位的正半径。"""
        ...
~~~

主插值使用PchipInterpolator，构造时设置extrapolate=False；程序自行处理末端保持。SciPy文档指出PCHIP保持数据单调性并避免过冲。[^7]

### 8.5 网格对象

固定域节点：

\[
r_i=i\Delta r,\qquad i=0,\ldots,N,\qquad \Delta r=R/N.
\]

界面：

\[
r_{i-\frac12}=\max(0,r_i-\Delta r/2),
\]

\[
r_{i+\frac12}=\min(R,r_i+\Delta r/2).
\]

单位轴向长度的控制体面积与界面面积：

\[
V_i=\pi(r_{i+\frac12}^2-r_{i-\frac12}^2),
\qquad
A_{i+\frac12}=2\pi r_{i+\frac12}.
\]

Q4使用完全相同的构造，但把 \(r\) 换成 \(\xi\)，区间换成 \([0,1]\)。

grid.py建议返回只读数据：

~~~python
@dataclass(frozen=True)
class RadialGrid:
    nodes: np.ndarray
    left_faces: np.ndarray
    right_faces: np.ndarray
    volumes: np.ndarray
    left_areas: np.ndarray
    right_areas: np.ndarray
    spacing: float
~~~

网格验收恒等式：

\[
\sum_i V_i=\pi R^2,\qquad
A_{-\frac12}=0,\qquad
A_{N+\frac12}=2\pi R.
\]

这些恒等式应以接近机器精度通过。

### 8.6 调和平均

\[
K_{i+\frac12}=\frac{2K_iK_{i+1}}{K_i+K_{i+1}}.
\]

实现：

~~~python
def harmonic_mean(left, right):
    if np.any(left <= 0.0) or np.any(right <= 0.0):
        raise ValueError("harmonic mean requires positive coefficients")
    return 2.0 * left * right / (left + right)
~~~

不要为了避免报错而随意给分母加一个很大的epsilon；物性非正说明上游状态或公式已经错误。

## 9. 固定域有限体积右端

### 9.1 状态布局

令节点数 \(n=N+1\)，采用

\[
\boldsymbol y=(T_0,\ldots,T_{n-1},C_0,\ldots,C_{n-1})^{\mathsf T}.
\]

拆分时只建立视图：

~~~python
n = grid.nodes.size
T = y[:n]
C = y[n:]
~~~

Q1虽然可以把两个场分开求解，为减少代码分支也可使用同一状态布局；但应明确Q1交叉依赖为零。

### 9.2 内部通量

\[
q^T_{i+\frac12}
=-k_{i+\frac12}\frac{T_{i+1}-T_i}{\Delta r},
\]

\[
q^C_{i+\frac12}
=-D_{i+\frac12}\frac{C_{i+1}-C_i}{\Delta r}.
\]

数组化实现方向：

~~~python
k_face = harmonic_mean(k[:-1], k[1:])
D_face = harmonic_mean(D[:-1], D[1:])
qT_inner = -k_face * np.diff(T) / grid.spacing
qC_inner = -D_face * np.diff(C) / grid.spacing
~~~

### 9.3 中心和表面

中心面积为0，因此无须虚拟节点，也无须直接计算 \(1/r\)。

表面沿正半径方向的通量：

\[
q^T_s=h_T(T_s-T_a),\qquad
q^C_s=h_C(C_s-C_a).
\]

当 \(T_a>T_s\) 时 \(q^T_s<0\)，表示净热流方向指向药材内部；当 \(C_s>C_a\) 时 \(q^C_s>0\)，表示水分向外排出。这个符号解释应写进测试。

### 9.4 右端装配

\[
\rho_ic_{p,i}V_i\dot T_i
=A_{i-\frac12}q^T_{i-\frac12}
-A_{i+\frac12}q^T_{i+\frac12},
\]

\[
V_i\dot C_i
=A_{i-\frac12}q^C_{i-\frac12}
-A_{i+\frac12}q^C_{i+\frac12}.
\]

实现时可先建立长度n的left_flux和right_flux：

~~~python
net_T = area_left * qT_left - area_right * qT_right
net_C = area_left * qC_left - area_right * qC_right

dTdt = net_T / (rho * cp * volume)
dCdt = net_C / volume
return np.concatenate((dTdt, dCdt))
~~~

不得误写为

\[
\frac d{dt}(\rho c_pVT)=\text{净热通量},
\]

因为当前主模型定义的是 \(\rho c_pT_t\)，而不是完整变组分焓方程。

## 10. Q4材料坐标有限体积右端

### 10.1 与固定域程序的差别

Q4网格固定在 \(\xi\in[0,1]\)。内部通量仍由节点差构造，但净通量需乘

\[
\frac1{R(t)^2}.
\]

表面材料坐标通量为

\[
\widehat q^T_s=R(t)h_T(\theta_s-T_a),
\]

\[
\widehat q^C_s=R(t)h_C(c_s-C_a).
\]

因此rhs_shrink.py的核心顺序是：

1. 由 \(t\) 计算 \(R(t)\)；
2. 由当前 \(\theta,c\) 计算附录4物性；
3. 在 \(\xi\) 网格计算内部通量；
4. 用 \(R(t)h\) 计算表面材料通量；
5. 用 \(R(t)^{-2}\) 缩放净通量；
6. 返回 \(\dot\theta,\dot c\)。

### 10.2 禁止出现的错误

- 不在物理坐标的固定节点上删除超出半径的节点；
- 不在每个时步重新生成长度不同的状态数组；
- 不计算分段半径曲线的 \(\dot R\) 后再手工加对流项；
- 不同时使用材料坐标方程和显式收缩速度项，否则会重复计算；
- 不把输出坐标 \(r_k\) 直接当成材料坐标；
- 不把 \(R(t)\) 的cm数值直接代入SI方程。

### 10.3 极限一致性

若令 \(R(t)\equiv R_0\)，并让Q4求解器使用与固定域求解器完全相同的物性，则二者在映射 \(r=R_0\xi\) 后应给出同一结果。这是Q4实现最重要的自动测试。

## 11. 稀疏Jacobian结构

### 11.1 局部依赖

对于每个节点i：

- 温度方程依赖相邻的 \(T_{i-1},T_i,T_{i+1}\)；
- 因 \(\rho,c_p,k\) 依赖C，还依赖相邻的 \(C_{i-1},C_i,C_{i+1}\)；
- 含水率方程通过D依赖相邻T和C。

因此Q2至Q4的每一行最多只需要相邻节点的两个场。可以构造 \(2n\times2n\) 的布尔CSR稀疏矩阵：

~~~python
from scipy.sparse import lil_matrix

def build_jac_sparsity(n: int):
    S = lil_matrix((2 * n, 2 * n), dtype=bool)
    for i in range(n):
        neighbors = range(max(0, i - 1), min(n, i + 2))
        for j in neighbors:
            S[i, j] = True
            S[i, n + j] = True
            S[n + i, j] = True
            S[n + i, n + j] = True
    return S.tocsr()
~~~

SciPy说明，对于每行只有少量非零元素的Jacobian，提供jac_sparsity可显著加速有限差分Jacobian计算。[^2]

### 11.2 不要过早手写解析Jacobian

第一版优先使用正确的jac_sparsity，让SciPy数值估计Jacobian。只有在：

- 模型已通过全部测试；
- 性能确实成为瓶颈；
- 解析导数有独立有限差分测试；

之后才考虑手写Jacobian。错误的解析Jacobian通常比不提供Jacobian更危险。

## 12. BDF积分与输出采样

### 12.1 基本调用

~~~python
atol = np.concatenate((
    np.full(n, cfg.atol_temperature),
    np.full(n, cfg.atol_moisture),
))

solution = solve_ivp(
    fun=rhs,
    t_span=(t0, t_end),
    y0=y0,
    method="BDF",
    rtol=cfg.rtol,
    atol=atol,
    jac_sparsity=jac_sparsity,
    dense_output=True,
    events=event,
    max_step=max_step,
)
~~~

BDF是1至5阶变阶隐式方法；SciPy同时支持分量化atol、稠密输出、事件方向和终止事件。[^2]

### 12.2 分阶段积分

推荐按环境数据范围拆成两段：

| 阶段 | 时间 | 环境 | 建议max_step |
|---|---|---|---:|
| A | 0–14400 s | 附件1线性插值 | 30–60 s |
| B | 14400 s–终点 | 稳态延拓 | 300–600 s |

阶段B以阶段A的未舍入末态作为初值。这只是同一问题内部的连续积分，不是把Q1接到Q2。

对Q1仅运行0–1800 s。对Q2/3，Q2和Q3共享从0开始的同一解。对Q4独立运行。

### 12.3 输出时刻不等于内部步长

- result1：每1 s采样；
- result2：默认前三小时每1 s采样，最终以模板为准；
- result3、result4：每60 s采样；
- 论文表：按题目指定时刻采样；
- 求解器内部步长由误差控制决定。

不要为得到每1 s输出就把积分器强制成固定1 s。应使用t_eval或稠密输出。

### 12.4 内存控制

Q2若从0到三天全部按1 s保存，将产生约259200个时刻。虽然单表仍可能存放，但计算内存、Excel大小和写入时间都会明显增加。执行规则：

1. 先检查result2官方模板时间列；
2. 无明确长时模板时，result2只保存0–3 h；
3. Q3长期结果按60 s保存；
4. 内部自适应步不全部转换成DataFrame；
5. 长时解可按6 h分块积分和写入中间npz检查点。

## 13. 终止事件与精确烘干时间

### 13.1 事件函数

~~~python
def make_drying_event(n: int, threshold: float):
    def event(t, y):
        C = y[n:]
        return float(np.max(C) - threshold)

    event.terminal = True
    event.direction = -1.0
    return event
~~~

Q4状态中的后半段同样是材料坐标含水率，因此事件写法不变。

### 13.2 为什么不能只监测平均值

\[
\bar C(t)=\frac2{R^2}\int_0^R C(r,t)r\,dr<0.15
\]

不能推出所有位置达标。题目要求“药材各处”低于0.15，所以必须使用

\[
C_{\max}(t)=\max_rC(r,t).
\]

### 13.3 为什么仍要记录中心

正常由表面向外排水时，中心通常最湿。但这应由结果验证，而不能先验假定。每个保存时刻记录：

~~~text
time_s
max_moisture
argmax_node
argmax_radius_or_xi
center_moisture
surface_moisture
~~~

若所有时刻argmax_node均为0，则用 \(C(0,t)-0.15\) 的光滑事件复核终点。

### 13.4 Brent复核

solve_ivp通过事件函数的符号变化寻找零点，单步内若存在多个零点可能漏检。[^2] 本题一般只有一次下降穿越，但仍应保存

\[
g(t_a)>0,\qquad g(t_b)\le0.
\]

然后对稠密输出调用brentq：

~~~python
def g_dense(t):
    y_t = dense_solution(t)
    return float(np.max(y_t[n:]) - threshold)

t_star = brentq(g_dense, t_a, t_b, xtol=1.0e-8, rtol=1.0e-12)
~~~

Brent法要求连续函数且区间端点异号，结合二分、割线和逆二次插值，适合此类已经括住的单根。[^3]

### 13.5 严格小于的报告方式

连续解的临界点满足

\[
C_{\max}(t_*)=0.15.
\]

严格 \(C_{\max}<0.15\) 在 \(t_*\) 之后成立。论文建议写：

> 以全域最大含水率首次下降至0.15 kg/kg的时刻作为临界烘干时间；该时刻之后药材各处满足严格低于阈值的要求。

如需工艺安全时间，另行给出向上取整时间，不要替代数学临界时间。

## 14. 各问具体执行路线

### 14.1 问题1

目标：

- 计算0–1800 s的温度和含水率；
- 填表1、表2；
- 生成result1.xlsx。

步骤：

1. 读取附件1的0–1800 s数据；
2. 建立固定物性热方程和 \(D(C)\) 非线性湿方程；
3. 用N=160做冒烟运行；
4. 检查表面温度上升、含水率下降、中心变化滞后；
5. 运行N=320和640收敛计算；
6. 选择收敛网格；
7. 在100、300、600、900、1200、1500、1800 s采样；
8. 在0、0.5、1、1.5、2 cm插值；
9. 在1–1800 s、0–2 cm每0.1 cm采样并写Excel；
10. 输出温度与水分径向曲线。

Q1重点：

- D必须用每个节点的局部C；
- 不能把表面直接设为环境值；
- 表面半控制体体积不能按完整控制体处理；
- 计算网格不能直接等于0.1 cm输出网格。

### 14.2 问题2

目标：

- 从 \(t=0\) 统一使用附录3；
- 得到前三小时温湿分布；
- 生成result2.xlsx。

步骤：

1. 重新建立初始状态，不读取Q1末态；
2. 每次右端计算更新 \(\rho(C),c_p(C),k(C),D(C,T_K)\)；
3. 同步求解T和C；
4. 在0.5、1、1.5、2、2.5、3 h采样；
5. 在0、0.5、1、1.5、2 cm插值；
6. 按模板确定result2的时间范围；
7. 输出前3 h温度、含水率等值或径向曲线；
8. 保存3 h末态供同一次Q2/Q3长时积分检查，但不要把它当成另一个物性阶段的起点。

Q2重点：

- 变k、变D保留在散度内；
- \(D\) 中使用K；
- 物性用局部C，不用截面平均C；
- Jacobian交叉块不为零；
- 不添加没有参数支持的潜热项。

### 14.3 问题3

目标：

- 沿用Q2模型找到全域达标时刻；
- 填表5；
- 生成result3.xlsx。

步骤：

1. 使用Q2从零开始的同一长时积分；
2. 0–4 h使用附件1，之后用主延拓；
3. 设置 \(g_3=\max C-0.15\) 下降事件；
4. 先以每6 h检查点观察事件接近情况；
5. 事件触发后用Brent法复核；
6. 检查最大点是否始终在中心；
7. 每6 h采样0、0.5、1、1.5、2 cm；
8. 最后加入精确终点行；
9. 每60 s、每0.1 cm输出result3；
10. 运行三种环境延拓敏感性。

Q3重点：

- 事件判断不使用四位小数；
- 不用平均含水率；
- 若模板不允许非整分钟行，精确终点单独保存；
- 终点小数的可信度取决于网格和容差收敛。

### 14.4 问题4

目标：

- 使用附件2半径和附录4物性；
- 找到收缩情况下全域达标时间；
- 填表6；
- 生成result4.xlsx；
- 分离收缩和物性变化的影响。

步骤：

1. 从初始状态重新开始；
2. 构造PCHIP半径函数；
3. 在固定材料网格 \(\xi\in[0,1]\) 上建模；
4. 每次右端计算读取 \(R(t)\) 并乘 \(R^{-2}\)；
5. 表面材料通量乘R；
6. 设置 \(g_4=\max c-0.15\) 事件；
7. 每60 s保存材料坐标解；
8. 输出时将物理位置映射为 \(\xi=r/R(t)\)；
9. 对 \(r>R(t)\) 写空值，不做外推；
10. 表面列始终取 \(c(1,t)\)；
11. 运行“附录4 + 固定2 cm”的对照；
12. 运行PCHIP与线性半径敏感性；
13. 若终点超过72 h，半径保持1.198 cm并明确说明。

纯收缩影响使用

\[
\Delta t_{\rm shrink}
=t_{*,{\rm appendix4,shrink}}
-t_{*,{\rm appendix4,fixed}}.
\]

不要用Q3与Q4的时间差直接表示收缩影响，因为二者物性公式不同。

## 15. 空间和时间采样

### 15.1 固定域

若输出物理位置为 \(r_{\rm out}\)，直接在计算节点上做一维插值：

~~~python
values_out = np.interp(r_out_m, grid.nodes, values_on_grid)
~~~

### 15.2 Q4

~~~python
R_cm = radius_law.evaluate_m(t_s) * 100.0

if r_out_cm <= R_cm + domain_tolerance_cm:
    xi = min(1.0, r_out_cm / R_cm)
    value = np.interp(xi, xi_grid.nodes, moisture)
else:
    value = None
~~~

注意浮点边界：当 \(r_{\rm out}\) 与 \(R(t)\) 理论相等时，可用很小的domain_tolerance_cm避免因舍入被误判为域外；随后把 \(\xi\) 限制在1以内。

### 15.3 输出时间表

| 文件或表 | 时间 |
|---|---|
| 表1、表2 | 100、300、600、900、1200、1500、1800 s |
| result1 | 1至1800 s，步长1 s |
| 表3、表4 | 0.5至3 h，步长0.5 h |
| result2 | 默认1至10800 s，步长1 s；以模板为准 |
| 表5、表6 | 每6 h，另加精确终点 |
| result3、result4 | 每60 s；精确事件行按模板规则 |

所有输出时间必须排序、去重。若终点正好是规则采样点，不得重复写两行。

## 16. Excel输出规范

### 16.1 为什么官方结果使用openpyxl

pandas的ExcelWriter适合生成新表，但整个工作簿写入可能改变现有模板结构。正式结果应：

1. 用shutil.copy2复制模板；
2. 用openpyxl.load_workbook读取副本；
3. 只修改要求的数值单元格；
4. 保留原工作表名、列头、宽度和格式；
5. 保存到outputs/official。

openpyxl支持读取现有工作簿、按行列访问单元格并保存；保存同名文件会覆盖，因此只能操作模板副本。[^9][^10]

### 16.2 写入规则

- A列写时间，单位s；
- 第一行写物理距离，单位cm；
- 数值写Python float，不写字符串；
- 单元格number_format设置为0.0000；
- Q4域外位置写None；
- 不用字符串“NaN”污染提交文件；
- 事件计算使用原值，写入时才显示四位；
- 写完后关闭工作簿，再重新打开做回读检查。

### 16.3 回读验收

每个文件检查：

- 文件能被openpyxl重新打开；
- 工作表名完全正确；
- 行列数符合模板；
- A列时间单调递增；
- 第一行距离单调递增；
- 所有应填区域为数值；
- Q4域外区域为空；
- 数值格式为四位小数；
- 温度、水分没有写反工作表；
- 没有额外索引列。

## 17. 验证体系

验证分为五层。必须先通过低层测试，再相信正式结果。

### 17.1 第一层：函数单元测试

使用pytest参数化测试多组状态。pytest支持同一测试函数在多组输入上运行，适合测试三套物性和多个边界场景。[^11]

必须测试：

| 测试 | 输入 | 预期 |
|---|---|---|
| T转K | 28 ℃ | 301.15 K |
| Q1扩散系数 | 多个C | 正数且随C增大而减小 |
| Q2/Q4扩散系数 | 固定C，不同T | 随T升高而增大 |
| \(C/(C+1)\) | \(C=0,2.55\) | 有限且在合理范围 |
| 调和平均 | \(K_L=K_R\) | 返回同一K |
| 环境插值 | 原始节点 | 精确返回原值 |
| 半径插值 | 原始节点 | 精确返回原值 |
| 网格体积 | 任意N | 总和为 \(\pi R^2\) |
| Jacobian模式 | 边界/内部行 | 只含允许的局部依赖 |

数组比较使用numpy.testing.assert_allclose，并显式给出atol和rtol。NumPy文档说明其判据为

\[
|a-b|\le {\rm atol}+{\rm rtol}|b|.
\]

[^12]

### 17.2 第二层：零变化与符号测试

#### TEST-ZERO-01：平衡均匀场

设

\[
T(r,0)=T_a,\qquad C(r,0)=C_a.
\]

内部梯度和表面通量都为零，右端必须接近机器零。

Q4即使 \(R(t)\) 改变，均匀平衡场也必须保持不变。若发生变化，说明错误加入了几何稀释项或重复处理了收缩速度。

#### TEST-SIGN-01：纯加热

设 \(T_a>T_0\)、\(C_a=C_0\)。预期：

- 表面温度导数为正；
- 中心初始导数可为0或很小；
- 水分导数为0。

#### TEST-SIGN-02：纯干燥

设 \(C_a<C_0\)、\(T_a=T_0\)。预期：

- 表面含水率导数为负；
- 总含水率指标下降；
- 温度导数为0。

这两组测试最容易发现Robin边界符号写反。

### 17.3 第三层：常系数圆柱解析基准

为单独验证圆柱扩散算子，建立常系数、固定半径、表面Dirichlet为0的合成问题：

\[
u_t=D\left(u_{rr}+\frac1ru_r\right),
\]

\[
u(r,0)=u_0,\qquad u_r(0,t)=0,\qquad u(R,t)=0.
\]

其级数解为

\[
\frac{u(r,t)}{u_0}
=2\sum_{m=1}^{\infty}
\frac{J_0(\lambda_mr/R)}
{\lambda_mJ_1(\lambda_m)}
\exp\left(-\lambda_m^2\frac{Dt}{R^2}\right),
\]

其中 \(\lambda_m\) 是 \(J_0\) 的正零点。

用scipy.special.jn_zeros、j0、j1计算足够多项，与数值解在 \(t>0\) 的多个位置比较。该测试验证：

- 圆柱几何因子；
- 中心处理；
- 内部通量；
- 空间收敛。

解析基准使用Dirichlet边界，因此需在测试代码中提供一个简单的Dirichlet边界分支，不应改动正式Robin模型。

### 17.4 第四层：Robin与收缩极限测试

#### TEST-LUMPED-01：小Bi极限

人为设置很小的h，使 \(Bi<0.01\)。固定圆柱的平均温度应接近集中参数解：

\[
T(t)-T_a=[T(0)-T_a]
\exp\left(-\frac{2h_T}{\rho c_pR}t\right).
\]

水分常系数情形同理：

\[
\bar C(t)-C_a=[C(0)-C_a]
\exp\left(-\frac{2h_C}{R}t\right).
\]

该测试主要验证Robin边界面积、体积和符号。

#### TEST-SHRINK-01：固定半径极限

令 \(R(t)=R_0\)，Q4材料坐标求解器和固定域求解器使用相同物性。映射到共同物理位置后，两解应在设定容差内一致。

#### TEST-SHRINK-02：均匀平衡收缩

环境等于初值，半径随时间下降，场仍应保持均匀不变。

#### TEST-SHRINK-03：半径插值范围

在每个附件2区间密集采样，检查：

\[
R_{m+1}\le R(t)\le R_m.
\]

### 17.5 第五层：正式问题验证

正式运行必须同时通过：

1. 求解器success为真；
2. 无NaN或Inf；
3. \(T_K>0\)，\(C\ge0\)；
4. \(\rho,c_p,k,D>0\)；
5. 温度处于初值与历史环境温度包络内，允许数值容差；
6. 含水率处于初值与历史边界势包络内；
7. 总含水率在净干燥阶段不增；
8. 固定域和材料域离散收支残差足够小；
9. 终点有正负括区；
10. 事件时 \(|C_{\max}-0.15|\) 足够小；
11. 中心和全域最大事件相互解释一致；
12. 输出文件回读通过。

## 18. 守恒与收支验证

### 18.1 固定域水分

\[
M_C(t)=\sum_iV_iC_i(t).
\]

\[
\frac{dM_C}{dt}
=-A_Rh_C(C_s-C_a).
\]

积分残差：

\[
\epsilon_C(t)=
\frac{
\left|M_C(t)-M_C(0)
+\int_0^tA_Rh_C(C_s-C_a)\,d\tau\right|
}{M_C(0)}.
\]

边界通量积分可把 \(F(t)=A_Rh_C(C_s-C_a)\) 作为额外状态同步积分：

\[
\dot I_C=F(t),\qquad I_C(0)=0.
\]

这样比对稀疏输出再做梯形积分更准确。

### 18.2 Q4材料域水分

\[
\widehat M_C(t)=\sum_i\widehat V_ic_i(t),
\]

\[
\frac{d\widehat M_C}{dt}
=-\frac{2\pi h_C}{R(t)}[c_s-C_a].
\]

同样可增加积分状态 \(\widehat I_C\)。这里检查的是所采用有效干基含水率模型的离散收支，不应宣称已经获得真实水质量，除非另有干固体密度数据。

### 18.3 热方程

固定域瞬时平衡：

\[
\sum_i\rho_ic_{p,i}V_i\dot T_i
=A_Rh_T(T_a-T_s).
\]

这是方程残差检查。由于 \(\rho c_p\) 随C变化，不能简单把 \(\sum\rho c_pVT\) 当成完整真实焓进行时间积分守恒检查。

### 18.4 建议阈值

建议但不机械强制：

- 零右端测试：绝对误差 \(<10^{-12}\) 至 \(10^{-10}\)；
- 网格几何恒等式：相对误差 \(<10^{-14}\)；
- 标准运行水分收支相对残差：先要求 \(<10^{-6}\)；
- 事件残差：\(|C_{\max}-0.15|<10^{-8}\)；
- Excel回读：显示误差不超过 \(5\times10^{-5}\)。

若阈值未通过，应先分析误差来源，不能通过放宽阈值掩盖问题。

## 19. 网格与时间收敛

### 19.1 网格收敛

运行

\[
N=160,\quad320,\quad640.
\]

所有解必须投影到共同的题目输出位置和共同时间，再比较：

\[
E_T^{(N)}=\max|T_N-T_{2N}|,
\]

\[
E_C^{(N)}=\max|C_N-C_{2N}|,
\]

\[
E_t^{(N)}=|t_{*,N}-t_{*,2N}|.
\]

可估计观测收敛阶：

\[
p\approx
\log_2\left(\frac{E^{(N)}}{E^{(2N)}}\right).
\]

不要强行要求 \(p=2\)。非线性Robin边界、半控制体、事件定位和不光滑环境数据都可能影响观测阶。重点是误差随网格细化稳定下降。

建议输出convergence_space.csv：

| question | N | max_error_T | max_error_C | event_time_s | event_diff_s | mass_residual | runtime_s |
|---|---:|---:|---:|---:|---:|---:|---:|

### 19.2 时间容差收敛

固定细网格，至少比较：

\[
\mathrm{rtol}=10^{-7},10^{-8},10^{-9}.
\]

每档都使用相匹配的分量atol。比较论文表格值和事件时刻，不只比较求解器success。

建议输出convergence_time.csv：

| question | rtol | atol_T | atol_C | max_diff_T | max_diff_C | event_time_s | nfev | njev | nlu |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|

### 19.3 四位小数的可信度

题目要求四位小数是输出格式，不代表四位都具有物理意义。

终点以h报告时：

\[
0.0001\ {\rm h}=0.36\ {\rm s}.
\]

只有当细网格与更细网格的终点差小于约0.36 s时，才能声称时间小数点后第四位得到数值收敛支持。否则仍按格式输出四位，但应在论文中报告计算不确定度。

若终点附近下降率为

\[
s_*=\left|\frac{dC_{\max}}{dt}\right|_{t_*},
\]

含水率误差会产生近似时间误差

\[
\delta t_*\approx\frac{\delta C}{s_*}.
\]

后期下降很慢时，小的含水率误差也可能放大成明显时间误差。

## 20. 敏感性与对照实验

### 20.1 环境延拓

Q3、Q4分别运行：

| ID | 4 h后温度 | 4 h后水分势 |
|---|---:|---:|
| ENV-MAIN | 49.998934 | 0.04998754 |
| ENV-S1 | 50 | 0.05 |
| ENV-S2 | 50.165 | 0.04986 |

输出每个方案的 \(t_*\)、中心终点斜率和终点差。

### 20.2 Q4半径插值

比较：

- PCHIP + 72 h后末值保持；
- 线性 + 72 h后末值保持。

若终点超过72 h，再增加一个仅用于敏感性的渐近拟合方案，但不能把拟合外推当作观测事实。

### 20.3 收缩贡献

比较：

- 附录4 + 固定2 cm；
- 附录4 + 实测 \(R(t)\)；
- 附录3 + 固定2 cm。

解释规则：

- 前两者之差主要反映几何收缩；
- 第1与第3之差反映物性经验式改变；
- Q3与Q4正式结果之差是几何和物性共同作用。

### 20.4 模型层级

主模型不含蒸发潜热、吸附等温线、轴向端部效应和非均匀形变。论文可以说明这些机制可能影响结果，但不应在没有参数时任意补值。

若希望讨论潜热，可只给扩展形式：

\[
-kT_r=h_T(T_s-T_a)+L_vj_w,
\]

并说明 \(L_v\)、真实水质量通量 \(j_w\) 及空气—固体平衡映射未给出，所以未进入主计算。

## 21. 图形和论文数据

至少生成以下图：

1. 附件1环境温度与水分势随时间；
2. Q1指定时刻温度径向曲线；
3. Q1指定时刻含水率径向曲线；
4. Q2前三小时中心、半径中点和表面温度曲线；
5. Q2前三小时中心、半径中点和表面含水率曲线；
6. Q3的 \(C_{\max}(t)\) 与0.15阈值；
7. Q3每6 h径向含水率；
8. 附件2半径数据、PCHIP和线性插值；
9. Q4若干时刻材料坐标和物理坐标含水率；
10. Q4的 \(C_{\max}(t)\) 与阈值；
11. Q3/Q4终止时间与敏感性方案比较；
12. 网格收敛误差图。

作图规则：

- 计算使用未舍入数据；
- 横轴单位写明cm、h或s；
- Q4物理坐标曲线的终点必须是当时表面 \(R(t)\)；
- 不把域外空值连成曲线；
- 图例中写明问题、时刻和模型场景；
- 保存PNG 300 dpi和PDF矢量版本；
- 不使用平滑曲线掩盖原始数值。

## 22. 性能与稳定性建议

### 22.1 优先优化位置

1. 内部通量全部NumPy向量化；
2. 网格几何量预计算；
3. 提供jac_sparsity；
4. 避免右端函数中创建DataFrame；
5. 不在右端函数中打印日志；
6. 长时结果分块采样；
7. 敏感性计算使用进程级并行。

### 22.2 不推荐的优化

- 不要用Python循环逐节点装配通量；
- 不要用显式Euler配极小时间步；
- 不要在第一版引入GPU；
- 不要同时开启大量Python线程和BLAS线程；
- 不要为了速度减少验证网格；
- 不要先四舍五入再存储中间状态。

### 22.3 运行时间记录

每次求解保存：

~~~json
{
  "solver": "BDF",
  "n_intervals": 320,
  "rtol": 1e-8,
  "atol_temperature": 1e-8,
  "atol_moisture": 1e-10,
  "nfev": 0,
  "njev": 0,
  "nlu": 0,
  "wall_time_s": 0.0,
  "success": true,
  "message": ""
}
~~~

## 23. 常见故障排查

| 症状 | 高概率原因 | 检查与修复 |
|---|---|---|
| Q2/Q4含水率几乎不变 | 使用了 \(e^{-3850T_K}\) | 打印log_D，核对DEC-01 |
| D出现异常大值 | 温度误用摄氏度或指数符号错 | 检查 \(T_K=T_C+273.15\) 和负号 |
| 表面含水率上升 | Robin符号写反 | 运行TEST-SIGN-02 |
| 表面温度下降 | 热通量符号写反 | 运行TEST-SIGN-01 |
| 中心出现除零 | 直接离散 \(1/r\) | 改用环形有限体积，中心面积置零 |
| 总含水率跳动 | 相邻控制体通量不共享 | 每个内部面只计算一次通量 |
| BDF非常慢 | 未提供稀疏模式或右端含Python循环 | 添加CSR jac_sparsity并向量化 |
| BDF失败并提示步长过小 | D、k非正，状态越界，容差过严或Jacobian模式错 | 先检查物性、NaN和测试，不要直接放宽容差 |
| Q3事件提前 | 使用平均值或表面值 | 改为全域max |
| Q3事件不触发 | D为0、时间上限不足、边界势设置错 | 检查log_D、延长上限并核对环境 |
| Q4与固定域差异离谱 | 漏乘 \(R^{-2}\)、表面多乘或少乘R | 运行TEST-SHRINK-01 |
| Q4均匀场随收缩改变 | 添加了伪几何浓缩项 | 运行TEST-SHRINK-02 |
| Q4在1.5 cm仍有后期数据 | 对域外位置做了外推 | 使用 \(r\le R(t)\) 条件 |
| Excel变成文本 | 写入格式化字符串 | 写float并设置number_format |
| Excel模板格式丢失 | pandas重建了整张表 | 用openpyxl修改模板副本 |
| 结果四位变化明显 | 网格或容差未收敛 | 完成第19节收敛分析 |

## 24. Claw执行指令

### 24.1 工作原则

Claw必须：

- 先读完本指导书和赛题原文件；
- 不修改原始附件；
- 每完成一个模块立即写对应测试；
- 先通过合成测试，再运行正式问题；
- 所有正式计算使用float64；
- 记录所有假设、版本和哈希；
- 遇到题意歧义时优先检查官方模板；
- 若无法核实扩散系数公式，使用DEC-01主方案并在结果中醒目标注；
- 不编造未计算的数值；
- 不因图形看起来合理就跳过守恒和收敛验证。

### 24.2 建议命令行

~~~bash
python -m drying_model.cli inspect-data --config configs/main.yaml
python -m pytest -q

python -m drying_model.cli solve --question 1 --config configs/main.yaml
python -m drying_model.cli solve --question 2-3 --config configs/main.yaml
python -m drying_model.cli solve --question 4 --config configs/main.yaml

python -m drying_model.cli verify --all --config configs/main.yaml
python -m drying_model.cli sensitivity --config configs/sensitivity.yaml
python -m drying_model.cli export --all --config configs/main.yaml
python -m drying_model.cli report --config configs/main.yaml
~~~

命令名称可调整，但必须保留inspect、solve、verify、sensitivity、export五个独立阶段。

### 24.3 推荐开发里程碑

| 阶段 | 内容 | 退出条件 |
|---|---|---|
| M0 | 环境、目录、输入检查 | Python3.12与附件校验通过 |
| M1 | 物性、网格、通量 | 单元测试全部通过 |
| M2 | Q1求解器 | 符号、解析基准、收支通过 |
| M3 | Q2耦合求解器 | 3 h结果稳定且网格误差下降 |
| M4 | Q3事件 | 事件与Brent复核一致 |
| M5 | Q4材料坐标 | 两个收缩极限测试通过 |
| M6 | 敏感性与收敛 | 形成完整误差表 |
| M7 | Excel与论文表 | 模板回读无误 |

任何阶段测试失败时，不进入下一阶段。

## 25. 最终交付物

### 25.1 代码

- 完整src/drying_model包；
- requirements.txt与requirements-lock.txt；
- configs/main.yaml与sensitivity.yaml；
- tests目录；
- README运行说明。

### 25.2 数值结果

- result1.xlsx；
- result2.xlsx；
- result3.xlsx；
- result4.xlsx；
- tables_q1_q4.xlsx或CSV集合；
- q3_event.json；
- q4_event.json。

### 25.3 验证

- validation_report.md；
- convergence_space.csv；
- convergence_time.csv；
- sensitivity_environment.csv；
- sensitivity_radius.csv；
- conservation_residuals.csv；
- pytest运行结果。

### 25.4 图形

- figures目录中的PNG和PDF；
- 图形所用数据CSV；
- 每张图对应的问题、场景和网格说明。

### 25.5 运行清单

run_summary.json至少包含：

~~~json
{
  "model_version": "1.0",
  "python_version": "3.12.x",
  "dependency_versions": {},
  "input_hashes": {},
  "assumptions": {
    "diffusivity_temperature_mode": "arrhenius_inverse_T",
    "ambient_moisture_as_equivalent_potential": true,
    "post_4h_environment": "tail_1h_mean",
    "q4_shrinkage": "homothetic_radial"
  },
  "selected_grid": {},
  "solver_tolerances": {},
  "event_times_unrounded_s": {},
  "validation_status": {},
  "output_files": {}
}
~~~

## 26. 完成定义

只有同时满足以下条件，任务才算完成：

- 四问均使用正确初始状态和对应附录物性；
- Q1至Q4的正式Excel全部生成且回读通过；
- Q3、Q4事件由全域最大含水率决定；
- Q4没有对收缩域外位置外推；
- 严格题面扩散式的异常已经记录；
- 合成解析、符号、守恒和收缩极限测试通过；
- 至少完成160/320/640网格比较；
- 至少完成两档时间容差比较；
- Q3、Q4完成环境延拓敏感性；
- Q4完成PCHIP与线性半径敏感性；
- Q4完成固定半径对照；
- 所有论文数字能追溯到配置、输入哈希和运行文件；
- 未通过验证的数字没有进入最终论文。

## 27. 研究依据

有限体积法通过控制体边界上的共享通量实现局部守恒，适合圆柱坐标和变系数扩散问题。[^4] 非线性湿迁移研究也表明，数值稳定性并不能替代网格和时间误差检验。[^5]

干燥收缩研究指出，尺寸变化会影响温湿传递，收缩模型可分为经验型和机理型；本题直接提供 \(R(t)\)，因此用观测半径驱动材料坐标比构造缺少参数的力学模型更合适。[^6] 轴对称食品干燥已有使用ALE处理径向收缩的研究，为Q4移动边界处理提供了直接参照。[^8]

Python实现方面，SciPy提供BDF、事件、稠密输出、逐分量误差容差和稀疏Jacobian支持。[^2] PCHIP用于保持半径数据形状，Brent法用于已括区事件的稳健复核。[^3][^7]

## Sources

[^1]: Python Software Foundation, “[venv — Creation of virtual environments](https://docs.python.org/3.12/library/venv.html),” Python 3.12 documentation, accessed 2026.

[^2]: SciPy, “[solve_ivp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html),” SciPy reference documentation, accessed 2026.

[^3]: SciPy, “[brentq](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.brentq.html),” SciPy reference documentation, accessed 2026.

[^4]: R. Eymard, T. Gallouët, and R. Herbin, “[Finite Volume Methods](https://hal.science/hal-02100732v2),” Handbook of Numerical Analysis, Vol. VII, 2000.

[^5]: S. Gasparin et al., “[Reliable numerical schemes for a nonlinear heat and moisture transfer problem](https://arxiv.org/abs/1701.07059),” 2017; related DOI: 10.1080/19401493.2017.1298669.

[^6]: L. Mayor and A. M. Sereno, “[Modelling shrinkage during convective drying of food materials: a review](https://doi.org/10.1016/S0260-8774(03)00144-4),” Journal of Food Engineering, 61(3), 373–386, 2004.

[^7]: SciPy, “[PchipInterpolator](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.PchipInterpolator.html),” SciPy reference documentation, accessed 2026.

[^8]: E. Seyedabadi, M. Khojastehpour, and M. H. Abbaspour-Fard, “[Finite element modeling of convective drying of banana with radial shrinkage using the ALE method](https://jift.irost.ir/article_402.html?lang=en),” 2016, DOI: 10.22104/jift.2016.402.

[^9]: openpyxl, “[openpyxl.reader.excel](https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html),” version 3.1.3 documentation.

[^10]: openpyxl, “[Tutorial: loading, editing and saving workbooks](https://openpyxl.readthedocs.io/en/stable/tutorial.html),” version 3.1.3 documentation.

[^11]: pytest, “[How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html),” pytest documentation.

[^12]: NumPy, “[numpy.testing.assert_allclose](https://numpy.org/doc/stable/reference/generated/numpy.testing.assert_allclose.html),” NumPy documentation.

[^13]: 赛题原文、附件说明及附录公式，“A(1).md”，本地上传文件。

