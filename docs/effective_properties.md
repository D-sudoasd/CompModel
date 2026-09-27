# CompModel 多相有效性能模型

本工作台计算标量或各向同性有效性能。各相数据应来自同一温度、压力和测量条件；教学示例不是材料数据库。所有模型并列展示，程序不替用户选择唯一有效性能。

## 组成、单位和零值

内部采用 SI：E、K、G 为 Pa，α 为 1/K，k 为 W/(m·K)，σ 为 S/m，ρ 为 kg/m³，cp 为 J/(kg·K)。界面弹性单位为 GPa，CTE 为 10⁻⁶/K。自定义系数的单位由工程显式指定，所有相必须一致。

支持任意数量的组成相，要求输入分数非负且总和为 1（数值容差 10⁻⁹）；不自动修正错误配比。质量分数 w 经密度换算：fᵢ=(wᵢ/ρᵢ)/Σ(wⱼ/ρⱼ)。零分数相不参与一般平均；两相形貌模型仍要求明确的两个相及其角色。

空白表示未知，不能用 0 代替。弹性模型要求严格正的 K、G（或 E>0、−1<ν<0.5）；本版不处理弹性孔隙和液相。输运系数允许为零，调和平均按绝缘层极限处理；几何平均只接受正值。CTE 和自定义算术平均允许负值。

## 弹性

每相输入 E、ν 或 K、G；同时提供时必须一致，程序不会静默选一组。

K=E/[3(1−2ν)]，G=E/[2(1+ν)]。
有效 E=9KG/(3K+G)，ν=(3K−2G)/[2(3K+G)]。

- **Voigt**：K_V=ΣfᵢKᵢ，G_V=ΣfᵢGᵢ；均匀应变上界。
- **Reuss**：K_R=1/Σ(fᵢ/Kᵢ)，G_R=1/Σ(fᵢ/Gᵢ)；均匀应力下界。
- **Hill**：分别对 K、G 的 Voigt 和 Reuss 结果取算术平均；属于估计，不是额外边界。
- **Hashin–Shtrikman**：三维宏观各向同性；使用各相最大/最小 K₀、G₀ 构造上下参考介质。令 ζ₀=G₀(9K₀+8G₀)/[6(K₀+2G₀)]，则 K=⟨1/(Kᵢ+4G₀/3)⟩⁻¹−4G₀/3，G=⟨1/(Gᵢ+ζ₀)⟩⁻¹−ζ₀。多相采用 Hashin–Shtrikman–Walpole 形式。

这里 ⟨·⟩ 为体积分数加权。E 的边界由对应 K、G 换算；**ν 的对应值不是泊松比上下界**。这些计算针对各向同性相的集合体，不是任意单晶取向集合的张量均匀化。

**Mori–Tanaka（球形夹杂、两相）**需显式指定 matrix 与 inclusion：

K=Kₘ+fᵢ(Kᵢ−Kₘ)/[1+fₘ(Kᵢ−Kₘ)/(Kₘ+4Gₘ/3)]；
G=Gₘ+fᵢ(Gᵢ−Gₘ)/[1+fₘ(Gᵢ−Gₘ)/(Gₘ+ζₘ)]。

假设连续基体、各向同性线弹性相、完全结合；不显式描述团聚、界面层和裂纹。高夹杂含量时需验证基体连续性的假设。

**Halpin–Tsai**仅给出指定方向的杨氏模量：

η=(Eᵢ/Eₘ−1)/(Eᵢ/Eₘ+ξ)，E=Eₘ(1+ξηfᵢ)/(1−ηfᵢ)。

ξ>0 需按形貌、方向或实验标定；默认 2 是演示参数。此结果不能和各向同性弹性边界当作同一类结论，也不能从一个方向 E 自动恢复 K、G、ν。

## 导热与导电

两者在**稳态、线性、标量、界面无阻抗**的条件下共享数学形式。令 x 为 k 或 σ：

