"""将扩展实证模型、三线表和图形写入论文副本。"""

from __future__ import annotations

import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCE = Path(r"C:\Users\Lenovo\Desktop\全要素生产率对经济高质量发展的作用与路径.docx")
OUTPUT = BASE / "全要素生产率对经济高质量发展的作用与路径_完善版.docx"
RESULT = BASE / "结果"

import pandas as pd
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


def set_run_font(run, size=10.5, bold=False, east_asia="宋体", latin="Times New Roman"):
    run.font.name = latin
    run.font.size = Pt(size)
    run.font.bold = bold
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), east_asia)


def move_after(cursor, element):
    cursor.addnext(element)
    return element


def add_paragraph_after(doc, cursor, text="", style="Normal", align=None, first_line=True,
                        keep_with_next=False, bold=False):
    paragraph = doc.add_paragraph(style=style)
    run = paragraph.add_run(text)
    set_run_font(run, bold=bold)
    if align is not None:
        paragraph.alignment = align
    paragraph.paragraph_format.keep_with_next = keep_with_next
    if first_line and style == "Normal":
        paragraph.paragraph_format.first_line_indent = Pt(21)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.5
    return paragraph, move_after(cursor, paragraph._p)


def add_equation(doc, cursor, equation):
    p, cursor = add_paragraph_after(doc, cursor, equation, align=WD_ALIGN_PARAGRAPH.CENTER,
                                    first_line=False)
    for run in p.runs:
        set_run_font(run, size=10.5, east_asia="宋体", latin="Cambria Math")
    return cursor


def set_cell_border(cell, **kwargs):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        if edge in kwargs:
            tag = "w:" + edge
            element = borders.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                borders.append(element)
            for key, value in kwargs[edge].items():
                element.set(qn("w:" + key), str(value))


def set_table_borders(table, header=True):
    nil = {"val": "nil"}
    for row in table.rows:
        for cell in row.cells:
            set_cell_border(cell, top=nil, bottom=nil, left=nil, right=nil, insideH=nil, insideV=nil)
    line = {"val": "single", "sz": "10", "color": "000000", "space": "0"}
    for cell in table.rows[0].cells:
        set_cell_border(cell, top=line, bottom=line)
    for cell in table.rows[-1].cells:
        set_cell_border(cell, bottom=line)


def set_cell_margins(cell, top=60, start=70, bottom=60, end=70):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for name, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def add_three_line_table(doc, cursor, caption, headers, rows, widths=None, font_size=8.5,
                         note=None):
    cap, cursor = add_paragraph_after(doc, cursor, caption, style="Caption",
                                      align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False,
                                      keep_with_next=True)
    for run in cap.runs:
        set_run_font(run, size=9, east_asia="黑体", latin="Times New Roman")
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    if widths is None:
        widths = [5.65 / len(headers)] * len(headers)
    for col, (header, width) in enumerate(zip(headers, widths)):
        table.columns[col].width = Inches(width)
        table.cell(0, col).width = Inches(width)
        table.cell(0, col).text = str(header)
    for values in rows:
        cells = table.add_row().cells
        for col, (value, width) in enumerate(zip(values, widths)):
            cells[col].width = Inches(width)
            cells[col].text = str(value)
    for r_idx, row in enumerate(table.rows):
        for cell in row.cells:
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cell)
            for p in cell.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.0
                for run in p.runs:
                    set_run_font(run, size=font_size, bold=(r_idx == 0),
                                 east_asia="宋体" if r_idx else "黑体")
    set_table_borders(table)
    cursor = move_after(cursor, table._tbl)
    if note:
        note_p, cursor = add_paragraph_after(doc, cursor, note,
            align=WD_ALIGN_PARAGRAPH.LEFT, first_line=False)
        for run in note_p.runs:
            set_run_font(run, size=8)
    return cursor


def remove_table_borders(table):
    nil = {"val": "nil"}
    for row in table.rows:
        for cell in row.cells:
            set_cell_border(cell, top=nil, bottom=nil, left=nil, right=nil, insideH=nil, insideV=nil)


def add_figure(doc, cursor, image_path, caption, width=5.65):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    remove_table_borders(table)
    cell = table.cell(0, 0)
    cell.width = Inches(width)
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run()
    run.add_picture(str(image_path), width=Inches(width))
    cursor = move_after(cursor, table._tbl)
    cap, cursor = add_paragraph_after(doc, cursor, caption, style="Caption",
                                      align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False)
    for run in cap.runs:
        set_run_font(run, size=9, east_asia="黑体")
    return cursor


