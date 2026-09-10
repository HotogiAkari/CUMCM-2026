---
document_type: model_execution_framework
schema_version: "2.0"
language: zh-CN
problem: A题_药材烘干
runtime: Python_3.12
target_executor: Claw
questions: [Q1, Q2, Q3, Q4]
primary_method: radial_finite_volume_plus_BDF
status: ready_for_implementation
---

# A题药材烘干：四问统一建模与Claw执行规范

## 0. 使用方式

本文件是四道题的最终模型框架。Claw应据此完成Python 3.12代码、数值计算、结果验证和四个Excel文件，不需要重新选择模型。

执行目标：

1. 建立问题1至问题4的径向温湿传递模型；
2. 使用守恒型有限体积法离散空间；
3. 使用BDF隐式方法积分时间；
4. 用全域最大含水率确定问题3、问题4的烘干终点；
5. 按模板生成result1.xlsx至result4.xlsx；
6. 完成守恒、解析基准、网格、容差和敏感性验证。

## 1. 四问关系与统一约定

~~~mermaid
flowchart TD
    I["共同初始场：T=28 ℃，C=2.55"] --> Q1["问题1：附录2，固定半径"]
    I --> Q2["问题2：附录3，固定半径"]
    Q2 --> Q3["问题3：沿用问题2并增加终止事件"]
    I --> Q4["问题4：附录4，收缩半径R(t)"]
~~~

计算关系：

- 问题1从初始场计算至1800 s；
- 问题2从初始场重新计算，不使用问题1末态；
- 问题3沿用问题2从初始时刻开始的同一次长时积分；
- 问题4使用附录4和附件2半径，从初始场独立计算。

统一几何与状态：

\[
R_0=0.02\ {\rm m},\qquad L=0.25\ {\rm m},
\]

\[
T(r,0)=28^\circ{\rm C},\qquad C(r,0)=2.55\ {\rm kg/kg}.
\]

统一表面系数：

\[
h_T=25\ {\rm W/(m^2K)},\qquad
h_C=8\times10^{-7}\ {\rm m/s}.
\]

统一假设：

- 药材为均匀、各向同性圆柱；
- 忽略周向和轴向梯度，只保留径向传递；
- 问题1至问题3半径不变，问题4只考虑径向相似收缩；
- 烘房环境在药材周围均匀；
- 不考虑辐射、化学反应、裂纹、表面硬化和内部宏观液体流动；
- 采用题设能够闭合的有效热容和有效水分扩散模型；
- 空气水分数据作为药材表面的等效平衡水分势 \(C_a(t)\)；
- 温度状态使用摄氏度，扩散系数内部使用绝对温度

\[
T_K=T+273.15.
\]

附录3、附录4的温度指数在本框架中统一采用

\[
\boxed{\exp\left(-\frac{3850}{T_K}\right)}.
\]

Claw必须把这一公式选择写入配置和run_summary.json。

## 2. 环境函数

附件1给出

\[
(t_j,T_{a,j},C_{a,j}),\qquad j=0,\ldots,240,
\]

其中 \(t_j=60j\) s，数据到14400 s。

在任意 \(t_j\le t\le t_{j+1}\) 上使用分段线性插值：

\[
T_a(t)=T_{a,j}
+\frac{t-t_j}{t_{j+1}-t_j}
(T_{a,j+1}-T_{a,j}),
\]

\[
C_a(t)=C_{a,j}
+\frac{t-t_j}{t_{j+1}-t_j}
(C_{a,j+1}-C_{a,j}).
\]

对问题3、问题4，在 \(t>14400\) s 时使用附件1末1 h均值：

\[
\boxed{
T_a(t)=49.998934^\circ{\rm C},\qquad
C_a(t)=0.04998754
}.
\]

环境敏感性验证另外使用：

\[
(T_a,C_a)=(50,0.05)
\]

和

\[
(T_a,C_a)=(50.165,0.04986).
\]

## 3. 问题1：固定物性温湿传递模型

### 3.1 物性

\[
\rho=820\ {\rm kg/m^3},
\]

