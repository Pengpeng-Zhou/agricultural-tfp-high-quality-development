"""空间相关、稳健性、内生性、空间溢出、门槛与空间马尔科夫分析。"""

from __future__ import annotations

import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(BASE / ".matplotlib-cache"))

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import chi2, norm, t as student_t
from linearmodels.panel import PanelOLS
from linearmodels.iv import IV2SLS
from libpysal.weights import W
from esda import Moran, Moran_Local
import spreg


DATA_PATH = BASE / "数据" / "新构建分析数据.csv"
PCGDP_PATH = BASE / "数据" / "原始数据_只读副本" / "Y原始指标_data_for_res.xlsx"
RESULT_ROOT = BASE / "结果"
SEED = 20260903

PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏",
    "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西",
    "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
]

# 省级接壤关系。海南作为岛屿与地理距离最近且经济联系紧密的广东桥接，避免孤岛权重。
EDGES = [
    ("北京", "天津"), ("北京", "河北"), ("天津", "河北"),
    ("河北", "辽宁"), ("河北", "内蒙古"), ("河北", "山西"), ("河北", "河南"), ("河北", "山东"),
    ("山西", "内蒙古"), ("山西", "陕西"), ("山西", "河南"),
    ("内蒙古", "黑龙江"), ("内蒙古", "吉林"), ("内蒙古", "辽宁"), ("内蒙古", "陕西"),
    ("内蒙古", "宁夏"), ("内蒙古", "甘肃"),
    ("辽宁", "吉林"), ("吉林", "黑龙江"),
    ("上海", "江苏"), ("上海", "浙江"),
    ("江苏", "山东"), ("江苏", "安徽"), ("江苏", "浙江"),
    ("浙江", "安徽"), ("浙江", "江西"), ("浙江", "福建"),
    ("安徽", "江西"), ("安徽", "湖北"), ("安徽", "河南"), ("安徽", "山东"),
    ("福建", "江西"), ("福建", "广东"),
    ("江西", "广东"), ("江西", "湖南"), ("江西", "湖北"),
    ("山东", "河南"),
    ("河南", "陕西"), ("河南", "湖北"),
    ("湖北", "湖南"), ("湖北", "重庆"), ("湖北", "陕西"),
    ("湖南", "广东"), ("湖南", "广西"), ("湖南", "贵州"), ("湖南", "重庆"),
    ("广东", "广西"), ("广东", "海南"),
    ("广西", "贵州"), ("广西", "云南"),
    ("重庆", "四川"), ("重庆", "陕西"), ("重庆", "贵州"),
    ("四川", "陕西"), ("四川", "甘肃"), ("四川", "青海"), ("四川", "西藏"),
    ("四川", "云南"), ("四川", "贵州"),
    ("贵州", "云南"),
    ("云南", "西藏"),
    ("西藏", "新疆"), ("西藏", "青海"),
    ("陕西", "甘肃"), ("陕西", "宁夏"),
    ("甘肃", "新疆"), ("甘肃", "宁夏"), ("甘肃", "青海"),
    ("青海", "新疆"),
]


def setup_style() -> None:
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def make_weights() -> W:
    neighbors = {p: [] for p in PROVINCES}
    for a, b in EDGES:
        neighbors[a].append(b)
        neighbors[b].append(a)
    if any(len(v) == 0 for v in neighbors.values()):
        raise ValueError("空间权重矩阵存在孤立省份")
    weights = W(neighbors, id_order=PROVINCES, silence_warnings=True)
    weights.transform = "r"
    return weights


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    pcgdp = pd.read_excel(PCGDP_PATH, sheet_name="RAW_DATA", usecols=["REGION", "YEAR", "PCGDP"])
    pcgdp = pcgdp.rename(columns={"REGION": "province", "YEAR": "year", "PCGDP": "pcgdp"})
    pcgdp = pcgdp[pcgdp["year"].between(2016, 2020)]
    df = df.merge(pcgdp, on=["province", "year"], validate="one_to_one")
    df["ln_pcgdp"] = np.log(df["pcgdp"])
    if len(df) != 155 or set(df["province"]) != set(PROVINCES):
        raise ValueError("分析数据必须为31省×5年的平衡面板")
    return df.sort_values(["province", "year"]).reset_index(drop=True)


def spatial_lag(values: np.ndarray, weights: W) -> np.ndarray:
    return weights.sparse @ np.asarray(values, dtype=float)


