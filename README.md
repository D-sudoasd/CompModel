# CompCTE

**Two-Phase Composite CTE Calculator**  
**可解释的两相复合材料 CTE 本地计算器**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/downloads/)

本地 **Streamlit** 工具：用各相晶面族 CTE、峰面积、R 因子与体积分数，计算  
**XRD 衍射强度加权表观相 CTE**，再给出 **串联 / 并联**（及 Turner、Kerner 等）复合结果。

**设计原则：计算过程透明、物理假设明确，不把单一模型包装成“唯一真实 CTE”。**

```bash
git clone https://github.com/D-sudoasd/compcte.git
cd compcte
py -3 -m pip install -r requirements.txt
py -3 -m streamlit run app.py
```

---

## 换电脑 / 第一次使用（3 步）

### 0. 环境要求

- Windows 10/11（也可用 macOS/Linux 命令行）
- **Python 3.10+**（安装时勾选 *Add python.exe to PATH*）
- 能访问 PyPI 的网络（首次装依赖）

### 1. 获取代码

```bash
git clone https://github.com/D-sudoasd/compcte.git
cd compcte
```

或下载 ZIP 后解压整包（**不要只拷 `app.py`**，需保留 `cte_app/`、`requirements.txt` 等）。

### 2. 安装依赖

**方式 A（推荐，Windows 双击）**

1. 双击 `首次安装依赖.bat`（英文机可双击 `install_deps.bat`）
2. 等待 pip 结束，看到“成功”

**方式 B（命令行）**

```bash
cd <本项目根目录>
py -3 -m pip install -r requirements.txt
# 若没有 py 启动器：
python -m pip install -r requirements.txt
```

### 3. 启动

**方式 A：** 双击 `启动_CTE计算器.bat`（或 `start_app.bat`）

**方式 B：**

```bash
cd <本项目根目录>
py -3 -m streamlit run app.py
```

浏览器会打开界面（一般是 `http://localhost:8501`）。  
**关闭黑色命令行窗口 = 停止程序。**

更细的操作说明见 → **[docs/00_QUICKSTART.md](docs/00_QUICKSTART.md)**  
目录说明见 → **[docs/PROJECT_MAP.md](docs/PROJECT_MAP.md)**

---

## 30 秒会什么

| 功能 | 说明 |
|------|------|
| 直接 CTE | 每相填一个标量 α + 体积分数 → 复合 |
| XRD 加权 | 晶面表：α_hkl、峰面积、R → 相表观 CTE |
| 内置 R 表 | β-Ti no_LP；α″ Shuffle-58 / 73 下拉填充 |
| 串联 / 并联 | 默认对照；填 E 后可拉开并联 |
| 工程 JSON | 导入/导出可再加载的输入包 |
| 导出 | JSON / CSV / Excel（含模型区间与 R 匹配报告） |

---

## 项目结构

```
compcte/
├── README.md                 ← 你在这里
├── LICENSE                   ← MIT
├── AGENTS.md                 ← 给协作者 / AI
├── requirements.txt          ← pip 依赖
├── pyproject.toml            ← package name: compcte
├── app.py                    ← Streamlit 入口
├── 首次安装依赖.bat / install_deps.bat
├── 启动_CTE计算器.bat / start_app.bat
├── cte_app/                  ← 计算核心（与 UI 解耦）
│   └── data/r_libraries/     ← 内置 R 因子库（运行真源）
├── sample_data/              ← 示例项目与结构模板
├── scripts/                  ← 批处理分析（如 ZTE）
├── tests/                    ← pytest
├── docs/
│   ├── 00_QUICKSTART.md
│   ├── PROJECT_MAP.md
│   ├── model_assumptions.md
│   └── specs/                ← 原始需求 PDF
├── results/                  ← 本地计算结果（默认不入库）
└── raw_sources/              ← 本地原始备份（默认不入库）
```

---

## 测试

```bash
py -3 -m pip install pytest
py -3 -m pytest -q
```

---

## 科学概念请区分

1. **晶面族晶格 CTE**（表中每一行 α）  
2. **XRD 衍射强度加权表观相 CTE**（相内加权结果）  
3. **复合材料宏观有效 CTE**（ROM / 并联等模型）

模型公式与假设：`docs/model_assumptions.md`。

---

## 常见问题

**Q: 双击启动提示没有 Python**  
A: 安装 [Python 3.10+](https://www.python.org/downloads/)，勾选 Add to PATH，重开终端后再装依赖。

**Q: 提示没有 streamlit**  
A: 先运行 `首次安装依赖.bat`。

**Q: 浏览器没自动打开**  
A: 手动访问命令行里显示的 Local URL（通常 `http://localhost:8501`）。

**Q: 内置 R 从哪来？**  
A: 见 `cte_app/data/r_libraries/catalog.json`（运行真源）。

**Q: 能否离线安装？**  
A: 需在有网机器 `pip download -r requirements.txt -d wheels`，目标机  
`pip install --no-index --find-links=wheels -r requirements.txt`。

---

## 许可与责任

- 许可证：**[MIT](LICENSE)**  
- 科研自用 / 教学工具。结果依赖输入质量与模型假设，**请勿当作唯一标定真值**。  
- 问题与二次开发请先读 `docs/PROJECT_MAP.md` 与 `AGENTS.md`。