\[
c_p=2600\ {\rm J/(kgK)},
\]

\[
k=0.36\ {\rm W/(mK)},
\]

\[
D(C)=7\times10^{-9}\exp(-0.89C)\ {\rm m^2/s}.
\]

### 3.2 温度方程

\[
\boxed{
\rho c_p\frac{\partial T}{\partial t}
=\frac1r\frac{\partial}{\partial r}
\left(rk\frac{\partial T}{\partial r}\right)
},\qquad 0<r<R_0.
\]

### 3.3 水分方程

\[
\boxed{
\frac{\partial C}{\partial t}
=\frac1r\frac{\partial}{\partial r}
\left[rD(C)\frac{\partial C}{\partial r}\right]
},\qquad 0<r<R_0.
\]

扩散系数必须用局部节点含水率计算，并保留在散度算子内。

### 3.4 初边值条件

\[
T(r,0)=28,\qquad C(r,0)=2.55.
\]

圆柱中心：

\[
\left.\frac{\partial T}{\partial r}\right|_{r=0}=0,
\qquad
\left.\frac{\partial C}{\partial r}\right|_{r=0}=0.
\]

圆柱表面：

\[
-k\left.\frac{\partial T}{\partial r}\right|_{r=R_0}
=h_T[T(R_0,t)-T_a(t)],
\]

\[
-D(C_s)\left.\frac{\partial C}{\partial r}\right|_{r=R_0}
=h_C[C_s-C_a(t)],
\qquad C_s=C(R_0,t).
\]

### 3.5 输出

论文表1、表2：

- 时间：100、300、600、900、1200、1500、1800 s；
- 位置：0、0.5、1、1.5、2 cm。

result1.xlsx：

- 时间：1至1800 s，步长1 s；
- 位置：0至2 cm，步长0.1 cm；
- 工作表：温度、水分浓度；
- 数值显示四位小数。

## 4. 问题2：固定域变物性热湿耦合模型

### 4.1 物性

\[
\rho(C)=650+128C,
\]

\[
c_p(C)=1450+2736\frac{C}{C+1},
\]

\[
k(C)=0.21+0.38\frac{C}{C+1},
\]

\[
\boxed{
D(C,T_K)=2.4\times10^{-3}
\exp(-0.45C)
\exp\left(-\frac{3850}{T_K}\right)
}.
\]

所有物性均用当前节点的局部状态计算。

### 4.2 温度方程

\[
\boxed{
\rho(C)c_p(C)\frac{\partial T}{\partial t}
=\frac1r\frac{\partial}{\partial r}
\left[rk(C)\frac{\partial T}{\partial r}\right]
}.
\]

### 4.3 水分方程

\[
\boxed{
\frac{\partial C}{\partial t}
=\frac1r\frac{\partial}{\partial r}
\left[
rD(C,T+273.15)\frac{\partial C}{\partial r}
\right]
}.
\]

模型耦合关系：

\[
C\longrightarrow \rho,c_p,k\longrightarrow T,
\]

\[
T,C\longrightarrow D\longrightarrow C.
\]

### 4.4 初边值条件

问题2从初始时刻重新计算：

\[
T(r,0)=28,\qquad C(r,0)=2.55.
\]

中心：

\[
T_r(0,t)=0,\qquad C_r(0,t)=0.
\]

表面：

\[
-k(C_s)T_r(R_0,t)=h_T[T_s-T_a(t)],
\]

\[
-D(C_s,T_s+273.15)C_r(R_0,t)
=h_C[C_s-C_a(t)].
\]

### 4.5 输出

论文表3、表4：

- 时间：0.5、1、1.5、2、2.5、3 h；
- 位置：0、0.5、1、1.5、2 cm。

result2.xlsx：

- 默认时间：1至10800 s，步长1 s；
- 位置：0至2 cm，步长0.1 cm；
- 工作表：温度、水分浓度；
- 若官方模板给出的时间范围不同，以模板为准。

## 5. 问题3：全域含水率终止模型

问题3完整沿用问题2的控制方程、物性、初值和边界。

定义全域最大含水率：