def find_heading(doc, text):
    for paragraph in doc.paragraphs:
        if paragraph.text.strip() == text:
            return paragraph
    raise KeyError(f"未找到标题：{text}")


def sig(coef, p):
    stars = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""
    return f"{coef:.3f}{stars}"


def insert_dagum(doc):
    cursor = find_heading(doc, "3.1.2Dagum基尼系数")._p
    text = (
        "核密度估计能够刻画分布位置、峰态及拖尾变化，但无法定量识别差异究竟来自区域内部、区域之间，还是不同区域分布交叉。为此，本文采用Dagum（1997）基尼系数及其子群分解方法，将省际总体差异分解为区域内差异、区域间净差异和超变密度三部分。相较于传统基尼分解，该方法能够处理不同区域分布相互重叠的问题。"
    )
    _, cursor = add_paragraph_after(doc, cursor, text)
    cursor = add_equation(doc, cursor, "G＝[ΣⱼΣₕΣᵢΣᵣ|xⱼᵢ－xₕᵣ|]／(2n²x̄)")
    _, cursor = add_paragraph_after(doc, cursor,
        "式中，xⱼᵢ表示区域j中第i个省份的指标值，n为省份总数，x̄为全国均值。设pⱼ＝nⱼ／n为区域省份数量份额，sⱼ＝nⱼx̄ⱼ／(nx̄)为区域指标份额，Gⱼⱼ和Gⱼₕ分别表示区域内部及区域之间的基尼系数，则总体基尼系数可分解为：")
    cursor = add_equation(doc, cursor, "G＝Gw＋Gnb＋Gt")
    cursor = add_equation(doc, cursor, "Gw＝ΣⱼGⱼⱼpⱼsⱼ")
    cursor = add_equation(doc, cursor, "Gnb＝Σⱼ>ₕGⱼₕDⱼₕ(pⱼsₕ＋pₕsⱼ)")
    cursor = add_equation(doc, cursor, "Gt＝Σⱼ>ₕGⱼₕ(1－Dⱼₕ)(pⱼsₕ＋pₕsⱼ)")
    _, cursor = add_paragraph_after(doc, cursor,
        "其中，Gw为区域内差异，Gnb为区域间净差异，Gt为超变密度；Dⱼₕ＝(dⱼₕ－pⱼₕ)/(dⱼₕ＋pⱼₕ)为区域间相对影响系数。dⱼₕ表示高均值区域样本超过低均值区域样本的平均超距，pⱼₕ表示低均值区域样本反超高均值区域样本产生的平均交叉差异。Dⱼₕ越接近1，说明两区域分布分离越明显；越接近0，说明分布重叠越充分。")
    dagum = pd.read_csv(RESULT / "Dagum" / "Dagum_年度分解结果.csv", encoding="utf-8-sig")
    rows = []
    for _, r in dagum.iterrows():
        variable = "高质量发展" if str(r["变量"]).startswith("Y") else "累计TFP"
        if pd.isna(r["区域内贡献率"]):
            shares = ("—", "—", "—")
        else:
            shares = tuple(f"{100*r[c]:.2f}%" for c in ["区域内贡献率", "区域间净差异贡献率", "超变密度贡献率"])
        rows.append([variable, int(r["年份"]), f"{r['总基尼系数']:.4f}", *shares])
    cursor = add_three_line_table(doc, cursor, "表3  Dagum基尼系数及差异来源贡献率",
        ["变量", "年份", "总基尼", "区域内", "区域间净差异", "超变密度"], rows,
        widths=[1.05, .55, .75, .85, 1.25, 1.0], font_size=8,
        note="注：三类贡献率之和为100%；累计TFP在2016年为共同基期，故该年贡献率不计算。")
    _, cursor = add_paragraph_after(doc, cursor,
        "结果显示，高质量发展指数的总体基尼系数由2016年的0.2151持续下降至2020年的0.1414，累计降幅约34.3%，表明省际高质量发展差异呈稳定收敛。区域间净差异的贡献率始终位于57.95%—67.30%，是总体差异的首要来源；区域内差异约占24%—28%，超变密度约占9%—14%。因此，现阶段高质量发展不平衡主要体现为东中西部整体发展梯度，而不是单一区域内部的离散。")
    _, cursor = add_paragraph_after(doc, cursor,
        "累计TFP在2016年被统一设为1，故该年差异为0，不具有横截面比较含义。2017—2020年其总基尼由0.0397上升至0.0846，表明累计增长路径逐步分化。区域间净差异贡献率由40.20%升至54.28%，超变密度由31.22%降至15.24%，说明区域主体分布逐渐拉开。区域内结果进一步表明，西部TFP区域内基尼由0.0309上升至0.1036，是总体分化扩大的重要来源。需要强调的是，Dagum分解揭示的是差异的空间统计构成，而非差异形成的因果机制。")
    cursor = add_figure(doc, cursor, RESULT / "Dagum" / "Dagum_总基尼系数趋势.png",
                        "Figure7  高质量发展指数与累计农业TFP的Dagum总基尼系数")
    cursor = add_figure(doc, cursor, RESULT / "Dagum" / "Dagum_差异来源贡献率.png",
                        "Figure8  Dagum基尼系数差异来源贡献率")


