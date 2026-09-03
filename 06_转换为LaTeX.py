from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pypandoc


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "全要素生产率对经济高质量发展的作用与路径_完善版.docx"
PROJECT_DIR_NAME = "全要素生产率对经济高质量发展的作用与路径_调整版"
PROJECT_NAME = "thesis_adjusted"
OUTDIR = ROOT / PROJECT_DIR_NAME
BODY = OUTDIR / "body_pandoc.tex"
TEX = OUTDIR / f"{PROJECT_NAME}.tex"


PREAMBLE = r"""\documentclass[UTF8,a4paper,12pt,fontset=windows]{ctexart}
\usepackage[left=2.7cm,right=2.7cm,top=2.5cm,bottom=2.5cm]{geometry}
\usepackage{fontspec}
\setmainfont{Times New Roman}
\usepackage{amsmath,amssymb,mathtools,bm}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{booktabs,longtable,array,multirow,calc}
\usepackage{caption}
\usepackage{float}
\usepackage{setspace}
\usepackage{etoolbox}
\usepackage{titlesec}
\usepackage{url}
\usepackage[hidelinks]{hyperref}

\newcommand{\real}[1]{#1}
\newcounter{none}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\providecommand{\pandocbounded}[1]{#1}
\newcommand{\hl}[1]{#1}
\setcounter{secnumdepth}{-1}
\setlength{\parindent}{2em}
\setlength{\parskip}{0.25em}
\setlength{\tabcolsep}{4pt}
\renewcommand{\arraystretch}{1.18}
\setstretch{1.45}
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\AtBeginEnvironment{longtable}{\small\setstretch{1.12}}
\captionsetup{font=small,labelformat=empty,justification=centering}
\titleformat{\paragraph}[block]{\large\bfseries}{}{0pt}{}
\titlespacing*{\paragraph}{0pt}{1.25ex}{0.6ex}
\ctexset{
  section={format=\Large\bfseries,beforeskip=1.8ex,afterskip=1.0ex},
  subsection={format=\large\bfseries,beforeskip=1.5ex,afterskip=0.8ex},
  subsubsection={format=\normalsize\bfseries,beforeskip=1.2ex,afterskip=0.6ex}
}
\emergencystretch=3em

\begin{document}
\pagestyle{plain}
\begin{center}
  {\zihao{2}\bfseries 农业全要素生产率对经济高质量发展的驱动\par}
  \vspace{0.8em}
  {\zihao{2}\bfseries 机制与空间效应\par}
\end{center}
\vspace{1.5em}
\noindent\textbf{摘要：}\par
\noindent\textbf{关键词：}\par
\vspace{1em}
"""


POSTAMBLE = "\n\\end{document}\n"


