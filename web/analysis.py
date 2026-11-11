"""Bridge between the web API and the repo's real analysis code (io_utils.read_file, core.process_sheet).

Nothing here re-implements the maths: each sheet/condition goes through `core.process_sheet` exactly as `cli.process_file`
does. The one difference is preparation: the sheet is reduced to frame/x/y with `io_utils.identify_columns`, rows with
missing values are dropped and the index is reset to 0..n-1 BEFORE `process_sheet` is called.

The reset is now redundant: `core.process_sheet` renumbers rows itself since the 2026-11-11 fix (track starts were taken
from index labels but sliced by position, so every condition after the first in a multi-condition CSV came out NaN).
It is kept so this module does not depend on that detail.
"""
import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import process_sheet  # noqa: E402
from io_utils import get_file_type, identify_columns, read_file  # noqa: E402

MAX_SEGMENTS_RETURNED = 300  # trajectories sent back for plotting (per condition); the analysis always uses all


def _num(v):
    """JSON-safe float: NaN/inf become None."""
    v = float(v)
    return v if np.isfinite(v) else None


def _segments(df: pd.DataFrame):
    """Trajectory segments as process_sheet sees them: a new one starts wherever the frame number does not increase."""
    if len(df) == 0:
        return []
    frame = df["frame"].to_numpy(dtype=float)
    starts = [0] + [i for i in range(1, len(frame)) if frame[i] - frame[i - 1] <= 0] + [len(frame)]
    x, y = df["x"].to_numpy(dtype=float), df["y"].to_numpy(dtype=float)
    return [(i, starts[i], starts[i + 1]) for i in range(len(starts) - 1)], x, y


def analyse_sheet(name: str, raw: pd.DataFrame, time_interval: float, num_intervals: int) -> dict:
    """Run core.process_sheet on one sheet and return a JSON-ready dict (the same shape dac_engine.js produces)."""
    with contextlib.redirect_stdout(io.StringIO()):
        cols = identify_columns(raw)
    if cols is None:
        return {"name": str(name), "error": "Could not find frame, x and y columns (see the data format page)."}
    n_rows = len(cols)
    clean = cols.dropna(subset=["frame", "x", "y"]).reset_index(drop=True)
    with contextlib.redirect_stdout(io.StringIO()):
        scalar_products, averages, tracks = process_sheet(clean, time_interval, num_intervals)
    lags = [float(c) for c in averages.columns]
    n_pairs = [0] + [int(scalar_products[c].count()) for c in scalar_products.columns]
    track_list = {}
    for row in tracks.itertuples(index=False):
        t = track_list.setdefault(row.track_id, {"id": row.track_id, "t": [], "c": []})
        t["t"].append(float(row.time_interval))
        t["c"].append(_num(row.correlation))
    segs, segments_out = _segments(clean), []
    n_segments = 0
    if segs:
        bounds, x, y = segs
        n_segments = len(bounds)
        for i, a, b in bounds[:MAX_SEGMENTS_RETURNED]:
            segments_out.append({"id": f"track_{i + 1}", "x": [float(v) for v in x[a:b]], "y": [float(v) for v in y[a:b]]})
    return {
        "name": str(name), "n_rows": n_rows, "n_dropped": n_rows - len(clean), "n_segments": n_segments,
        "lags": lags, "avg": [_num(v) for v in averages.loc["AVG"]], "sem": [_num(v) for v in averages.loc["SEM"]],
        "n_pairs": n_pairs, "tracks": list(track_list.values()), "segments": segments_out,
    }


def analyse_upload(filename: str, data: bytes, time_interval: float, num_intervals: int) -> dict:
    """Analyse an uploaded CSV/Excel file with the repo's reader and core. Raises ValueError on bad input."""
    if not (time_interval > 0) or num_intervals < 1:
        raise ValueError("time_interval must be > 0 and num_intervals >= 1")
    ext = os.path.splitext(filename or "")[1].lower()
    get_file_type("x" + ext)  # raises ValueError for unsupported types
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "upload" + ext)
        with open(path, "wb") as f:
            f.write(data)
        with contextlib.redirect_stdout(io.StringIO()):
            source, file_type = read_file(path)
            if file_type == "excel":
                sheets = {n: pd.read_excel(source, sheet_name=n) for n in source.sheet_names}
            else:
                sheets = source
        conditions = [analyse_sheet(n, df, time_interval, num_intervals) for n, df in sheets.items()]
    return {"engine": "python", "file": filename, "time_interval": time_interval, "num_intervals": num_intervals,
            "conditions": conditions}