def insert_moran(doc):
    global_df = pd.read_csv(RESULT / "空间自相关初步检验" / "全局莫兰指数结果.csv", encoding="utf-8-sig")
    cursor = find_heading(doc, "3.3.1全局莫兰指数")._p
    _, cursor = add_paragraph_after(doc, cursor,
        "为检验高质量发展及农业TFP是否具有空间依赖性，本文以省级行政区接壤关系构建二元邻接矩阵，并进行行标准化。海南不存在陆地邻省，为避免空间孤岛，将其与地理距离最近且联系密切的广东桥接。全局Moran指数定义为：")
    cursor = add_equation(doc, cursor, "I＝[n／S₀]·[ΣᵢΣⱼwᵢⱼ(xᵢ－x̄)(xⱼ－x̄)]／[Σᵢ(xᵢ－x̄)²]")
    _, cursor = add_paragraph_after(doc, cursor,
        "其中，wᵢⱼ为空间权重，S₀＝ΣᵢΣⱼwᵢⱼ。I大于其随机期望值－1/(n－1)表示正空间相关，小于期望值表示负空间相关。显著性采用999次随机置换获得伪p值。")
    rows = []
    for _, r in global_df.iterrows():
        var = "高质量发展" if r["变量"] == "高质量发展指数" else "累计TFP"
        if pd.isna(r["Moran_I"]):
            rows.append([var, int(r["年份"]), "—", "—", "共同基期"])
        else:
            rows.append([var, int(r["年份"]), f"{r['Moran_I']:.3f}", f"{r['置换z值']:.3f}", f"{r['置换p值']:.3f}"])
    cursor = add_three_line_table(doc, cursor, "表4  全局Moran指数及置换检验",
        ["变量", "年份", "Moran's I", "置换z值", "置换p值"], rows,
        widths=[1.3, .65, 1.05, 1.0, 1.0], font_size=8.5,
        note="注：伪p值基于999次随机置换；累计TFP在2016年为共同基期，横截面无差异。")
    _, cursor = add_paragraph_after(doc, cursor,
        "高质量发展指数的Moran值在0.236—0.402之间，所有年份均在5%水平显著为正，说明相近省份之间长期存在高—高或低—低集聚。2019年空间相关程度有所减弱，但2020年重新升至0.356。累计TFP在2017年的Moran值为0.069且不显著，表明基期后初始增长主要体现为省份个体波动；2018—2020年Moran值分别为0.201、0.249和0.168，均通过5%置换检验，说明TFP增长逐步形成空间集聚，但2020年集聚强度有所回落。")
    cursor = add_figure(doc, cursor, RESULT / "空间自相关初步检验" / "全局莫兰指数趋势.png",
                        "Figure9  高质量发展指数与累计农业TFP的全局Moran指数")
    cursor = add_figure(doc, cursor, RESULT / "空间自相关初步检验" / "全局莫兰散点图_y_clean.png",
                        "Figure10  高质量发展指数Moran散点图")

    cursor = find_heading(doc, "3.3.2局部莫兰指数")._p
    _, cursor = add_paragraph_after(doc, cursor,
        "全局指标仅反映总体空间相关，无法识别具体集聚位置，因而进一步采用Anselin局部Moran指数（LISA）：")
    cursor = add_equation(doc, cursor, "Iᵢ＝zᵢΣⱼwᵢⱼzⱼ")
    _, cursor = add_paragraph_after(doc, cursor,
        "其中，zᵢ为标准化指标值。依据自身取值与空间滞后值的符号，将省份划分为高—高（HH）、低—低（LL）、高—低（HL）和低—高（LH）四类；仅将999次置换检验p<0.05的结果认定为显著局部集聚。")
    _, cursor = add_paragraph_after(doc, cursor,
        "高质量发展指数的局部集聚格局具有较强稳定性。以2020年为例，上海、江苏和浙江表现为显著HH集聚，内蒙古、四川、云南和青海表现为显著LL集聚，新疆表现为HL型空间离群。该结果表明长三角形成了连续高值集聚，而部分西部省份仍处于低值邻接环境。累计TFP的局部格局波动更大，2020年广西、西藏和新疆为HH，浙江为LL，河北为HL，四川为LH。由于局部检验数量较多且样本期较短，这些结果应主要作为空间模型设定的诊断依据，不宜作强因果解释。")
    cursor = add_figure(doc, cursor, RESULT / "空间自相关初步检验" / "局部莫兰聚类热图_y_clean.png",
                        "Figure11  高质量发展指数局部Moran显著聚类")
    cursor = add_figure(doc, cursor, RESULT / "空间自相关初步检验" / "局部莫兰聚类热图_cum_tfp.png",
                        "Figure12  累计农业TFP局部Moran显著聚类")