DISPLAY_REPLACEMENTS = {
    r"\[TFP_{it}：第i省第t年的累计全要素生产率\left. (以2016年为基期 \right.)。\]":
        r"\noindent \(TFP_{it}\)：第i省第t年的累计全要素生产率（以2016年为基期）。",
    r"\[TFP_{\min},TFP_{\max}：全样本中TFP的最小值和最大值\left. (跨年份,跨省份 \right.)\]":
        r"\noindent \(TFP_{\min},TFP_{\max}\)：全样本中TFP的最小值和最大值（跨年份、跨省份）。",
    r"\[a:常数项\]": r"\noindent \(a\)：常数项",
    "G＝{[}ΣⱼΣₕΣᵢΣᵣ\\textbar xⱼᵢ－xₕᵣ\\textbar{]}／(2n²x̄)":
        r"\[G=\frac{\sum_j\sum_h\sum_i\sum_r\lvert x_{ji}-x_{hr}\rvert}{2n^2\bar{x}}\]",
    "G＝Gw＋Gnb＋Gt": r"\[G=G_w+G_{nb}+G_t\]",
    "Gw＝ΣⱼGⱼⱼpⱼsⱼ": r"\[G_w=\sum_j G_{jj}p_js_j\]",
    "Gnb＝Σⱼ\\textgreater ₕGⱼₕDⱼₕ(pⱼsₕ＋pₕsⱼ)":
        r"\[G_{nb}=\sum_{j>h}G_{jh}D_{jh}(p_js_h+p_hs_j)\]",
    "Gt＝Σⱼ\\textgreater ₕGⱼₕ(1－Dⱼₕ)(pⱼsₕ＋pₕsⱼ)":
        r"\[G_t=\sum_{j>h}G_{jh}(1-D_{jh})(p_js_h+p_hs_j)\]",
    "I＝{[}n／S₀{]}·{[}ΣᵢΣⱼwᵢⱼ(xᵢ－x̄)(xⱼ－x̄){]}／{[}Σᵢ(xᵢ－x̄)²{]}":
        r"\[I=\frac{n}{S_0}\frac{\sum_i\sum_jw_{ij}(x_i-\bar{x})(x_j-\bar{x})}{\sum_i(x_i-\bar{x})^2}\]",
    "Iᵢ＝zᵢΣⱼwᵢⱼzⱼ": r"\[I_i=z_i\sum_jw_{ij}z_j\]",
    "第一阶段：lnTFPᵢₜ＝πlnTFPᵢ,ₜ₋₁＋γXᵢₜ＋μᵢ＋λₜ＋νᵢₜ":
        r"\[\text{第一阶段：}\quad \ln TFP_{it}=\pi\ln TFP_{i,t-1}+\gamma X_{it}+\mu_i+\lambda_t+\nu_{it}\]",
    "第二阶段：lnYᵢₜ＝βlnTFP̂ᵢₜ＋δXᵢₜ＋μᵢ＋λₜ＋εᵢₜ":
        r"\[\text{第二阶段：}\quad \ln Y_{it}=\beta\widehat{\ln TFP}_{it}+\delta X_{it}+\mu_i+\lambda_t+\varepsilon_{it}\]",
    "lnYᵢₜ＝ρΣⱼwᵢⱼlnYⱼₜ＋βlnTFPᵢₜ＋θΣⱼwᵢⱼlnTFPⱼₜ＋γXᵢₜ＋ηWXᵢₜ＋μᵢ＋λₜ＋εᵢₜ":
        r"\[\ln Y_{it}=\rho\sum_jw_{ij}\ln Y_{jt}+\beta\ln TFP_{it}+\theta\sum_jw_{ij}\ln TFP_{jt}+\gamma X_{it}+\eta WX_{it}+\mu_i+\lambda_t+\varepsilon_{it}\]",
    "lnYᵢₜ＝β₁lnTFPᵢₜ·I(qᵢₜ≤γ)＋β₂lnTFPᵢₜ·I(qᵢₜ\\textgreater γ)＋δXᵢₜ＋μᵢ＋λₜ＋εᵢₜ":
        r"\[\ln Y_{it}=\beta_1\ln TFP_{it}\,\mathbf{1}(q_{it}\leq\gamma)+\beta_2\ln TFP_{it}\,\mathbf{1}(q_{it}>\gamma)+\delta X_{it}+\mu_i+\lambda_t+\varepsilon_{it}\]",
}


