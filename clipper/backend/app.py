#!/usr/bin/env python3
"""
app.py - FastAPI backend server for CLIPPER dashboard.
Provides REST API for status, sync, job control, and log viewing.
"""

import os
import subprocess
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend import github_sync, process
from backend.utils import DATA_DIR, LOGS_DIR, process_logger

# Create FastAPI app
app = FastAPI(title="CLIPPER API", description="CLIPPER - Autonomous YouTube Clipper")

# Mount frontend static files
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_path)), name="frontend")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "worker": os.getenv("WORKER_NAME", "clipper"),
        "version": "1.0.0"
    }


@app.get("/status")
async def get_status():
    """
    Get queue status.
    Returns counts of pending, in_progress, done, failed, and next link info.
    """
    csv_path = DATA_DIR / "links.csv"
    
    if not csv_path.exists():
        return {"error": "links.csv not found", "pending": 0, "in_progress": 0, "done": 0, "failed": 0, "total": 0}
    
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return {"error": str(e)}
    
    pending = len(df[df['status'] == 0])
    in_progress = len(df[df['status'] == 2])
    done = len(df[df['status'] == 1])
    failed = len(df[df['status'] == 3])
    total = len(df)
    
    # Get next pending link
    next_link = None
    if pending > 0:
        next_row = df[df['status'] == 0].iloc[0]
        next_link = {
            "link": next_row['link'],
            "title": next_row.get('title', 'No Title')
        }
    
    return {
        "pending": pending,
        "in_progress": in_progress,
        "done": done,
        "failed": failed,
        "total": total,
        "next_link": next_link
    }


@app.post("/sync")
async def sync():
    """
    Trigger GitHub sync.
    Returns number of new links added and total.
    """
    # Count before
    csv_path = DATA_DIR / "links.csv"
    before = 0
    if csv_path.exists():
        before = len(pd.read_csv(csv_path))
    
    try:
        result = github_sync.sync()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    
    # Count after
    after = 0
    if csv_path.exists():
        after = len(pd.read_csv(csv_path))
    
    added = after - before
    
    return {
        "message": "Sync completed",
        "added": added,
        "total": after,
        "success": result.get('success', True)
    }


@app.post("/start-job")
async def start_job():
    """
    Start processing job in background.
    Runs process.py as subprocess.
    """
    try:
        # Get project root
        root_dir = Path(__file__).parent.parent
        
        # Run process.py as detached subprocess
        proc = subprocess.Popen(
            [sys.executable, "backend/process.py"],
            cwd=str(root_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True  # Detach from parent
        )
        
        process_logger.info(f"Started job with PID: {proc.pid}")
        
        return {
            "message": "Job started in background",
            "pid": proc.pid
        }
    except Exception as e:
        process_logger.error(f"Failed to start job: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/stop-job")
async def stop_job():
    """
    Signal stop to running job.
    Creates stop flag file.
    """
    try:
        stop_file = Path("/tmp/clipper_stop")
        stop_file.touch()
        process_logger.info("Stop signal sent")
        return {"message": "Stop signal sent"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/logs")
async def get_logs(lines: int=Query(50, ge=1, le=1000)):
    """
    Get last N lines from process.log.
    """
    log_file = LOGS_DIR / "process.log"
    
    if not log_file.exists():
        return {"logs": ""}
    
    try:
        with open(log_file, "r") as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:]
        return {"logs": "".join(last_lines)}
    except Exception as e:
        return {"logs": f"Error reading log: {e}"}


@app.post("/reset")
async def reset_status():
    """
    Reset all statuses to 0 (pending).
    """
    try:
        process.reset_all_statuses()
        return {"message": "All statuses reset to 0"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/queue")
async def get_queue():
    """
    Get full queue details.
    """
    csv_path = DATA_DIR / "links.csv"
    
    if not csv_path.exists():
        return {"error": "links.csv not found", "queue": []}
    
    try:
        df = pd.read_csv(csv_path)
        # Convert to list of dicts
        queue = df.to_dict('records')
        return {"queue": queue, "total": len(queue)}
    except Exception as e:
        return {"error": str(e), "queue": []}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
