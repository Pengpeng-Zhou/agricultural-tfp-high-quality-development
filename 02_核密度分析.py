"""2016—2020 年高质量发展指数与累计农业 TFP 的核密度分析。"""

from pathlib import Path
import os
import warnings

BASE = Path(__file__).resolve().parent
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(BASE / ".matplotlib-cache"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore", category=FutureWarning)

DATA_PATH = BASE / "数据" / "新构建分析数据.csv"
OUT_DIR = BASE / "结果" / "核密度"

REGIONS = {
    "东部": ["北京", "天津", "河北", "辽宁", "上海", "江苏", "浙江", "福建", "山东", "广东", "海南"],
    "中部": ["山西", "吉林", "黑龙江", "安徽", "江西", "河南", "湖北", "湖南"],
    "西部": ["内蒙古", "广西", "重庆", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆"],
}
REGION_COLORS = {"东部": "#2878B5", "中部": "#F28E2B", "西部": "#59A14F"}
YEAR_COLORS = sns.color_palette("viridis", 5)


def match_region(province: str) -> str | None:
    for region, names in REGIONS.items():
        if any(name in str(province) for name in names):
            return region
    return None


def padded_limits(values: pd.Series, lower_bound: float | None = None) -> tuple[float, float]:
    low, high = float(values.min()), float(values.max())
    span = high - low
    # 为 KDE 在样本极值之外自然衰减预留空间，避免只显示峰尖周围。
    pad = max(span * 0.30, abs(high) * 0.04, 0.04)
    left, right = low - pad, high + pad
    if lower_bound is not None:
        left = max(lower_bound, left)
    return left, right


def draw_density(series: pd.Series, label: str, color: str, *, baseline_note: bool = False,
                 clip: tuple[float | None, float | None] | None = None) -> None:
    values = series.dropna().astype(float)
    if len(values) < 2:
        return
    if values.nunique() == 1:
        x = float(values.iloc[0])
        plt.axvline(x, color=color, linewidth=2.2, linestyle="--", label=f"{label}（基期={x:g}）")
        if baseline_note:
            plt.annotate("基期各省均为 1，无法估计核密度", xy=(x, 0), xytext=(8, 22),
                         textcoords="offset points", color=color, fontsize=9)
        return
    sns.kdeplot(values, label=label, linewidth=2.3, color=color, bw_adjust=1.0,
                cut=3, clip=clip, common_norm=False)


def finish_plot(filename: str, xlabel: str, title: str, limits: tuple[float, float]) -> None:
    plt.xlabel(xlabel, fontsize=12)
    plt.ylabel("核密度", fontsize=12)
    plt.title(title, fontsize=14)
    plt.xlim(*limits)
    plt.grid(alpha=0.25)
    plt.legend(frameon=True)
    plt.tight_layout()
    plt.savefig(OUT_DIR / filename, dpi=300, bbox_inches="tight")
    plt.close()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"未找到分析数据：{DATA_PATH}")

    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    required = {"province", "year", "y_clean", "cum_tfp"}
    missing_columns = required.difference(df.columns)
    if missing_columns:
        raise ValueError(f"数据缺少必要列：{sorted(missing_columns)}")
    df["year"] = pd.to_numeric(df["year"], errors="raise").astype(int)
    if df[["province", "year"]].duplicated().any():
        raise ValueError("省份—年份键存在重复")
    if df[list(required)].isna().any().any():
        raise ValueError("核密度所需字段存在缺失值")

    df["region"] = df["province"].map(match_region)
    unmatched = sorted(df.loc[df["region"].isna(), "province"].unique())
    if unmatched:
        raise ValueError(f"以下省份未匹配区域：{unmatched}")
    years = sorted(df["year"].unique())
    if years != [2016, 2017, 2018, 2019, 2020]:
        raise ValueError(f"预期年份为 2016—2020，实际为：{years}")

    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    y_limits = padded_limits(df["y_clean"], lower_bound=0)
    x_limits = padded_limits(df["cum_tfp"], lower_bound=0)

    plt.figure(figsize=(11, 6.5))
    for color, year in zip(YEAR_COLORS, years):
        draw_density(df.loc[df["year"] == year, "y_clean"], str(year), color, clip=(0, 1))
    finish_plot("KDE_Y_2016_2020_年份叠加.png", "高质量发展综合指数（y_clean）",
                "2016—2020 年高质量发展指数核密度", y_limits)

    plt.figure(figsize=(11, 6.5))
    for color, year in zip(YEAR_COLORS, years):
        draw_density(df.loc[df["year"] == year, "cum_tfp"], str(year), color,
                     baseline_note=(year == 2016), clip=(0, None))
    finish_plot("KDE_X_TFP_2016_2020_年份叠加.png", "累计农业 TFP（2016=1）",
                "2016—2020 年累计农业 TFP 核密度", x_limits)

    for year in years:
        yearly = df[df["year"] == year]
        plt.figure(figsize=(10, 6))
        for region in ["东部", "中部", "西部"]:
            draw_density(yearly.loc[yearly["region"] == region, "y_clean"], region,
                         REGION_COLORS[region], clip=(0, 1))
        finish_plot(f"KDE_Y_{year}_分区域.png", "高质量发展综合指数（y_clean）",
                    f"{year} 年高质量发展指数区域核密度", y_limits)

        plt.figure(figsize=(10, 6))
        for region in ["东部", "中部", "西部"]:
            draw_density(yearly.loc[yearly["region"] == region, "cum_tfp"], region,
                         REGION_COLORS[region], baseline_note=(year == 2016 and region == "东部"),
                         clip=(0, None))
        finish_plot(f"KDE_X_TFP_{year}_分区域.png", "累计农业 TFP（2016=1）",
                    f"{year} 年累计农业 TFP 区域核密度", x_limits)

    summary = (df.groupby(["year", "region"], observed=True)
                 .agg(省份数=("province", "nunique"), Y均值=("y_clean", "mean"),
                      Y标准差=("y_clean", "std"), TFP均值=("cum_tfp", "mean"),
                      TFP标准差=("cum_tfp", "std"))
                 .reset_index())
    national = (df.groupby("year")
                   .agg(省份数=("province", "nunique"), Y均值=("y_clean", "mean"),
                        Y标准差=("y_clean", "std"), TFP均值=("cum_tfp", "mean"),
                        TFP标准差=("cum_tfp", "std"))
                   .reset_index())
    national.insert(1, "region", "全国")
    stats_path = OUT_DIR / "核密度配套描述统计.csv"
    try:
        pd.concat([national, summary], ignore_index=True).to_csv(
            stats_path, index=False, encoding="utf-8-sig")
        stats_message = "1 份描述统计"
    except PermissionError:
        # Windows 下文件若正在 Excel 中打开会被锁定；绘图不应因此判定失败。
        stats_message = "描述统计文件正被占用，已保留原文件"

    outputs = sorted(OUT_DIR.glob("*.png"))
    print(f"完成：{len(outputs)} 张 PNG 图；{stats_message}。")
    print(f"样本：{len(df)} 行，{df['province'].nunique()} 省，年份 {years[0]}—{years[-1]}。")
    print(f"输出目录：{OUT_DIR}")


if __name__ == "__main__":
    main()