INLINE_REPLACEMENTS = {
    "xⱼᵢ": r"\(x_{ji}\)",
    "xₕᵣ": r"\(x_{hr}\)",
    "x̄": r"\(\bar{x}\)",
    "pⱼ＝nⱼ／n": r"\(p_j=n_j/n\)",
    "sⱼ＝nⱼx̄ⱼ／(nx̄)": r"\(s_j=n_j\bar{x}_j/(n\bar{x})\)",
    "Gⱼⱼ": r"\(G_{jj}\)",
    "Gⱼₕ": r"\(G_{jh}\)",
    "Dⱼₕ＝(dⱼₕ－pⱼₕ)/(dⱼₕ＋pⱼₕ)": r"\(D_{jh}=(d_{jh}-p_{jh})/(d_{jh}+p_{jh})\)",
    "dⱼₕ": r"\(d_{jh}\)",
    "pⱼₕ": r"\(p_{jh}\)",
    "wᵢⱼ": r"\(w_{ij}\)",
    "S₀＝ΣᵢΣⱼwᵢⱼ": r"\(S_0=\sum_i\sum_jw_{ij}\)",
    "zᵢ": r"\(z_i\)",
    "S＝(I－ρW)⁻¹(βI＋θW)": r"\(S=(I-\rho W)^{-1}(\beta I+\theta W)\)",
    "pᵢⱼ＝nᵢⱼ/nᵢ": r"\(p_{ij}=n_{ij}/n_i\)",
    "pᵢⱼ\\textbar c＝nᵢⱼ\\textbar c/nᵢ\\textbar c": r"\(p_{ij\mid c}=n_{ij\mid c}/n_{i\mid c}\)",
}


def convert_with_pandoc() -> str:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    pandoc = pypandoc.get_pandoc_path()
    cmd = [
        pandoc,
        str(SOURCE.resolve()),
        "--from=docx",
        "--to=latex",
        "--extract-media=media",
        "--wrap=none",
        "--output=body_pandoc.tex",
    ]
    subprocess.run(cmd, cwd=OUTDIR, check=True)
    return BODY.read_text(encoding="utf-8")


def figure_environment(include: str, caption: str | None) -> str:
    path_match = re.search(r"\{([^{}]+)\}\s*$", include.strip())
    if not path_match:
        raise ValueError(f"无法解析图片路径：{include}")
    path = path_match.group(1)
    cap = caption or ""
    return (
        "\\begin{figure}[htbp]\n"
        "\\centering\n"
        f"\\includegraphics[width=\\linewidth,height=0.82\\textheight,keepaspectratio]{{{path}}}\n"
        f"\\caption*{{{cap}}}\n"
        "\\end{figure}\n"
    )


def restore_one_cell_figures(text: str) -> str:
    pattern = re.compile(
        r"(?ms)^(?:\{\\def\\LTcaptype\{none\}[^\n]*\n)?"
        r"\\begin\{longtable\}.*?^\\end\{longtable\}\s*\n(?:^\}\s*\n)?"
    )
    figures: dict[int, tuple[str, str | None]] = {}
    next_id = 0

    def replace_block(match: re.Match[str]) -> str:
        nonlocal next_id
        block = match.group(0)
        includes = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{[^{}]+\}", block)
        unique_includes = list(dict.fromkeys(includes))
        if len(unique_includes) != 1:
            return block
        cap_match = re.search(r"\\caption\{(Figure\d+[^{}]*)\}\\tabularnewline", block)
        figures[next_id] = (unique_includes[0], cap_match.group(1).strip() if cap_match else None)
        token = f"\n%%FIGURE_BLOCK_{next_id}%%\n"
        next_id += 1
        return token

    tokenized = pattern.sub(replace_block, text)
    token_re = re.compile(r"%%FIGURE_BLOCK_(\d+)%%")
    pieces = token_re.split(tokenized)
    out: list[str] = []
    pending: tuple[str, str | None] | None = None
    i = 0
    while i < len(pieces):
        if i % 2 == 1:
            current = figures[int(pieces[i])]
            if current[1] and pending:
                out.append(figure_environment(pending[0], current[1]))
                pending = None
            pending = (current[0], None if current[1] else current[1])
            i += 1
            continue

        chunk = pieces[i]
        if pending:
            lines = chunk.splitlines(keepends=True)
            consumed = False
            for line_idx, line in enumerate(lines):
                stripped = line.strip()
                if not stripped:
                    continue
                if re.fullmatch(r"Figure\d+\s+.+", stripped):
                    out.append(figure_environment(pending[0], stripped))
                    pending = None
                    lines[line_idx] = ""
                    consumed = True
                break
            if pending and any(line.strip() for line in lines):
                out.append(figure_environment(pending[0], pending[1]))
                pending = None
            out.append("".join(lines))
            if consumed:
                pass
        else:
            out.append(chunk)
        i += 1
    if pending:
        out.append(figure_environment(pending[0], pending[1]))
    return "".join(out)