def insert_robustness(doc):
    data = pd.read_csv(RESULT / "稳健性检验" / "稳健性检验结果.csv", encoding="utf-8-sig")
    cursor = find_heading(doc, "4.2稳健性检验")._p
    _, cursor = add_paragraph_after(doc, cursor,
        "为避免基准结论受到极端值、特殊行政单元、同期性、函数形式和标准误设定的驱动，本文依次进行双侧1%缩尾、剔除四个直辖市、核心解释变量滞后一期、水平值估计以及Driscoll—Kraay标准误检验。除特别说明外，各模型均控制人口密度、第一产业占比以及省份和年份固定效应。")
    rows = []
    for _, r in data.iterrows():
        rows.append([r["模型"], sig(r["系数"], r["p值"]), f"({r['标准误']:.3f})",
                     int(r["观测值"]), f"{r['组内R2']:.3f}"])
    cursor = add_three_line_table(doc, cursor, "表5  稳健性检验结果",
        ["模型", "TFP系数", "标准误", "N", "组内R²"], rows,
        widths=[2.15, .9, .85, .55, .85], font_size=8.2,
        note="注：括号内为标准误；*、**、***分别表示在10%、5%和1%水平上显著。")
    _, cursor = add_paragraph_after(doc, cursor,
        "对数基准模型中TFP系数为0.446，并在5%水平显著。缩尾处理和剔除直辖市后，系数分别为0.382和0.493，均保持显著为正；采用Driscoll—Kraay标准误后结论亦未改变。滞后一期TFP的系数为0.255，在10%水平弱显著，说明促进作用可能具有一定时滞。水平值模型的系数为0.043，但未达到常用显著性水平，意味着结论对函数形式并非完全不敏感。总体而言，正向影响在主要对数设定和样本调整下较为稳定，但不应将稳健性表述为对所有函数形式均成立。")
    cursor = add_figure(doc, cursor, RESULT / "稳健性检验" / "稳健性系数森林图.png",
                        "Figure13  农业TFP影响的稳健性检验")


def insert_iv(doc):
    data = pd.read_csv(RESULT / "内生性检验" / "内生性检验结果.csv", encoding="utf-8-sig")
    cursor = find_heading(doc, "4.3内生性检验")._p
    _, cursor = add_paragraph_after(doc, cursor,
        "农业TFP与高质量发展之间可能存在反向作用，同时遗漏的制度与技术冲击也可能影响二者。受样本期较短且缺乏可信外部冲击变量的限制，本文采用农业TFP的一期滞后作为内部工具变量进行双向固定效应2SLS估计。其识别要求是：滞后TFP与当期TFP相关，并在控制省份、年份和控制变量后不通过其他持续性渠道直接影响当期高质量发展。该排除限制无法由数据完全检验，因此本节属于缓解性而非决定性因果识别。")
    cursor = add_equation(doc, cursor, "第一阶段：lnTFPᵢₜ＝πlnTFPᵢ,ₜ₋₁＋γXᵢₜ＋μᵢ＋λₜ＋νᵢₜ")
    cursor = add_equation(doc, cursor, "第二阶段：lnYᵢₜ＝βlnTFP̂ᵢₜ＋δXᵢₜ＋μᵢ＋λₜ＋εᵢₜ")
    rows = []
    for _, r in data.iterrows():
        rows.append([r["模型"], sig(r["系数"], r["p值"]), f"({r['标准误']:.3f})",
                     int(r["观测值"]), "—" if pd.isna(r["第一阶段部分F"]) else f"{r['第一阶段部分F']:.2f}",
                     "—" if pd.isna(r["Wu-Hausman p值"]) else f"{r['Wu-Hausman p值']:.3f}"])
    cursor = add_three_line_table(doc, cursor, "表6  内生性检验：一期滞后内部工具变量",
        ["模型", "TFP系数", "标准误", "N", "第一阶段F", "DWH p值"], rows,
        widths=[1.75, .85, .8, .5, 1.0, .9], font_size=8,
        note="注：括号内为省份聚类稳健标准误；*、**、***分别表示在10%、5%和1%水平上显著。")
    _, cursor = add_paragraph_after(doc, cursor,
        "第一阶段部分F统计量为39.36，显著高于经验阈值10，未显示明显弱工具变量问题。2SLS估计系数为0.526，p值为0.055，在10%水平显著为正，与基准回归方向一致且数值略大。Wu—Hausman检验p值为0.401，不能拒绝解释变量外生的原假设，说明样本内没有强证据表明OLS存在显著内生性偏误。结合工具变量排除限制无法完全验证这一事实，本文将IV结果视为支持性证据，而不作严格因果宣称。")
    cursor = add_figure(doc, cursor, RESULT / "内生性检验" / "OLS与IV估计比较.png",
                        "Figure14  OLS与工具变量估计结果比较")