\[
C_{\max}(t)=\max_{0\le r\le R_0}C(r,t).
\]

定义事件函数：

\[
\boxed{
g_3(t)=C_{\max}(t)-0.15
}.
\]

烘干临界时间：

\[
\boxed{
t_{*,3}=\inf\{t\ge0:C_{\max}(t)\le0.15\}
},
\]

\[
\tau_{*,3}=\frac{t_{*,3}}{3600}\ {\rm h}.
\]

数值计算使用

\[
g_{3,h}(t)=\max_iC_i(t)-0.15
\]

并监测其由正到负的第一次穿越。事件判断必须使用未舍入值。

输出：

- 表5：每6 h、位置0、0.5、1、1.5、2 cm，并增加精确终点行；
- result3.xlsx：每60 s、位置0至2 cm、步长0.1 cm；
- 若精确终点不是整分钟，模板允许时增加终点行，否则把精确时间写入独立结果文件和论文。

## 6. 问题4：收缩圆柱移动边界模型

### 6.1 半径函数

附件2提供

\[
(t_m,R_m),\qquad R_m\ {\rm 的单位为cm}.
\]

读入后转换：

\[
R_m^{\rm SI}=0.01R_m.
\]

在数据范围 \(0\le t\le259200\) s 内，使用PCHIP构造正值、单调不增的 \(R(t)\)。超过数据末端时使用

\[
R(t)=0.01198\ {\rm m}.
\]

### 6.2 材料坐标

假设药材做均匀径向相似收缩：

\[
r=\xi R(t),\qquad 0\le\xi\le1.
\]

定义

\[
\theta(\xi,t)=T(\xi R(t),t),
\]

\[
c(\xi,t)=C(\xi R(t),t).
\]

### 6.3 附录4物性

\[
\rho(c)=760+90c,
\]

\[
c_p(c)=1850+2150\frac{c}{c+1},
\]

\[
k(c)=0.12+0.20\frac{c}{c+1},
\]

\[
\boxed{
D(c,\theta_K)=4.2\times10^{-4}
\exp(-0.30c)
\exp\left(-\frac{3850}{\theta_K}\right)
},
\qquad \theta_K=\theta+273.15.
\]

### 6.4 固定材料域方程

\[
\boxed{
\rho(c)c_p(c)\frac{\partial\theta}{\partial t}
=\frac1{R(t)^2\xi}
\frac{\partial}{\partial\xi}
\left[
\xi k(c)\frac{\partial\theta}{\partial\xi}
\right]
}.
\]

\[
\boxed{
\frac{\partial c}{\partial t}
=\frac1{R(t)^2\xi}
\frac{\partial}{\partial\xi}
\left[
\xi D(c,\theta+273.15)
\frac{\partial c}{\partial\xi}
\right]
}.
\]

该形式使用固定区间 \([0,1]\)，程序不需要计算 \(\dot R(t)\)。

### 6.5 初边值条件

\[
\theta(\xi,0)=28,\qquad c(\xi,0)=2.55.
\]

中心：

\[
\theta_\xi(0,t)=0,\qquad c_\xi(0,t)=0.
\]

表面：

\[
-\frac{k(c_s)}{R(t)}\theta_\xi(1,t)
=h_T[\theta_s-T_a(t)],
\]

\[
-\frac{D(c_s,\theta_s+273.15)}{R(t)}
c_\xi(1,t)
=h_C[c_s-C_a(t)].
\]

### 6.6 终止事件

\[
\boxed{
g_4(t)=\max_{0\le\xi\le1}c(\xi,t)-0.15
}.
\]

\[
t_{*,4}=\inf\{t\ge0:\max_\xi c(\xi,t)\le0.15\}.
\]

### 6.7 输出坐标

对于固定物理位置 \(r_k\)：

\[
\xi_k(t)=\frac{r_k}{R(t)}.
\]

- 当 \(r_k\le R(t)\) 时，输出 \(c(\xi_k,t)\)；
- 当 \(r_k>R(t)\) 时，该位置已在药材外部，Excel留空；
- 药材表面列始终输出 \(c(1,t)\)；
- 不允许对 \(\xi>1\) 外推。