def polish_latex(text: str) -> str:
    section_pos = text.find("\\section{1引言}")
    if section_pos < 0:
        raise ValueError("未找到正文起始标题“1引言”")
    text = text[section_pos:]
    text = restore_one_cell_figures(text)
    text = re.sub(
        r"(?ms)^\{\\def\\LTcaptype\{none\}[^\n]*\n"
        r"(\\begin\{longtable\}.*?^\\end\{longtable\})\s*\n^\}\s*$",
        r"\1",
        text,
    )
    text = re.sub(r"\\hl\{([^{}]*)\}", r"\1", text)
    for old in sorted(DISPLAY_REPLACEMENTS, key=len, reverse=True):
        text = text.replace(old, DISPLAY_REPLACEMENTS[old])
    for old in sorted(INLINE_REPLACEMENTS, key=len, reverse=True):
        text = text.replace(old, INLINE_REPLACEMENTS[old])
    text = re.sub(
        r"\\\[TFP_\{it\}：.*?\\\]",
        r"\\noindent \\(TFP_{it}\\)：第i省第t年的累计全要素生产率（以2016年为基期）。",
        text,
        flags=re.S,
    )
    text = re.sub(
        r"\\\[TFP_\{\\min\},TFP_\{\\max\}：.*?\\\]",
        r"\\noindent \\(TFP_{\\min},TFP_{\\max}\\)：全样本中TFP的最小值和最大值（跨年份、跨省份）。",
        text,
        flags=re.S,
    )
    text = text.replace(r"\[a:常数项\]", r"\noindent \(a\)：常数项")
    for old, new in {
        "①": "（1）", "②": "（2）", "③": "（3）", "④": "（4）",
        "⑤": "（5）", "⑥": "（6）", "𝑖": "i", "𝑗": "j",
    }.items():
        text = text.replace(old, new)

    def clean_math(match: re.Match[str]) -> str:
        block = match.group(0)
        block = block.replace("（", "(").replace("）", ")").replace("、", ",")
        block = block.replace("满足", r"\text{满足}")
        block = block.replace("∈", r"\in")
        block = re.sub(r"\\#\\left\.\s*\((\d+)\s*\\right\.\)", r"\\qquad(\1)", block)
        block = re.sub(r"\\#\((\d+)\)", r"\\qquad(\1)", block)
        block = block.replace(r"\#", "")
        return block

    text = re.sub(r"\\\[.*?\\\]", clean_math, text, flags=re.S)
    text = re.sub(r"\\\(.*?\\\)", clean_math, text, flags=re.S)
    text = text.replace("∈", r"\(\in\)")
    text = text.replace("2016‑2020", "2016--2020")
    text = text.replace("\u00a0", "~")
    return PREAMBLE + text.strip() + POSTAMBLE


def write_readme() -> None:
    readme = OUTDIR / "README_编译说明.txt"
    readme.write_text(
        "本目录为论文LaTeX调整版。\n\n"
        f"主文件：{PROJECT_NAME}.tex\n"
        f"预览文件：{PROJECT_NAME}.pdf\n"
        "图片目录：media/media\n\n"
        "推荐编译命令：\n"
        f"latexmk -xelatex \"{PROJECT_NAME}.tex\"\n\n"
        "编译引擎必须使用 XeLaTeX，以支持中文和原文中的数学符号。\n",
        encoding="utf-8-sig",
    )


def main() -> None:
    body = convert_with_pandoc()
    final = polish_latex(body)
    TEX.write_text(final, encoding="utf-8")
    write_readme()
    print(f"LaTeX主文件：{TEX}")
    print(f"图片数量：{sum(1 for p in (OUTDIR / 'media').rglob('*') if p.is_file())}")


if __name__ == "__main__":
    main()