def insert_spillover(doc):
    coef = pd.read_csv(RESULT / "空间溢出效应" / "空间杜宾模型系数.csv", encoding="utf-8-sig")
    impacts = pd.read_csv(RESULT / "空间溢出效应" / "空间效应分解.csv", encoding="utf-8-sig")
    tests = pd.read_csv(RESULT / "空间溢出效应" / "空间模型约束检验.csv", encoding="utf-8-sig")
    cursor = find_heading(doc, "5.1空间溢出效应")._p
    _, cursor = add_paragraph_after(doc, cursor,
        "全局Moran检验表明高质量发展存在稳定空间依赖，因此使用非空间面板模型可能忽略邻近地区的联动。本文采用同时包含被解释变量空间滞后项和解释变量空间滞后项的空间杜宾模型（SDM）：")
    cursor = add_equation(doc, cursor, "lnYᵢₜ＝ρΣⱼwᵢⱼlnYⱼₜ＋βlnTFPᵢₜ＋θΣⱼwᵢⱼlnTFPⱼₜ＋γXᵢₜ＋ηWXᵢₜ＋μᵢ＋λₜ＋εᵢₜ")
    _, cursor = add_paragraph_after(doc, cursor,
        "模型采用省级接壤权重并控制省份固定效应和年份虚拟变量。由于存在空间反馈，β和θ不能直接解释为最终边际效应，需根据偏微分矩阵S＝(I－ρW)⁻¹(βI＋θW)分解为直接效应、间接效应和总效应。")
    test_rows = [[r["检验"].split("：")[0], f"{r['Wald统计量']:.3f}", int(r["自由度"]), f"{r['p值']:.3f}"] for _, r in tests.iterrows()]
    cursor = add_three_line_table(doc, cursor, "表7  空间杜宾模型约束检验",
        ["原假设", "Wald统计量", "自由度", "p值"], test_rows,
        widths=[2.45, 1.1, .7, .7], font_size=8.5,
        note="注：SDM→SAR检验空间滞后解释变量系数是否联合为0；SDM→SEM检验共同因子约束。")
    key_rows = []
    for name, label in [("ln_cum_tfp", "lnTFP"), ("W_ln_cum_tfp", "W×lnTFP"), ("rho", "空间滞后系数ρ")]:
        r = coef[coef["变量"] == name].iloc[0]
        key_rows.append([label, sig(r["系数"], r["p值"]), f"({r['标准误']:.3f})", f"{r['p值']:.3f}"])
    for _, r in impacts.iterrows():
        key_rows.append([r["效应"], sig(r["估计值"], r["p值"]), f"({r['模拟标准误']:.3f})", f"{r['p值']:.3f}"])
    cursor = add_three_line_table(doc, cursor, "表8  空间杜宾模型与TFP效应分解",
        ["变量/效应", "估计值", "标准误", "p值"], key_rows,
        widths=[2.0, 1.0, 1.0, .8], font_size=8.5,
        note="注：效应分解标准误由参数模拟获得；*、**、***分别表示在10%、5%和1%水平上显著。")
    _, cursor = add_paragraph_after(doc, cursor,
        "空间滞后系数ρ为0.216，并在5%水平显著，说明本地高质量发展会受到邻近省份高质量发展水平的正向影响。SDM简化为SEM的共同因子约束在5%水平被拒绝；空间滞后解释变量联合为0的约束在5%水平不能拒绝、但在10%水平被拒绝，因此保留一般SDM并报告偏微分效应，同时对间接效应作保守解释。")
    _, cursor = add_paragraph_after(doc, cursor,
        "TFP的直接效应为0.368且在1%水平显著，总效应为0.665且在1%水平显著，说明农业生产率提高主要通过本地渠道推动高质量发展。间接效应为0.297，但p值为0.164，置信区间包含0，尚不能确认邻近省份TFP对本地高质量发展产生稳定溢出。由此，H3关于高质量发展空间联动的部分得到支持，但关于TFP跨省间接溢出的证据不足。")
    cursor = add_figure(doc, cursor, RESULT / "空间溢出效应" / "空间效应分解森林图.png",
                        "Figure15  农业TFP对高质量发展的空间效应分解")


