"""Run a saved project: python -m cte_app.batch input.json --family elastic."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

import pandas as pd

from cte_app.composite_project import display_rows, json_bytes, load_project, report_dict, sweep
from cte_app.homogenization import FAMILIES, HomogenizationError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CompModel 多相有效性能批处理")
    parser.add_argument("input", type=Path)
    parser.add_argument("--family", choices=list(FAMILIES), required=True)
    parser.add_argument("--xi", type=float, default=2.)
    parser.add_argument("--output", type=Path, help="新建结果目录；已存在时拒绝覆盖")
    parser.add_argument("--sweep-phase", type=int, help="扫描相的索引（从 0 开始）")
    parser.add_argument("--points", type=int, default=51)
    args = parser.parse_args(argv)
    try:
        project = load_project(json.loads(args.input.read_text(encoding="utf-8-sig")))
        report = report_dict(project, args.family, args.xi)
        if not any(r["values"] for r in report["results"]):
            raise HomogenizationError("没有可用模型：" + "; ".join(r["reason"] for r in report["results"]))
        scan = sweep(project, args.family, args.sweep_phase, args.points, args.xi) if args.sweep_phase is not None else None
        report_bytes = json_bytes(report)
        output = args.output or Path("results") / ("compmodel_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        output.mkdir(parents=True, exist_ok=False)
        (output / "report.json").write_bytes(report_bytes)
        pd.DataFrame(display_rows(report["results"], project)).to_csv(output / "results.csv", index=False, encoding="utf-8-sig")
        if scan is not None:
            pd.DataFrame(scan).to_csv(output / "sweep_SI.csv", index=False, encoding="utf-8-sig")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"CompModel: {exc}\n")
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
