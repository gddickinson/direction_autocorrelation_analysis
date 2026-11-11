"""Web interface tests: every exported endpoint answers, the static build is complete, and the JS engine tests pass.

Run: python -m pytest -q tests/test_web.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web.app import STATIC, STATIC_ENDPOINTS, app  # noqa: E402

client = TestClient(app)


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200 and "static/main.js" in r.text


@pytest.mark.parametrize("path", STATIC_ENDPOINTS)
def test_endpoint(path):
    r = client.get("/api" + path)
    assert r.status_code == 200, r.text
    assert r.json() is not None


def test_static_build(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_static
    build_static.build(tmp_path / "site")
    assert (tmp_path / "site" / "index.html").read_text().count("APP_STATIC") == 1
    for path in STATIC_ENDPOINTS:
        assert (tmp_path / "site" / "api" / (path.strip("/") + ".json")).exists()


def test_static_assets_referenced_exist():
    html = (STATIC / "index.html").read_text()
    for name in ("style.css", "main.js"):
        assert f"static/{name}" in html and (STATIC / name).exists()


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_js_engine():
    tests = sorted(STATIC.glob("*.test.mjs"))
    for t in tests:
        r = subprocess.run(["node", str(t)], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr


# --- project-specific: the upload endpoint runs the repo's Python analysis ---------------------------------------
import json  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "dac_fixture.json").read_text())


def _post(csv: str, dt=1.0, n=10, name="t.csv"):
    return client.post("/api/analyze", files={"file": (name, csv.encode(), "text/csv")},
                       data={"time_interval": str(dt), "num_intervals": str(n)})


def test_info_has_config_defaults():
    import config
    d = client.get("/api/info").json()["defaults"]
    assert d["time_interval"] == config.INPUT_TIME_INTERVAL and d["num_intervals"] == config.INPUT_NUM_INTERVALS


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda c: c["name"])
def test_analyze_matches_fixture(case):
    """The endpoint reproduces the committed fixture (so the JS test compares against what the server returns)."""
    r = _post(case["csv"], case["time_interval"], case["num_intervals"], case["name"] + ".csv")
    assert r.status_code == 200, r.text
    got = r.json()
    for g, e in zip(got["conditions"], case["expected"]["conditions"]):
        assert g["n_pairs"] == e["n_pairs"] and len(g["tracks"]) == len(e["tracks"])
        for a, b in zip(g["avg"] + g["sem"], e["avg"] + e["sem"]):
            assert (a is None and b is None) or abs(a - b) < 1e-12


def test_single_condition_identical_to_cli_path():
    """For a clean single-condition file the web layer gives exactly what read_file + process_sheet give (the CLI path)."""
    from core import process_sheet
    from io_utils import read_file
    case = FIXTURE["cases"][1]  # 'aliases': one condition, no missing values
    path = ROOT / "tests" / "fixtures" / "_tmp_aliases.csv"
    path.write_text(case["csv"])
    try:
        sheets, _ = read_file(str(path))
        _, averages, _ = process_sheet(sheets["Sheet1"], case["time_interval"], case["num_intervals"])
    finally:
        path.unlink()
    got = _post(case["csv"], case["time_interval"], case["num_intervals"]).json()["conditions"][0]
    np.testing.assert_array_equal(np.array(got["avg"], dtype=float), averages.loc["AVG"].to_numpy(dtype=float))


def test_every_condition_analysed():
    """Conditions after the first get real numbers (the web layer renumbers rows; see web/analysis.py)."""
    got = _post(FIXTURE["cases"][0]["csv"], 0.5, 12).json()["conditions"]
    assert len(got) == 2
    for c in got:
        assert all(v is not None for v in c["avg"])  # including the last lag (num_intervals * dt)


def test_excel_upload(tmp_path):
    pytest.importorskip("openpyxl")
    df = pd.DataFrame({"frame": range(1, 21), "x": np.cumsum(np.ones(20)), "y": np.zeros(20)})
    p = tmp_path / "t.xlsx"
    df.to_excel(p, sheet_name="straight", index=False)
    r = client.post("/api/analyze", files={"file": ("t.xlsx", p.read_bytes())}, data={"time_interval": "2", "num_intervals": "5"})
    c = r.json()["conditions"][0]
    assert c["name"] == "straight" and c["lags"] == [0, 2, 4, 6, 8, 10] and c["avg"][:5] == [1, 1, 1, 1, 1]


def test_bad_inputs():
    assert _post("frame,x,y\n1,0,0\n", name="t.txt").status_code == 400
    assert _post("frame,x,y\n1,0,0\n", dt=0).status_code == 400
    c = _post("a,b\n1,2\n").json()["conditions"][0]
    assert "error" in c