def insert_threshold(doc):
    threshold = pd.read_csv(RESULT / "空间门槛效应" / "门槛检验结果.csv", encoding="utf-8-sig").iloc[0]
    slopes = pd.read_csv(RESULT / "空间门槛效应" / "门槛区间效应.csv", encoding="utf-8-sig")
    cursor = find_heading(doc, "5.2空间门槛效应")._p
    _, cursor = add_paragraph_after(doc, cursor,
        "农业TFP能否转化为高质量发展可能取决于地区既有经济基础。本文以人均GDP的自然对数作为门槛变量，采用Hansen（1999）面板门槛方法估计单一门槛模型：")
    cursor = add_equation(doc, cursor, "lnYᵢₜ＝β₁lnTFPᵢₜ·I(qᵢₜ≤γ)＋β₂lnTFPᵢₜ·I(qᵢₜ>γ)＋δXᵢₜ＋μᵢ＋λₜ＋εᵢₜ")
    _, cursor = add_paragraph_after(doc, cursor,
        "其中q为ln(人均GDP)，γ为待估门槛。门槛值通过最小化残差平方和确定，显著性采用499次省份层面野聚类Bootstrap检验，门槛置信区间依据似然比统计量LR(γ)≤7.35确定。")
    rows = [["门槛检验", f"{threshold['门槛估计值']:.3f}", f"{threshold['门槛原值_元每人']:.0f}",
             f"[{threshold['95%CI下限']:.3f}, {threshold['95%CI上限']:.3f}]",
             f"{threshold['SupF']:.3f}", f"{threshold['Bootstrap_p值']:.3f}"]]
    for _, r in slopes.iterrows():
        rows.append([r["区间"], "—", "—", "—", sig(r["TFP系数"], r["p值"]), f"{r['p值']:.3f}"])
    cursor = add_three_line_table(doc, cursor, "表9  人均GDP门槛检验及分区间效应",
        ["项目", "ln门槛", "门槛（元/人）", "95%置信区间", "统计量/系数", "p值"], rows,
        widths=[1.35, .72, 1.0, 1.2, 1.0, .65], font_size=7.8,
        note="注：门槛显著性采用499次省份层面野聚类Bootstrap；*、**、***分别表示在10%、5%和1%水平上显著。")
    _, cursor = add_paragraph_after(doc, cursor,
        "门槛估计值为ln(人均GDP)=11.069，对应约64171元/人，原值95%置信区间约为62537—76712元/人。SupF统计量为47.646，Bootstrap p值为0.002，拒绝不存在门槛的原假设。低门槛区间内TFP系数为0.375，在5%水平显著为正；高门槛区间系数为－0.344，但p值为0.133，不能认为其显著为负。更稳妥的解释是：农业TFP对高质量发展的促进作用主要存在于经济基础相对较低阶段，跨过门槛后边际作用明显减弱并失去统计显著性，而不是出现确定的负向作用。H4得到非线性意义上的支持。")
    cursor = add_figure(doc, cursor, RESULT / "空间门槛效应" / "门槛似然比轮廓图.png",
                        "Figure16  人均GDP门槛的似然比轮廓")
    cursor = add_figure(doc, cursor, RESULT / "空间门槛效应" / "门槛区间效应图.png",
                        "Figure17  不同经济发展门槛下的农业TFP效应")


