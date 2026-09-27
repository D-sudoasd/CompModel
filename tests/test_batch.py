import json

import pytest

from cte_app.batch import main
from cte_app.composite_project import demo_project, json_bytes, project_dict, load_project


def test_batch_report_sweep_and_existing_directory_protection(tmp_path):
    source = tmp_path / "input.json"
    source.write_bytes(json_bytes(project_dict(demo_project())))
    target = tmp_path / "output"
    args = [str(source), "--family", "elastic", "--sweep-phase", "1", "--output", str(target)]
    assert main(args) == 0
    report_path = target / "report.json"
    before = report_path.read_bytes()
    assert load_project(json.loads(before)) == demo_project()
    assert (target / "sweep_SI.csv").is_file()
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    assert report_path.read_bytes() == before