表6每6 h输出一次，并增加精确终点行。result4.xlsx每60 s输出一次，物理距离步长0.1 cm。

### 6.8 收缩效应对照

另外计算

\[
\text{附录4物性}+R(t)\equiv0.02\ {\rm m}
\]

作为固定半径对照。

纯几何收缩造成的时间变化定义为

\[
\Delta t_{\rm shrink}
=t_{*,4}^{\rm shrinking}
-t_{*,4}^{\rm fixed}.
\]

## 7. 统一有限体积离散

### 7.1 固定物理域网格

取

\[
r_i=i\Delta r,\qquad
i=0,\ldots,N,\qquad
\Delta r=\frac{R_0}{N}.
\]

节点控制体界面：

\[
r_{i-\frac12}=\max\left(0,r_i-\frac{\Delta r}{2}\right),
\]

\[
r_{i+\frac12}=\min\left(R_0,r_i+\frac{\Delta r}{2}\right).
\]

按单位轴向长度定义：

\[
V_i=\pi\left(r_{i+\frac12}^2-r_{i-\frac12}^2\right),
\]

\[
A_{i\pm\frac12}=2\pi r_{i\pm\frac12}.
\]

中心界面满足

\[
A_{-\frac12}=0,
\]

因此不需要直接计算 \(1/r\)，也不需要虚拟节点。

### 7.2 界面物性

对导热系数和扩散系数使用调和平均：

\[
k_{i+\frac12}
=\frac{2k_ik_{i+1}}{k_i+k_{i+1}},
\]

\[
D_{i+\frac12}
=\frac{2D_iD_{i+1}}{D_i+D_{i+1}}.
\]

内部界面通量：

\[
q^T_{i+\frac12}
=-k_{i+\frac12}
\frac{T_{i+1}-T_i}{\Delta r},
\]

\[
q^C_{i+\frac12}
=-D_{i+\frac12}
\frac{C_{i+1}-C_i}{\Delta r}.
\]

### 7.3 固定域半离散方程

\[
\rho_ic_{p,i}V_i\frac{dT_i}{dt}
=A_{i-\frac12}q^T_{i-\frac12}
-A_{i+\frac12}q^T_{i+\frac12},
\]

\[
V_i\frac{dC_i}{dt}
=A_{i-\frac12}q^C_{i-\frac12}
-A_{i+\frac12}q^C_{i+\frac12}.
\]

表面通量：

\[
q^T_{N+\frac12}=h_T(T_N-T_a),
\]

\[
q^C_{N+\frac12}=h_C(C_N-C_a).
\]

### 7.4 Q4材料域网格

取

\[
\xi_i=i\Delta\xi,\qquad
\Delta\xi=\frac1N.
\]

定义

\[
\widehat V_i
=\pi\left(
\xi_{i+\frac12}^2-\xi_{i-\frac12}^2
\right),
\]

\[
\widehat A_{i\pm\frac12}
=2\pi\xi_{i\pm\frac12}.
\]

材料坐标内部通量：

\[
\widehat q^T_{i+\frac12}
=-k_{i+\frac12}
\frac{\theta_{i+1}-\theta_i}{\Delta\xi},
\]

\[
\widehat q^C_{i+\frac12}
=-D_{i+\frac12}
\frac{c_{i+1}-c_i}{\Delta\xi}.
\]

Q4半离散方程：

\[
\rho_ic_{p,i}\widehat V_i\frac{d\theta_i}{dt}
=\frac1{R(t)^2}
\left(
\widehat A_{i-\frac12}\widehat q^T_{i-\frac12}
-\widehat A_{i+\frac12}\widehat q^T_{i+\frac12}
\right),
\]

\[
\widehat V_i\frac{dc_i}{dt}
=\frac1{R(t)^2}
\left(
\widehat A_{i-\frac12}\widehat q^C_{i-\frac12}
-\widehat A_{i+\frac12}\widehat q^C_{i+\frac12}
\right).
\]

材料坐标表面通量：

