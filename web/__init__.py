"""Web interface for direction autocorrelation analysis.

Contents:
    app.py       FastAPI app: static front end, GET /api/info, POST /api/analyze (upload -> Python analysis)
    analysis.py  bridge from uploaded files to io_utils.read_file + core.process_sheet (JSON results)
    static/      ES-module front end (no build step); dac_engine.js is the JS port used on the static site
"""
