# 项目目录地图

## 根目录（给人用的入口）

| 路径 | 作用 |
|------|------|
| `README.md` | 安装、启动、FAQ |
| `docs/00_QUICKSTART.md` | 界面操作 5 分钟 |
| `app.py` | Streamlit 唯一 UI 入口 |
| `启动_CTE计算器.bat` / `start_app.bat` | 双击启动 |
| `首次安装依赖.bat` / `install_deps.bat` | 双击装依赖 |
| `requirements.txt` | pip 依赖列表 |
| `pyproject.toml` | 包元数据 / 可选 editable 安装 |

## 代码

| 路径 | 作用 |
|------|------|
| `cte_app/` | 计算核心，**勿把公式写进 app.py** |
| `cte_app/phase_weighting.py` | 单相 XRD 加权 |
| `cte_app/composite_models.py` | ROM / 并联 / Turner / Kerner |
| `cte_app/r_library.py` | 内置 R 表加载与匹配 |
| `cte_app/data/r_libraries/` | **R 因子运行真源**（catalog + csv） |
| `cte_app/model_advisor.py` | 规则推荐 |
| `cte_app/uncertainty.py` | Monte Carlo |
| `cte_app/export.py` | 导出 |
| `tests/` | pytest |

## 数据与文档

| 路径 | 作用 |
|------|------|
| `sample_data/` | 界面示例 JSON/CSV |
| `raw_sources/` | 原始备份，**非运行依赖** |
| `results/` | 脚本/分析输出 |
| `docs/specs/` | 需求 PDF 归档 |
| `docs/model_assumptions.md` | 模型假设 |

## 改代码从哪进

| 需求 | 文件 |
|------|------|
| 改界面布局 | `app.py` |
| 改加权公式 | `cte_app/phase_weighting.py` |
| 改复合模型 | `cte_app/composite_models.py` |
| 增加一套内置 R | `cte_app/data/r_libraries/` + `catalog.json` |
| 改推荐规则 | `cte_app/model_advisor.py` |

## 不要放在根目录的东西

- 大体积原始实验数据 → `raw_sources/` 或项目外  
- 计算结果 → `results/`  
- 规格/论文 PDF → `docs/`  

## 整理记录

最近一次目录整理：`MOVE_LOG_tidy.csv`（根目录）。