\[
\widehat q^T_{N+\frac12}
=R(t)h_T(\theta_N-T_a),
\]

\[
\widehat q^C_{N+\frac12}
=R(t)h_C(c_N-C_a).
\]

## 8. 时间积分

固定域状态向量：

\[
\boldsymbol y=
(T_0,\ldots,T_N,C_0,\ldots,C_N)^{\mathsf T}.
\]

Q4使用相同布局，只把 \(T,C\) 换成 \(\theta,c\)。

空间离散后：

\[
\frac{d\boldsymbol y}{dt}
=\boldsymbol F(t,\boldsymbol y).
\]

统一使用SciPy solve_ivp的BDF方法：

~~~python
atol = np.concatenate((
    np.full(n_nodes, atol_temperature),
    np.full(n_nodes, atol_moisture),
))

solution = solve_ivp(
    fun=rhs,
    t_span=(t_start, t_end),
    y0=y0,
    method="BDF",
    rtol=1.0e-8,
    atol=atol,
    jac_sparsity=jac_sparsity,
    dense_output=True,
    events=drying_event,
    max_step=max_step,
)
~~~

建议：

- 温度绝对容差：\(10^{-8}\)；
- 水分绝对容差：\(10^{-10}\)；
- 0至4 h期间max_step取30至60 s；
- 4 h后max_step取300至600 s；
- 输出时刻与内部积分步长分离。

问题2至问题4的Jacobian包含四个局部耦合块：

\[
J=
\begin{pmatrix}
J_{TT}&J_{TC}\\
J_{CT}&J_{CC}
\end{pmatrix}.
\]

每一节点的方程只依赖本节点及相邻节点的温度和含水率。Claw应构造对应的CSR布尔稀疏结构并传给jac_sparsity。

事件函数：

~~~python
def drying_event(t, y):
    moisture = y[n_nodes:]
    return float(np.max(moisture) - 0.15)

drying_event.terminal = True
drying_event.direction = -1.0
~~~

事件触发后，保存事件前的正值时刻 \(t_a\) 和事件时刻 \(t_b\)，使用稠密输出和brentq复核根：

\[
g(t_a)>0,\qquad g(t_b)\le0.
\]

## 9. Python 3.12项目结构

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
│     └─ cli.py
├─ tests/
├─ configs/
│  ├─ main.yaml
│  └─ sensitivity.yaml
├─ outputs/
│  ├─ official/
│  ├─ diagnostics/
│  ├─ figures/
│  └─ tables/
├─ requirements.txt
└─ README.md
~~~

建议依赖：

~~~text
numpy>=1.26,<3
scipy>=1.11,<2
pandas>=2.1,<4
openpyxl>=3.1,<4
matplotlib>=3.8,<4
pyyaml>=6,<7
pytest>=8,<10
~~~

程序内部统一使用numpy.float64。正式计算优先使用CPU，无需引入CuPy。

## 10. 模块职责

| 模块 | 职责 |
|---|---|
| config.py | 读取YAML，集中保存参数和求解器设置 |
| data_io.py | 读取附件1、附件2和模板，校验单位与表结构 |
| environment.py | 构造 \(T_a(t),C_a(t)\) |
| properties.py | 实现附录2、3、4物性 |
| radius.py | 构造Q4的PCHIP和线性半径函数 |
| grid.py | 构造固定域及材料域环形控制体 |
| rhs_fixed.py | Q1至Q3固定域右端 |
| rhs_shrink.py | Q4材料坐标右端 |
| events.py | 全域最大含水率事件 |
| solve.py | BDF积分、分阶段计算、检查点 |
| sampling.py | 时间和空间插值 |
| export_excel.py | 复制模板并写入结果 |
| diagnostics.py | 守恒、范围、收敛和敏感性 |
| cli.py | inspect、solve、verify、export入口 |

配置文件至少包含：

~~~yaml
runtime:
  python: "3.12"
  dtype: float64

model:
  initial_radius_m: 0.02
  initial_temperature_C: 28.0
  initial_moisture: 2.55
  diffusivity_temperature_term: inverse_absolute_temperature

