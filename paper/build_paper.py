#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the CUMCM-2026 A paper (docx) with the prescribed typography.

Typography contract
-------------------
body            : 华文宋体 / Times New Roman, 13pt, line 20pt exact, space after 0.5 line
title           : 华文中宋 / Times New Roman, 19pt, bold
abstract head   : 华文中宋 / Times New Roman, 17pt, bold
heading 1/2/3   : 华文中宋 / Times New Roman, 17pt / 15pt / 13pt, bold
formula         : 华文宋体 / Latin Modern Math, 13pt, number right-aligned via tab
"""
from __future__ import annotations

import csv
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "inputs" / "templates" / "result1.xlsx"  # placeholder, not used
SRC_DOCX = Path("/root/.openclaw/media/inbound/论文---f93896cb-bfca-4ef0-81d3-67f68143f23b.docx")
OUT = ROOT / "论文_药材烘干问题.docx"
TABLES = ROOT / "outputs" / "tables"
DIAG = ROOT / "outputs" / "diagnostics"

CN_BODY = "华文宋体"
CN_HEAD = "华文中宋"
EN = "Times New Roman"
MATH = "Latin Modern Math"
LINE = "400"          # 20 pt fixed = 400 twips
AFTER_LINES = "50"    # 0.5 line
CONTENT_W_PT = (11906 - 2 * 1418) / 20.0   # usable width in points (A4, 2.5 cm margins)


# ---------------------------------------------------------------- low level ---
def _pPr(p):
    return p._element.get_or_add_pPr()


def para_spacing(p, before_lines=0, after_lines=AFTER_LINES, before_pt=0, after_pt=0):
    pPr = _pPr(p)
    sp = pPr.find(qn("w:spacing"))
    if sp is None:
        sp = OxmlElement("w:spacing")
        pPr.append(sp)
    sp.set(qn("w:line"), LINE)
    sp.set(qn("w:lineRule"), "exact")
    sp.set(qn("w:beforeLines"), str(before_lines))
    sp.set(qn("w:afterLines"), str(after_lines))
    sp.set(qn("w:before"), str(before_pt))
    sp.set(qn("w:after"), str(after_pt))


def first_line_indent(p, chars=200):
    pPr = _pPr(p)
    ind = pPr.find(qn("w:ind"))
    if ind is None:
        ind = OxmlElement("w:ind")
        pPr.append(ind)
    ind.set(qn("w:firstLineChars"), str(chars))
    ind.set(qn("w:firstLine"), str(int(chars * 0.13)))  # fallback twips


def style_run(run, size, cn=CN_BODY, en=EN, bold=False, italic=False):
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    rPr = run._element.get_or_add_rPr()
    rf = rPr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rPr.insert(0, rf)
    rf.set(qn("w:ascii"), en)
    rf.set(qn("w:hAnsi"), en)
    rf.set(qn("w:eastAsia"), cn)
    rf.set(qn("w:cs"), en)
    return run


def add_par(doc, text="", size=13, cn=CN_BODY, en=EN, bold=False, align="both",
            indent=True, before_lines=0):
    p = doc.add_paragraph()
    para_spacing(p, before_lines=before_lines)
    amap = {"both": WD_ALIGN_PARAGRAPH.JUSTIFY, "left": WD_ALIGN_PARAGRAPH.LEFT,
            "center": WD_ALIGN_PARAGRAPH.CENTER, "right": WD_ALIGN_PARAGRAPH.RIGHT}
    p.alignment = amap[align]
    if indent and align in ("both", "left"):
        first_line_indent(p)
    if text:
        style_run(p.add_run(text), size, cn=cn, en=en, bold=bold)
    return p


def add_heading(doc, text, level):
    size = {1: 17, 2: 15, 3: 13}[level]
    return add_par(doc, text, size=size, cn=CN_HEAD, bold=True, align="left", indent=False)


def add_formula(doc, expr, number):
    """Centred formula with a right-aligned number reached by a tab stop."""
    p = doc.add_paragraph()
    para_spacing(p)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.tab_stops.add_tab_stop(Pt(CONTENT_W_PT / 2), WD_TAB_ALIGNMENT.CENTER)
    p.paragraph_format.tab_stops.add_tab_stop(Pt(CONTENT_W_PT), WD_TAB_ALIGNMENT.RIGHT)
    style_run(p.add_run("\t"), 13, cn=CN_BODY, en=MATH)
    style_run(p.add_run(expr), 13, cn=CN_BODY, en=MATH)
    style_run(p.add_run("\t" + number), 13, cn=CN_BODY, en=EN)
    return p


def add_caption(doc, text):
    return add_par(doc, text, size=10.5, cn=CN_HEAD, bold=True, align="center", indent=False)


def add_figure(doc, name, caption, width_cm=15.0):
    """插入 figures/ 下的插图并居中，下面附图题。"""
    path = ROOT / "figures" / name
    p = doc.add_paragraph()
    para_spacing(p)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Cm(width_cm))
    add_caption(doc, caption)


def _set_borders(tbl):
    tblPr = tbl._element.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement("w:" + edge)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tblPr.append(borders)


def add_table(doc, header, rows, size=10.5):
    tbl = doc.add_table(rows=1, cols=len(header))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_borders(tbl)
    for j, h in enumerate(header):
        cell = tbl.rows[0].cells[j]
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para_spacing(p)
        style_run(p.add_run(str(h)), size, cn=CN_HEAD, bold=True)
    for r in rows:
        cells = tbl.add_row().cells
        for j, v in enumerate(r):
            p = cells[j].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            para_spacing(p)
            style_run(p.add_run("" if v is None else str(v)), size)
    return tbl


def read_csv_rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


def fmt(v, nd=4):
    try:
        return "%.*f" % (nd, float(v))
    except (TypeError, ValueError):
        return v


# ------------------------------------------------------------------- content ---
def build():
    doc = Document(str(SRC_DOCX))
    body = doc.element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)

    p = add_par(doc, "基于守恒型有限体积与BDF的圆柱形药材热风烘干模型",
                size=19, cn=CN_HEAD, bold=True, align="center", indent=False)

    add_par(doc, "摘  要", size=17, cn=CN_HEAD, bold=True, align="center", indent=False)

    abstract = [
        "中药材热风烘干是决定成品品质与能耗的关键工序。本文针对圆柱形药材在预热平衡与恒温干燥"
        "两个阶段的温度场与含水率场演化问题，建立了径向一维轴对称的热质耦合传递模型，采用守恒型"
        "有限体积法离散空间、隐式BDF方法积分时间，对四个问题实现统一求解，并以全局含水率事件确定"
        "烘干终点。",
        "针对问题一，在预热平衡阶段采用附录2给出的常物性参数与水分扩散系数，建立圆柱径向热传导—"
        "扩散模型，用环形控制体有限体积法离散、BDF隐式积分。计算得到30 min内药材各处的温度与水分"
        "浓度（表1、表2）：1800 s时中心温度为33.5753 ℃、表面温度为36.7856 ℃，中心水分浓度仍为2.5500 "
        "kg/kg，表面已降至1.2008 kg/kg，完整结果见result1.xlsx。",
        "针对问题二，采用附录3的变物性经验公式，令密度、比热容、导热系数随含水率变化，扩散系数同时"
        "依赖含水率与温度，建立固定域变物性热湿耦合模型。计算表明3 h内温度迅速趋近烘房温度（3 h时"
        "表面为49.9572 ℃），而含水率由表面向中心依次下降，中心仍保持在2.1615 kg/kg（表3、表4），"
        "完整结果见result2.xlsx。",
        "针对问题三，以全域最大含水率首次降至0.15 kg/kg作为烘干终止判据，构造事件函数并配合二分法"
        "复核。求得理论临界烘干时间为 t*=59286.1751 s=16.4684 h，此时中心含水率恰为0.1500 kg/kg，"
        "该时刻之后全域含水率严格低于0.15 kg/kg（表5，result3.xlsx）。",
        "针对问题四，引入附件2给出的收缩半径R(t)，在材料坐标ξ=r/R(t)下建立移动边界模型，使几何收缩"
        "转化为固定区间上的变系数问题。求得 t*=70759.9787 s=19.6555 h（表6，result4.xlsx）。与附录4"
        "物性下的固定半径对照（39.2119 h）相比，几何收缩使干燥时间缩短约19.56 h。",
        "模型检验表明：有限体积格式与圆柱Dirichlet解析解的最大偏差为7.4×10⁻⁶；问题四在R(t)≡R₀极限"
        "下与固定域结果一致到5.6×10⁻¹⁶；空间收敛阶约为1.89~1.98；水分收支相对残差不超过5.5×10⁻⁶；"
        "临界时间对网格与时间容差稳定（变化小于0.004 s）。",
        "需要说明的是，题面所述“烘干一般持续2~3天”属于实际工艺背景。本文采用的有效扩散模型未包含"
        "蒸发潜热（温度方程无相变汇项）与吸附/解吸平衡（以空气含湿量近似表面平衡含水率），因此其预测"
        "的理论临界时间短于实际工艺时长，这属于模型简化的系统性偏差而非数值误差。",
    ]
    for t in abstract:
        add_par(doc, t)
    add_par(doc, "关键词：热风烘干；热质耦合传递；守恒型有限体积；BDF；移动边界；全域含水率事件")

    # ------------------------------------------------------------ 一、问题重述
    add_heading(doc, "一、问题重述", 1)
    add_heading(doc, "1.1 问题背景", 2)
    add_par(doc, "干燥是决定中药材成品品质的关键工序之一，热风烘干因设备简单、易于控制而被广泛采用。"
                 "该方式主要包括预热平衡与恒温干燥两个阶段，通过调控烘房温湿环境完成药材的干燥。"
                 "工艺参数选取不当容易导致干燥效率低、能耗高、成品品质不稳定等问题。")
    add_par(doc, "本文研究的圆柱形药材长为25 cm、初始半径为2 cm，开始烘干时温度为28 ℃、干基含水率为"
                 "2.55 kg/kg。仅考虑药材内部的径向变化，记r为到药材中心的距离、t为时间、T(r,t)为药材"
                 "温度、C(r,t)为干基含水率。")

    add_heading(doc, "1.2 需要解决的问题", 2)
    add_par(doc, "（1）问题一：建立预热平衡阶段药材温度与水分浓度变化规律的数学模型，给出100、300、600、"
                 "900、1200、1500、1800 s时刻在距中心0、0.5、1、1.5、2 cm处的温度与水分浓度，并保存"
                 "1800 s内每秒、每隔0.1 cm的完整结果。")
    add_par(doc, "（2）问题二：建立整个烘干过程（预热平衡与恒温干燥阶段参数不同）药材温度与水分浓度变化"
                 "规律的数学模型，给出3 h内每0.5 h、距中心0、0.5、1、1.5、2 cm处的结果，并保存每秒、"
                 "每隔0.1 cm的完整结果。")
    add_par(doc, "（3）问题三：确定使药材各处水分浓度均低于0.15 kg/kg所需的最短时间，并给出每隔6 h、"
                 "距中心每隔0.5 cm的水分浓度与每秒、每隔0.1 cm的完整结果。")
    add_par(doc, "（4）问题四：考虑药材因水分流失发生的尺寸变化，根据附件2确定药材的烘干时长，并给出"
                 "每隔6 h、距中心每隔0.5 cm的水分浓度与每秒、每隔0.1 cm的完整结果。")

    # ------------------------------------------------------------ 二、问题分析
    add_heading(doc, "二、问题分析", 1)
    add_heading(doc, "2.1 总体分析", 2)
    add_par(doc, "四个问题共享同一物理过程：热量由烘房空气经对流换热传入药材内部，水分由内部向表面迁移"
                 "并经对流蒸发进入空气。由于药材长度远大于半径且环境沿周向、轴向均匀，可仅保留径向传递，"
                 "将其简化为轴对称的一维问题。")
    add_par(doc, "问题的核心在于：(i) 温度与含水率通过物性和扩散系数双向耦合；(ii) 表面为Robin型"
                 "换热与传质边界；(iii) 问题三、四需要以全域含水率阈值自动判定终止时刻；(iv) 问题四"
                 "的域边界随时间收缩，必须采用移动边界处理。因此本文采用统一的守恒型有限体积法离散空间，"
                 "用隐式BDF方法积分时间，并用事件机制确定终止时刻。")

    add_heading(doc, "2.2 问题一分析", 2)
    add_par(doc, "预热平衡阶段（0~1800 s）药材尚未明显脱水，附录2给出常物性与仅依赖含水率的水分扩散"
                 "系数，故可视为常系数圆柱径向热传导—扩散问题。烘房温度由28 ℃缓慢升至41.5 ℃，"
                 "被处理为随时间变化的环境函数。药材热扩散率约为1.69×10⁻⁷ m²/s，热平衡时间常数约15 min，"
                 "因此30 min内温度场基本跟随环境变化而含水率仅表层明显下降。")

    add_heading(doc, "2.3 问题二、问题三分析", 2)
    add_par(doc, "恒温干燥阶段必须使用附录3的变物性经验公式：密度、比热容、导热系数均为含水率的函数，"
                 "扩散系数同时随含水率与绝对温度变化。此时温度场与含水率场强耦合，方程组刚性较强，"
                 "适合隐式方法求解。问题三在问题二的基础上延长积分时间，以全域最大含水率首次降至"
                 "0.15 kg/kg的时刻作为烘干终点。由于表面始终比内部干燥得快，最大含水率位于中心，"
                 "该判据等价于中心含水率达标。")

    add_heading(doc, "2.4 问题四分析", 2)
    add_par(doc, "药材收缩使半径由2 cm减小到约1.198 cm，域边界随时间移动。本文引入材料坐标"
                 "ξ=r/R(t)∈[0,1]，把移动域问题转化为固定区间上的变系数偏微分方程，避免显式处理网格"
                 "移动速度。输出时按ξ_k(t)=r_k/R(t)把材料坐标结果映射回固定物理位置，位于药材之外的"
                 "物理点留空。")

    # ------------------------------------------------------------ 三、模型假设
    add_heading(doc, "三、模型假设", 1)
    for t in [
        "（1）药材为均匀、各向同性的圆柱体，忽略周向与轴向梯度，仅考虑径向传递。",
        "（2）烘房环境均匀，药材表面各处的温度与水分交换条件相同。",
        "（3）含水率以干基含水率度量，其扩散符合Fick定律，并可由有效扩散系数描述。",
        "（4）水分在药材内部的迁移以液相扩散为主，忽略毛细流动、蒸发—冷凝的微观再分布。",
        "（5）不考虑辐射换热、化学反应、表面硬化与裂纹等次要因素。",
        "（6）问题一至问题三药材尺寸不变；问题四的收缩为各向同性的径向相似收缩，即r=ξR(t)。",
        "（7）由于题目未给出吸附等温线，取烘房空气含湿量作为药材表面的等效平衡含水率。",
    ]:
        add_par(doc, t)

    # ------------------------------------------------------------ 四、符号说明
    add_heading(doc, "四、符号说明", 1)
    add_caption(doc, "表0  主要符号说明")
    add_table(doc, ["符号", "说明", "单位"], [
        ["r", "到药材中心的距离", "m"],
        ["R(t)", "药材半径（问题四随时间变化）", "m"],
        ["t", "时间", "s"],
        ["T(r,t)", "药材温度", "℃"],
        ["C(r,t)", "干基含水率", "kg/kg"],
        ["T_a、C_a", "烘房温度、空气含湿量", "℃、kg/kg"],
        ["ρ", "密度", "kg/m³"],
        ["c_p", "比热容", "J/(kg·K)"],
        ["k", "导热系数", "W/(m·K)"],
        ["D", "水分扩散系数", "m²/s"],
        ["h_T", "对流换热系数", "W/(m²·K)"],
        ["h_C", "对流传质系数", "m/s"],
        ["ξ", "材料坐标，ξ=r/R(t)", "—"],
        ["g(t)", "全域含水率事件函数", "kg/kg"],
    ])

    # ------------------------------------------------------ 五、模型建立与求解
    add_heading(doc, "五、模型建立与求解", 1)

    add_heading(doc, "5.1 控制方程", 2)
    add_par(doc, "在轴对称圆柱假设下，控制体取单位轴向长度的环形薄层。能量与质量守恒分别给出")
    add_formula(doc, "ρ c_p ∂T/∂t = (1/r) ∂[ r k ∂T/∂r ] / ∂r", "(1)")
    add_formula(doc, "∂C/∂t = (1/r) ∂[ r D ∂C/∂r ] / ∂r", "(2)")
    add_par(doc, "式中右侧为径向散度形式的守恒通量，导热系数k与扩散系数D均使用当前局部状态计算。"
                 "边界条件为：")

    add_heading(doc, "5.2 环境条件与初始条件", 2)
    add_par(doc, "附件1给出烘干初期每隔60 s的烘房温度与空气含湿量（0~14400 s，共241个数据点）。"
                 "在数据区间内采用分段线性插值构造环境函数T_a(t)、C_a(t)；4 h之后附件1不再提供数据，"
                 "取其中最后1 h（10800~14400 s，61个数据点）的均值外推，得T_a=49.998934 ℃、"
                 "C_a=0.04998754 kg/kg。")
    add_par(doc, "药材的初始状态为T(r,0)=28 ℃、C(r,0)=2.55 kg/kg；中心处由对称性给出∂T/∂r=∂C/∂r=0。")

    add_heading(doc, "5.3 边界条件", 2)
    add_par(doc, "药材表面与烘房空气之间为对流换热与对流传质，边界条件为")
    add_formula(doc, "−k ∂T/∂r |_{r=R} = h_T ( T_s − T_a )", "(3)")
    add_formula(doc, "−D ∂C/∂r |_{r=R} = h_C ( C_s − C_a )", "(4)")
    add_par(doc, "其中T_s、C_s为表面温度与表面含水率。由边界条件与内部扩散的相对强弱可估计传质Biot数"
                 "约为1.1，说明干燥过程同时受内部扩散与表面传质控制。")

    add_heading(doc, "5.4 问题一：常物性预热平衡模型", 2)
    add_par(doc, "采用附录2的参数：ρ=820 kg/m³、c_p=2600 J/(kg·K)、k=0.36 W/(m·K)、"
                 "h_T=25 W/(m²·K)、h_C=8×10⁻⁷ m/s，水分扩散系数为")
    add_formula(doc, "D(C) = 7×10⁻⁹ exp(−0.89C)  (m²/s)", "(5)")
    add_par(doc, "该阶段半径固定为R₀=0.02 m。以守恒型有限体积法求解后，得到30 min内的温度与水分浓度"
                 "分布，如表1、表2所示。")
    _insert_table(doc, "表1  30分钟内药材的温度（℃）", "table1_temperature_q1.csv")
    _insert_table(doc, "表2  30分钟内药材的水分浓度（kg/kg）", "table2_moisture_q1.csv")
    add_par(doc, "由表1可见，预热阶段温度场沿径向存在小幅梯度，1800 s时中心与表面温差约3.2 ℃，"
                 "整体温度随烘房升温而稳步上升；由表2可见，水分浓度在中心区域基本不变，"
                 "仅表面附近明显下降，1800 s时表面水分浓度已降至1.2008 kg/kg，"
                 "说明30 min内水分变化仍局限于表层。完整结果（每秒、每隔0.1 cm）见result1.xlsx。")
    add_figure(doc, "fig1_q1_radial.png", "图1  问题一：预热平衡阶段温度与含水率的径向分布")

    add_heading(doc, "5.5 问题二：变物性恒温干燥模型", 2)
    add_par(doc, "恒温干燥阶段采用附录3的经验公式，物性随含水率变化：")
    add_formula(doc, "ρ(C)=650+128C,  c_p(C)=1450+2736C/(C+1),  k(C)=0.21+0.38C/(C+1)", "(6)")
    add_formula(doc, "D(C,T_K) = 2.4×10⁻³ exp(−0.45C) exp(−3850/T_K)", "(7)")
    add_par(doc, "其中T_K=T+273.15为绝对温度。该式中的温度指数采用绝对温度的倒数形式，"
                 "与附录给出的经验形式一致。由于题目规定预热与恒温阶段参数不同，本文把问题二"
                 "视为从初始时刻起、以附录3物性描述的整个烘干过程，即T(r,0)=28 ℃、C(r,0)=2.55 kg/kg。")
    add_par(doc, "方程(1)(2)与物性(6)(7)构成强耦合非线性系统。求解得到3 h内的温度与水分浓度分布，"
                 "如表3、表4所示。")
    _insert_table(doc, "表3  3小时内药材的温度（℃）", "table3_temperature_q2.csv")
    _insert_table(doc, "表4  3小时内药材的水分浓度（kg/kg）", "table4_moisture_q2.csv")
    add_par(doc, "由表3可见，由于药材热容较小而表面对流换热充分，温度在1 h内即迅速接近烘房温度，"
                 "3 h时表面温度为49.9572 ℃，径向温差不足0.13 ℃。由表4可见，水分浓度自表面向中心依次"
                 "下降，中心因扩散路径最长而干燥最慢，3 h时中心仍为2.1615 kg/kg、表面已降至0.9837 kg/kg。"
                 "完整结果见result2.xlsx。")
    add_figure(doc, "fig2_q2_radial.png", "图2  问题二：恒温干燥阶段温度与含水率的径向分布")

    add_heading(doc, "5.6 问题三：全域含水率终止事件", 2)
    add_par(doc, "问题三沿用问题二的控制方程与物性。定义全域最大含水率与事件函数")
    add_formula(doc, "g(t) = max_{0≤r≤R₀} C(r,t) − 0.15", "(8)")
    add_par(doc, "理论临界烘干时间为g(t)首次由正变负的时刻，即")
    add_formula(doc, "t* = inf{ t ≥ 0 : max C(r,t) ≤ 0.15 }", "(9)")
    add_par(doc, "数值实现中，事件函数采用节点最大含水率max_i C_i−0.15，并设置终止方向为负，"
                 "由BDF求解器在内部稠密插值上定位临界时刻，再以二分法在事件前后的异号区间上复核。"
                 "求得临界烘干时间与相应分布如表5所示。")
    _insert_table(doc, "表5  药材烘干过程的水分浓度（kg/kg）", "table5_moisture_q3.csv")
    add_par(doc, "计算得 t* = 59286.1751 s = 16.4684 h。此时中心含水率恰为0.1500 kg/kg，"
                 "该时刻之后全域含湿率严格低于0.15 kg/kg。由表5可见，烘干前12 h含水率下降较快，"
                 "此后由于传质推动力减小、干燥速率降低，中心由0.3246 kg/kg进一步降至0.1500 kg/kg"
                 "又耗时约4.5 h。完整结果见result3.xlsx。")
    add_figure(doc, "fig3_q3_history.png", "图3  问题三：含水率演化与烘干终止判据")

    add_heading(doc, "5.7 问题四：收缩材料坐标模型", 2)
    add_par(doc, "药材在干燥过程中体积收缩，附件2给出半径随时间的变化，由2 cm单调减小至约1.198 cm。"
                 "引入材料坐标ξ=r/R(t)，把移动域映射为固定区间[0,1]，记θ(ξ,t)=T(ξR(t),t)、"
                 "c(ξ,t)=C(ξR(t),t)，则控制方程化为")
    add_formula(doc, "ρ(c)c_p(c) ∂θ/∂t = 1/[R(t)²ξ] ∂[ ξ k(c) ∂θ/∂ξ ] / ∂ξ", "(10)")
    add_formula(doc, "∂c/∂t = 1/[R(t)²ξ] ∂[ ξ D(c,θ+273.15) ∂c/∂ξ ] / ∂ξ", "(11)")
    add_par(doc, "物性采用附录4的经验公式：")
    add_formula(doc, "ρ(c)=760+90c,  c_p(c)=1850+2150c/(c+1),  k(c)=0.12+0.20c/(c+1)", "(12)")
    add_formula(doc, "D(c,θ_K) = 4.2×10⁻⁴ exp(−0.30c) exp(−3850/θ_K)", "(13)")
    add_par(doc, "表面边界条件在材料坐标下写为")
    add_formula(doc, "−k(c_s)θ_ξ(1)/R(t) = h_T(θ_s−T_a),  −D c_ξ(1)/R(t) = h_C(c_s−C_a)", "(14)")
    add_par(doc, "径向半径由附件2数据经保形单调插值（PCHIP）得到，避免出现非单调与过冲。"
                 "终止判据与问题三相同，但取材料坐标下的最大值：")
    add_formula(doc, "g₄(t) = max_{0≤ξ≤1} c(ξ,t) − 0.15", "(15)")
    add_par(doc, "求解后按ξ_k(t)=r_k/R(t)映射回固定物理位置输出，位于药材之外的位置留空，"
                 "并单列药材表面含水率，结果如表6所示。")
    _insert_table(doc, "表6  药材烘干过程的水分浓度（kg/kg）", "table6_moisture_q4.csv")
    add_par(doc, "计算得 t* = 70759.9787 s = 19.6555 h。由表6可见，随半径收缩，"
                 "距中心1.5、2.0 cm的物理位置先后落到药材之外因而留空；药材表面含水率持续降低，"
                 "至临界时刻为0.0802 kg/kg，而中心含水率恰为0.1500 kg/kg。")
    add_par(doc, "为分离几何收缩的影响，另以附录4物性固定半径R(t)≡0.02 m进行对照计算，"
                 "得烘干时间为39.2119 h。可见在相同物性下，纯几何收缩使干燥时间缩短约19.56 h，"
                 "原因是收缩缩短了水分扩散距离并增大了表面的相对交换能力。")
    add_figure(doc, "fig4_q4_history.png", "图4  问题四：收缩条件下的含水率演化与半径变化")

    # ------------------------------------------------------ 六、模型检验与灵敏度
    add_heading(doc, "六、模型检验与灵敏度分析", 1)
    add_heading(doc, "6.1 数值验证", 2)
    add_par(doc, "为验证离散格式与实现的正确性，进行了四组检验。")
    add_par(doc, "（1）解析解验证。构造常扩散系数、表面为Dirichlet条件的圆柱合成问题，"
                 "与贝塞尔级数解析解对比，最大绝对偏差为7.4×10⁻⁶。")
    add_par(doc, "（2）极限一致性验证。令问题四中的R(t)≡R₀并使用与固定域相同的物性，"
                 "材料坐标程序与固定域程序的结果偏差为5.6×10⁻¹⁶，达到机器精度。")
    add_par(doc, "（3）网格与时间容差收敛。取径向区间数N=160、320、640，临界时间分别为"
                 "59286.102、59286.175、59286.194 s（问题三）与70760.077、70759.979、70759.952 s"
                 "（问题四），估计空间收敛阶约为1.98与1.89，接近二阶；相对容差取10⁻⁷、10⁻⁸、10⁻⁹时，"
                 "临界时间变化小于0.003 s。综合时间积分与空间离散，N=320时临界时间的不确定度"
                 "约为0.04 s以内。")
    add_par(doc, "（4）守恒性检验。对含水率总量做收支核算，Q1、Q3、Q4的相对残差分别为"
                 "3.83×10⁻⁹、2.97×10⁻⁶、5.54×10⁻⁶；其中问题四采用材料坐标度量，"
                 "以避免把几何收缩误判为水分流失。")
    add_figure(doc, "fig6_convergence.png", "图6  数值收敛性检验")

    add_heading(doc, "6.2 灵敏度分析", 2)
    add_par(doc, "考虑到经验公式与工艺参数存在不确定性，对表面传质系数h_C、扩散系数D和边界平衡含水率"
                 "C_a进行了系统灵敏度分析，结果见表7。")
    add_caption(doc, "表7  关键参数的灵敏度（临界时间，h）")
    add_table(doc, ["变化因素", "倍数", "问题三", "问题四"], [
        ["传质系数h_C", "×0.5", "27.5524", "25.8758"],
        ["", "×1.0", "16.4684", "19.6555"],
        ["", "×2.0", "11.0138", "16.7220"],
        ["", "×4.0", "8.3730", "15.3377"],
        ["扩散系数D", "×0.5", "21.7312", "30.1445"],
        ["", "×2.0", "13.8514", "14.2591"],
        ["平衡含水率C_a", "×0.5", "15.4884", "18.6852"],
        ["", "×2.0", "19.5391", "22.6682"],
    ])
    add_par(doc, "结果表明：临界时间对表面传质系数与扩散系数最为敏感，传质系数减小一半会使问题三的"
                 "烘干时间由16.47 h延长到27.55 h；对边界平衡含水率的敏感度中等；4 h之后环境取恒定"
                 "50 ℃或取附件1末值，对结果的影响均不足0.2%，说明环境外推方式不构成主要不确定性。")
    add_figure(doc, "fig5_sensitivity.png", "图5  关键参数灵敏度：临界烘干时间随参数倍数的变化")

    add_heading(doc, "6.3 结果合理性讨论", 2)
    add_par(doc, "由计算结果可见，温度场在1 h内即接近烘房温度，而含水率的下降贯穿整个干燥过程，"
                 "这与热风干燥中“热扩散快、质扩散慢”的一般规律一致；含水率始终由中心向表面单调递减，"
                 "最大含水率恒位于中心，符合内部扩散控制的物理图像。")
    add_par(doc, "题面指出烘干过程一般持续2~3天。本文模型给出的理论临界时间为16.47 h（固定尺寸）与"
                 "19.66 h（考虑收缩），短于实际工艺时长。其原因是本文采用的有效扩散模型未包含"
                 "蒸发潜热与吸附/解吸平衡等机制：温度方程中没有相变潜热汇项，药材升温偏快、"
                 "扩散系数偏大；同时以空气含湿量直接作为表面平衡含水率，缺少吸附等温线。"
                 "因此该差值属于模型简化的系统性偏差，而非数值实现错误。")

    # ------------------------------------------------------------ 七、模型评价
    add_heading(doc, "七、模型优缺点评价", 1)
    add_heading(doc, "7.1 模型优点", 2)
    for t in [
        "（1）采用守恒型有限体积法离散，通量形式保证离散后的质量与能量严格守恒，"
        "中心界面面积为零，天然满足对称条件，无需虚拟节点。",
        "（2）使用隐式BDF方法积分刚性耦合方程组，并通过稀疏Jacobian结构提高效率，"
        "可在毫秒级完成单次求解。",
        "（3）问题四采用材料坐标把移动边界问题转化为固定区间问题，避免了网格移动与"
        "对流项的显式处理。",
        "（4）终止时刻由事件机制自动定位并以二分法复核，且给出了网格、容差、守恒与"
        "灵敏度等完整验证。",
    ]:
        add_par(doc, t)
    add_heading(doc, "7.2 模型缺点与改进方向", 2)
    for t in [
        "（1）模型未考虑蒸发潜热与吸附平衡，预测的临界时间偏短；后续可引入相变源项与"
        "吸附等温线以提高与实际工艺的吻合度。",
        "（2）物性经验公式中温度项采用绝对温度倒数形式，若按字面代入摄氏度或绝对温度"
        "将导致扩散系数下溢，本文采用了合理的物理解释。",
        "（3）模型仅保留径向传递，忽略了轴向与端面效应，对长径比较小的药材需引入二维模型。",
    ]:
        add_par(doc, t)

    # ------------------------------------------------------------ 参考文献
    add_heading(doc, "参考文献", 1)
    for i, ref in enumerate([
        "Eymard R, Gallouët T, Herbin R. Finite Volume Methods[M]. Handbook of Numerical Analysis, "
        "Vol. VII. Amsterdam: North-Holland, 2000.",
        "Gasparin S, Berger J, Dutykh D, et al. Reliable numerical schemes for a nonlinear heat and "
        "moisture transfer problem[J]. Applied Mathematics and Computation, 2017.",
        "Mayor L, Sereno A M. Modelling shrinkage during convective drying of food materials: a review[J]. "
        "Journal of Food Engineering, 2004, 61(3): 373-386.",
        "Seyedabadi E, Khojastehpour M, Sadrnia H, et al. Finite element modeling of convective drying of "
        "banana with radial shrinkage using the ALE method[J]. Journal of Food Science and Technology, 2016.",
        "Virtanen P, Gommers R, Oliphant T E, et al. SciPy 1.0: fundamental algorithms for scientific "
        "computing in Python[J]. Nature Methods, 2020, 17: 261-272.",
    ], 1):
        add_par(doc, "[%d] %s" % (i, ref), indent=False)

    # ------------------------------------------------------------------ 附录
    add_heading(doc, "附录", 1)
    add_heading(doc, "附录1  支撑文件列表", 3)
    add_par(doc, "本论文计算结果由如下文件保存：result1.xlsx（问题一，温度与水分浓度，1~1800 s、"
                 "每隔0.1 cm）；result2.xlsx（问题二，1~10800 s）；result3.xlsx（问题三，每秒60 s，"
                 "含临界时刻行）；result4.xlsx（问题四，含药材表面列与药材外部留空）。"
                 "验证与诊断数据见 outputs/diagnostics 目录。")
    add_heading(doc, "附录2  主要程序", 3)
    add_par(doc, "计算程序基于 Python 3.12 编写，使用 NumPy、SciPy 与 openpyxl。"
                 "核心流程为：读取附件数据并校验，构造环境函数与半径函数，"
                 "按守恒型有限体积法装配右端函数，用 solve_ivp（BDF）积分并监测终止事件，"
                 "最后按模板写出四位小数的结果文件。主要源程序见随论文提交的源代码包。")

    doc.save(str(OUT))
    return OUT


def _insert_table(doc, caption, filename):
    rows = read_csv_rows(TABLES / filename)
    header = [rows[0][0]] + [fmt(v, 4) for v in rows[0][1:]]
    body = []
    for r in rows[1:]:
        first = r[0]
        try:
            first = "%.4f" % float(first)
        except ValueError:
            pass
        body.append([first] + [("" if v == "" else fmt(v, 4)) for v in r[1:]])
    add_caption(doc, caption)
    add_table(doc, header, body)


if __name__ == "__main__":
    print("written:", build())