def run_spatial_autocorrelation(df: pd.DataFrame, weights: W) -> dict[str, pd.DataFrame]:
    out = RESULT_ROOT / "空间自相关初步检验"
    out.mkdir(parents=True, exist_ok=True)
    rng_seed = SEED
    variables = {"高质量发展指数": "y_clean", "累计农业TFP": "cum_tfp"}
    global_rows, local_rows = [], []
    scatter_data = {}
    for variable, column in variables.items():
        for year in range(2016, 2021):
            yearly = df[df["year"] == year].set_index("province").loc[PROVINCES]
            x = yearly[column].to_numpy(dtype=float)
            if np.std(x) < 1e-12:
                global_rows.append({"变量": variable, "年份": year, "Moran_I": np.nan,
                                    "期望值": -1 / (len(x) - 1), "置换p值": np.nan,
                                    "置换z值": np.nan, "置换次数": 999, "备注": "共同基期，变量无截面差异"})
                continue
            np.random.seed(rng_seed + year + (0 if column == "y_clean" else 100))
            moran = Moran(x, weights, permutations=999, two_tailed=False)
            global_rows.append({"变量": variable, "年份": year, "Moran_I": moran.I,
                                "期望值": moran.EI, "置换p值": moran.p_sim,
                                "置换z值": moran.z_sim, "置换次数": 999, "备注": ""})
            z = (x - x.mean()) / x.std(ddof=0)
            wz = spatial_lag(z, weights)
            scatter_data[(variable, year)] = (z, wz, moran.I)
            lisa = Moran_Local(x, weights, permutations=999, seed=rng_seed + year)
            qmap = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
            for idx, province in enumerate(PROVINCES):
                significant = bool(lisa.p_sim[idx] < 0.05)
                local_rows.append({"变量": variable, "年份": year, "省份": province,
                                   "Local_Moran_I": lisa.Is[idx], "置换p值": lisa.p_sim[idx],
                                   "象限": qmap[int(lisa.q[idx])],
                                   "显著聚类类型": qmap[int(lisa.q[idx])] if significant else "不显著"})

    global_df = pd.DataFrame(global_rows)
    local_df = pd.DataFrame(local_rows)
    global_df.to_csv(out / "全局莫兰指数结果.csv", index=False, encoding="utf-8-sig")
    local_df.to_csv(out / "局部莫兰指数结果.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([{"省份": p, "相邻省份": "、".join(weights.neighbors[p]),
                   "邻接数量": len(weights.neighbors[p])} for p in PROVINCES]).to_csv(
        out / "空间权重矩阵说明.csv", index=False, encoding="utf-8-sig")

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    for ax, variable in zip(axes, variables):
        part = global_df[global_df["变量"] == variable]
        ax.plot(part["年份"], part["Moran_I"], marker="o", linewidth=2.3, color="#2F5597")
        ax.axhline(0, color="black", linewidth=0.8)
        for _, row in part.dropna(subset=["Moran_I"]).iterrows():
            ax.annotate(f"{row['Moran_I']:.3f}\n(p={row['置换p值']:.3f})",
                        (row["年份"], row["Moran_I"]), xytext=(0, 9), textcoords="offset points",
                        ha="center", fontsize=8)
        ax.set_title(variable)
        ax.set_xlabel("年份")
        ax.set_ylabel("全局 Moran's I")
        ax.set_xticks(range(2016, 2021))
    fig.suptitle("2016—2020年全局空间自相关", fontsize=16)
    fig.tight_layout()
    fig.savefig(out / "全局莫兰指数趋势.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    for variable, column in variables.items():
        valid_years = [y for y in range(2016, 2021) if (variable, y) in scatter_data]
        ncols = 3 if len(valid_years) == 5 else 2
        nrows = int(np.ceil(len(valid_years) / ncols))
        fig, axes = plt.subplots(nrows, ncols, figsize=(5.3 * ncols, 4.4 * nrows), squeeze=False)
        for ax, year in zip(axes.flat, valid_years):
            z, wz, mi = scatter_data[(variable, year)]
            ax.scatter(z, wz, color="#2F5597", alpha=0.8, s=34)
            line_x = np.linspace(z.min() - 0.3, z.max() + 0.3, 100)
            ax.plot(line_x, mi * line_x, color="#C00000", linewidth=1.8)
            ax.axhline(0, color="grey", linewidth=0.8)
            ax.axvline(0, color="grey", linewidth=0.8)
            ax.set_title(f"{year}年（I={mi:.3f}）")
            ax.set_xlabel("标准化观测值")
            ax.set_ylabel("空间滞后值")
        for ax in axes.flat[len(valid_years):]:
            ax.axis("off")
        fig.suptitle(f"{variable} Moran散点图", fontsize=16)
        fig.tight_layout()
        fig.savefig(out / f"全局莫兰散点图_{column}.png", dpi=300, bbox_inches="tight")
        plt.close(fig)

        part = local_df[local_df["变量"] == variable].copy()
        if part.empty:
            continue
        code = {"不显著": 0, "HH": 1, "LH": 2, "LL": 3, "HL": 4}
        matrix = part.pivot(index="省份", columns="年份", values="显著聚类类型").reindex(PROVINCES)
        coded = matrix.replace(code).astype(float)
        fig, ax = plt.subplots(figsize=(8, 11))
        cmap = ListedColormap(["#E7E6E6", "#C00000", "#5B9BD5", "#4472C4", "#F4B183"])
        sns.heatmap(coded, cmap=cmap, vmin=-0.5, vmax=4.5, cbar=False, linewidths=0.4,
                    linecolor="white", annot=matrix, fmt="", ax=ax)
        ax.set_title(f"{variable}局部Moran显著聚类（p<0.05）")
        ax.set_xlabel("年份")
        ax.set_ylabel("省份")
        fig.tight_layout()
        fig.savefig(out / f"局部莫兰聚类热图_{column}.png", dpi=300, bbox_inches="tight")
        plt.close(fig)
    return {"global": global_df, "local": local_df}


def fit_panel(data: pd.DataFrame, dep: str, core: str, covariance: str = "clustered") -> dict[str, float]:
    panel = data.set_index(["province", "year"])
    exog = panel[[core, "ln_pop_density", "primary_share"]]
    model = PanelOLS(panel[dep], exog, entity_effects=True, time_effects=True, drop_absorbed=True)
    if covariance == "kernel":
        result = model.fit(cov_type="kernel", kernel="bartlett", bandwidth=2)
    else:
        result = model.fit(cov_type="clustered", cluster_entity=True, debiased=True)
    return {"coef": result.params[core], "se": result.std_errors[core], "t": result.tstats[core],
            "p": result.pvalues[core], "n": result.nobs, "entities": data["province"].nunique(),
            "r2_within": result.rsquared_within}


def run_robustness(df: pd.DataFrame) -> pd.DataFrame:
    out = RESULT_ROOT / "稳健性检验"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    specs = []
    specs.append(("基准：双向固定效应", df.copy(), "ln_y_clean", "ln_cum_tfp", "clustered",
                  "省份聚类稳健标准误"))
    winsor = df.copy()
    for col in ["ln_y_clean", "ln_cum_tfp", "ln_pop_density", "primary_share"]:
        winsor[col] = winsor[col].clip(winsor[col].quantile(0.01), winsor[col].quantile(0.99))
    specs.append(("双侧1%缩尾", winsor, "ln_y_clean", "ln_cum_tfp", "clustered", "降低极端值影响"))
    no_city = df[~df["province"].isin(["北京", "天津", "上海", "重庆"])].copy()
    specs.append(("剔除四个直辖市", no_city, "ln_y_clean", "ln_cum_tfp", "clustered", "检验行政层级影响"))
    lagged = df.sort_values(["province", "year"]).copy()
    lagged["L1_ln_cum_tfp"] = lagged.groupby("province")["ln_cum_tfp"].shift(1)
    lagged = lagged.dropna(subset=["L1_ln_cum_tfp"])
    specs.append(("解释变量滞后一期", lagged, "ln_y_clean", "L1_ln_cum_tfp", "clustered", "缓解同期反向作用"))
    specs.append(("水平值函数形式", df.copy(), "y_clean", "cum_tfp", "clustered", "不依赖对数设定"))
    specs.append(("Driscoll-Kraay标准误", df.copy(), "ln_y_clean", "ln_cum_tfp", "kernel",
                  "允许截面相关和序列相关"))
    for name, data, dep, core, cov, note in specs:
        result = fit_panel(data, dep, core, cov)
        rows.append({"模型": name, "被解释变量": dep, "核心解释变量": core,
                     "系数": result["coef"], "标准误": result["se"], "t值": result["t"],
                     "p值": result["p"], "观测值": result["n"], "省份数": result["entities"],
                     "组内R2": result["r2_within"], "说明": note})
    results = pd.DataFrame(rows)
    results.to_csv(out / "稳健性检验结果.csv", index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(10, 6))
    y_pos = np.arange(len(results))
    lower = results["系数"] - 1.96 * results["标准误"]
    upper = results["系数"] + 1.96 * results["标准误"]
    ax.errorbar(results["系数"], y_pos, xerr=[results["系数"] - lower, upper - results["系数"]],
                fmt="o", color="#2F5597", ecolor="#7F8FA6", capsize=4)
    ax.axvline(0, color="#C00000", linestyle="--", linewidth=1)
    ax.set_yticks(y_pos, results["模型"])
    ax.invert_yaxis()
    ax.set_xlabel("核心解释变量系数及95%置信区间")
    ax.set_title("农业TFP影响的稳健性检验")
    fig.tight_layout()
    fig.savefig(out / "稳健性系数森林图.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    return results


def run_endogeneity(df: pd.DataFrame) -> pd.DataFrame:
    out = RESULT_ROOT / "内生性检验"
    out.mkdir(parents=True, exist_ok=True)
    work = df.sort_values(["province", "year"]).copy()
    work["L1_ln_cum_tfp"] = work.groupby("province")["ln_cum_tfp"].shift(1)
    work = work.dropna(subset=["L1_ln_cum_tfp"]).reset_index(drop=True)
    province_dummies = pd.get_dummies(work["province"], prefix="省", drop_first=True, dtype=float)
    year_dummies = pd.get_dummies(work["year"].astype(str), prefix="年", drop_first=True, dtype=float)
    exog = pd.concat([pd.Series(1.0, index=work.index, name="常数"),
                      work[["ln_pop_density", "primary_share"]], province_dummies, year_dummies], axis=1)
    iv_model = IV2SLS(work["ln_y_clean"], exog, work[["ln_cum_tfp"]], work[["L1_ln_cum_tfp"]])
    iv = iv_model.fit(cov_type="clustered", clusters=work["province"], debiased=True)
    ols = IV2SLS(work["ln_y_clean"], pd.concat([exog, work[["ln_cum_tfp"]]], axis=1), None, None).fit(
        cov_type="clustered", clusters=work["province"], debiased=True)
    first = iv.first_stage.diagnostics.loc["ln_cum_tfp"]
    wu = iv.wu_hausman()
    rows = [
        {"模型": "同样本双向固定效应OLS", "系数": ols.params["ln_cum_tfp"],
         "标准误": ols.std_errors["ln_cum_tfp"], "p值": ols.pvalues["ln_cum_tfp"],
         "观测值": len(work), "工具变量": "—", "第一阶段部分F": np.nan,
         "第一阶段p值": np.nan, "Wu-Hausman p值": np.nan},
        {"模型": "2SLS内部工具变量", "系数": iv.params["ln_cum_tfp"],
         "标准误": iv.std_errors["ln_cum_tfp"], "p值": iv.pvalues["ln_cum_tfp"],
         "观测值": len(work), "工具变量": "农业TFP的一期滞后",
         "第一阶段部分F": first["f.stat"], "第一阶段p值": first["f.pval"],
         "Wu-Hausman p值": wu.pval},
    ]
    results = pd.DataFrame(rows)
    results.to_csv(out / "内生性检验结果.csv", index=False, encoding="utf-8-sig")
    with open(out / "2SLS完整输出.txt", "w", encoding="utf-8") as handle:
        handle.write(str(iv.summary))
        handle.write("\n\n第一阶段：\n")
        handle.write(str(iv.first_stage))
        handle.write("\n\nWu-Hausman：\n")
        handle.write(str(wu))
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ypos = np.arange(2)
    lower = results["系数"] - 1.96 * results["标准误"]
    upper = results["系数"] + 1.96 * results["标准误"]
    ax.errorbar(results["系数"], ypos, xerr=[results["系数"] - lower, upper - results["系数"]],
                fmt="o", capsize=5, color="#2F5597")
    ax.axvline(0, color="#C00000", linestyle="--")
    ax.set_yticks(ypos, results["模型"])
    ax.set_xlabel("ln(累计TFP)系数及95%置信区间")
    ax.set_title("OLS与工具变量估计比较")
    fig.tight_layout()
    fig.savefig(out / "OLS与IV估计比较.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    return results


def run_spatial_spillover(df: pd.DataFrame, weights: W) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = RESULT_ROOT / "空间溢出效应"
    out.mkdir(parents=True, exist_ok=True)
    work = df.copy()
    for col in ["ln_cum_tfp", "ln_pop_density", "primary_share"]:
        lag_col = f"W_{col}"
        work[lag_col] = np.nan
        for year in range(2016, 2021):
            idx = work.index[work["year"] == year]
            yearly = work.loc[idx].set_index("province").loc[PROVINCES]
            lag_values = spatial_lag(yearly[col].to_numpy(), weights)
            mapping = dict(zip(PROVINCES, lag_values))
            work.loc[idx, lag_col] = work.loc[idx, "province"].map(mapping)
    year_dummies = pd.get_dummies(work["year"].astype(str), prefix="year", drop_first=True, dtype=float)
    x_cols = ["ln_cum_tfp", "ln_pop_density", "primary_share",
              "W_ln_cum_tfp", "W_ln_pop_density", "W_primary_share"]
    model_frame = pd.concat([work, year_dummies], axis=1)
    year_cols = year_dummies.columns.tolist()
    ordered = model_frame.copy()
    ordered["province"] = pd.Categorical(ordered["province"], categories=PROVINCES, ordered=True)
    ordered = ordered.sort_values(["year", "province"])
    y = ordered[["ln_y_clean"]].to_numpy(dtype=float)
    X = ordered[x_cols + year_cols].to_numpy(dtype=float)
    model = spreg.Panel_FE_Lag(y, X, weights, vm=True, name_y="ln_y_clean",
                               name_x=x_cols + year_cols, name_w="省级接壤矩阵",
                               name_ds="31省2016—2020面板")
    names = x_cols + year_cols + ["rho"]
    betas = model.betas.flatten()
    std = np.asarray(model.std_err).flatten()
    zstats = [z[0] for z in model.z_stat]
    pvals = [z[1] for z in model.z_stat]
    coef = pd.DataFrame({"变量": names, "系数": betas, "标准误": std,
                         "z值": zstats, "p值": pvals})
    coef["观测值"] = model.n
    coef["省份数"] = len(PROVINCES)
    coef["年份数"] = 5
    coef["对数似然"] = model.logll
    coef["AIC"] = model.aic
    coef.to_csv(out / "空间杜宾模型系数.csv", index=False, encoding="utf-8-sig")
    with open(out / "空间杜宾模型完整输出.txt", "w", encoding="utf-8") as handle:
        handle.write(model.summary)

    # Wald约束检验：SDM是否可简化为SAR或空间误差模型（SEM）。
    theta_indices = [names.index("W_ln_cum_tfp"), names.index("W_ln_pop_density"),
                     names.index("W_primary_share")]
    theta_vec = betas[theta_indices]
    theta_cov = np.asarray(model.vm)[np.ix_(theta_indices, theta_indices)]
    wald_sar = float(theta_vec @ np.linalg.pinv(theta_cov) @ theta_vec)
    base_indices = [names.index("ln_cum_tfp"), names.index("ln_pop_density"),
                    names.index("primary_share")]
    rho_index = names.index("rho")
    restrictions = betas[theta_indices] + float(model.rho) * betas[base_indices]
    jacobian = np.zeros((3, len(names)))
    for row_idx, (base_idx, theta_idx) in enumerate(zip(base_indices, theta_indices)):
        jacobian[row_idx, base_idx] = float(model.rho)
        jacobian[row_idx, theta_idx] = 1.0
        jacobian[row_idx, rho_index] = betas[base_idx]
    restriction_cov = jacobian @ np.asarray(model.vm) @ jacobian.T
    wald_sem = float(restrictions @ np.linalg.pinv(restriction_cov) @ restrictions)
    tests = pd.DataFrame([
        {"检验": "SDM简化为SAR：空间滞后解释变量系数联合为0", "Wald统计量": wald_sar,
         "自由度": 3, "p值": chi2.sf(wald_sar, 3)},
        {"检验": "SDM简化为SEM：共同因子约束", "Wald统计量": wald_sem,
         "自由度": 3, "p值": chi2.sf(wald_sem, 3)},
    ])
    tests.to_csv(out / "空间模型约束检验.csv", index=False, encoding="utf-8-sig")

    beta = float(coef.loc[coef["变量"] == "ln_cum_tfp", "系数"].iloc[0])
    theta = float(coef.loc[coef["变量"] == "W_ln_cum_tfp", "系数"].iloc[0])
    rho = float(model.rho)
    Wm = weights.full()[0]
    S = np.linalg.inv(np.eye(len(PROVINCES)) - rho * Wm)
    impact_matrix = S @ (beta * np.eye(len(PROVINCES)) + theta * Wm)
    direct = float(np.trace(impact_matrix) / len(PROVINCES))
    total = float(impact_matrix.sum(axis=1).mean())
    indirect = total - direct

    rng = np.random.default_rng(SEED)
    vm = np.asarray(model.vm)
    draws = rng.multivariate_normal(betas, vm, size=5000, check_valid="ignore")
    impact_draws = []
    beta_idx, theta_idx, rho_idx = names.index("ln_cum_tfp"), names.index("W_ln_cum_tfp"), names.index("rho")
    for draw in draws:
        r = float(draw[rho_idx])
        if abs(r) >= 0.98:
            continue
        Sd = np.linalg.inv(np.eye(len(PROVINCES)) - r * Wm)
        Md = Sd @ (float(draw[beta_idx]) * np.eye(len(PROVINCES)) + float(draw[theta_idx]) * Wm)
        d = float(np.trace(Md) / len(PROVINCES))
        tt = float(Md.sum(axis=1).mean())
        impact_draws.append([d, tt - d, tt])
    impact_draws = np.asarray(impact_draws)
    labels = ["直接效应", "间接效应", "总效应"]
    points = [direct, indirect, total]
    impact_rows = []
    for idx, label in enumerate(labels):
        sd = float(impact_draws[:, idx].std(ddof=1))
        z = points[idx] / sd
        impact_rows.append({"效应": label, "估计值": points[idx], "模拟标准误": sd,
                            "z值": z, "p值": 2 * norm.sf(abs(z)),
                            "95%CI下限": np.quantile(impact_draws[:, idx], 0.025),
                            "95%CI上限": np.quantile(impact_draws[:, idx], 0.975)})
    impacts = pd.DataFrame(impact_rows)
    impacts.to_csv(out / "空间效应分解.csv", index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(8, 5))
    ypos = np.arange(3)
    ax.errorbar(impacts["估计值"], ypos,
                xerr=[impacts["估计值"] - impacts["95%CI下限"], impacts["95%CI上限"] - impacts["估计值"]],
                fmt="o", capsize=5, color="#2F5597")
    ax.axvline(0, color="#C00000", linestyle="--")
    ax.set_yticks(ypos, impacts["效应"])
    ax.set_xlabel("弹性效应及95%模拟置信区间")
    ax.set_title("农业TFP对高质量发展的空间效应分解")
    fig.tight_layout()
    fig.savefig(out / "空间效应分解森林图.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    return coef, impacts


def ols_cluster(y: np.ndarray, X: np.ndarray, clusters: np.ndarray):
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ beta
    bread = np.linalg.pinv(X.T @ X)
    unique = np.unique(clusters)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for group in unique:
        score = X[clusters == group].T @ resid[clusters == group]
        meat += np.outer(score, score)
    rank = np.linalg.matrix_rank(X)
    correction = (len(unique) / (len(unique) - 1)) * ((len(y) - 1) / (len(y) - rank))
    cov = correction * bread @ meat @ bread
    return beta, np.sqrt(np.maximum(np.diag(cov), 0)), resid


def run_threshold(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = RESULT_ROOT / "空间门槛效应"
    out.mkdir(parents=True, exist_ok=True)
    work = df.sort_values(["province", "year"]).reset_index(drop=True)
    y = work["ln_y_clean"].to_numpy(dtype=float)
    x = work["ln_cum_tfp"].to_numpy(dtype=float)
    q = work["ln_pcgdp"].to_numpy(dtype=float)
    controls = work[["ln_pop_density", "primary_share"]].to_numpy(dtype=float)
    prov = pd.get_dummies(work["province"], drop_first=True, dtype=float).to_numpy()
    years = pd.get_dummies(work["year"].astype(str), drop_first=True, dtype=float).to_numpy()
    fixed = np.column_stack([np.ones(len(work)), controls, prov, years])
    X0 = np.column_stack([fixed, x])
    beta0 = np.linalg.lstsq(X0, y, rcond=None)[0]
    fitted0 = X0 @ beta0
    resid0 = y - fitted0
    ssr0 = float(resid0 @ resid0)

    lower, upper = np.quantile(q, [0.15, 0.85])
    candidates = np.sort(np.unique(q[(q >= lower) & (q <= upper)]))
    profiles = []
    best = None
    for gamma in candidates:
        low = x * (q <= gamma)
        high = x * (q > gamma)
        Xg = np.column_stack([fixed, low, high])
        bg = np.linalg.lstsq(Xg, y, rcond=None)[0]
        resid = y - Xg @ bg
        ssr = float(resid @ resid)
        profiles.append((gamma, ssr))
        if best is None or ssr < best[1]:
            best = (gamma, ssr, Xg)
    gamma_hat, ssr1, X_best = best
    rank = np.linalg.matrix_rank(X_best)
    sigma2 = ssr1 / (len(y) - rank)
    F_obs = (ssr0 - ssr1) / sigma2

    rng = np.random.default_rng(SEED)
    cluster_values = work["province"].to_numpy()
    unique_clusters = np.unique(cluster_values)
    boot_stats = []
    for _ in range(499):
        signs = dict(zip(unique_clusters, rng.choice([-1.0, 1.0], size=len(unique_clusters))))
        yb = fitted0 + resid0 * np.array([signs[c] for c in cluster_values])
        b0 = np.linalg.lstsq(X0, yb, rcond=None)[0]
        r0 = yb - X0 @ b0
        b_ssr0 = float(r0 @ r0)
        b_min = np.inf
        b_rank = 0
        for gamma in candidates:
            Xg = np.column_stack([fixed, x * (q <= gamma), x * (q > gamma)])
            bg = np.linalg.lstsq(Xg, yb, rcond=None)[0]
            rr = yb - Xg @ bg
            rss = float(rr @ rr)
            if rss < b_min:
                b_min, b_rank = rss, np.linalg.matrix_rank(Xg)
        b_sigma2 = b_min / (len(yb) - b_rank)
        boot_stats.append((b_ssr0 - b_min) / b_sigma2)
    bootstrap_p = (1 + np.sum(np.asarray(boot_stats) >= F_obs)) / (len(boot_stats) + 1)
    profile = pd.DataFrame(profiles, columns=["门槛值_ln人均GDP", "SSR"])
    profile["LR"] = (profile["SSR"] - ssr1) / sigma2
    ci = profile.loc[profile["LR"] <= 7.35, "门槛值_ln人均GDP"]
    ci_low, ci_high = float(ci.min()), float(ci.max())

    beta, se, resid = ols_cluster(y, X_best, cluster_values)
    dof = len(unique_clusters) - 1
    low_idx, high_idx = X_best.shape[1] - 2, X_best.shape[1] - 1
    slope_rows = []
    for label, idx in [("低于或等于门槛", low_idx), ("高于门槛", high_idx)]:
        stat = beta[idx] / se[idx]
        slope_rows.append({"区间": label, "TFP系数": beta[idx], "聚类标准误": se[idx],
                           "t值": stat, "p值": 2 * student_t.sf(abs(stat), dof),
                           "观测值": int(np.sum(q <= gamma_hat) if idx == low_idx else np.sum(q > gamma_hat))})
    slopes = pd.DataFrame(slope_rows)
    threshold = pd.DataFrame([{"门槛变量": "ln(人均GDP)", "门槛估计值": gamma_hat,
                               "门槛原值_元每人": np.exp(gamma_hat), "95%CI下限": ci_low,
                               "95%CI上限": ci_high, "SupF": F_obs, "Bootstrap_p值": bootstrap_p,
                               "Bootstrap次数": 499, "LR临界值": 7.35}])
    threshold.to_csv(out / "门槛检验结果.csv", index=False, encoding="utf-8-sig")
    slopes.to_csv(out / "门槛区间效应.csv", index=False, encoding="utf-8-sig")
    profile.to_csv(out / "门槛似然比轮廓.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(profile["门槛值_ln人均GDP"], profile["LR"], color="#2F5597", linewidth=2)
    ax.axhline(7.35, color="#C00000", linestyle="--", label="95%临界值=7.35")
    ax.axvline(gamma_hat, color="#548235", linestyle="--", label=f"门槛={gamma_hat:.3f}")
    ax.set_xlabel("门槛变量：ln(人均GDP)")
    ax.set_ylabel("似然比统计量 LR")
    ax.set_title("单一门槛估计的似然比轮廓")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "门槛似然比轮廓图.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    ypos = np.arange(2)
    lo = slopes["TFP系数"] - 1.96 * slopes["聚类标准误"]
    hi = slopes["TFP系数"] + 1.96 * slopes["聚类标准误"]
    ax.errorbar(slopes["TFP系数"], ypos, xerr=[slopes["TFP系数"] - lo, hi - slopes["TFP系数"]],
                fmt="o", capsize=5, color="#2F5597")
    ax.axvline(0, color="#C00000", linestyle="--")
    ax.set_yticks(ypos, slopes["区间"])
    ax.set_xlabel("TFP弹性及95%置信区间")
    ax.set_title("不同经济发展门槛下的TFP效应")
    fig.tight_layout()
    fig.savefig(out / "门槛区间效应图.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    return threshold, slopes


def row_normalize(counts: np.ndarray) -> np.ndarray:
    sums = counts.sum(axis=1, keepdims=True)
    return np.divide(counts, sums, out=np.zeros_like(counts, dtype=float), where=sums > 0)


def g_statistic(transitions: pd.DataFrame, context_col: str) -> float:
    total = np.zeros((4, 4), dtype=float)
    conditional = {}
    for _, row in transitions.iterrows():
        i, j, c = int(row["起始状态"]) - 1, int(row["终止状态"]) - 1, int(row[context_col])
        total[i, j] += 1
        conditional.setdefault(c, np.zeros((4, 4), dtype=float))[i, j] += 1
    pooled_p = row_normalize(total)
    stat = 0.0
    for counts in conditional.values():
        pc = row_normalize(counts)
        mask = (counts > 0) & (pooled_p > 0) & (pc > 0)
        stat += float(2 * np.sum(counts[mask] * np.log(pc[mask] / pooled_p[mask])))
    return stat


def run_spatial_markov(df: pd.DataFrame, weights: W) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = RESULT_ROOT / "空间马尔科夫链"
    out.mkdir(parents=True, exist_ok=True)
    work = df.copy()
    work["状态"] = np.nan
    work["空间环境"] = np.nan
    for year in range(2016, 2021):
        idx = work.index[work["year"] == year]
        yearly = work.loc[idx].set_index("province").loc[PROVINCES]
        state = pd.qcut(yearly["y_clean"].rank(method="first"), 4, labels=False) + 1
        lag = pd.Series(spatial_lag(yearly["y_clean"].to_numpy(), weights), index=PROVINCES)
        context = pd.qcut(lag.rank(method="first"), 3, labels=False) + 1
        state_map, context_map = state.to_dict(), context.to_dict()
        work.loc[idx, "状态"] = work.loc[idx, "province"].map(state_map)
        work.loc[idx, "空间环境"] = work.loc[idx, "province"].map(context_map)
    work["状态"] = work["状态"].astype(int)
    work["空间环境"] = work["空间环境"].astype(int)

    transition_rows = []
    for province, group in work.groupby("province"):
        group = group.sort_values("year")
        for (_, current), (_, nxt) in zip(group.iloc[:-1].iterrows(), group.iloc[1:].iterrows()):
            transition_rows.append({"省份": province, "起始年份": current["year"],
                                    "终止年份": nxt["year"], "起始状态": current["状态"],
                                    "终止状态": nxt["状态"], "空间环境": current["空间环境"]})
    transitions = pd.DataFrame(transition_rows)
    transitions.to_csv(out / "空间马尔科夫转移明细.csv", index=False, encoding="utf-8-sig")
    labels = ["低", "中低", "中高", "高"]
    context_labels = {1: "低邻域", 2: "中邻域", 3: "高邻域"}
    matrix_rows = []
    matrices = {}
    for context in [0, 1, 2, 3]:
        subset = transitions if context == 0 else transitions[transitions["空间环境"] == context]
        counts = np.zeros((4, 4), dtype=int)
        for _, row in subset.iterrows():
            counts[int(row["起始状态"]) - 1, int(row["终止状态"]) - 1] += 1
        probs = row_normalize(counts)
        name = "无条件" if context == 0 else context_labels[context]
        matrices[name] = probs
        for i in range(4):
            for j in range(4):
                matrix_rows.append({"空间条件": name, "起始状态": labels[i], "终止状态": labels[j],
                                    "转移次数": counts[i, j], "转移概率": probs[i, j]})
    matrix_df = pd.DataFrame(matrix_rows)
    matrix_df.to_csv(out / "空间条件转移矩阵.csv", index=False, encoding="utf-8-sig")

    observed_g = g_statistic(transitions, "空间环境")
    rng = np.random.default_rng(SEED)
    permuted = []
    for _ in range(999):
        temp = transitions.copy()
        for state in range(1, 5):
            mask = temp["起始状态"] == state
            temp.loc[mask, "随机环境"] = rng.permutation(temp.loc[mask, "空间环境"].to_numpy())
        permuted.append(g_statistic(temp, "随机环境"))
    perm_p = (1 + np.sum(np.asarray(permuted) >= observed_g)) / 1000
    summary = []
    for name, matrix in matrices.items():
        mobility = (4 - np.trace(matrix)) / 3
        # 条件矩阵可能不可约，稳态分布不唯一；仅报告无条件矩阵的稳态分布。
        if name == "无条件":
            eigenvalues, eigenvectors = np.linalg.eig(matrix.T)
            idx = np.argmin(np.abs(eigenvalues - 1))
            stationary = np.real(eigenvectors[:, idx])
            stationary = stationary / stationary.sum()
        else:
            stationary = np.full(4, np.nan)
        summary.append({"空间条件": name, "Shorrocks流动性指数": mobility,
                        "稳态_低": stationary[0], "稳态_中低": stationary[1],
                        "稳态_中高": stationary[2], "稳态_高": stationary[3],
                        "空间条件独立性G统计量": observed_g if name == "无条件" else np.nan,
                        "置换p值": perm_p if name == "无条件" else np.nan})
    summary_df = pd.DataFrame(summary)
    summary_df.to_csv(out / "空间马尔科夫汇总.csv", index=False, encoding="utf-8-sig")

    fig, axes = plt.subplots(1, 4, figsize=(18, 4.5))
    for ax, (name, matrix) in zip(axes, matrices.items()):
        sns.heatmap(matrix, annot=True, fmt=".2f", cmap="Blues", vmin=0, vmax=1,
                    xticklabels=labels, yticklabels=labels, cbar=False, ax=ax)
        ax.set_title(name)
        ax.set_xlabel("下一期状态")
        ax.set_ylabel("本期状态")
    fig.suptitle("高质量发展水平的空间条件转移概率", fontsize=16)
    fig.tight_layout()
    fig.savefig(out / "空间马尔科夫转移矩阵.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    stay = []
    for name, matrix in matrices.items():
        stay.append({"空间条件": name, **{labels[i]: matrix[i, i] for i in range(4)}})
    stay_df = pd.DataFrame(stay).set_index("空间条件")
    stay_df.plot(kind="bar", ax=ax, color=["#9DC3E6", "#5B9BD5", "#2F75B5", "#1F4E78"])
    ax.set_ylabel("原状态保持概率")
    ax.set_xlabel("")
    ax.set_ylim(0, 1)
    ax.set_title("不同空间环境下的状态锁定概率")
    ax.legend(title="状态", ncol=4)
    fig.tight_layout()
    fig.savefig(out / "空间状态锁定概率.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    return matrix_df, summary_df


def main() -> None:
    setup_style()
    df = load_data()
    weights = make_weights()
    run_spatial_autocorrelation(df, weights)
    run_robustness(df)
    run_endogeneity(df)
    run_spatial_spillover(df, weights)
    run_threshold(df)
    run_spatial_markov(df, weights)
    print("全部扩展实证分析完成。")


if __name__ == "__main__":
    main()