boundary:
  heat_transfer: 25.0
  mass_transfer: 8.0e-7

solver:
  method: BDF
  grid_intervals: 320
  rtol: 1.0e-8
  atol_temperature: 1.0e-8
  atol_moisture: 1.0e-10

environment:
  measured_interpolation: linear
  post_4h: tail_1h_mean

radius_q4:
  interpolation: pchip
  post_72h: last_value_hold
~~~

## 11. 数据读取规范

附件1读取后检查：

- 三列分别为时间、温度、水分浓度；
- 时间严格递增；
- 首时刻0 s，末时刻14400 s；
- 共241条记录；
- 无NaN和Inf。

附件2读取后检查：

- 两列分别为时间、半径；
- 时间严格递增；
- 半径单位由cm转换成m；
- 首半径2 cm，末半径1.198 cm；
- 半径为正且单调不增。

模板读取后记录：

- 文件名和工作表名；
- 最大行数和最大列数；
- 第一行距离；
- A列时间范围；
- 合并单元格和数值格式。

原始附件保持只读。先把模板复制到outputs/official，再用openpyxl写入副本。

## 12. Excel写入规范

- A列为时间，单位s；
- 第一行为距离，单位cm；
- 数值以Python float写入；
- 单元格number_format设为0.0000；
- 不把数值预先转换成字符串；
- 保留原工作表名、列宽、合并单元格和模板格式；
- Q4域外位置写None；
- 写完后重新打开文件进行回读校验。

空间采样：

- 固定域：在物理半径网格上插值；
- Q4：先计算 \(\xi=r/R(t)\)，再在材料网格上插值；
- 所有插值只允许在计算域内进行。

## 13. 模型与程序验证

### 13.1 网格几何验证

固定域必须满足：

\[
\sum_iV_i=\pi R_0^2,
\]

\[
A_{-\frac12}=0,\qquad
A_{N+\frac12}=2\pi R_0.
\]

材料域必须满足：

\[
\sum_i\widehat V_i=\pi,
\]

\[
\widehat A_{-\frac12}=0,\qquad
\widehat A_{N+\frac12}=2\pi.
\]

### 13.2 均匀平衡场验证

构造

\[
T(r,0)=T_a,\qquad C(r,0)=C_a.
\]

此时内部梯度和表面通量均为零，数值右端应接近零。

Q4在相同平衡条件下，即使 \(R(t)\) 变化，\(\theta\) 和 \(c\) 仍应保持常数。

### 13.3 Robin边界方向验证

纯加热测试：

\[
T_a>T_0,\qquad C_a=C_0.
\]

应得到表面温度导数为正，水分场不变。

纯干燥测试：

\[
C_a<C_0,\qquad T_a=T_0.
\]

应得到表面含水率导数为负，总含水率指标下降。

### 13.4 常系数圆柱解析验证

建立固定半径、常扩散系数、零Dirichlet表面的合成问题：

\[
u_t=D\left(u_{rr}+\frac1ru_r\right),
\]

\[
u(r,0)=u_0,\qquad
u_r(0,t)=0,\qquad
u(R,t)=0.
\]

解析级数：

\[
\frac{u(r,t)}{u_0}
=2\sum_{m=1}^{\infty}
\frac{J_0(\lambda_mr/R)}
{\lambda_mJ_1(\lambda_m)}
\exp\left(-\lambda_m^2\frac{Dt}{R^2}\right),
\]

其中 \(\lambda_m\) 为 \(J_0\) 的正零点。

使用scipy.special.jn_zeros、j0和j1计算截断级数，并与有限体积结果比较。该测试用于验证圆柱几何、中心处理、内部通量和空间收敛。

### 13.5 小Biot数验证

人为减小表面交换系数，使 \(Bi<0.01\)。固定圆柱的平均温度应接近

\[
T(t)-T_a
=[T(0)-T_a]
\exp\left(-\frac{2h_T}{\rho c_pR_0}t\right).
\]

常系数水分模型应接近

\[
\bar C(t)-C_a
=[C(0)-C_a]
\exp\left(-\frac{2h_C}{R_0}t\right).
\]

