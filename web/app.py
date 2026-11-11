"""FastAPI web app for Direction Autocorrelation: serves the front end in static/ and the JSON API under /api.

Run with `python run_web.py` (http://127.0.0.1:8105, local only). `scripts/build_static.py` exports every path in
STATIC_ENDPOINTS to JSON for the GitHub Pages site, so keep that list in step with the GET routes below. The upload
endpoint (POST /api/analyze) runs the repo's Python analysis; on the static site static_api.js answers it with the JS port
(dac_engine.js) instead.
"""
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from web.analysis import analyse_upload  # noqa: I001  (puts the repo root on sys.path first)
import config  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

app = FastAPI(title="Direction Autocorrelation")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/info")
def info():
    """Project summary and the repo's own defaults (config.py) for the pages."""
    return {
        "title": "Direction Autocorrelation Analysis",
        "description": "Directional persistence in cell migration and particle trajectories from fluorescence "
                       "microscopy data (Gorelik & Gautreau 2014).",
        "repo": "direction_autocorrelation_analysis",
        "defaults": {"time_interval": config.INPUT_TIME_INTERVAL, "num_intervals": config.INPUT_NUM_INTERVALS,
                     "max_tracks_to_plot": config.MAX_TRACKS_TO_PLOT, "plot_y_min": config.PLOT_Y_MIN,
                     "plot_y_max": config.PLOT_Y_MAX},
        "columns": {
            "frame": ["frame", "frames", "frame_number", "frameno", "time", "f", "#frame"],
            "x": ["x", "x_coord", "x_coordinate", "xpos", "x_position", "x-position", "x position"],
            "y": ["y", "y_coord", "y_coordinate", "ypos", "y_position", "y-position", "y position"],
            "condition": ["sheet", "condition", "group", "experiment"],
        },
        "reference": {"text": "Gorelik, R., & Gautreau, A. (2014). Quantitative and unbiased analysis of directional "
                              "persistence in cell migration. Nature Protocols, 9(8), 1931-1943.",
                      "url": "https://doi.org/10.1038/nprot.2014.131"},
    }


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), time_interval: float = Form(...), num_intervals: int = Form(...)):
    """Analyse an uploaded CSV/Excel trajectory file with core.process_sheet (see web/analysis.py)."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large for the web app (25 MB); use the command line for big files.")
    try:
        return analyse_upload(file.filename or "upload.csv", data, time_interval, num_intervals)
    except ValueError as e:
        raise HTTPException(400, str(e))


# GET paths (without the /api prefix) written to the static site as api/<path>.json.
STATIC_ENDPOINTS = ["/info"]