def insert_markov(doc):
    matrix = pd.read_csv(RESULT / "空间马尔科夫链" / "空间条件转移矩阵.csv", encoding="utf-8-sig")
    summary = pd.read_csv(RESULT / "空间马尔科夫链" / "空间马尔科夫汇总.csv", encoding="utf-8-sig")
    cursor = find_heading(doc, "5.3空间马尔科夫链")._p
    _, cursor = add_paragraph_after(doc, cursor,
        "为考察高质量发展状态的动态跃迁及其邻域依赖，本文借鉴Rey（2001）的空间马尔科夫链方法。首先按每年省际分布的四分位数将高质量发展划分为低、中低、中高和高四种相对状态，再将当期邻省加权平均水平按年度三分位数划分为低、中、高三类空间环境。无条件转移概率定义为pᵢⱼ＝nᵢⱼ/nᵢ，空间条件转移概率则为pᵢⱼ|c＝nᵢⱼ|c/nᵢ|c。")
    unconditional = matrix[matrix["空间条件"] == "无条件"]
    piv = unconditional.pivot(index="起始状态", columns="终止状态", values="转移概率").reindex(
        index=["低", "中低", "中高", "高"], columns=["低", "中低", "中高", "高"])
    rows = [[idx] + [f"{100*piv.loc[idx, col]:.2f}%" for col in piv.columns] for idx in piv.index]
    cursor = add_three_line_table(doc, cursor, "表10  高质量发展状态的无条件转移概率",
        ["t期状态", "低", "中低", "中高", "高"], rows,
        widths=[1.15, .85, .85, .85, .85], font_size=8.5,
        note="注：各行转移概率之和为100%；状态按各年度省际四分位数划分。")
    base = summary[summary["空间条件"] == "无条件"].iloc[0]
    _, cursor = add_paragraph_after(doc, cursor,
        f"无条件转移矩阵的主对角线概率分别为96.88%、84.38%、75.00%和87.50%，Shorrocks流动性指数仅为{base['Shorrocks流动性指数']:.4f}，说明省域高质量发展等级具有很强的路径依赖。低状态向中低状态跃迁的概率仅为3.13%，未观察到跨越两个及以上等级的跃迁；高状态保持概率达到87.50%。这意味着低水平省份向上流动困难，同时高水平省份具有较强稳定性。")
    _, cursor = add_paragraph_after(doc, cursor,
        f"空间条件独立性检验的G统计量为{base['空间条件独立性G统计量']:.3f}，999次置换p值为{base['置换p值']:.3f}，在10%水平上呈边际显著、但未通过5%检验。因此邻域环境对状态转移具有提示性而非强证据。具体看，中低状态在高邻域环境下向中高状态跃迁的概率为33.33%，高于低邻域和中邻域下的7.69%；中高状态在高邻域环境下向高状态跃迁的概率为22.22%，也高于低邻域下的0。这与正向空间关联相符，但部分条件单元样本很少，应避免过度解释。总体上，H5关于等级锁定得到较强支持，邻域条件效应仅得到弱支持。")
    cursor = add_figure(doc, cursor, RESULT / "空间马尔科夫链" / "空间马尔科夫转移矩阵.png",
                        "Figure18  高质量发展水平的空间条件转移矩阵")
    cursor = add_figure(doc, cursor, RESULT / "空间马尔科夫链" / "空间状态锁定概率.png",
                        "Figure19  不同空间环境下的状态锁定概率")