### 13.6 Q4固定半径极限

令

\[
R(t)\equiv R_0,
\]

并让固定域程序与材料域程序使用同一套物性。将 \(\xi\) 映射到 \(r=R_0\xi\) 后，两种程序必须得到相同结果。

### 13.7 水分收支

固定域定义

\[
M_C(t)=\sum_iV_iC_i(t).
\]

应满足

\[
\frac{dM_C}{dt}
=-A_Rh_C(C_s-C_a).
\]

相对残差：

\[
\varepsilon_C(t)=
\frac{
\left|
M_C(t)-M_C(0)
+\int_0^tA_Rh_C(C_s-C_a)\,d\tau
\right|
}{M_C(0)}.
\]

Q4材料域定义

\[
\widehat M_C(t)=\sum_i\widehat V_ic_i(t),
\]

应满足

\[
\frac{d\widehat M_C}{dt}
=-\frac{2\pi h_C}{R(t)}[c_s-C_a].
\]

边界通量积分建议作为额外ODE状态同步积分，避免只用稀疏输出做低精度积分。

### 13.8 物理范围

每次求解检查：

\[
C_i\ge0,\qquad T_i+273.15>0,
\]

\[
\rho_i>0,\qquad c_{p,i}>0,\qquad
k_i>0,\qquad D_i>0.
\]

同时检查：

- 求解器success为真；
- 不存在NaN或Inf；
- 净干燥阶段总含水率不增；
- 半径始终为正且不增；
- 事件触发前 \(g>0\)，触发时 \(g\approx0\)；
- 每个时刻记录最大含水率所在节点；
- 温度处于初值和历史环境温度形成的合理包络内。

### 13.9 空间网格收敛

运行

\[
N=160,\qquad320,\qquad640.
\]

在共同时间和共同输出位置比较：

\[
E_T^{(N)}=\max|T_N-T_{2N}|,
\]

\[
E_C^{(N)}=\max|C_N-C_{2N}|,
\]

\[
E_t^{(N)}
=|t_{*,N}-t_{*,2N}|.
\]

问题3、问题4必须单独比较终止时间。

### 13.10 时间容差收敛

固定细网格，至少比较：

\[
\mathrm{rtol}=10^{-7},10^{-8},10^{-9}
\]

中的两档，并使用对应的分量绝对容差。

### 13.11 敏感性验证

问题3、问题4比较三种4 h后环境。

问题4比较：

- PCHIP半径；
- 线性半径；
- 附录4固定半径；
- 附录4收缩半径。

输出各方案的终止时间和相对变化。

## 14. 实现约束

Claw编程时遵守以下约束：

1. 所有物性均在每次右端计算中按当前局部状态更新；
2. \(k\) 和 \(D\) 始终保留在通量形式中；
3. 计算网格与输出网格分离；
4. 事件判断使用未舍入数值；
5. 四位小数只在Excel显示阶段处理；
6. Q2、Q4从初始场独立计算；
7. Q4只使用材料坐标方程，不重复加入收缩速度项；
8. Q4物理输出位置超过当前半径时留空；
9. 原始附件只读，不直接覆盖；
10. Excel写入使用模板副本；
11. 数值写为float，不写为格式化字符串；
12. 所有正式计算使用float64；
13. 求解器内部步长由误差控制，不等于输出间隔；
14. 先完成单元测试和合成验证，再生成正式结果；
15. 每次运行保存配置、输入哈希、软件版本和验证状态。

## 15. Claw执行流程

### 15.1 阶段一：数据与环境

1. 建立Python 3.12虚拟环境；
2. 安装requirements.txt；
3. 读取附件1、附件2及四个模板；
4. 校验单位、时间、半径和工作表；
5. 生成输入文件SHA-256；
6. 构造环境函数和半径函数。

### 15.2 阶段二：公共数值模块

1. 实现三套物性；
2. 实现固定域和材料域网格；
3. 实现调和平均；
4. 实现内部及表面通量；
5. 实现Jacobian稀疏结构；
6. 完成网格、物性和符号测试。

### 15.3 阶段三：问题1

