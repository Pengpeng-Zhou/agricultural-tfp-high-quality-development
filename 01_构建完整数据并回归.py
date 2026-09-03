from __future__ import annotations

"""
从压缩包随附的原始 Excel 表重建 2016—2020 年 31 省平衡面板，
按同学原方案的五项投入重算 DEA—Malmquist 累计 TFP，并估计主回归。

主要修正：
1. 按《大体思路》的分组构造 Y。
2. 用控制变量表中的逐年城镇化率替换原表内按省不变的 IPR。
3. WEI 同样按省不变，但随包材料没有可靠的逐年替代值，因此不进入修正后 Y。
4. Y 的标准化区间和权重只用实际回归期 2016—2020 年计算。
5. 保留原五投入 TFP：机械动力、化肥、塑料薄膜、柴油、农药。
6. 主回归为省份+年份双向固定效应，标准误按省聚类，p值使用 t(30)。

运行：
    python3 01_构建完整数据并回归.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.stats import t as student_t


PACKAGE = Path(__file__).resolve().parent
RAW = PACKAGE / "数据" / "原始数据_只读副本"
DATA_OUT = PACKAGE / "数据"
RESULT_OUT = PACKAGE / "结果"

START_YEAR = 2016
END_YEAR = 2020

DIRECTIONS = {
    "PCGDP": "pos",
    "PCRS": "pos",
    "FSR": "pos",
    "TIG": "pos",
    "HBTP": "pos",
    "GCR": "pos",
    "URBAN_REPLACEMENT": "pos",
    "RUUR": "neg",
    "PCURA": "pos",
    "PTVP": "pos",
    "SDEI": "neg",
    "EPES": "neg",
    "HESP": "pos",
    "UGPR": "pos",
    "UWPR": "pos",
}

# 按项目文档修正后的一级指标分组。
GROUPS = {
    "经济运行质效": ["PCGDP", "PCRS", "TIG", "HBTP"],
    "政府治理质效": ["FSR", "GCR"],
    "城乡区域均衡": ["URBAN_REPLACEMENT", "RUUR", "PCURA", "PTVP"],
    "生态绿色可持续": ["SDEI", "EPES"],
    "居民民生福祉": ["HESP", "UGPR", "UWPR"],
}

DEA_FILES = {
    "machinery": ("各省农业机械总动力_2007-2024.xlsx", "农业机械总动力(万千瓦)"),
    "fertilizer": ("各省农用化肥施用量_2007-2024.xlsx", "农用化肥施用量(万吨)"),
    "plastic_film": ("各省农用塑料薄膜使用量_2007-2024.xlsx", "农用塑料薄膜使用量(万吨)"),
    "diesel": ("各省农用柴油使用量_2007-2024.xlsx", "农用柴油使用量(万吨)"),
    "pesticide": ("各省农药使用量_2007-2024.xlsx", "农药使用量(万吨)"),
    "output_nominal": ("各省农林牧渔业总产值_2007-2024.xlsx", "农林牧渔业总产值(亿元)"),
}

INPUTS = ["machinery", "fertilizer", "plastic_film", "diesel", "pesticide"]


def minmax_normalize(frame: pd.DataFrame) -> pd.DataFrame:
    """指标方向化后的0—1全样本极差标准化。"""
    result = pd.DataFrame(index=frame.index)
    for column in frame.columns:
        low = frame[column].min()
        high = frame[column].max()
        if high == low:
            result[column] = 0.5
        elif DIRECTIONS.get(column, "pos") == "pos":
            result[column] = (frame[column] - low) / (high - low)
        else:
            result[column] = (high - frame[column]) / (high - low)
    return result


def critic_spearman_entropy(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """附件原代码实际执行的“熵差异系数×Spearman冲突度”混合权重。"""
    shifted = frame + 1e-12
    proportions = shifted.div(shifted.sum(axis=0), axis=1)
    n_obs = len(shifted)
    entropy = -(1 / np.log(n_obs)) * np.sum(
        proportions * np.log(proportions + 1e-20), axis=0
    )
    dispersion = 1 - np.nan_to_num(entropy)
    spearman = frame.corr(method="spearman")
    conflict = (1 - spearman).sum(axis=0)
    information = dispersion * conflict
    weights = information / information.sum()
    scores = (frame * weights).sum(axis=1)
    return weights, scores


def build_y() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw_all = pd.read_excel(RAW / "Y原始指标_data_for_res.xlsx", sheet_name="RAW_DATA")
    raw = raw_all[raw_all["YEAR"].between(START_YEAR, END_YEAR)].copy()

    controls = pd.read_excel(RAW / "控制变量.xlsx", sheet_name="控制变量")
    controls = controls.rename(
        columns={"year": "YEAR", "id": "REGION", "城镇化率": "urban_rate"}
    )[["REGION", "YEAR", "urban_rate"]]
    controls = controls[controls["YEAR"].between(START_YEAR, END_YEAR)]
    raw = raw.merge(controls, on=["REGION", "YEAR"], validate="one_to_one")
    raw["URBAN_REPLACEMENT"] = raw["urban_rate"] * 100

    level_one = raw[["REGION", "YEAR"]].copy()
    weight_rows: list[dict[str, object]] = []
    normalized_parts = raw[["REGION", "YEAR"]].copy()
    for group, indicators in GROUPS.items():
        normalized = minmax_normalize(raw[indicators])
        weights, score = critic_spearman_entropy(normalized)
        level_one[group] = score
        for indicator in indicators:
            normalized_parts[f"norm_{indicator}"] = normalized[indicator]
            weight_rows.append(
                {"权重层级": "二级指标", "所属一级指标": group, "指标": indicator, "权重": weights[indicator]}
            )

    normalized_level_one = minmax_normalize(level_one[list(GROUPS)])
    final_weights, final_score = critic_spearman_entropy(normalized_level_one)
    for group in GROUPS:
        weight_rows.append(
            {"权重层级": "一级指标", "所属一级指标": "全部", "指标": group, "权重": final_weights[group]}
        )
    outcome = raw[["REGION", "YEAR"]].copy()
    outcome["Y_clean_with_urban"] = final_score
    return outcome, pd.DataFrame(weight_rows), raw, level_one.merge(
        outcome, on=["REGION", "YEAR"], validate="one_to_one"
    )


def load_long_indicator(filename: str, value_column: str, short_name: str) -> pd.DataFrame:
    frame = pd.read_excel(RAW / filename, sheet_name="长格式")
    if value_column not in frame.columns:
        raise KeyError(f"{filename} 中缺少列 {value_column}")
    frame = frame.rename(columns={"地区": "省份", "年份": "年份", value_column: short_name})
    return frame[["省份", "年份", short_name]]


def load_dea_panel() -> pd.DataFrame:
    panel: pd.DataFrame | None = None
    for short_name, (filename, value_column) in DEA_FILES.items():
        current = load_long_indicator(filename, value_column, short_name)
        panel = current if panel is None else panel.merge(
            current, on=["省份", "年份"], how="outer", validate="one_to_one"
        )
    assert panel is not None
    panel = panel[panel["年份"].between(START_YEAR, END_YEAR)].copy()
    panel = panel.sort_values(["省份", "年份"]).reset_index(drop=True)
    needed = ["output_nominal"] + INPUTS
    if panel[needed].isna().any().any():
        missing = panel.loc[panel[needed].isna().any(axis=1), ["省份", "年份"] + needed]
        raise ValueError(f"2016—2020 DEA数据存在缺失:\n{missing}")
    if (panel[needed] <= 0).any().any():
        raise ValueError("DEA投入或产出存在非正值")
    return panel


def distance_output_crs(
    reference_x: np.ndarray,
    reference_y: np.ndarray,
    target_x: np.ndarray,
    target_y: float,
) -> float:
    """产出导向、规模报酬不变（CRS）的输出距离函数。"""
    n_reference = len(reference_y)
    objective = np.zeros(n_reference + 1)
    objective[-1] = -1.0
    constraints: list[np.ndarray] = []
    bounds: list[float] = []

    output_constraint = np.zeros(n_reference + 1)
    output_constraint[:n_reference] = -reference_y
    output_constraint[-1] = target_y
    constraints.append(output_constraint)
    bounds.append(0.0)

    for column in range(reference_x.shape[1]):
        input_constraint = np.zeros(n_reference + 1)
        input_constraint[:n_reference] = reference_x[:, column]
        constraints.append(input_constraint)
        bounds.append(target_x[column])

    result = linprog(
        objective,
        A_ub=np.asarray(constraints),
        b_ub=np.asarray(bounds),
        bounds=[(0, None)] * (n_reference + 1),
        method="highs",
    )
    if not result.success or result.x[-1] <= 1e-10:
        return np.nan
    return 1.0 / result.x[-1]


def calculate_malmquist(dea_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    working = dea_panel[["省份", "年份", "output_nominal"] + INPUTS].copy()
    # 每列只除以一个全样本常数，不改变DEA距离，仅改善数值稳定性。
    for column in ["output_nominal"] + INPUTS:
        working[column] = working[column] / working[column].mean()

    years = sorted(working["年份"].unique())
    references: dict[int, dict[str, np.ndarray]] = {}
    for year in years:
        subset = working[working["年份"] == year]
        references[int(year)] = {
            "x": subset[INPUTS].to_numpy(dtype=float),
            "y": subset["output_nominal"].to_numpy(dtype=float),
        }

    rows: list[dict[str, object]] = []
    for province in sorted(working["省份"].unique()):
        province_panel = working[working["省份"] == province].set_index("年份")
        for year_from, year_to in zip(years[:-1], years[1:]):
            x_t = province_panel.loc[year_from, INPUTS].to_numpy(dtype=float)
            y_t = float(province_panel.loc[year_from, "output_nominal"])
            x_t1 = province_panel.loc[year_to, INPUTS].to_numpy(dtype=float)
            y_t1 = float(province_panel.loc[year_to, "output_nominal"])
            d_tt = distance_output_crs(references[year_from]["x"], references[year_from]["y"], x_t, y_t)
            d_t1t1 = distance_output_crs(references[year_to]["x"], references[year_to]["y"], x_t1, y_t1)
            d_t_t1 = distance_output_crs(references[year_from]["x"], references[year_from]["y"], x_t1, y_t1)
            d_t1_t = distance_output_crs(references[year_to]["x"], references[year_to]["y"], x_t, y_t)
            malmquist = np.sqrt((d_t_t1 / d_tt) * (d_t1t1 / d_t1_t))
            effch = d_t1t1 / d_tt
            tech = malmquist / effch
            rows.append(
                {
                    "province": province,
                    "year_from": int(year_from),
                    "year_to": int(year_to),
                    "D_tt": d_tt,
                    "D_t1t1": d_t1t1,
                    "D_t_t1": d_t_t1,
                    "D_t1_t": d_t1_t,
                    "EFFCH": effch,
                    "TECH": tech,
                    "Malmquist": malmquist,
                }
            )
    transitions = pd.DataFrame(rows)

    cumulative_rows: list[dict[str, object]] = []
    for province in sorted(working["省份"].unique()):
        cumulative = 1.0
        cumulative_rows.append({"省份": province, "年份": years[0], "cum_TFP_all5": cumulative})
        province_transitions = transitions[transitions["province"] == province].sort_values("year_to")
        for _, row in province_transitions.iterrows():
            cumulative *= row["Malmquist"]
            cumulative_rows.append(
                {"省份": province, "年份": int(row["year_to"]), "cum_TFP_all5": cumulative}
            )
    return transitions, pd.DataFrame(cumulative_rows)


def clustered_twfe(data: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    """显式加入省份和年份虚拟变量，并按省计算CR1聚类标准误。"""
    y_column = "ln_y_clean"
    regressors = ["ln_cum_tfp", "ln_pop_density", "primary_share"]
    frame = data[["province", "year", y_column] + regressors].dropna().reset_index(drop=True)
    pieces = [frame[regressors].astype(float)]
    pieces.append(pd.get_dummies(frame["province"], prefix="province", drop_first=True, dtype=float))
    pieces.append(pd.get_dummies(frame["year"].astype(str), prefix="year", drop_first=True, dtype=float))
    x_frame = pd.concat(pieces, axis=1)
    matrix = np.column_stack([np.ones(len(frame)), x_frame.to_numpy(dtype=float)])
    names = ["const"] + x_frame.columns.tolist()
    outcome = frame[y_column].to_numpy(dtype=float)

    bread = np.linalg.pinv(matrix.T @ matrix)
    coefficients = bread @ matrix.T @ outcome
    residuals = outcome - matrix @ coefficients
    n_obs = len(frame)
    rank = int(np.linalg.matrix_rank(matrix))
    groups = frame["province"].to_numpy()
    unique_groups = np.unique(groups)
    n_groups = len(unique_groups)

    meat = np.zeros((matrix.shape[1], matrix.shape[1]))
    for group in unique_groups:
        score = matrix[groups == group].T @ residuals[groups == group]
        meat += np.outer(score, score)
    correction = (n_groups / (n_groups - 1)) * ((n_obs - 1) / (n_obs - rank))
    covariance = correction * bread @ meat @ bread
    standard_errors = np.sqrt(np.maximum(np.diag(covariance), 0))
    statistics = coefficients / standard_errors
    inference_df = n_groups - 1
    p_values = 2 * student_t.sf(np.abs(statistics), inference_df)
    critical = student_t.ppf(0.975, inference_df)

    table = pd.DataFrame(
        {
            "variable": names,
            "coef": coefficients,
            "cluster_se": standard_errors,
            "t": statistics,
            "p": p_values,
            "ci_low": coefficients - critical * standard_errors,
            "ci_high": coefficients + critical * standard_errors,
        }
    )
    table["significance"] = np.select(
        [table["p"] < 0.01, table["p"] < 0.05, table["p"] < 0.10],
        ["***", "**", "*"],
        default="",
    )

    sse = float(residuals @ residuals)
    tss = float(((outcome - outcome.mean()) ** 2).sum())
    r_squared = 1 - sse / tss
    metadata = {
        "n": n_obs,
        "rank": rank,
        "province_clusters": n_groups,
        "inference_df": inference_df,
        "r_squared": r_squared,
        "adjusted_r_squared": 1 - (1 - r_squared) * (n_obs - 1) / (n_obs - rank),
    }
    return table, metadata


def source_catalog() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["Y二级指标", "Y原始指标_data_for_res.xlsx", "RAW_DATA", "见指标字典", "随包项目未标明各Y指标的年鉴、表名和页码，需作者补充"],
            ["城镇化率/IPR替代", "控制变量.xlsx", "控制变量", "城镇化率，0—1比例", "项目文档称其为城镇常住人口/总常住人口；随包项目未写明具体年鉴表页"],
            ["人口密度", "控制变量.xlsx", "控制变量", "人/平方公里", "项目文档称常住人口/行政区域面积；随包项目未写明具体年鉴表页"],
            ["第一产业增加值占GDP比重", "控制变量.xlsx", "控制变量", "%", "随包项目未写明具体年鉴表页"],
            ["农业机械总动力", DEA_FILES["machinery"][0], "长格式", "万千瓦", "《中国统计年鉴》/《中国农村统计年鉴》‘各地区主要农业机械年末拥有量’表，CNKI导出"],
            ["农用化肥施用量", DEA_FILES["fertilizer"][0], "长格式", "万吨（折纯）", "《中国农村统计年鉴》‘各地区农用化肥施用量（按折纯法计算）’表，CNKI导出"],
            ["农用塑料薄膜使用量", DEA_FILES["plastic_film"][0], "长格式", "万吨", "《中国农村统计年鉴》‘各地区农用塑料薄膜使用量’表，CNKI导出"],
            ["农用柴油使用量", DEA_FILES["diesel"][0], "长格式", "万吨", "《中国农村统计年鉴》‘各地区农用柴油和农药使用量’表，CNKI PDF经版面识别"],
            ["农药使用量", DEA_FILES["pesticide"][0], "长格式", "万吨", "《中国农村统计年鉴》‘各地区农用柴油和农药使用量’表，CNKI PDF经版面识别"],
            ["农林牧渔业总产值", DEA_FILES["output_nominal"][0], "长格式", "亿元，当年价", "《中国农村统计年鉴》‘各地区农林牧渔业总产值（、增加值和中间消耗）’表，CNKI PDF经版面识别"],
        ],
        columns=["变量/指标", "原始文件", "工作表", "单位", "来源与备注"],
    )


def variable_dictionary() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["province", "省份", "省级行政区", "-"],
            ["province_id", "省份数值编码", "Stata面板编码", "-"],
            ["year", "年份", "2016—2020", "年"],
            ["y_clean", "修正后高质量发展综合指数", "含逐年城镇化率，两层混合权重", "0—1"],
            ["ln_y_clean", "Y取自然对数", "ln(y_clean)", "-"],
            ["cum_tfp", "累计农业TFP", "原五投入DEA—Malmquist，2016=1", "指数"],
            ["ln_cum_tfp", "累计TFP取自然对数", "ln(cum_tfp)", "-"],
            ["urban_rate", "城镇化率", "已进入Y，主回归不重复控制", "0—1"],
            ["pop_density", "人口密度", "常住人口/行政区域面积", "人/平方公里"],
            ["ln_pop_density", "人口密度取自然对数", "ln(pop_density)", "-"],
            ["primary_share", "第一产业增加值占GDP比重", "控制变量", "%"],
            ["machinery", "农业机械总动力", "DEA投入1", "万千瓦"],
            ["fertilizer", "农用化肥施用量", "DEA投入2，折纯", "万吨"],
            ["plastic_film", "农用塑料薄膜使用量", "DEA投入3", "万吨"],
            ["diesel", "农用柴油使用量", "DEA投入4，按原方案保留", "万吨"],
            ["pesticide", "农药使用量", "DEA投入5", "万吨"],
            ["output_nominal", "农林牧渔业总产值", "DEA产出，当年价", "亿元"],
        ],
        columns=["variable", "中文名", "定义", "单位"],
    )


def main() -> None:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    RESULT_OUT.mkdir(parents=True, exist_ok=True)

    outcome, weights, y_raw, y_level_one = build_y()
    dea_panel = load_dea_panel()
    malmquist, cumulative = calculate_malmquist(dea_panel)

    controls = pd.read_excel(RAW / "控制变量.xlsx", sheet_name="控制变量").rename(
        columns={
            "year": "年份",
            "id": "省份",
            "人口密度（人/平方公里）": "人口密度",
        }
    )[["省份", "年份", "第一产业增加值占GDP比重", "城镇化率", "人口密度"]]
    controls = controls[controls["年份"].between(START_YEAR, END_YEAR)]

    panel = outcome.rename(columns={"REGION": "省份", "YEAR": "年份"})
    panel = panel.merge(controls, on=["省份", "年份"], validate="one_to_one")
    panel = panel.merge(cumulative, on=["省份", "年份"], validate="one_to_one")
    panel = panel.merge(dea_panel, on=["省份", "年份"], validate="one_to_one")

    province_codes = {name: index + 1 for index, name in enumerate(sorted(panel["省份"].unique()))}
    analysis = pd.DataFrame(
        {
            "province": panel["省份"],
            "province_id": panel["省份"].map(province_codes).astype(int),
            "year": panel["年份"].astype(int),
            "y_clean": panel["Y_clean_with_urban"],
            "ln_y_clean": np.log(panel["Y_clean_with_urban"]),
            "cum_tfp": panel["cum_TFP_all5"],
            "ln_cum_tfp": np.log(panel["cum_TFP_all5"]),
            "urban_rate": panel["城镇化率"],
            "pop_density": panel["人口密度"],
            "ln_pop_density": np.log(panel["人口密度"]),
            "primary_share": panel["第一产业增加值占GDP比重"],
            "machinery": panel["machinery"],
            "fertilizer": panel["fertilizer"],
            "plastic_film": panel["plastic_film"],
            "diesel": panel["diesel"],
            "pesticide": panel["pesticide"],
            "output_nominal": panel["output_nominal"],
        }
    ).sort_values(["province_id", "year"]).reset_index(drop=True)

    if len(analysis) != 155 or analysis[["province_id", "year"]].duplicated().any():
        raise AssertionError("新面板必须为31省×5年=155行且键唯一")
    if analysis.isna().any().any():
        raise AssertionError("新面板不应包含缺失值")

    coefficients, metadata = clustered_twfe(analysis)
    core = coefficients[coefficients["variable"] == "ln_cum_tfp"].copy()
    for key, value in metadata.items():
        core[key] = value

    analysis.to_csv(DATA_OUT / "新构建分析数据.csv", index=False, encoding="utf-8-sig")
    analysis.to_stata(DATA_OUT / "新构建分析数据.dta", write_index=False, version=118)
    weights.to_csv(RESULT_OUT / "Y权重.csv", index=False, encoding="utf-8-sig")
    malmquist.to_csv(RESULT_OUT / "Malmquist_原五投入.csv", index=False, encoding="utf-8-sig")
    coefficients.to_csv(RESULT_OUT / "Python主回归_全部系数.csv", index=False, encoding="utf-8-sig")
    core.to_csv(RESULT_OUT / "Python主回归_核心结果.csv", index=False, encoding="utf-8-sig")

    dictionary = variable_dictionary()
    sources = source_catalog()
    dictionary.to_csv(PACKAGE / "说明" / "05_变量字典.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(PACKAGE / "说明" / "06_数据来源索引.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(DATA_OUT / "新构建完整面板.xlsx", engine="openpyxl") as writer:
        analysis.to_excel(writer, sheet_name="analysis_panel", index=False)
        y_raw.to_excel(writer, sheet_name="Y_raw_2016_2020", index=False)
        y_level_one.to_excel(writer, sheet_name="Y_level1_and_final", index=False)
        weights.to_excel(writer, sheet_name="Y_weights", index=False)
        dea_panel.to_excel(writer, sheet_name="DEA_inputs_all5", index=False)
        malmquist.to_excel(writer, sheet_name="Malmquist_all5", index=False)
        cumulative.to_excel(writer, sheet_name="cumulative_TFP", index=False)
        coefficients.to_excel(writer, sheet_name="regression_all_coefs", index=False)
        core.to_excel(writer, sheet_name="regression_core", index=False)
        dictionary.to_excel(writer, sheet_name="variable_dictionary", index=False)
        sources.to_excel(writer, sheet_name="source_catalog", index=False)

    print("已生成完整数据和回归结果。")
    print(f"样本：{len(analysis)}行，{analysis['province_id'].nunique()}省，{analysis['year'].min()}—{analysis['year'].max()}年")
    print(core[["coef", "cluster_se", "t", "p", "ci_low", "ci_high", "n", "province_clusters"]].to_string(index=False))


# ==================== 三张图：核密度图 + 热力图 + 修改版曲面图 ====================
try:
    import numpy as np
    import matplotlib.pyplot as plt
    import seaborn as sns
    from mpl_toolkits.mplot3d import Axes3D

    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
    plt.rcParams['axes.unicode_minus'] = False

    df_plot = pd.read_csv(DATA_OUT / "新构建分析数据.csv", encoding='utf-8-sig')
    df_plot['year'] = df_plot['year'].astype(int)

    # ========== 图1：核密度图 ==========
    plt.figure(figsize=(10, 6))
    for year in sorted(df_plot['year'].unique()):
        subset = df_plot[df_plot['year'] == year]['y_clean']
        sns.kdeplot(subset, label=f"{year}年", linewidth=2)
    plt.xlabel("高质量发展综合指数 (y_clean)")
    plt.ylabel("核密度")
    plt.title("2016—2020年高质量发展指数分布变化")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(RESULT_OUT / "Y_核密度图.png", dpi=300)
    plt.close()
    print("✅ 图1 已保存：Y_核密度图.png")

    # ========== 图2：TFP热力图 ==========
    pivot_tfp = df_plot.pivot_table(index='province', columns='year', values='cum_tfp')
    province_order_tfp = pivot_tfp.mean(axis=1).sort_values(ascending=False).index
    pivot_tfp = pivot_tfp.loc[province_order_tfp]

    plt.figure(figsize=(12, 10))
    sns.heatmap(pivot_tfp, annot=True, fmt=".2f", cmap="YlOrRd",
                linewidths=0.5, cbar_kws={'label': '累计TFP (2016=1)'})
    plt.title("各省份累计农业TFP热力图 (2016—2020)")
    plt.xlabel("年份")
    plt.ylabel("省份")
    plt.tight_layout()
    plt.savefig(RESULT_OUT / "TFP_热力图.png", dpi=300)
    plt.close()
    print("✅ 图2 已保存：TFP_热力图.png")

    # ========== 图3：修改版曲面图（省份横轴 + 单色渐变 + 全部省份） ==========
    province_order = df_plot[df_plot['year'] == 2020].sort_values('y_clean', ascending=False)['province'].tolist()
    pivot = df_plot.pivot_table(index='province', columns='year', values='y_clean')
    pivot = pivot.loc[province_order]

    x_positions = np.arange(len(pivot.index))
    y_positions = pivot.columns.values
    X_grid, Y_grid = np.meshgrid(x_positions, y_positions)
    Z = pivot.values.T

    fig = plt.figure(figsize=(16, 10))
    ax = fig.add_subplot(111, projection='3d')
    surf = ax.plot_surface(X_grid, Y_grid, Z, cmap='Blues', edgecolor='none', alpha=0.9)

    ax.set_xlabel('省份（2020年指数从高到低）', fontsize=13, labelpad=10)
    ax.set_ylabel('年份', fontsize=13, labelpad=10)
    ax.set_zlabel('高质量发展综合指数 (y_clean)', fontsize=13, labelpad=10)
    ax.set_title('2016—2020年各省高质量发展指数时空曲面图（省份×年份）', fontsize=15, pad=20)

    ax.set_xticks(x_positions)
    ax.set_xticklabels(pivot.index, rotation=75, fontsize=7)

    ax.set_yticks(y_positions)
    ax.set_yticklabels(y_positions, fontsize=11)

    ax.view_init(elev=25, azim=-55)

    cbar = fig.colorbar(surf, ax=ax, shrink=0.6, aspect=15, pad=0.12)
    cbar.set_label('y_clean', fontsize=12)

    plt.tight_layout()
    plt.savefig(RESULT_OUT / "Y_三维曲面图_省份横轴_单色.png", dpi=300)
    plt.close()
    print("✅ 图3 已保存：Y_三维曲面图_省份横轴_单色.png")

    print("🎉 三张图全部生成完毕！")

except ImportError as e:
    print(f"⚠️ 缺少绘图库，请安装：pip install matplotlib seaborn numpy（{e}）")
except Exception as e:
    print(f"⚠️ 绘图时出现小问题（不影响主结果）：{e}")

# ==================== 五模型递进回归（含 Adj. R² + 设定标注） ====================
try:
    import pandas as pd
    import numpy as np
    from scipy.stats import t as student_t

    ROBUST_DIR = RESULT_OUT / "稳健性"
    df_5model = pd.read_csv(DATA_OUT / "新构建分析数据.csv", encoding='utf-8-sig')
    df_5model['year'] = df_5model['year'].astype(int)


    def run_5model_reg(df, use_controls=True, use_province_fe=True, use_year_fe=True):
        regressors = ["ln_cum_tfp"]
        if use_controls:
            regressors += ["ln_pop_density", "primary_share"]

        X_parts = [df[regressors].astype(float)]
        if use_province_fe:
            prov_dummies = pd.get_dummies(df["province"], prefix="prov", drop_first=True, dtype=float)
            X_parts.append(prov_dummies)
        if use_year_fe:
            year_dummies = pd.get_dummies(df["year"].astype(str), prefix="yr", drop_first=True, dtype=float)
            X_parts.append(year_dummies)

        X = pd.concat(X_parts, axis=1)
        X = np.column_stack([np.ones(len(X)), X.to_numpy(dtype=float)])
        col_names = ["const"] + list(X_parts[0].columns) + \
                    ([c for c in prov_dummies.columns] if use_province_fe else []) + \
                    ([c for c in year_dummies.columns] if use_year_fe else [])
        y = df["ln_y_clean"].to_numpy(dtype=float)

        n_obs, p = X.shape
        inv_XX = np.linalg.pinv(X.T @ X)
        beta = inv_XX @ X.T @ y
        resid = y - X @ beta
        rank = np.linalg.matrix_rank(X)

        groups = df["province"].to_numpy()
        unique_groups = np.unique(groups)
        n_groups = len(unique_groups)
        meat = np.zeros((p, p))
        for g in unique_groups:
            mask = (groups == g)
            score = X[mask].T @ resid[mask]
            meat += np.outer(score, score)
        correction = (n_groups / (n_groups - 1)) * ((n_obs - 1) / (n_obs - rank))
        cov = correction * inv_XX @ meat @ inv_XX
        se = np.sqrt(np.maximum(np.diag(cov), 0))
        t_stats = beta / se
        p_vals = 2 * student_t.sf(np.abs(t_stats), n_groups - 1)

        # 计算 R² 和调整后 R²
        tss = ((y - y.mean()) ** 2).sum()
        rss = (resid @ resid)
        r2 = 1 - rss / tss
        adj_r2 = 1 - (1 - r2) * (n_obs - 1) / (n_obs - rank)

        result = {
            "n": n_obs,
            "n_groups": n_groups,
            "r2": r2,
            "adj_r2": adj_r2,
        }
        for var in ["ln_cum_tfp", "ln_pop_density", "primary_share"]:
            if var in col_names:
                idx = col_names.index(var)
                result[f"{var}_coef"] = beta[idx]
                result[f"{var}_se"] = se[idx]
                result[f"{var}_p"] = p_vals[idx]
            else:
                result[f"{var}_coef"] = None
        return result


    # ===== 5种设定（含中文名称和设定说明） =====
    specs = [
        {
            "id": "Model_1",
            "label": "裸回归（无控制变量，无固定效应）",
            "ctrl": False, "prov_fe": False, "year_fe": False
        },
        {
            "id": "Model_2",
            "label": "加控制变量（无固定效应）",
            "ctrl": True, "prov_fe": False, "year_fe": False
        },
        {
            "id": "Model_3",
            "label": "加控制变量 + 年份固定效应（无省份固定效应）",
            "ctrl": True, "prov_fe": False, "year_fe": True
        },
        {
            "id": "Model_4",
            "label": "加控制变量 + 省份固定效应（无年份固定效应）",
            "ctrl": True, "prov_fe": True, "year_fe": False
        },
        {
            "id": "Model_5",
            "label": "加控制变量 + 双向固定效应（省份+年份）【基准模型】",
            "ctrl": True, "prov_fe": True, "year_fe": True
        },
    ]

    results_list = []
    for spec in specs:
        res = run_5model_reg(
            df_5model,
            use_controls=spec["ctrl"],
            use_province_fe=spec["prov_fe"],
            use_year_fe=spec["year_fe"]
        )
        row = {
            "模型编号": spec["id"],
            "模型设定": spec["label"],
            "控制变量": "是" if spec["ctrl"] else "否",
            "省份固定效应": "是" if spec["prov_fe"] else "否",
            "年份固定效应": "是" if spec["year_fe"] else "否",
            "ln_cum_tfp_系数": res.get("ln_cum_tfp_coef"),
            "ln_cum_tfp_聚类标准误": res.get("ln_cum_tfp_se"),
            "ln_cum_tfp_p值": res.get("ln_cum_tfp_p"),
            "ln_pop_density_系数": res.get("ln_pop_density_coef"),
            "ln_pop_density_标准误": res.get("ln_pop_density_se"),
            "ln_pop_density_p值": res.get("ln_pop_density_p"),
            "primary_share_系数": res.get("primary_share_coef"),
            "primary_share_标准误": res.get("primary_share_se"),
            "primary_share_p值": res.get("primary_share_p"),
            "观测值": res.get("n"),
            "省份数": res.get("n_groups"),
            "R²": res.get("r2"),
            "调整后R²": res.get("adj_r2"),  # <--- 新加的列
        }
        results_list.append(row)
        coef = res.get("ln_cum_tfp_coef")
        print(
            f"{spec['id']}: TFP系数={coef:.4f}, Adj.R²={res['adj_r2']:.4f}" if coef is not None else f"{spec['id']}: TFP未包含")

    df_output = pd.DataFrame(results_list)
    df_output.to_csv(ROBUST_DIR / "五模型递进结果_带标注.csv", index=False, encoding="utf-8-sig")
    print(f"✅ 五模型递进结果已保存到 {ROBUST_DIR / '五模型递进结果_带标注.csv'}")


except Exception as e:
    print(f"⚠️ 五模型递进出错：{e}")