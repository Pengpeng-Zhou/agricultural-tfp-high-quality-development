# MDPI/Sustainability 英文投稿包

本目录是按 MDPI/Sustainability 模板整理的英文稿及其图表资源。

## 文件

- `template.tex`: 主文件，包含方法公式、假设 H1--H5、描述性分析、基准回归、稳健性、空间效应、门槛和空间马尔可夫结果。
- `figure1/`: 英文核密度图、Y 三维曲面图、累计 TFP 热力图、回归表和配套校验数据。
- `figures/`: 英文 Dagum、Moran、耦合协调、空间影响分解、门槛和马尔可夫图表。
- `Definitions/`: MDPI 类文件和编译所需资源。
- `template_final.pdf`: 最新编译结果。

## 编译

在本目录运行两次：

```text
pdflatex -interaction=nonstopmode -halt-on-error template.tex
pdflatex -interaction=nonstopmode -halt-on-error template.tex
```

图表文件必须保持 `figure1/` 和 `figures/` 的相对目录结构。2016 年累计 TFP 的共同基期、空间权重中海南与广东的桥接、门槛变量与高质量发展指数的指标重叠，以及内部工具变量的识别限制，均已在正文和图表说明中明确记录。