def insert_discussion(doc):
    cursor = find_heading(doc, "6讨论与不足")._p
    paragraphs = [
        "本文基于2016—2020年31个省级行政区平衡面板，从分布演变、区域差异、空间依赖、非线性和动态跃迁等维度考察农业TFP与经济高质量发展的关系。研究发现，高质量发展指数在样本期内整体上升且省际差异收敛，而累计农业TFP虽然总体提高，但其省际差异持续扩大。二者呈现不同的分布演进方向，说明农业生产率增长并不会机械地、同步地转化为综合高质量发展。",
        "Dagum分解表明，高质量发展差异主要来自东中西部之间的净差异，但区域间差距呈缩小趋势；累计TFP的区域间净差异则逐渐扩大，且西部内部差异增长明显。这意味着部分西部省份的TFP追赶并不代表整个西部形成同步提升，更可能体现为少数省份的前沿移动、投入收缩或低基期下的累计放大。区域政策因而应从追求单一生产率增速转向提高生产率成果向居民福利、绿色转型、城乡协调和公共服务的转化效率。",
        "空间分析显示，高质量发展具有稳定的正空间相关，长三角形成较连续的高值集聚，部分西部省份表现为低值集聚。空间杜宾模型进一步表明，高质量发展本身存在显著正向空间联动，但农业TFP的间接效应未达到常用显著性水平。由此可见，邻近地区的发展基础、公共治理和市场联系可能具有协同作用，但农业技术效率能否跨省外溢仍取决于技术扩散渠道、要素流动和区域吸收能力。政策上应强化跨区域农技推广、农业社会化服务和基础设施互联，而不能将一般空间相关直接等同于生产率溢出。",
        "门槛结果显示，当人均GDP低于约6.42万元时，TFP提高对高质量发展具有显著促进作用；超过门槛后，估计效应转负但不显著。该结果更符合边际作用递减而非显著负效应：在经济基础较低地区，农业仍占据重要地位，生产率改善能够释放劳动力、提高农业收入并改善资源配置；在较高发展阶段，高质量发展的主要约束可能转向创新能力、现代服务业、生态治理与公共服务，单纯依靠农业TFP难以继续形成同等强度的推动。",
        "空间马尔科夫结果揭示了较强的等级锁定：四类状态的保持概率均较高，低水平省份向上跃迁尤其困难。邻域环境对转移概率仅在10%水平呈边际显著，说明空间环境可能影响跃迁机会，但在短样本下证据仍有限。对于长期处于低值集聚的地区，应通过跨区域基础设施、公共服务均等化、人才和技术流动打破低水平空间均衡；对于高值集聚地区，则需要发挥示范扩散和产业链带动作用。",
        "本文仍存在若干局限。第一，样本仅覆盖2016—2020年，时间维度较短，难以充分识别长期动态、结构突变和政策冲击。第二，DEA—Malmquist投入受数据可得性限制，尚未纳入土地和劳动等核心要素，产出使用当年价农林牧渔业总产值，可能同时受到价格变化和统计口径调整影响。第三，累计TFP以2016年为共同基期，后期差异具有机械累积性质，因此其基尼系数与马尔科夫结果不能解释为绝对生产率水平。",
        "第四，空间权重采用省级接壤矩阵，并将海南与广东桥接，尚未同时考察地理距离、经济距离、交通联系和贸易网络等替代权重。第五，内生性检验使用一期滞后内部工具变量，虽然第一阶段较强，但排除限制无法完全验证，结论仍不能等同于严格因果效应。第六，门槛、局部Moran和空间马尔科夫条件矩阵在31省、5年样本下存在小样本不确定性，多重局部检验也可能增加偶然显著概率。未来研究可扩展更长时期数据，使用价格平减后的农业产出，补充土地、劳动和气候投入，引入历史农业禀赋、政策试点或外生气候冲击等更有说服力的工具变量，并在动态空间面板及多重空间权重下检验结论稳健性。",
    ]
    for text in paragraphs:
        _, cursor = add_paragraph_after(doc, cursor, text)


def remove_redundant_final_page_break(doc):
    """原稿末尾有两个仅由空段落隔开的分页符，会生成整页空白。"""
    paragraphs = list(doc.paragraphs)
    page_break_paragraphs = [
        p for p in paragraphs
        if not p.text.strip() and p._p.xpath('.//w:br[@w:type="page"]')
    ]
    if len(page_break_paragraphs) < 2:
        return
    first = paragraphs.index(page_break_paragraphs[-2])
    second = paragraphs.index(page_break_paragraphs[-1])
    if all(not p.text.strip() for p in paragraphs[first + 1:second]):
        redundant = page_break_paragraphs[-1]._p
        redundant.getparent().remove(redundant)


def main():
    doc = Document(SOURCE)
    insert_dagum(doc)
    insert_moran(doc)
    insert_robustness(doc)
    insert_iv(doc)
    insert_spillover(doc)
    insert_threshold(doc)
    insert_markov(doc)
    insert_discussion(doc)
    remove_redundant_final_page_break(doc)

    # 保留原文版式，仅统一新增内容的孤行控制。
    for p in doc.paragraphs:
        if p.style.name.startswith("Heading"):
            p.paragraph_format.keep_with_next = True
            p.paragraph_format.keep_together = True
    doc.core_properties.title = "农业全要素生产率对经济高质量发展的驱动机制与空间效应（完善版）"
    doc.save(OUTPUT)
    print(f"已保存：{OUTPUT}")
    print(f"段落：{len(doc.paragraphs)}；表格：{len(doc.tables)}；图片：{len(doc.inline_shapes)}")


if __name__ == "__main__":
    main()
