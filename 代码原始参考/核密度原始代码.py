"""
Kernel Density Estimation - Complete Version
Includes:
1. Y and X density plots with all years overlaid (national trend)
2. Y and X regional comparison plots for each year 2016-2020
Output: 结果/核密度/
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import warnings

warnings.filterwarnings("ignore")

# ========== 1. Path Configuration ==========
BASE = Path(__file__).resolve().parent
DATA_PATH = BASE / "数据" / "新构建分析数据.csv"
OUT_DIR = BASE / "结果" / "核密度"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ========== 2. Set Style ==========
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")
sns.set_context("notebook", font_scale=1.1)

print("=" * 60)
print("KERNEL DENSITY ESTIMATION - COMPLETE VERSION")
print(f"Output: {OUT_DIR}")
print("=" * 60)

# ========== 3. Load Data ==========
df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')
df['year'] = df['year'].astype(int)
print(f"Data loaded: {len(df)} rows, {df['province'].nunique()} provinces")

# ========== 4. Region Matching ==========
region_keywords = {
    'Eastern': ['北京', '天津', '河北', '上海', '江苏', '浙江', '福建', '山东', '广东', '海南', '辽宁'],
    'Central': ['山西', '安徽', '江西', '河南', '湖北', '湖南', '吉林', '黑龙江'],
    'Western': ['内蒙古', '广西', '重庆', '四川', '贵州', '云南', '西藏', '陕西', '甘肃', '青海', '宁夏', '新疆']
}


def match_region(name):
    for region, keywords in region_keywords.items():
        for kw in keywords:
            if kw in name:
                return region
    return None


df['region'] = df['province'].apply(match_region)
print("\nRegion distribution:")
print(df['region'].value_counts())

colors = {'Eastern': '#1f77b4', 'Central': '#ff7f0e', 'Western': '#2ca02c'}
years = sorted(df['year'].unique())

# ========== 5. PART A: 不分区域·年份叠加图（全国整体趋势） ==========
print("\n" + "=" * 60)
print("PART A: National Trends (All Years Overlaid)")
print("=" * 60)

# 5a. Y 的年份叠加图
print("\n[1/4] Y (High-Quality Development) - All Years Overlaid...")
plt.figure(figsize=(12, 7))
for year in years:
    subset = df[df['year'] == year]['y_clean']
    if subset.std() > 1e-10:
        sns.kdeplot(subset, label=str(year), linewidth=2.5, alpha=0.8)

plt.xlabel("High-Quality Development Index", fontsize=13)
plt.ylabel("Density", fontsize=13)
plt.title("Kernel Density: High-Quality Development Index (2016-2020)", fontsize=15, fontweight='bold')
plt.legend(title="Year", fontsize=11)
plt.grid(alpha=0.3)
plt.xlim(0, 1)
plt.tight_layout()
plt.savefig(OUT_DIR / "KDE_Y_2016_2020_overlay.png", dpi=300, bbox_inches='tight')
plt.close()
print("   Saved: KDE_Y_2016_2020_overlay.png")

# 5b. X 的年份叠加图
print("\n[2/4] X (Cumulative TFP) - All Years Overlaid...")
plt.figure(figsize=(12, 7))
for year in years:
    subset = df[df['year'] == year]['cum_tfp']
    if subset.std() > 1e-10:
        sns.kdeplot(subset, label=str(year), linewidth=2.5, alpha=0.8)

plt.xlabel("Cumulative Agricultural TFP (2016=1)", fontsize=13)
plt.ylabel("Density", fontsize=13)
plt.title("Kernel Density: Cumulative Agricultural TFP (2016-2020)", fontsize=15, fontweight='bold')
plt.legend(title="Year", fontsize=11)
plt.grid(alpha=0.3)
plt.xlim(0.5, 3.5)
plt.tight_layout()
plt.savefig(OUT_DIR / "KDE_X_TFP_2016_2020_overlay.png", dpi=300, bbox_inches='tight')
plt.close()
print("   Saved: KDE_X_TFP_2016_2020_overlay.png")

# ========== 6. PART B: 分区域·逐年图（区域对比） ==========
print("\n" + "=" * 60)
print("PART B: Regional Comparisons (Year by Year)")
print("=" * 60)

# 6a. Y 的分区域逐年图
print("\n[3/4] Y (High-Quality Development) - Regional Comparison by Year...")
for year in years:
    df_year = df[df['year'] == year]
    plt.figure(figsize=(10, 6))

    has_data = False
    for region in ['Eastern', 'Central', 'Western']:
        subset = df_year[df_year['region'] == region]['y_clean']
        if len(subset) > 0 and subset.std() > 1e-10:
            sns.kdeplot(subset, label=region, linewidth=2.5,
                        color=colors.get(region, '#333'), alpha=0.8)
            has_data = True

    if has_data:
        plt.xlabel("High-Quality Development Index", fontsize=12)
        plt.ylabel("Density", fontsize=12)
        plt.title(f"Regional Comparison: Y (High-Quality Development) - {year}",
                  fontsize=14, fontweight='bold')
        plt.legend(title="Region", fontsize=10)
        plt.grid(alpha=0.3)
        plt.xlim(0, 1)
        plt.tight_layout()
        plt.savefig(OUT_DIR / f"KDE_Y_{year}_by_region.png", dpi=300, bbox_inches='tight')
        plt.close()
        print(f"   Saved: KDE_Y_{year}_by_region.png")

# 6b. X 的分区域逐年图
print("\n[4/4] X (Cumulative TFP) - Regional Comparison by Year...")
for year in years:
    df_year = df[df['year'] == year]
    plt.figure(figsize=(10, 6))

    has_data = False
    for region in ['Eastern', 'Central', 'Western']:
        subset = df_year[df_year['region'] == region]['cum_tfp']
        if len(subset) > 0 and subset.std() > 1e-10:
            sns.kdeplot(subset, label=region, linewidth=2.5,
                        color=colors.get(region, '#333'), alpha=0.8)
            has_data = True

    if has_data:
        plt.xlabel("Cumulative Agricultural TFP (2016=1)", fontsize=12)
        plt.ylabel("Density", fontsize=12)
        plt.title(f"Regional Comparison: X (Agricultural TFP) - {year}",
                  fontsize=14, fontweight='bold')
        plt.legend(title="Region", fontsize=10)
        plt.grid(alpha=0.3)
        plt.xlim(0.5, 3.5)
        plt.tight_layout()
        plt.savefig(OUT_DIR / f"KDE_X_TFP_{year}_by_region.png", dpi=300, bbox_inches='tight')
        plt.close()
        print(f"   Saved: KDE_X_TFP_{year}_by_region.png")

# ========== 7. Summary Statistics ==========
print("\n" + "=" * 60)
print("SUMMARY STATISTICS (2016 vs 2020)")
print("=" * 60)

y_2016 = df[df['year'] == 2016]['y_clean']
y_2020 = df[df['year'] == 2020]['y_clean']
x_2016 = df[df['year'] == 2016]['cum_tfp']
x_2020 = df[df['year'] == 2020]['cum_tfp']

print(f"\nY (High-Quality Development Index):")
print(f"  2016: mean={y_2016.mean():.4f}, std={y_2016.std():.4f}")
print(f"  2020: mean={y_2020.mean():.4f}, std={y_2020.std():.4f}")
print(f"  Change: +{y_2020.mean() - y_2016.mean():.4f}")

print(f"\nX (Cumulative Agricultural TFP, 2016=1):")
print(f"  2016: mean={x_2016.mean():.4f}, std={x_2016.std():.4f}")
print(f"  2020: mean={x_2020.mean():.4f}, std={x_2020.std():.4f}")
print(f"  Change: +{x_2020.mean() - x_2016.mean():.4f}")

print("\n" + "=" * 60)
print("ALL COMPLETED!")
print(f"Output folder: {OUT_DIR}")
print("\nFiles generated:")
print("  [National Trends - Overlay]")
for f in sorted(OUT_DIR.glob("KDE_*_overlay.png")):
    print(f"    - {f.name}")
print("  [Regional Comparisons - Year by Year]")
for f in sorted(OUT_DIR.glob("KDE_*_by_region.png")):
    print(f"    - {f.name}")
print("=" * 60)
from pathlib import Path

