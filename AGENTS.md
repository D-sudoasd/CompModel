# AGENTS.md — 协作者与 AI 工作约定

**项目公开名：CompModel**（原 CompCTE）。仓库和发行包暂保留 `compcte`，内部计算包仍为 `cte_app`。

## 这是什么

多相复合材料有效性能建模：Streamlit UI + `cte_app` 纯计算库；保留两相 CTE / XRD 工作流。
面向材料科研；结果必须可解释，禁止静默选“唯一真值”。

## 必读

1. `README.md` — 安装启动  
2. `docs/00_QUICKSTART.md` — 用户操作  
3. `docs/PROJECT_MAP.md` — 目录  
4. `docs/model_assumptions.md` — 科学假设  
5. `docs/effective_properties.md` — 多相模型、单位、公式与适用范围

## 架构边界

- **UI** 只在 `app.py`  
- **公式与校验** 只在 `cte_app/*.py`  
- **内置 R** 只在 `cte_app/data/r_libraries/`（不要改去依赖 `raw_sources`）  
- 分析结果写 `results/`，不要堆根目录  

## 常用命令

```bash
# 依赖
py -3 -m pip install -r requirements.txt

# 启动
py -3 -m streamlit run app.py

# 测试
py -3 -m pytest -q
```

## 编码约定

- 内部单位：CTE → 1/K，模量 → Pa；界面显示 10⁻⁶/K、GPa  
- R 默认定义：`corrected_intensity = peak_area / R`  
- 体积分数约束：Σfᵢ=1；质量分数必须通过密度显式换算
- 新多相模型在 `homogenization.py`，工程、扫描和分级均匀化在 `composite_project.py`
- Kerner 必须显式 matrix/inclusion  
- 中文用户回复；代码标识符保持英文  

## 禁止

- 在缺少 matrix/inclusion 时静默算 Kerner  
- 温度外推不警告  
- 覆盖 `raw_sources` 原始备份而不留记录  
- 删除 `results` 用户报告而不询问  

## 扩展 R 库

1. 将 `h,k,l,hkl,R_hkl_no_LP` CSV 放入 `cte_app/data/r_libraries/`  
2. 更新 `catalog.json`  
3. 加 `tests/test_r_library.py` 断言  
4. `pytest tests/test_r_library.py -q`  

## 交付语言

默认中文说明；路径与命令保持可复制原文。