1. 从统一初始场积分至1800 s；
2. 完成解析、符号和收支验证；
3. 完成160、320、640网格计算；
4. 生成表1、表2和result1.xlsx。

### 15.4 阶段四：问题2与问题3

1. 从统一初始场使用附录3积分；
2. 提取前三小时结果；
3. 继续积分至全域含水率事件；
4. 使用Brent法复核终点；
5. 完成网格、容差和环境敏感性；
6. 生成表3至表5、result2.xlsx和result3.xlsx。

### 15.5 阶段五：问题4

1. 从统一初始场使用附录4积分；
2. 使用材料坐标和附件2半径；
3. 定位全域含水率事件；
4. 运行固定半径极限和固定半径对照；
5. 运行半径插值敏感性；
6. 按动态物理域生成表6和result4.xlsx。

### 15.6 阶段六：结果汇总

1. 回读四个Excel；
2. 生成收敛表和敏感性表；
3. 生成中心、表面和径向分布图；
4. 生成run_summary.json；
5. 生成validation_report.md；
6. 将通过验证的数字提供给论文。

建议命令行：

~~~bash
python -m drying_model.cli inspect --config configs/main.yaml
python -m pytest -q
python -m drying_model.cli solve --question 1 --config configs/main.yaml
python -m drying_model.cli solve --question 2-3 --config configs/main.yaml
python -m drying_model.cli solve --question 4 --config configs/main.yaml
python -m drying_model.cli verify --all --config configs/main.yaml
python -m drying_model.cli export --all --config configs/main.yaml
~~~

## 16. 最终交付物

代码：

- src/drying_model完整包；
- tests测试目录；
- configs/main.yaml；
- configs/sensitivity.yaml；
- requirements.txt；
- requirements-lock.txt；
- README.md。

正式结果：

- result1.xlsx；
- result2.xlsx；
- result3.xlsx；
- result4.xlsx；
- q3_event.json；
- q4_event.json。

验证结果：

- validation_report.md；
- convergence_space.csv；
- convergence_time.csv；
- sensitivity_environment.csv；
- sensitivity_radius.csv；
- conservation_residuals.csv。

运行记录：

~~~json
{
  "python_version": "3.12.x",
  "dependency_versions": {},
  "input_hashes": {},
  "diffusivity_temperature_term": "inverse_absolute_temperature",
  "selected_grid": {},
  "solver_tolerances": {},
  "event_times_unrounded_s": {},
  "validation_status": {},
  "output_files": {}
}
~~~

## 17. 完成标准

当且仅当以下条件全部满足时，Claw可以报告任务完成：

- 四问全部使用本文件规定的模型；
- Q2、Q4从初始场计算；
- Q3、Q4由全域最大含水率事件确定终点；
- Q4没有对药材外部位置外推；
- 常系数解析验证通过；
- Robin符号验证通过；
- Q4固定半径极限验证通过；
- 水分收支残差满足设定阈值；
- 160、320、640网格误差稳定下降；
- 时间容差结果稳定；
- 环境和半径敏感性结果已保存；
- 四个Excel回读校验通过；
- 所有论文数字可追溯到具体配置和运行记录。

## 参考资料

1. R. Eymard, T. Gallouët, and R. Herbin, [Finite Volume Methods](https://hal.science/hal-02100732v2), Handbook of Numerical Analysis, Vol. VII, 2000.
2. S. Gasparin et al., [Reliable numerical schemes for a nonlinear heat and moisture transfer problem](https://arxiv.org/abs/1701.07059), 2017.
3. L. Mayor and A. M. Sereno, [Modelling shrinkage during convective drying of food materials](https://doi.org/10.1016/S0260-8774(03)00144-4), Journal of Food Engineering, 2004.
4. E. Seyedabadi et al., [Finite element modeling of convective drying of banana with radial shrinkage using the ALE method](https://jift.irost.ir/article_402.html?lang=en), 2016.
5. SciPy, [solve_ivp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html).
6. SciPy, [brentq](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.brentq.html).
7. SciPy, [PchipInterpolator](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.PchipInterpolator.html).

