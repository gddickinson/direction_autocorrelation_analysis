"""Write tests/fixtures/dac_fixture.json: small CSV inputs plus the results of the repo's Python analysis on them.

The node test web/static/dac_engine.test.mjs runs the JS port on the same CSV text and asserts agreement to 1e-9.
Expected values come from web.analysis.analyse_upload, i.e. io_utils.read_file + core.process_sheet.
Inputs are seeded persistent random walks (heading += N(0, sigma) per frame, as in test_core.py) plus edge cases:
a one-point segment, a zero-length step, a missing value, a frame gap, alias headers, the 6-column fallback and
numeric condition labels with a missing label.

Run: python scripts/make_dac_fixture.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web.analysis import analyse_upload  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "dac_fixture.json"


def walk(rng, n, sigma, step=2.5):
    th = rng.uniform(0, 2 * np.pi) + np.cumsum(rng.normal(0, sigma, n))
    x = 100 + np.concatenate([[0], np.cumsum(step * np.cos(th[:-1]))])
    y = 100 + np.concatenate([[0], np.cumsum(step * np.sin(th[:-1]))])
    return x, y


def case_conditions(rng):
    lines = ["condition,track_id,frame,x,y"]
    tid = 0
    for cond, sigma, lengths in [("persistent", 0.3, [30, 25, 8, 1]), ("random", 1.2, [28, 14, 6])]:
        for L in lengths:
            tid += 1
            x, y = walk(rng, L, sigma)
            for k in range(L):
                xs, ys = repr(float(x[k])), repr(float(y[k]))
                if cond == "persistent" and L == 25 and k == 10:      # zero-length step: same position as frame 10
                    xs, ys = repr(float(x[k - 1])), repr(float(y[k - 1]))
                if cond == "random" and L == 28 and k == 5:           # missing value: row dropped
                    xs = ""
                frame = k + 1 + (3 if cond == "random" and L == 14 and k > 6 else 0)  # frame gap, same track
                lines.append(f"{cond},{tid},{frame},{xs},{ys}")
    return "\n".join(lines) + "\n"


def case_aliases(rng):
    lines = ["Frame_Number,X_Position,Y_Position,intensity"]
    for L in [40, 22, 3]:
        x, y = walk(rng, L, 0.6, step=1.7)
        lines += [f"{k},{float(x[k])!r},{float(y[k])!r},{rng.uniform(100, 900):.1f}" for k in range(L)]
    return "\n".join(lines) + "\n"


def case_positional(rng):
    lines = ["id,a,b,t,px,py"]
    for i, L in enumerate([18, 12]):
        x, y = walk(rng, L, 0.4)
        lines += [f"{i},0,0,{k},{float(x[k])!r},{float(y[k])!r}" for k in range(L)]
    return "\n".join(lines) + "\n"


def case_numeric_groups(rng):
    """Numeric condition labels ('02' is read as 2) with one row whose label is missing (so pandas uses floats)."""
    lines = ["group,frame,x,y"]
    for g, L in [("02", 15), ("1", 12), ("02", 9), ("", 5), ("10", 8)]:
        x, y = walk(rng, L, 0.5)
        lines += [f"{g},{k + 1},{float(x[k])!r},{float(y[k])!r}" for k in range(L)]
    return "\n".join(lines) + "\n"


def main():
    rng = np.random.default_rng(20261111)
    cases = []
    for name, csv, dt, n in [("conditions", case_conditions(rng), 0.5, 12),
                             ("aliases", case_aliases(rng), 1.0, 25),
                             ("positional", case_positional(rng), 0.1, 7),
                             ("numeric_groups", case_numeric_groups(rng), 1.0, 6)]:
        res = analyse_upload(name + ".csv", csv.encode(), dt, n)
        for c in res["conditions"]:
            c.pop("segments", None)
        cases.append({"name": name, "csv": csv, "time_interval": dt, "num_intervals": n, "expected": res})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated_by": "scripts/make_dac_fixture.py", "cases": cases}, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e3:.1f} kB, {len(cases)} cases)")


if __name__ == "__main__":
    main()
