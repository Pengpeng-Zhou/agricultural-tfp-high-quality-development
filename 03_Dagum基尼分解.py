"""对高质量发展指数与累计农业 TFP 进行 Dagum 基尼系数分解。"""

from __future__ import annotations

import os
from itertools import combinations
from pathlib import Path

BASE = Path(__file__).resolve().parent
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(BASE / ".matplotlib-cache"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


DATA_PATH = BASE / "数据" / "新构建分析数据.csv"
OUT_DIR = BASE / "结果" / "Dagum"

REGIONS = {
    "东部": ["北京", "天津", "河北", "辽宁", "上海", "江苏", "浙江", "福建", "山东", "广东", "海南"],
    "中部": ["山西", "吉林", "黑龙江", "安徽", "江西", "河南", "湖北", "湖南"],
    "西部": ["内蒙古", "广西", "重庆", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆"],
}
VARIABLES = {
    "Y：高质量发展指数": "y_clean",
    "X：累计农业TFP": "cum_tfp",
}
REGION_COLORS = {"东部": "#2878B5", "中部": "#F28E2B", "西部": "#59A14F"}
COMPONENT_COLORS = {
    "区域内差异": "#4E79A7",
    "区域间净差异": "#F28E2B",
    "超变密度": "#59A14F",
}


def match_region(province: str) -> str | None:
    for region, names in REGIONS.items():
        if any(name in str(province) for name in names):
            return region
    return None


def gini(values: np.ndarray) -> float:
    """有限样本的未校正基尼：所有有序样本对绝对差的均值除以 2 倍总体均值。"""
    x = np.asarray(values, dtype=float)
    if len(x) == 0 or not np.isfinite(x).all() or np.any(x < 0):
        raise ValueError("Dagum 基尼要求有限的非负样本")
    mean = float(x.mean())
    if mean <= 0:
        return 0.0 if np.allclose(x, 0) else np.nan
    return float(np.abs(x[:, None] - x[None, :]).mean() / (2 * mean))


def decompose_one_year(frame: pd.DataFrame, value_col: str, variable: str, year: int):
    values = frame[value_col].to_numpy(dtype=float)
    overall = gini(values)
    n_total = len(frame)
    mean_total = float(values.mean())

    group_info: dict[str, dict[str, float | np.ndarray]] = {}
    within_rows = []
    within_component = 0.0
    for region in ["东部", "中部", "西部"]:
        group_values = frame.loc[frame["region"] == region, value_col].to_numpy(dtype=float)
        n_group = len(group_values)
        mean_group = float(group_values.mean())
        p_share = n_group / n_total
        income_share = n_group * mean_group / (n_total * mean_total)
        group_gini = gini(group_values)
        contribution = p_share * income_share * group_gini
        group_info[region] = {
            "values": group_values,
            "n": n_group,
            "mean": mean_group,
            "p": p_share,
            "s": income_share,
            "gini": group_gini,
            "contribution": contribution,
        }
        within_component += contribution
        within_rows.append({
            "变量": variable, "年份": year, "区域": region, "省份数": n_group,
            "区域均值": mean_group, "区域内基尼": group_gini,
            "人口份额p_j": p_share, "指标份额s_j": income_share,
            "区域内贡献": contribution,
        })

    pair_rows = []
    net_between = 0.0
    transvariation = 0.0
    for region_a, region_b in combinations(["东部", "中部", "西部"], 2):
        if group_info[region_a]["mean"] >= group_info[region_b]["mean"]:
            high, low = region_a, region_b
        else:
            high, low = region_b, region_a
        high_info, low_info = group_info[high], group_info[low]
        x_high = high_info["values"]
        x_low = low_info["values"]
        diffs = x_high[:, None] - x_low[None, :]
        d_jh = float(np.maximum(diffs, 0).mean())
        p_jh = float(np.maximum(-diffs, 0).mean())
        denominator = d_jh + p_jh
        relative_effect = (d_jh - p_jh) / denominator if denominator > 1e-15 else 0.0
        cross_gini = denominator / (high_info["mean"] + low_info["mean"])
        cross_weight = high_info["p"] * low_info["s"] + low_info["p"] * high_info["s"]
        cross_total = cross_gini * cross_weight
        pair_net = cross_total * relative_effect
        pair_trans = cross_total * (1 - relative_effect)
        net_between += pair_net
        transvariation += pair_trans
        pair_rows.append({
            "变量": variable, "年份": year, "高均值区域j": high, "低均值区域h": low,
            "区域j均值": high_info["mean"], "区域h均值": low_info["mean"],
            "区域间基尼G_jh": cross_gini, "超距一阶矩d_jh": d_jh,
            "超变一阶矩p_jh": p_jh, "相对影响D_jh": relative_effect,
            "区域对总贡献": cross_total, "区域间净差异贡献": pair_net,
            "超变密度贡献": pair_trans,
        })

    reconstructed = within_component + net_between + transvariation
    if overall > 1e-15:
        within_share = within_component / overall
        net_share = net_between / overall
        trans_share = transvariation / overall
    else:
        within_share = net_share = trans_share = np.nan

    decomposition_row = {
        "变量": variable, "年份": year, "样本数": n_total, "总体均值": mean_total,
        "总基尼系数": overall, "区域内差异": within_component,
        "区域间净差异": net_between, "超变密度": transvariation,
        "区域内贡献率": within_share, "区域间净差异贡献率": net_share,
        "超变密度贡献率": trans_share, "分解加总": reconstructed,
        "加总误差": reconstructed - overall,
        "区域均值排序": ">".join(sorted(group_info, key=lambda r: group_info[r]["mean"], reverse=True)),
    }
    return decomposition_row, within_rows, pair_rows


def make_charts(decomposition: pd.DataFrame, within: pd.DataFrame) -> None:
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    variable_order = list(VARIABLES)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    for ax, variable in zip(axes, variable_order):
        part = decomposition[decomposition["变量"] == variable]
        ax.plot(part["年份"], part["总基尼系数"], marker="o", linewidth=2.4, color="#333333")
        for x, y in zip(part["年份"], part["总基尼系数"]):
            ax.annotate(f"{y:.3f}", (x, y), xytext=(0, 8), textcoords="offset points", ha="center")
        ax.set_title(variable)
        ax.set_xlabel("年份")
        ax.set_ylabel("Dagum 总基尼系数")
        ax.set_xticks(part["年份"])
        ax.set_ylim(bottom=0)
    fig.suptitle("2016—2020 年总体差异演变", fontsize=16)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "Dagum_总基尼系数趋势.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    component_columns = ["区域内差异", "区域间净差异", "超变密度"]
    for ax, variable in zip(axes, variable_order):
        part = decomposition[decomposition["变量"] == variable].set_index("年份")
        bottom = np.zeros(len(part))
        for component in component_columns:
            values = part[component].to_numpy()
            ax.bar(part.index, values, bottom=bottom, label=component,
                   color=COMPONENT_COLORS[component], width=0.65)
            bottom += values
        ax.plot(part.index, part["总基尼系数"], color="#222222", marker="o",
                linewidth=1.8, label="总基尼")
        ax.set_title(variable)
        ax.set_xlabel("年份")
        ax.set_ylabel("基尼系数贡献值")
        ax.set_xticks(part.index)
        ax.legend(fontsize=9)
    fig.suptitle("Dagum 基尼系数来源分解", fontsize=16)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "Dagum_差异来源分解.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    share_columns = ["区域内贡献率", "区域间净差异贡献率", "超变密度贡献率"]
    share_labels = ["区域内差异", "区域间净差异", "超变密度"]
    for ax, variable in zip(axes, variable_order):
        part = decomposition[decomposition["变量"] == variable].set_index("年份")
        bottom = np.zeros(len(part))
        for column, label in zip(share_columns, share_labels):
            values = part[column].fillna(0).to_numpy() * 100
            ax.bar(part.index, values, bottom=bottom, label=label,
                   color=COMPONENT_COLORS[label], width=0.65)
            bottom += values
        if variable == "X：累计农业TFP":
            ax.annotate("2016年为共同基期，总差异为0", xy=(2016, 0), xytext=(8, 18),
                        textcoords="offset points", fontsize=9)
        ax.set_title(variable)
        ax.set_xlabel("年份")
        ax.set_ylabel("贡献率（%）")
        ax.set_xticks(part.index)
        ax.set_ylim(0, 105)
        ax.legend(fontsize=9)
    fig.suptitle("Dagum 差异来源贡献率", fontsize=16)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "Dagum_差异来源贡献率.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for ax, variable in zip(axes, variable_order):
        part = within[within["变量"] == variable]
        for region in ["东部", "中部", "西部"]:
            group = part[part["区域"] == region]
            ax.plot(group["年份"], group["区域内基尼"], marker="o", linewidth=2.2,
                    color=REGION_COLORS[region], label=region)
        ax.set_title(variable)
        ax.set_xlabel("年份")
        ax.set_ylabel("区域内基尼系数")
        ax.set_xticks(sorted(part["年份"].unique()))
        ax.set_ylim(bottom=0)
        ax.legend()
    fig.suptitle("东中西部区域内差异演变", fontsize=16)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "Dagum_区域内基尼趋势.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    required = {"province", "year", *VARIABLES.values()}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"缺少必要字段：{sorted(missing)}")
    if df[["province", "year"]].duplicated().any():
        raise ValueError("省份—年份键存在重复")
    df["region"] = df["province"].map(match_region)
    if df["region"].isna().any():
        raise ValueError(f"未匹配区域：{sorted(df.loc[df['region'].isna(), 'province'].unique())}")

    decomposition_rows, within_rows, pair_rows = [], [], []
    for variable, value_col in VARIABLES.items():
        for year, yearly in df.groupby("year"):
            row, groups, pairs = decompose_one_year(yearly, value_col, variable, int(year))
            decomposition_rows.append(row)
            within_rows.extend(groups)
            pair_rows.extend(pairs)

    decomposition = pd.DataFrame(decomposition_rows)
    within = pd.DataFrame(within_rows)
    pairs = pd.DataFrame(pair_rows)
    max_error = float(decomposition["加总误差"].abs().max())
    if max_error > 1e-12:
        raise AssertionError(f"Dagum 分解加总未通过校验，最大误差={max_error}")

    decomposition.to_csv(OUT_DIR / "Dagum_年度分解结果.csv", index=False, encoding="utf-8-sig")
    within.to_csv(OUT_DIR / "Dagum_区域内结果.csv", index=False, encoding="utf-8-sig")
    pairs.to_csv(OUT_DIR / "Dagum_区域对分解结果.csv", index=False, encoding="utf-8-sig")
    make_charts(decomposition, within)

    print("Dagum 基尼系数分解完成。")
    print(f"最大加总误差：{max_error:.3e}")
    print(f"输出目录：{OUT_DIR}")
    print(decomposition[["变量", "年份", "总基尼系数", "区域内贡献率",
                         "区域间净差异贡献率", "超变密度贡献率"]].to_string(index=False))


if __name__ == "__main__":
    main()
