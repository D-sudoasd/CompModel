# 两相复合 CTE 模型假设与适用范围

此文档描述保留的 CTE / XRD 工作流。CompModel 多相弹性、输运及其他物性参见 [effective_properties.md](effective_properties.md)。

## 概念区分

1. **晶面族晶格 CTE**（`alpha_hkl`）：由特定晶面间距随温度变化得到的方向性膨胀系数。
2. **XRD 衍射强度加权表观相 CTE**：由峰面积与 R 因子得到的晶面权重加权平均，**不是**严格的单相本征宏观 CTE。
3. **复合材料宏观有效 CTE**：在给定微结构与力学假设下，由两相表观 CTE 与弹性参数经解析模型估算。

## R 因子定义

| 定义 | 公式 |
|------|------|
| theoretical_relative_intensity | `I_corr = peak_area / R_factor` |
| multiplicative_correction | `I_corr = peak_area * R_factor` |
| already_corrected_weight | `I_corr = peak_area` |
| custom_weight | `I_corr = custom_weight` |

不得默认不同实验室的 R 因子含义相同。

## 模型公式

### ROM（自由伸长 / 体积分数混合）

\[
\alpha_{\mathrm{rom}} = f_1\alpha_1 + f_2\alpha_2
\]

- 不引入弹性不匹配
- 筛选级估计

### 并联（等应变一维）

\[
\alpha_{\parallel} = \frac{f_1 E_1\alpha_1 + f_2 E_2\alpha_2}{f_1 E_1 + f_2 E_2}
\]

- 同方向总应变相等、界面完全结合、线弹性、外力合力为零

### Turner

\[
\alpha_{\mathrm{Turner}} = \frac{f_1 K_1\alpha_1 + f_2 K_2\alpha_2}{f_1 K_1 + f_2 K_2}
\]

- 近似各向同性、体积/静水约束主导

### Kerner

\[
\alpha_{\mathrm{Kerner}} =
\frac{
\alpha_i f_i \frac{K_i}{3K_i+4G_m}
+
\alpha_m f_m \frac{K_m}{3K_m+4G_m}
}{
f_i \frac{K_i}{3K_i+4G_m}
+
f_m \frac{K_m}{3K_m+4G_m}
}
\]

- **必须**明确 matrix / inclusion
- 球形颗粒、连续基体、近似各向同性

## 弹性换算

\[
K = \frac{E}{3(1-2\nu)},\quad G = \frac{E}{2(1+\nu)}
\]

要求 \(E>0\), \(K>0\), \(G>0\), \(-1<\nu<0.5\)。

## 孔隙

首版不把孔隙当作零 CTE、零模量的第三相代入全部两相公式。孔隙 > 0 时显示警告，可选仅按实体相归一化体积分数（筛选用途）。

## 后续扩展

- 张量 CTE / Mori–Tanaka
- 有限元 RVE
- 严格三相（含孔隙）模型