- Arithmetic：x=Σfᵢxᵢ，层状材料沿层方向；一般标量输运上界。
- Harmonic：x=1/Σ(fᵢ/xᵢ)，垂直层方向；一般标量输运下界。
- Geometric：x=exp(Σfᵢln xᵢ)，经验混合规则。
- Hashin–Shtrikman：三维宏观各向同性，x=⟨1/(xᵢ+2x₀)⟩⁻¹−2x₀；参考值 x₀ 取最小/最大系数。
- Maxwell：两相、球形夹杂、正系数连续基体，x=xₘ[xᵢ+2xₘ+2fᵢ(xᵢ−xₘ)]/[xᵢ+2xₘ−fᵢ(xᵢ−xₘ)]。

这些模型不包含界面热阻、隧穿导电或渗流网络，不能据此预测实际导电阈值。

## 热膨胀、密度、比热和通用系数

多相 CTE 包括 ROM、E 加权一维 Parallel、K 加权 Turner；两相 Kerner 复用原计算库。详见 [CTE 模型假设](model_assumptions.md)。原 XRD 加权流程保留在独立页面，表观相 CTE 不等于本征宏观 CTE。

密度 ρ=Σfᵢρᵢ，要求体积可加。质量比热 cp=Σ(fᵢρᵢcpᵢ)/Σ(fᵢρᵢ)，要求局部热平衡且无相变潜热；**不能直接按体积分数平均质量比热**。

自定义系数仅提供算术、调和与几何规则，并保留系数名称及单位。系数的物理含义由用户定义；程序不把任意系数当作导热系数，也不把标量平均当作压电、热电等耦合本构关系。

## 分级均匀化与扫描

用户显式选择某模型，将其输出属性保存为有效相，再与其他相建立下一层。仅继承该模型实际输出的属性；缺少属性必须补充。来源工程、模型、ξ、公式与假设随相记录并写入 JSON。

各层之间假设存在尺度分离；这是一种建模近似，不是对真实团聚形貌的解析求解。界面层、颗粒空间关联、各向异性张量、多场耦合及有限元 RVE 尚未实现。

组成扫描逐点改变指定相的体积分数（0–1），其他相保持相互体积比。导出包含不可用原因；曲线间差异不是置信区间。新工作台未实现温度扫描或温度外推。

## 工程与可复现性

新工程使用 `format=compmodel.project`、`schema_version=1`；JSON 属性采用内部 SI，完整报告额外记录物理量、ξ、实际体积分数和所有模型的结果/不可用原因。可导入输入工程或完整报告。旧 CTE JSON 仍在 CTE / XRD 页面导入。

有效相列表保存在当前会话中。需要长期保存时，建立下一层后下载工程 JSON；文件包含上一层来源。刷新或关闭会话前请保存工程。

## 公式参考

1. [COMSOL Material Library：混合规则、Voigt–Reuss 与 Halpin–Tsai](https://doc.comsol.com/6.3/doc/com.comsol.help.matlib/matlib_ug_using.3.28.html)。
2. [Rock physics modelling for determination of effective elastic properties…：多相 Hashin–Shtrikman–Walpole 形式](https://link.springer.com/article/10.1007/s11600-019-00355-6)。
3. [Exact results for generalized Biot–Gassmann equations…，附录 B：两相 Hashin–Shtrikman 边界](https://academic.oup.com/gji/article/203/3/1575/2594790)。
4. [Archives of Mechanics：球形夹杂 Mori–Tanaka 弹性公式](https://am.ippt.gov.pl/index.php/am/article/download/v70p337/pdf/7436)。
5. [Stránský 等：Mori–Tanaka Based Estimates of Effective Thermal Conductivity of Various Engineering Materials](https://arxiv.org/abs/1101.4121)。

本仓库的测试验证公式实现、守恒、端点、边界顺序与界面流程；不替代真实材料实验验证。
