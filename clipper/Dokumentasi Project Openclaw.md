Berikut adalah skeleton proyek CLIPER beserta file-file template sesuai spesifikasi. Semua file ditempatkan dalam struktur folder `/home/hasant/clipper`. Silakan disesuaikan jika diperlukan.

---

## **Struktur Folder dan File**

text

/home/hasant/clipper/
├── README.md
├── CLIPPER_SPEC.md
├── .env.example
├── data/
│   └── links.csv
├── backups/
├── raw/
├── transcript/
├── rendered/
├── logs/
│   ├── process.log
│   └── sync.log
├── backend/
│   ├── app.py
│   ├── github_sync.py
│   ├── process.py
│   ├── youtube_uploader.py
│   ├── utils.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── main.js
│   └── style.css
├── scripts/
│   ├── runner.sh
│   └── install-deps.sh
└── systemd/
    └── clipper.service

---

## **Isi File**

### **1. README.md**

markdown

# CLIPPER - Autonomous YouTube Clipper
CLIPPER adalah sistem otomatis untuk mengambil video dari YouTube, membuat klip pendek, mentranskripsi, menghasilkan skrip baru dengan Ollama, merender, dan mengunggah ke YouTube/TikTok.
## Instalasi Cepat
1. Clone repositori ini ke `/home/hasant/clipper`.
2. Jalankan `scripts/install-deps.sh` untuk menginstal dependensi sistem.
3. Buat virtual environment: `python3 -m venv ~/yt-env` dan aktifkan.
4. Install Python dependencies: `pip install -r backend/requirements.txt`.
5. Salin `.env.example` menjadi `.env` dan isi variabel yang diperlukan.
6. Jalankan backend: `uvicorn backend.app:app --host 0.0.0.0 --port 8000`.
7. Akses dashboard di `http://localhost:8000/frontend/index.html`.
Lihat `CLIPPER_SPEC.md` untuk dokumentasi lengkap.

### **2. CLIPPER_SPEC.md**

Salin seluruh teks spesifikasi yang diberikan dalam prompt. (Tidak perlu diulang di sini, tetapi dalam implementasi sebenarnya file ini berisi spesifikasi lengkap.)

### **3. .env.example**

bash

# GitHub raw CSV URL (public or private with token)
GITHUB_RAW_URL="https://raw.githubusercontent.com/username/repo/main/links.csv"
# GitHub personal access token (if private repo)
GITHUB_TOKEN=""
# Ollama API URL (default local)
OLLAMA_URL="http://localhost:11434/api/generate"
# Worker name for identification
WORKER_NAME="clipper-01"
# Reset all statuses to 0 when queue empty? (true/false)
RESET_ON_EMPTY="true"
# Max repeats per video before marking as failed
MAX_REPEATS=3
# Path to YouTube client secrets JSON (from Google Cloud Console)
YOUTUBE_CLIENT_SECRETS="/home/hasant/clipper/backend/client_secrets.json"

### **4. data/links.csv**

csv

link,title,status,times_processed,last_processed,notes
https://www.youtube.com/watch?v=dQw4w9WgXcQ,Rick Astley - Never Gonna Give You Up,0,0,,

### **5. logs/process.log** (kosong)

### **6. logs/sync.log** (kosong)

### **7. backend/requirements.txt**

text

fastapi==0.104.1
uvicorn[standard]==0.24.0
python-dotenv==1.0.0
requests==2.31.0
PyGithub==2.1.1
pandas==2.1.4
pydantic==2.5.0
google-api-python-client==2.108.0
google-auth==2.23.4
google-auth-oauthlib==1.1.0
google-auth-httplib2==0.1.1

### **8. backend/utils.py**

python

import os
import logging
import fcntl
import time
from pathlib import Path
from dotenv import load_dotenv
# Load environment variables
load_dotenv()
# Paths
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"
BACKUPS_DIR = ROOT_DIR / "backups"
RAW_DIR = ROOT_DIR / "raw"
TRANSCRIPT_DIR = ROOT_DIR / "transcript"
RENDERED_DIR = ROOT_DIR / "rendered"
# Ensure directories exist
for d in [DATA_DIR, LOGS_DIR, BACKUPS_DIR, RAW_DIR, TRANSCRIPT_DIR, RENDERED_DIR]:
    d.mkdir(parents=True, exist_ok=True)
# Logging setup
def setup_logger(name, log_file):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
process_logger = setup_logger('process', LOGS_DIR / 'process.log')
sync_logger = setup_logger('sync', LOGS_DIR / 'sync.log')
# Lock file to prevent multiple runs
LOCK_FILE = Path("/tmp/clipper.lock")
def acquire_lock():
    try:
        fp = open(LOCK_FILE, "w")
        fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fp
    except IOError:
        return None
def release_lock(fp):
    if fp:
        fcntl.flock(fp, fcntl.LOCK_UN)
        fp.close()
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()

### **9. backend/github_sync.py**

python

#!/usr/bin/env python3
import requests
import pandas as pd
from pathlib import Path
import shutil
from datetime import datetime
from .utils import DATA_DIR, BACKUPS_DIR, sync_logger
import os
GITHUB_RAW_URL = os.getenv("GITHUB_RAW_URL")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
def download_csv():
    """Download CSV from GitHub, return pandas DataFrame."""
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    try:
        resp = requests.get(GITHUB_RAW_URL, headers=headers)
        resp.raise_for_status()
        # Read CSV into DataFrame
        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))
        # Ensure required columns
        if 'link' not in df.columns:
            raise ValueError("Remote CSV missing 'link' column")
        if 'title' not in df.columns:
            df['title'] = ''
        if 'status' not in df.columns:
            df['status'] = 0
        return df
    except Exception as e:
        sync_logger.error(f"Download failed: {e}")
        return None
def merge_with_local(remote_df):
    """Merge remote DataFrame with local CSV, preserving local status."""
    local_path = DATA_DIR / "links.csv"
    if local_path.exists():
        local_df = pd.read_csv(local_path)
        # Backup local
        backup_name = f"links.{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
        shutil.copy(local_path, BACKUPS_DIR / backup_name)
    else:
        local_df = pd.DataFrame(columns=['link','title','status','times_processed','last_processed','notes'])
    # Ensure all columns exist
    for col in ['times_processed','last_processed','notes']:
        if col not in local_df.columns:
            local_df[col] = '' if col=='notes' else 0
    # Merge: for each remote row, if link exists in local, keep local status, else add new
    merged = local_df.copy()
    for _, row in remote_df.iterrows():
        link = row['link']
        if link in merged['link'].values:
            # Update title if changed? optional
            merged.loc[merged['link']==link, 'title'] = row['title']
        else:
            # New link
            new_row = {
                'link': link,
                'title': row.get('title', ''),
                'status': 0,
                'times_processed': 0,
                'last_processed': '',
                'notes': ''
            }
            merged = pd.concat([merged, pd.DataFrame([new_row])], ignore_index=True)
    merged.to_csv(local_path, index=False)
    sync_logger.info(f"Sync completed. Total links: {len(merged)}")
    return len(merged)
def sync():
    if not GITHUB_RAW_URL:
        sync_logger.error("GITHUB_RAW_URL not set")
        return
    remote_df = download_csv()
    if remote_df is not None:
        merge_with_local(remote_df)
if __name__ == "__main__":
    sync()

### **10. backend/process.py**

python

#!/usr/bin/env python3
import subprocess
import os
import time
import pandas as pd
import requests
import json
from pathlib import Path
from .utils import DATA_DIR, RAW_DIR, TRANSCRIPT_DIR, RENDERED_DIR, process_logger, acquire_lock, release_lock
# Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MAX_REPEATS = int(os.getenv("MAX_REPEATS", 3))
RESET_ON_EMPTY = os.getenv("RESET_ON_EMPTY", "true").lower() == "true"
def get_next_pending():
    df = pd.read_csv(DATA_DIR / "links.csv")
    pending = df[df['status'] == 0]
    if pending.empty:
        return None, df
    # Take first pending
    idx = pending.index[0]
    return idx, df
def mark_in_progress(idx, df):
    df.loc[idx, 'status'] = 2  # in_progress
    df.to_csv(DATA_DIR / "links.csv", index=False)
def mark_done(idx, df, success=True):
    if success:
        df.loc[idx, 'status'] = 1  # done
    else:
        df.loc[idx, 'status'] = 3  # failed
    df.loc[idx, 'times_processed'] = df.loc[idx, 'times_processed'] + 1
    df.loc[idx, 'last_processed'] = time.strftime('%Y-%m-%d %H:%M:%S')
    df.to_csv(DATA_DIR / "links.csv", index=False)
def reset_all():
    df = pd.read_csv(DATA_DIR / "links.csv")
    df['status'] = 0
    df.to_csv(DATA_DIR / "links.csv", index=False)
    process_logger.info("All statuses reset to 0")
def run_cmd(cmd, cwd=None):
    process_logger.info(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        process_logger.error(f"Command failed: {cmd}\n{result.stderr}")
        return False
    return True
def download_video(link, output_template):
    cmd = f"yt-dlp -f best -o '{output_template}' '{link}'"
    return run_cmd(cmd)
def extract_audio(video_path, audio_path):
    cmd = f"ffmpeg -i '{video_path}' -q:a 0 -map a '{audio_path}' -y"
    return run_cmd(cmd)
def transcribe_audio(audio_path, transcript_path):
    # Assume whisper-cli installed at ~/whisper.cpp/build/bin/whisper-cli
    whisper_bin = os.path.expanduser("~/whisper.cpp/build/bin/whisper-cli")
    if not os.path.exists(whisper_bin):
        process_logger.error("whisper-cli not found")
        return False
    cmd = f"{whisper_bin} -f '{audio_path}' -otxt -of '{transcript_path}' -m base.en"
    return run_cmd(cmd)
def generate_script(transcript_text):
    prompt = f"Buat script video pendek menarik berdasarkan transkrip berikut:\n{transcript_text}\n\nScript:"
    payload = {
        "model": "llama2",
        "prompt": prompt,
        "stream": False
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")
    except Exception as e:
        process_logger.error(f"Ollama failed: {e}")
        return None
def render_clip(video_path, output_path, duration=60):
    # Render first 60 seconds scaled to 720p
    cmd = f"ffmpeg -i '{video_path}' -t {duration} -vf scale=1280:720 -preset veryfast -c:a copy '{output_path}' -y"
    return run_cmd(cmd)
def process_one():
    lock = acquire_lock()
    if not lock:
        process_logger.warning("Another process is running, exiting")
        return
    try:
        idx, df = get_next_pending()
        if idx is None:
            process_logger.info("No pending links")
            if RESET_ON_EMPTY and len(df) > 0:
                reset_all()
            return
        row = df.loc[idx]
        link = row['link']
        title = row['title']
        process_logger.info(f"Processing: {title} - {link}")
        mark_in_progress(idx, df)
        # Prepare paths
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        timestamp = int(time.time())
        raw_video = RAW_DIR / f"{safe_title}_{timestamp}.mp4"
        raw_audio = RAW_DIR / f"{safe_title}_{timestamp}.wav"
        transcript_file = TRANSCRIPT_DIR / f"{safe_title}_{timestamp}.txt"
        rendered_video = RENDERED_DIR / f"{safe_title}_{timestamp}.mp4"
        # Step 1: download
        if not download_video(link, str(raw_video)):
            mark_done(idx, df, success=False)
            return
        # Step 2: extract audio
        if not extract_audio(str(raw_video), str(raw_audio)):
            mark_done(idx, df, success=False)
            return
        # Step 3: transcribe
        if not transcribe_audio(str(raw_audio), str(transcript_file.with_suffix(''))):  # whisper adds .txt
            mark_done(idx, df, success=False)
            return
        # Read transcript
        with open(transcript_file, 'r') as f:
            transcript = f.read()
        # Step 4: generate script
        script = generate_script(transcript)
        if script is None:
            mark_done(idx, df, success=False)
            return
        process_logger.info(f"Generated script: {script[:100]}...")
        # Step 5: render clip
        if not render_clip(str(raw_video), str(rendered_video)):
            mark_done(idx, df, success=False)
            return
        # Step 6: upload (call youtube_uploader later)
        # from .youtube_uploader import upload_video
        # upload_video(str(rendered_video), title, script)
        process_logger.info(f"Successfully processed {link}")
        mark_done(idx, df, success=True)
    except Exception as e:
        process_logger.exception(f"Unexpected error: {e}")
    finally:
        release_lock(lock)
if __name__ == "__main__":
    process_one()

### **11. backend/youtube_uploader.py**

python

import os
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from .utils import process_logger
# Scopes required for uploading to YouTube
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = "yt_token.pkl"  # will be saved in backend folder
def get_authenticated_service(client_secrets_file):
    credentials = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            credentials = pickle.load(token)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            credentials = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(credentials, token)
    return build("youtube", "v3", credentials=credentials)
def upload_video(video_path, title, description, privacy_status="unlisted", tags=None):
    client_secrets = os.getenv("YOUTUBE_CLIENT_SECRETS")
    if not client_secrets or not os.path.exists(client_secrets):
        process_logger.error("YouTube client secrets not found")
        return False
    try:
        youtube = get_authenticated_service(client_secrets)
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": "22"  # 22 = People & Blogs
            },
            "status": {
                "privacyStatus": privacy_status
            }
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        response = request.execute()
        process_logger.info(f"Uploaded video ID: {response['id']}")
        return True
    except Exception as e:
        process_logger.error(f"Upload failed: {e}")
        return False
if __name__ == "__main__":
    # Example usage
    upload_video("/path/to/video.mp4", "Test Title", "Test Description")

### **12. backend/app.py**

python

from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import subprocess
import os
from pathlib import Path
from . import github_sync, process
from .utils import process_logger, sync_logger, LOGS_DIR
app = FastAPI()
# Serve frontend static files
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/frontend", StaticFiles(directory=str(frontend_path)), name="frontend")
@app.get("/")
async def root():
    return {"status": "ok", "worker": os.getenv("WORKER_NAME", "clipper")}
@app.post("/sync")
async def sync():
    try:
        github_sync.sync()
        return {"message": "Sync completed"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
@app.post("/start-job")
async def start_job(background_tasks: BackgroundTasks):
    # Run process in background
    background_tasks.add_task(process.process_one)
    return {"message": "Job started"}
@app.post("/stop-job")
async def stop_job():
    # Signal stop (implement with a flag file)
    return {"message": "Stop not implemented yet"}
@app.get("/status")
async def get_status():
    import pandas as pd
    df = pd.read_csv(process.DATA_DIR / "links.csv")
    pending = len(df[df['status'] == 0])
    in_progress = len(df[df['status'] == 2])
    done = len(df[df['status'] == 1])
    failed = len(df[df['status'] == 3])
    return {
        "pending": pending,
        "in_progress": in_progress,
        "done": done,
        "failed": failed,
        "total": len(df)
    }
@app.get("/logs")
async def get_logs(lines: int = 50):
    log_file = LOGS_DIR / "process.log"
    if not log_file.exists():
        return {"logs": ""}
    with open(log_file, "r") as f:
        all_lines = f.readlines()
        last_lines = all_lines[-lines:]
    return {"logs": "".join(last_lines)}
@app.post("/reset")
async def reset_status():
    process.reset_all()
    return {"message": "All statuses reset to 0"}

### **13. frontend/index.html**

html

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>CLIPPER Dashboard</title>
    <link rel="stylesheet" href="/frontend/style.css">
</head>
<body>
    <h1>CLIPPER Control Panel</h1>
    <div id="status">
        <h2>Status</h2>
        <pre id="status-output">Loading...</pre>
    </div>
    <div id="controls">
        <button onclick="syncNow()">Sync GitHub</button>
        <button onclick="startJob()">Start Job</button>
        <button onclick="stopJob()">Stop Job</button>
        <button onclick="resetStatus()">Reset All</button>
        <button onclick="refreshStatus()">Refresh Status</button>
    </div>
    <div id="logs">
        <h2>Logs</h2>
        <pre id="log-output">Loading...</pre>
        <button onclick="refreshLogs()">Refresh Logs</button>
    </div>
    <script src="/frontend/main.js"></script>
</body>
</html>

### **14. frontend/main.js**

javascript

const API_BASE = '';  // same origin
async function fetchJSON(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}
async function syncNow() {
    try {
        const data = await fetchJSON('/sync', { method: 'POST' });
        alert('Sync success: ' + JSON.stringify(data));
        refreshStatus();
    } catch (e) {
        alert('Sync failed: ' + e.message);
    }
}
async function startJob() {
    try {
        const data = await fetchJSON('/start-job', { method: 'POST' });
        alert('Job started');
        refreshStatus();
    } catch (e) {
        alert('Start job failed: ' + e.message);
    }
}
async function stopJob() {
    try {
        const data = await fetchJSON('/stop-job', { method: 'POST' });
        alert('Stop signal sent');
    } catch (e) {
        alert('Stop failed: ' + e.message);
    }
}
async function resetStatus() {
    if (!confirm('Reset all statuses to 0?')) return;
    try {
        const data = await fetchJSON('/reset', { method: 'POST' });
        alert('Reset done');
        refreshStatus();
    } catch (e) {
        alert('Reset failed: ' + e.message);
    }
}
async function refreshStatus() {
    try {
        const data = await fetchJSON('/status');
        document.getElementById('status-output').innerText = JSON.stringify(data, null, 2);
    } catch (e) {
        document.getElementById('status-output').innerText = 'Error loading status';
    }
}
async function refreshLogs() {
    try {
        const data = await fetchJSON('/logs?lines=50');
        document.getElementById('log-output').innerText = data.logs || '(empty)';
    } catch (e) {
        document.getElementById('log-output').innerText = 'Error loading logs';
    }
}
// Initial load
refreshStatus();
refreshLogs();
setInterval(refreshStatus, 10000); // refresh every 10s
setInterval(refreshLogs, 10000);

### **15. frontend/style.css**

css

body {
    font-family: Arial, sans-serif;
    margin: 20px;
    background: #f5f5f5;
}
h1 {
    color: #333;
}
#status, #logs, #controls {
    background: white;
    padding: 15px;
    margin-bottom: 20px;
    border-radius: 5px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
pre {
    background: #eee;
    padding: 10px;
    overflow-x: auto;
    max-height: 300px;
}
button {
    margin-right: 10px;
    padding: 8px 12px;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 3px;
    cursor: pointer;
}
button:hover {
    background: #0056b3;
}

### **16. scripts/runner.sh**

bash

#!/bin/bash
# Simple loop runner for CLIPPER
# Usage: ./runner.sh (run inside virtualenv)
cd /home/hasant/clipper
source /home/hasant/yt-env/bin/activate
while true; do
    echo "$(date): Running sync..."
    python backend/github_sync.py
    echo "$(date): Running process..."
    python backend/process.py
    echo "$(date): Sleeping for 300 seconds..."
    sleep 300
done

### **17. scripts/install-deps.sh**

bash

#!/bin/bash
# Install system dependencies for CLIPPER
sudo apt update
sudo apt install -y ffmpeg git curl build-essential cmake pkg-config libsndfile1
# Install yt-dlp
sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
sudo chmod a+rx /usr/local/bin/yt-dlp
# Install whisper.cpp (optional, manual step)
# cd ~
# git clone https://github.com/ggerganov/whisper.cpp.git
# cd whisper.cpp
# make -j4
# # Download base.en model
# ./models/download-ggml-model.sh base.en
# Install Ollama (if not installed)
# curl -fsSL https://ollama.com/install.sh | sh
# ollama pull llama2
echo "System dependencies installed."
echo "Next steps: create virtualenv, install python packages, configure .env"

### **18. systemd/clipper.service**

ini

[Unit]
Description=CLIPPER Runner Service
After=network.target
[Service]
User=hasant
WorkingDirectory=/home/hasant/clipper
Environment="PATH=/home/hasant/yt-env/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/hasant/clipper/scripts/runner.sh
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target

---

## **Catatan Penting**

- Pastikan semua path disesuaikan dengan lingkungan Anda.
    
- Untuk whisper.cpp, kompilasi manual diperlukan. Lokasi binary diasumsikan `~/whisper.cpp/build/bin/whisper-cli`. Ubah di `process.py` jika berbeda.
    
- YouTube upload memerlukan `client_secrets.json` dari Google Cloud Console. Simpan di `backend/client_secrets.json`.
    
- Jalankan OAuth sekali secara manual untuk menghasilkan token (`yt_token.pkl`).
    
- Gunakan `chmod +x scripts/*.sh` untuk memberi izin eksekusi.
    

Dengan skeleton ini, Anda sudah memiliki dasar sistem CLIPPER yang siap dikembangkan lebih lanjut. 


---
Berikut adalah implementasi `backend/github_sync.py` sesuai spesifikasi:

python

#!/usr/bin/env python3
"""
github_sync.py - Sinkronisasi daftar link YouTube dari GitHub CSV ke lokal.
Membaca GITHUB_RAW_URL dari .env, mendownload CSV, lalu menggabungkan dengan
data/links.csv lokal sesuai kebijakan:
- Pertahankan status, times_processed, last_processed, notes untuk link yang sudah ada.
- Tambahkan link baru dari remote dengan status=0.
- Backup file lokal sebelum ditimpa.
Penggunaan:
    python github_sync.py          # sinkronisasi normal
    python github_sync.py --dry-run # hanya simulasi, tanpa menulis file
"""
import os
import sys
import argparse
import logging
import shutil
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import requests
import pandas as pd
# Load environment variables
load_dotenv()
# Konfigurasi path
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"
BACKUPS_DIR = ROOT_DIR / "backups"
# Pastikan direktori ada
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
BACKUPS_DIR.mkdir(exist_ok=True)
# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "sync.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("sync")
# Kolom yang diharapkan di file lokal
EXPECTED_COLUMNS = ['link', 'title', 'status', 'times_processed', 'last_processed', 'notes']
def download_csv(url, token=None):
    """
    Download CSV dari GitHub.
    Returns DataFrame jika sukses, None jika gagal.
    """
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        logger.info(f"Downloading CSV from {url}")
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        # Coba parse CSV
        from io import StringIO
        content = resp.text
        df = pd.read_csv(StringIO(content))
        # Validasi kolom minimal
        if 'link' not in df.columns:
            logger.error("Remote CSV tidak memiliki kolom 'link'")
            return None
        # Isi kolom yang mungkin hilang
        if 'title' not in df.columns:
            df['title'] = ''
        if 'status' not in df.columns:
            df['status'] = 0
        logger.info(f"Download sukses, {len(df)} baris ditemukan")
        return df
    except requests.exceptions.RequestException as e:
        logger.error(f"Gagal download: {e}")
    except pd.errors.EmptyDataError:
        logger.error("File CSV kosong")
    except Exception as e:
        logger.error(f"Error tidak terduga saat download: {e}")
    return None
def ensure_columns(df):
    """Pastikan DataFrame memiliki semua kolom yang diharapkan."""
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            if col in ['title', 'notes', 'last_processed']:
                df[col] = ''
            elif col in ['status', 'times_processed']:
                df[col] = 0
    return df[EXPECTED_COLUMNS]
def load_local_csv():
    """Membaca file lokal, jika tidak ada buat DataFrame kosong."""
    local_path = DATA_DIR / "links.csv"
    if local_path.exists():
        try:
            df = pd.read_csv(local_path)
            logger.info(f"File lokal dibaca, {len(df)} baris")
            return ensure_columns(df)
        except Exception as e:
            logger.error(f"Gagal membaca file lokal: {e}, akan dibuat baru")
            return pd.DataFrame(columns=EXPECTED_COLUMNS)
    else:
        logger.info("File lokal belum ada, akan dibuat baru")
        return pd.DataFrame(columns=EXPECTED_COLUMNS)
def backup_local():
    """Backup file links.csv ke folder backups dengan timestamp."""
    local_path = DATA_DIR / "links.csv"
    if not local_path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"links.{timestamp}.bak"
    backup_path = BACKUPS_DIR / backup_name
    shutil.copy(local_path, backup_path)
    logger.info(f"Backup dibuat: {backup_path}")
    return backup_path
def merge_data(remote_df, local_df):
    """
    Gabungkan remote dengan lokal sesuai kebijakan.
    Return DataFrame hasil merge.
    """
    # Konversi link ke set untuk pencarian cepat
    local_links = set(local_df['link'].values)
    # Salin lokal sebagai dasar
    merged = local_df.copy()
    # Proses setiap baris remote
    new_rows = []
    for _, row in remote_df.iterrows():
        link = row['link']
        if link in local_links:
            # Update title dari remote, sisanya tetap
            merged.loc[merged['link'] == link, 'title'] = row['title']
        else:
            # Link baru, buat baris baru
            new_row = {
                'link': link,
                'title': row.get('title', ''),
                'status': 0,
                'times_processed': 0,
                'last_processed': '',
                'notes': ''
            }
            new_rows.append(new_row)
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        merged = pd.concat([merged, new_df], ignore_index=True)
        logger.info(f"Menambahkan {len(new_rows)} link baru")
    else:
        logger.info("Tidak ada link baru")
    return merged
def save_local(df, dry_run=False):
    """Simpan DataFrame ke file lokal jika bukan dry run."""
    local_path = DATA_DIR / "links.csv"
    if dry_run:
        logger.info("DRY RUN: Tidak menulis file")
        return
    try:
        df.to_csv(local_path, index=False)
        logger.info(f"File lokal disimpan: {local_path} ({len(df)} baris)")
    except Exception as e:
        logger.error(f"Gagal menyimpan file lokal: {e}")
def sync(dry_run=False):
    """Proses sinkronisasi utama."""
    url = os.getenv("GITHUB_RAW_URL")
    token = os.getenv("GITHUB_TOKEN")
    if not url:
        logger.error("GITHUB_RAW_URL tidak diset di .env")
        return False
    # Download remote
    remote_df = download_csv(url, token)
    if remote_df is None:
        return False
    # Baca lokal
    local_df = load_local_csv()
    # Backup sebelum perubahan (kecuali dry run)
    if not dry_run:
        backup_local()
    # Merge
    merged_df = merge_data(remote_df, local_df)
    # Simpan hasil
    save_local(merged_df, dry_run)
    # Log ringkasan
    added = len(merged_df) - len(local_df)
    logger.info(f"Sinkronisasi selesai. Total lokal: {len(merged_df)} (baru: {added})")
    return True
def main():
    parser = argparse.ArgumentParser(description="Sinkronisasi link YouTube dari GitHub")
    parser.add_argument("--dry-run", action="store_true", help="Jalankan simulasi tanpa menulis file")
    args = parser.parse_args()
    success = sync(dry_run=args.dry_run)
    sys.exit(0 if success else 1)
if __name__ == "__main__":
    main()

### Penjelasan Singkat

- **Environment**: Menggunakan `python-dotenv` untuk memuat `.env`.
    
- **Logging**: Output ke `logs/sync.log` dan juga ke console.
    
- **Download**: Menggunakan `requests` dengan header token jika ada.
    
- **Parsing CSV**: Menggunakan pandas, dengan penanganan error jika file kosong atau corrupt.
    
- **Merge**: Link yang sudah ada dipertahankan status dan metadatanya, hanya judul diperbarui. Link baru ditambahkan dengan status 0.
    
- **Backup**: File lokal dibackup sebelum ditimpa dengan format `links.YYYYmmdd-HHMMSS.bak`.
    
- **Dry-run**: Opsi `--dry-run` untuk simulasi tanpa perubahan file.
    

Pastikan file `.env` sudah berisi `GITHUB_RAW_URL` dan opsional `GITHUB_TOKEN`.

---
Berikut adalah implementasi `backend/process.py` sesuai spesifikasi:

python

#!/usr/bin/env python3
"""
process.py - Proses satu link YouTube: download, transkripsi, generate script, render, upload.
Membaca file data/links.csv, mengambil link dengan status 0, menjalankan pipeline:
- Download video dengan yt-dlp
- Ekstrak audio (16k mono) dengan ffmpeg
- Transkripsi dengan whisper-cli
- Generate script via Ollama
- Render klip 720p dengan ffmpeg
- Upload ke YouTube atau simpan lokal
Logging ke logs/process.log. Gunakan lockfile untuk memastikan hanya satu instance berjalan.
"""
import os
import sys
import subprocess
import time
import json
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
# Tambahkan parent directory ke path untuk import utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.utils import (
    acquire_lock, release_lock,
    process_logger as logger,
    DATA_DIR, RAW_DIR, TRANSCRIPT_DIR, RENDERED_DIR, LOGS_DIR
)
# Load environment variables
load_dotenv()
# Konfigurasi dari environment
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")
WHISPER_CLI_PATH = os.getenv("WHISPER_CLI_PATH", os.path.expanduser("~/whisper.cpp/build/bin/whisper-cli"))
MAX_REPEATS = int(os.getenv("MAX_REPEATS", "3"))
RESET_ON_EMPTY = os.getenv("RESET_ON_EMPTY", "true").lower() == "true"
def run_cmd(cmd, cwd=None, check=True):
    """Jalankan perintah shell, log output, return True jika sukses."""
    logger.info(f"Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=3600)
        if result.returncode != 0:
            logger.error(f"Command failed (exit {result.returncode}): {cmd}")
            logger.error(f"STDERR: {result.stderr[:500]}")
            if check:
                return False
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.error(f"Command timeout: {cmd}")
        return False
    except Exception as e:
        logger.exception(f"Exception running command: {cmd}")
        return False
def get_next_pending():
    """Ambil baris pertama dengan status 0 dari CSV. Kembalikan (index, df) atau (None, df)."""
    csv_path = DATA_DIR / "links.csv"
    if not csv_path.exists():
        logger.error("File links.csv tidak ditemukan")
        return None, None
    df = pd.read_csv(csv_path)
    pending = df[df['status'] == 0]
    if pending.empty:
        return None, df
    idx = pending.index[0]
    return idx, df
def mark_in_progress(idx, df):
    """Ubah status baris menjadi 2 (in_progress) dan simpan CSV."""
    df.loc[idx, 'status'] = 2
    df.to_csv(DATA_DIR / "links.csv", index=False)
    logger.info(f"Marked link index {idx} as in_progress")
def mark_done(idx, df, success=True, notes=""):
    """Tandai selesai (status=1 jika sukses, 3 jika gagal), increment times_processed, simpan."""
    if success:
        df.loc[idx, 'status'] = 1
    else:
        df.loc[idx, 'status'] = 3
    df.loc[idx, 'times_processed'] = df.loc[idx, 'times_processed'] + 1
    df.loc[idx, 'last_processed'] = time.strftime('%Y-%m-%d %H:%M:%S')
    if notes:
        df.loc[idx, 'notes'] = notes
    df.to_csv(DATA_DIR / "links.csv", index=False)
    status = "success" if success else "failed"
    logger.info(f"Marked link index {idx} as {status}")
def safe_filename(text):
    """Buat nama file aman dari string."""
    keep = "".join(c for c in text if c.isalnum() or c in (' ', '-', '_')).strip()
    return keep.replace(' ', '_')[:100]
def download_video(link, output_path):
    """Download video dengan yt-dlp ke output_path (template)."""
    cmd = f"yt-dlp -f 'best[height<=720]' -o '{output_path}' '{link}'"
    return run_cmd(cmd)
def extract_audio(video_path, audio_path):
    """Ekstrak audio 16kHz mono ke WAV."""
    cmd = f"ffmpeg -i '{video_path}' -ar 16000 -ac 1 -c:a pcm_s16le '{audio_path}' -y"
    return run_cmd(cmd)
def transcribe_audio(audio_path, output_txt_base):
    """
    Transkripsi dengan whisper-cli.
    output_txt_base adalah path tanpa ekstensi, whisper akan menambahkan .txt
    """
    if not os.path.exists(WHISPER_CLI_PATH):
        logger.error(f"whisper-cli tidak ditemukan di {WHISPER_CLI_PATH}")
        return None
    # Gunakan model base.en, bisa diubah via env
    model = os.getenv("WHISPER_MODEL", "base.en")
    cmd = f"{WHISPER_CLI_PATH} -f '{audio_path}' -otxt -of '{output_txt_base}' -m {model}"
    if not run_cmd(cmd):
        return None
    txt_file = output_txt_base + ".txt"
    if not os.path.exists(txt_file):
        logger.error(f"File transkripsi tidak ditemukan: {txt_file}")
        return None
    with open(txt_file, 'r', encoding='utf-8') as f:
        transcript = f.read().strip()
    logger.info(f"Transkripsi selesai: {len(transcript)} karakter")
    return transcript
def generate_script(transcript):
    """Kirim prompt ke Ollama, kembalikan teks script."""
    prompt = f"""Buat script video pendek yang menarik berdasarkan transkrip berikut:
{transcript}
Script harus singkat, engaging, dan cocok untuk video pendek (durasi 30-60 detik). Tulis dalam bahasa Indonesia.
Script:"""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        script = data.get("response", "").strip()
        logger.info(f"Script generated: {len(script)} chars")
        return script
    except Exception as e:
        logger.error(f"Ollama request gagal: {e}")
        return None
def render_clip(video_path, output_path, duration=60):
    """
    Render klip: ambil 60 detik pertama, scale ke 1280x720, copy audio.
    Jika durasi video kurang, gunakan seluruh video.
    """
    # Cek durasi video dengan ffprobe
    probe_cmd = f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 '{video_path}'"
    try:
        result = subprocess.run(probe_cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            total_duration = float(result.stdout.strip())
            if total_duration < duration:
                duration = total_duration
                logger.info(f"Durasi video asli {total_duration:.1f}s, gunakan semua")
    except:
        logger.warning("Gagal mendapatkan durasi video, asumsi cukup panjang")
    cmd = (f"ffmpeg -i '{video_path}' -t {duration} "
           f"-vf scale=1280:720 -preset veryfast -c:a aac -b:a 128k "
           f"'{output_path}' -y")
    return run_cmd(cmd)
def upload_or_save(video_path, title, script):
    """
    Upload ke YouTube jika credential tersedia, else simpan lokal.
    Return (success, notes) dengan notes berisi URL atau path lokal.
    """
    try:
        from backend.youtube_uploader import upload_video
        # Cek apakah client secrets ada
        client_secrets = os.getenv("YOUTUBE_CLIENT_SECRETS")
        if client_secrets and os.path.exists(client_secrets):
            logger.info("Mencoba upload ke YouTube...")
            video_id = upload_video(video_path, title, script)
            if video_id:
                return True, f"https://youtu.be/{video_id}"
            else:
                logger.error("Upload YouTube gagal")
                return False, "Upload YouTube gagal"
        else:
            logger.info("YouTube credential tidak ada, simpan lokal")
            # Simpan ke rendered/ sudah dilakukan render_clip, cukup catat path
            return True, f"LOCAL:{video_path}"
    except ImportError:
        logger.warning("youtube_uploader tidak tersedia, simpan lokal")
        return True, f"LOCAL:{video_path}"
    except Exception as e:
        logger.exception("Error saat upload")
        return False, f"Upload exception: {str(e)}"
def reset_all():
    """Set semua status menjadi 0 (jika RESET_ON_EMPTY true)."""
    df = pd.read_csv(DATA_DIR / "links.csv")
    df['status'] = 0
    df.to_csv(DATA_DIR / "links.csv", index=False)
    logger.info("Semua status direset ke 0")
def process_one():
    """Proses satu link (jika ada)."""
    lock = acquire_lock()
    if not lock:
        logger.warning("Instance lain sedang berjalan, keluar")
        return
    try:
        # Ambil link pending
        idx, df = get_next_pending()
        if idx is None:
            logger.info("Tidak ada link pending")
            if RESET_ON_EMPTY and df is not None and not df.empty:
                reset_all()
            return
        row = df.loc[idx]
        link = row['link']
        title = row.get('title', 'No Title') or 'No Title'
        logger.info(f"Memproses: {title} - {link}")
        mark_in_progress(idx, df)
        # Buat nama file unik
        safe = safe_filename(title)
        timestamp = int(time.time())
        base_name = f"{safe}_{timestamp}"
        raw_video = RAW_DIR / f"{base_name}.mp4"
        raw_audio = RAW_DIR / f"{base_name}.wav"
        transcript_base = TRANSCRIPT_DIR / base_name  # tanpa ekstensi
        rendered_video = RENDERED_DIR / f"{base_name}.mp4"
        notes = []
        # Step 1: Download
        if not download_video(link, str(raw_video)):
            mark_done(idx, df, success=False, notes="Download gagal")
            return
        # Step 2: Ekstrak audio
        if not extract_audio(str(raw_video), str(raw_audio)):
            mark_done(idx, df, success=False, notes="Ekstrak audio gagal")
            return
        # Step 3: Transkripsi
        transcript = transcribe_audio(str(raw_audio), str(transcript_base))
        if transcript is None:
            mark_done(idx, df, success=False, notes="Transkripsi gagal")
            return
        # Step 4: Generate script via Ollama
        script = generate_script(transcript)
        if script is None:
            mark_done(idx, df, success=False, notes="Generate script gagal")
            return
        # Simpan script ke file (opsional)
        script_file = TRANSCRIPT_DIR / f"{base_name}_script.txt"
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script)
        # Step 5: Render klip
        if not render_clip(str(raw_video), str(rendered_video)):
            mark_done(idx, df, success=False, notes="Render gagal")
            return
        # Step 6: Upload atau simpan
        upload_ok, upload_note = upload_or_save(str(rendered_video), title, script)
        notes.append(upload_note)
        if upload_ok:
            mark_done(idx, df, success=True, notes="; ".join(notes))
            logger.info(f"Proses selesai untuk {link}")
        else:
            mark_done(idx, df, success=False, notes="; ".join(notes))
    except Exception as e:
        logger.exception("Error tidak terduga di process_one")
        # Jika df dan idx tersedia, tandai gagal
        if 'idx' in locals() and 'df' in locals():
            try:
                mark_done(idx, df, success=False, notes=f"Exception: {str(e)}")
            except:
                pass
    finally:
        release_lock(lock)
if __name__ == "__main__":
    process_one()

### Penjelasan dan Catatan

1. **Import utils**: Menggunakan fungsi dan konstanta dari `backend.utils` (asumsi sudah ada).
    
2. **Environment**: `OLLAMA_URL`, `OLLAMA_MODEL`, `WHISPER_CLI_PATH`, `MAX_REPEATS`, `RESET_ON_EMPTY`.
    
3. **Lockfile**: `acquire_lock()` dan `release_lock()` dari utils.
    
4. **CSV handling**: Menggunakan pandas untuk baca/tulis.
    
5. **Subprocess**: `run_cmd` mengeksekusi perintah dan log error.
    
6. **Whisper**: Path diambil dari env, default `~/whisper.cpp/build/bin/whisper-cli`. Model `base.en`.
    
7. **Ollama**: Mengirim prompt dengan transkrip, respons JSON.
    
8. **Render**: Mengambil 60 detik pertama (durasi bisa disesuaikan), scale 720p, audio AAC.
    
9. **Upload**: Mencoba impor `youtube_uploader.upload_video`, jika gagal simpan lokal dan catat path.
    
10. **Error handling**: Setiap langkah diperiksa, jika gagal langsung tandai sebagai error dan keluar.
    
11. **Logging**: Semua log ditulis ke `logs/process.log` via `process_logger`.
    

Pastikan file `utils.py` sudah ada dengan fungsi yang diperlukan. Jika tidak, proses ini akan gagal impor.

---
Kita perlu membuat file `backend/youtube_uploader.py` sesuai spesifikasi. Harus menggunakan Google API Client, mengelola OAuth flow, menyimpan token, dan fungsi upload dengan retry. Juga perlu instruksi dan komentar jelas.

Rencana:

- Import library: googleapiclient.discovery, googleapiclient.http, google.auth, google_auth_oauthlib.flow, google.auth.transport.requests.
    
- Fungsi `init_oauth`: membaca client_secrets, melakukan flow jika token tidak ada, menyimpan token ke file (pickle atau json). Bisa juga digabung dengan upload.
    
- Fungsi `upload_video`: menerima path file, judul, deskripsi, privacyStatus (default private), tags. Melakukan autentikasi (menggunakan token yang disimpan), lalu upload dengan MediaFileUpload. Retry 3 kali jika gagal.
    
- Gunakan logging (dari utils) untuk mencatat.
    
- Tangani exception, kembalikan video ID jika sukses, None jika gagal.
    

Perhatikan: token sebaiknya disimpan sebagai pickle atau json? Biasanya google-auth menyimpan credentials sebagai pickle. Kita bisa gunakan pickle untuk simplicity, atau json. Pickle lebih mudah karena objek credentials bisa langsung di-pickle. Tapi pastikan file token hanya bisa dibaca user.

Tambahkan docstring dan komentar tentang setup OAuth di Google Cloud Console.

Juga, perlu environment variable untuk client_secrets path, atau parameter. Spesifikasi dari .env: YOUTUBE_CLIENT_SECRETS. Kita bisa pakai itu.

Implementasi:

python

#!/usr/bin/env python3
"""
youtube_uploader.py - Upload video ke YouTube menggunakan OAuth.
Membutuhkan client_secrets.json dari Google Cloud Console.
Pertama kali akan membuka browser untuk otorisasi, token disimpan di yt_token.pkl.
Untuk penggunaan headless, bisa menggunakan service account atau token offline.
"""
import os
import pickle
import time
from pathlib import Path
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
# Import logger dari utils (asumsi)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.utils import process_logger as logger
# Scope untuk upload
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = Path(__file__).parent / "yt_token.pkl"
CLIENT_SECRETS_FILE = os.getenv("YOUTUBE_CLIENT_SECRETS", "")
def get_authenticated_service(client_secrets_file=None):
    """
    Mendapatkan credentials YouTube yang terautentikasi.
    Jika token tersimpan, muat; jika tidak atau expired, lakukan flow OAuth.
    """
    if client_secrets_file is None:
        client_secrets_file = CLIENT_SECRETS_FILE
    if not client_secrets_file or not os.path.exists(client_secrets_file):
        logger.error(f"Client secrets file tidak ditemukan: {client_secrets_file}")
        return None
    credentials = None
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE, 'rb') as f:
                credentials = pickle.load(f)
            logger.info("Token dimuat dari file")
        except Exception as e:
            logger.warning(f"Gagal memuat token: {e}")
    # Jika credentials tidak ada atau tidak valid
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                logger.info("Token berhasil direfresh")
            except Exception as e:
                logger.error(f"Gagal refresh token: {e}")
                credentials = None
        else:
            # Lakukan flow OAuth baru
            if not os.path.exists(client_secrets_file):
                logger.error("File client secrets tidak ada")
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_secrets_file, SCOPES)
                # Jalankan server lokal untuk mendapatkan kode
                credentials = flow.run_local_server(
                    host='localhost',
                    port=8080,
                    open_browser=True
                )
                logger.info("OAuth flow selesai, token baru didapat")
            except Exception as e:
                logger.exception("Gagal menjalankan OAuth flow")
                return None
        # Simpan token
        try:
            with open(TOKEN_FILE, 'wb') as f:
                pickle.dump(credentials, f)
            logger.info(f"Token disimpan di {TOKEN_FILE}")
        except Exception as e:
            logger.warning(f"Gagal menyimpan token: {e}")
    # Bangun service
    try:
        youtube = build("youtube", "v3", credentials=credentials)
        return youtube
    except Exception as e:
        logger.exception("Gagal membangun YouTube service")
        return None
def upload_video(file_path, title, description, privacy_status="private", tags=None, max_retries=3):
    """
    Upload video ke YouTube.
    Args:
        file_path: path ke file video
        title: judul video
        description: deskripsi
        privacy_status: "private", "unlisted", atau "public"
        tags: list of strings
    Returns:
        video_id jika sukses, None jika gagal.
    """
    if not os.path.exists(file_path):
        logger.error(f"File tidak ditemukan: {file_path}")
        return None
    youtube = get_authenticated_service()
    if not youtube:
        logger.error("Tidak bisa mendapatkan service YouTube")
        return None
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "22"  # 22 = People & Blogs
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Mengupload video (percobaan {attempt})...")
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            response = request.execute()
            video_id = response.get("id")
            logger.info(f"Upload sukses, video ID: {video_id}")
            return video_id
        except HttpError as e:
            logger.error(f"HTTP error: {e}")
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.info(f"Menunggu {wait} detik sebelum percobaan ulang...")
                time.sleep(wait)
            else:
                logger.error("Gagal setelah beberapa percobaan")
                return None
        except Exception as e:
            logger.exception("Error tak terduga saat upload")
            return None
# Jika dijalankan langsung, bisa testing
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python youtube_uploader.py <video_file>")
        sys.exit(1)
    video = sys.argv[1]
    vid = upload_video(video, "Test Upload", "Deskripsi test", "private")
    if vid:
        print(f"Uploaded: https://youtu.be/{vid}")
    else:
        print("Upload gagal")

Penjelasan:

- Menggunakan `get_authenticated_service` yang menangani token.
    
- Token disimpan sebagai pickle di `yt_token.pkl`.
    
- Fungsi upload dengan retry exponential backoff sederhana.
    
- Menambahkan categoryId 22 (People & Blogs) default, bisa diubah.
    
- Menggunakan logger dari `backend.utils`.
    

Pastikan untuk menambahkan instruksi di komentar tentang cara mendapatkan client_secrets.json dari Google Cloud Console.

Berikut adalah implementasi `backend/youtube_uploader.py` sesuai spesifikasi:

python

#!/usr/bin/env python3
"""
youtube_uploader.py - Upload video ke YouTube menggunakan OAuth 2.0.
Panduan Setup:
1. Buka https://console.cloud.google.com/
2. Buat project baru atau pilih project yang ada.
3. Aktifkan YouTube Data API v3.
4. Buat credentials OAuth 2.0 Client ID (tipe "Desktop Application").
5. Download file JSON dan simpan sebagai `client_secrets.json` di folder backend.
6. Jalankan script ini pertama kali untuk mendapatkan token otorisasi.
   Akan terbuka browser untuk login dan memberikan izin.
7. Token tersimpan di `yt_token.pkl` dan akan digunakan untuk upload berikutnya.
Environment variable yang diperlukan (di .env):
- YOUTUBE_CLIENT_SECRETS: path ke file client_secrets.json
"""
import os
import pickle
import time
from pathlib import Path
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
# Import logger dari utils (pastikan path benar)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.utils import process_logger as logger
# Scope yang diperlukan untuk upload video
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
# Lokasi token disimpan (di folder backend)
TOKEN_FILE = Path(__file__).parent / "yt_token.pkl"
# Ambil path client secrets dari environment
CLIENT_SECRETS_FILE = os.getenv("YOUTUBE_CLIENT_SECRETS", "")
def get_authenticated_service(client_secrets_file=None):
    """
    Mendapatkan service YouTube yang terautentikasi.
    Mengelola refresh token dan menyimpan token lokal.
    """
    if client_secrets_file is None:
        client_secrets_file = CLIENT_SECRETS_FILE
    if not client_secrets_file or not os.path.exists(client_secrets_file):
        logger.error(f"Client secrets file tidak ditemukan: {client_secrets_file}")
        return None
    credentials = None
    # Coba muat token yang sudah disimpan
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE, 'rb') as f:
                credentials = pickle.load(f)
            logger.info("Token dimuat dari file")
        except Exception as e:
            logger.warning(f"Gagal memuat token: {e}")
    # Jika credentials tidak ada atau tidak valid
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                logger.info("Token berhasil direfresh")
            except Exception as e:
                logger.error(f"Gagal refresh token: {e}")
                credentials = None
        else:
            # Lakukan OAuth flow (membuka browser)
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_secrets_file, SCOPES)
                # Jalankan server lokal untuk menerima redirect
                credentials = flow.run_local_server(
                    host='localhost',
                    port=8080,
                    open_browser=True
                )
                logger.info("OAuth flow selesai, token baru didapat")
            except Exception as e:
                logger.exception("Gagal menjalankan OAuth flow")
                return None
        # Simpan token untuk penggunaan berikutnya
        try:
            with open(TOKEN_FILE, 'wb') as f:
                pickle.dump(credentials, f)
            logger.info(f"Token disimpan di {TOKEN_FILE}")
        except Exception as e:
            logger.warning(f"Gagal menyimpan token: {e}")
    # Bangun service YouTube
    try:
        youtube = build("youtube", "v3", credentials=credentials)
        return youtube
    except Exception as e:
        logger.exception("Gagal membangun YouTube service")
        return None
def upload_video(file_path, title, description, privacy_status="private", tags=None, max_retries=3):
    """
    Upload video ke YouTube.
    
    Args:
        file_path (str): Path ke file video yang akan diupload.
        title (str): Judul video.
        description (str): Deskripsi video.
        privacy_status (str): 'private', 'unlisted', atau 'public'.
        tags (list): Daftar tag (string).
        max_retries (int): Jumlah maksimal percobaan ulang jika gagal.
    
    Returns:
        str: Video ID jika sukses, None jika gagal.
    """
    if not os.path.exists(file_path):
        logger.error(f"File tidak ditemukan: {file_path}")
        return None
    youtube = get_authenticated_service()
    if not youtube:
        logger.error("Tidak bisa mendapatkan service YouTube")
        return None
    # Body request
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "22"  # 22 = People & Blogs (bisa disesuaikan)
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }
    # Media file dengan upload resumable
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Mengupload video (percobaan {attempt}/{max_retries})...")
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            response = request.execute()
            video_id = response.get("id")
            logger.info(f"Upload sukses, video ID: {video_id}")
            return video_id
        except HttpError as e:
            logger.error(f"HTTP error: {e}")
            if attempt < max_retries:
                wait = 2 ** attempt  # exponential backoff
                logger.info(f"Menunggu {wait} detik sebelum percobaan ulang...")
                time.sleep(wait)
            else:
                logger.error("Gagal setelah beberapa percobaan")
                return None
        except Exception as e:
            logger.exception("Error tak terduga saat upload")
            return None
# Jika dijalankan langsung untuk testing
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python youtube_uploader.py <video_file> [title]")
        sys.exit(1)
    video = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else "Test Upload"
    vid = upload_video(video, title, "Uploaded by CLIPPER", "private")
    if vid:
        print(f"Uploaded: https://youtu.be/{vid}")
    else:
        print("Upload gagal")

### Penjelasan & Fitur:

- **OAuth Flow**: Menggunakan `InstalledAppFlow` untuk mendapatkan token pertama kali, membuka browser untuk login. Token disimpan di `yt_token.pkl`.
    
- **Refresh Token**: Token otomatis di-refresh jika expired.
    
- **Upload dengan Retry**: Mencoba ulang hingga 3 kali dengan exponential backoff jika terjadi HTTP error.
    
- **Logging**: Menggunakan logger dari `backend.utils` agar terintegrasi dengan sistem logging proyek.
    
- **Environment**: Membaca `YOUTUBE_CLIENT_SECRETS` dari `.env`.
    

### Catatan Penting:

- Pastikan file `client_secrets.json` sudah diunduh dari Google Cloud Console dan disimpan di path yang benar.
    
- Pada penggunaan pertama, script akan membuka browser untuk otorisasi. Pastikan environment memiliki akses GUI atau gunakan remote forwarding jika headless. Alternatif bisa menggunakan OAuth offline (service account) tetapi lebih kompleks.
    
- Token disimpan sebagai pickle; jika ingin portabilitas, bisa diubah ke format JSON namun perlu menyesuaikan.
---
We need to implement backend/app.py and frontend/index.html + main.js according to the spec. Let's break it down.

Backend endpoints:

- GET / -> simple status { "status": "ok", "worker": ... }
    
- GET /status -> returns queue state (pending, in_progress, done, failed, total, maybe next link info)
    
- POST /sync -> call github_sync.sync() (from module). Should return something like {"message": "sync started"}? Actually the spec says returns summary {added: n, skipped: m}. But github_sync.sync() currently returns True/False and logs, but doesn't return added count. We need to modify github_sync to return stats. But maybe we can just return a simple message and let user check logs. However, the spec says "Returns summary {added: n, skipped: m}". So we need to adjust github_sync to return that. But we can implement by reading the local CSV before and after and compute added. But we can also have github_sync.sync() return a dict. Let's design that: github_sync.sync() should return a dict with added, total, etc. For now, we'll implement a simple version and later enhance.
    
- POST /start-job -> start process_one in background (non-blocking). Use background_tasks from FastAPI or subprocess.Popen. Since process_one uses lockfile, we can just run it in background thread using BackgroundTasks. That will run inside the same process, but it might block the event loop if it's long? FastAPI's BackgroundTasks runs in the same event loop thread? Actually BackgroundTasks are run after the response is sent, but they still run in the same event loop thread if using asyncio? FastAPI's BackgroundTasks are designed for short tasks. process_one could take minutes, so better to use subprocess to avoid blocking the server. We'll use subprocess.Popen to run "python backend/process.py" detached.
    
- POST /stop-job -> need to signal stop. The spec says "signal to stop current job (graceful)". We can implement by creating a stop flag file, and process.py should check for that flag periodically. For now, we can just return a message that stop is not implemented, or we can implement a simple mechanism: process.py can check for /tmp/clipper_stop and exit gracefully. Then /stop-job can create that file. But for simplicity, we'll implement a stub.
    
- GET /logs?lines=N -> return last N lines from process.log (or combined logs). We'll read from logs/process.log.
    

We'll also need to serve the frontend static files. We can mount the frontend directory as static.

Now, frontend:

- index.html with buttons and pre elements for status and logs.
    
- main.js to fetch and update.
    

Let's write the code.

First, modify github_sync.py to return stats? But we haven't been asked to modify it, but we can adapt app.py to compute stats. Alternatively, we can have github_sync.sync() return the number of added rows. For simplicity, I'll have app.py call github_sync.sync() which currently only logs and returns True/False. We'll keep it simple and just return a message that sync was triggered. But the spec says "Returns summary {added: n, skipped: m}". So we need to implement that. Let's modify github_sync.sync() to return a dict. However, we already have the previous code for github_sync.py; we need to adjust it to return added count. Since we're implementing app.py now, we can also compute added by comparing before and after. But that would require reading CSV twice. I'll do that in the endpoint.

So in app.py, for /sync, we'll:

- Load current CSV count before sync.
    
- Run github_sync.sync().
    
- Load after sync, compute added = after - before (if before exists). Return added and maybe skipped? Skipped is duplicates, we can compute by checking existing links. But simpler: we can just return added.
    

Let's implement.

Also need to implement /stop-job: we'll create a file /tmp/clipper_stop when called, and process.py should check for that file at each step. We'll include that in process.py later. For now, just create the file and return.

Now, code.

We'll write app.py:

python

from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import subprocess
import os
import signal
import time
from pathlib import Path
import pandas as pd
from backend import github_sync, process
from backend.utils import DATA_DIR, LOGS_DIR, process_logger
app = FastAPI()
# Serve frontend static files
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/frontend", StaticFiles(directory=str(frontend_path)), name="frontend")
@app.get("/")
async def root():
    return {"status": "ok", "worker": os.getenv("WORKER_NAME", "clipper")}
@app.get("/status")
async def get_status():
    csv_path = DATA_DIR / "links.csv"
    if not csv_path.exists():
        return {"error": "No CSV file"}
    df = pd.read_csv(csv_path)
    pending = len(df[df['status'] == 0])
    in_progress = len(df[df['status'] == 2])
    done = len(df[df['status'] == 1])
    failed = len(df[df['status'] == 3])
    total = len(df)
    # Get next pending link info if any
    next_link = None
    if pending > 0:
        next_row = df[df['status'] == 0].iloc[0]
        next_link = {"link": next_row['link'], "title": next_row.get('title', '')}
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
    # Count before
    csv_path = DATA_DIR / "links.csv"
    before = 0
    if csv_path.exists():
        before = len(pd.read_csv(csv_path))
    # Run sync
    try:
        github_sync.sync()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    # Count after
    after = len(pd.read_csv(csv_path)) if csv_path.exists() else 0
    added = after - before
    return {"message": "Sync completed", "added": added, "total": after}
@app.post("/start-job")
async def start_job():
    # Run process.py as subprocess (non-blocking)
    try:
        # Use subprocess.Popen to detach
        proc = subprocess.Popen(
            ["python", "backend/process.py"],
            cwd=Path(__file__).parent.parent,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return {"message": "Job started in background", "pid": proc.pid}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
@app.post("/stop-job")
async def stop_job():
    # Create stop flag file
    stop_file = Path("/tmp/clipper_stop")
    try:
        stop_file.touch()
        return {"message": "Stop signal sent"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
@app.get("/logs")
async def get_logs(lines: int = Query(50, ge=1, le=1000)):
    log_file = LOGS_DIR / "process.log"
    if not log_file.exists():
        return {"logs": ""}
    with open(log_file, "r") as f:
        all_lines = f.readlines()
        last_lines = all_lines[-lines:]
    return {"logs": "".join(last_lines)}
@app.post("/reset")
async def reset_status():
    try:
        process.reset_all()
        return {"message": "All statuses reset to 0"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

Now frontend:

index.html:

html

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CLIPPER Dashboard</title>
    <link rel="stylesheet" href="/frontend/style.css">
</head>
<body>
    <h1>CLIPPER Control Panel</h1>
    <div id="status">
        <h2>Status</h2>
        <pre id="status-output">Loading...</pre>
    </div>
    <div id="controls">
        <button onclick="syncNow()">Sync GitHub</button>
        <button onclick="startJob()">Start Job</button>
        <button onclick="stopJob()">Stop Job</button>
        <button onclick="resetStatus()">Reset All</button>
        <button onclick="refreshStatus()">Refresh Status</button>
    </div>
    <div id="logs">
        <h2>Logs</h2>
        <pre id="log-output">Loading...</pre>
        <button onclick="refreshLogs()">Refresh Logs</button>
    </div>
    <script src="/frontend/main.js"></script>
</body>
</html>

main.js:

javascript

const API_BASE = '';  // same origin
async function fetchJSON(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text}`);
    }
    return res.json();
}
async function syncNow() {
    try {
        const data = await fetchJSON('/sync', { method: 'POST' });
        alert(`Sync success: added ${data.added} links. Total: ${data.total}`);
        refreshStatus();
    } catch (e) {
        alert('Sync failed: ' + e.message);
    }
}
async function startJob() {
    try {
        const data = await fetchJSON('/start-job', { method: 'POST' });
        alert('Job started (PID: ' + data.pid + ')');
        refreshStatus();
    } catch (e) {
        alert('Start job failed: ' + e.message);
    }
}
async function stopJob() {
    try {
        const data = await fetchJSON('/stop-job', { method: 'POST' });
        alert('Stop signal sent');
    } catch (e) {
        alert('Stop failed: ' + e.message);
    }
}
async function resetStatus() {
    if (!confirm('Reset all statuses to 0?')) return;
    try {
        const data = await fetchJSON('/reset', { method: 'POST' });
        alert('Reset done');
        refreshStatus();
    } catch (e) {
        alert('Reset failed: ' + e.message);
    }
}
async function refreshStatus() {
    try {
        const data = await fetchJSON('/status');
        let output = `Pending: ${data.pending}
In Progress: ${data.in_progress}
Done: ${data.done}
Failed: ${data.failed}
Total: ${data.total}`;
        if (data.next_link) {
            output += `\n\nNext link:\nTitle: ${data.next_link.title}\nLink: ${data.next_link.link}`;
        }
        document.getElementById('status-output').innerText = output;
    } catch (e) {
        document.getElementById('status-output').innerText = 'Error loading status: ' + e.message;
    }
}
async function refreshLogs() {
    try {
        const data = await fetchJSON('/logs?lines=50');
        document.getElementById('log-output').innerText = data.logs || '(empty)';
    } catch (e) {
        document.getElementById('log-output').innerText = 'Error loading logs: ' + e.message;
    }
}
// Initial load
refreshStatus();
refreshLogs();
// Auto refresh every 10 seconds
setInterval(refreshStatus, 10000);
setInterval(refreshLogs, 10000);

style.css (simple):

css

body {
    font-family: Arial, sans-serif;
    margin: 20px;
    background: #f5f5f5;
}
h1 {
    color: #333;
}
#status, #logs, #controls {
    background: white;
    padding: 15px;
    margin-bottom: 20px;
    border-radius: 5px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
pre {
    background: #eee;
    padding: 10px;
    overflow-x: auto;
    max-height: 300px;
    white-space: pre-wrap;
}
button {
    margin-right: 10px;
    padding: 8px 12px;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 3px;
    cursor: pointer;
}
button:hover {
    background: #0056b3;
}

Now we need to ensure that the imports work. In app.py we import from backend.github_sync, backend.process. Since we are running from the root, the backend module is available. Also need to adjust process.reset_all() - we haven't defined that in process.py yet. In process.py we have reset_all() function, so it's fine.

Also note that in /start-job we run "python backend/process.py" which should be executable from the root. We set cwd to parent of backend (the project root). That's correct.

We also need to handle the stop flag in process.py. We should modify process.py to check for /tmp/clipper_stop at various points and exit gracefully. But that's a separate task. For now, the endpoint just creates the file.

Now provide the final answer with all three files.

Berikut adalah implementasi `backend/app.py`, `frontend/index.html`, dan `frontend/main.js` sesuai spesifikasi.

---

## **backend/app.py**

python

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import subprocess
import os
import pandas as pd
from pathlib import Path
# Import modul internal
from backend import github_sync, process
from backend.utils import DATA_DIR, LOGS_DIR
app = FastAPI()
# Sajikan file frontend sebagai static
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/frontend", StaticFiles(directory=str(frontend_path)), name="frontend")
@app.get("/")
async def root():
    """Endpoint dasar untuk mengecek kesehatan server."""
    return {"status": "ok", "worker": os.getenv("WORKER_NAME", "clipper")}
@app.get("/status")
async def get_status():
    """Mengembalikan status antrian: jumlah pending, in_progress, done, failed, total, dan link berikutnya."""
    csv_path = DATA_DIR / "links.csv"
    if not csv_path.exists():
        return {"error": "File links.csv belum ada"}
    df = pd.read_csv(csv_path)
    pending = len(df[df['status'] == 0])
    in_progress = len(df[df['status'] == 2])
    done = len(df[df['status'] == 1])
    failed = len(df[df['status'] == 3])
    total = len(df)
    next_link = None
    if pending > 0:
        row = df[df['status'] == 0].iloc[0]
        next_link = {"link": row['link'], "title": row.get('title', '')}
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
    """Memaksa sinkronisasi dari GitHub. Mengembalikan jumlah link baru dan total setelah sinkron."""
    csv_path = DATA_DIR / "links.csv"
    before = 0
    if csv_path.exists():
        before = len(pd.read_csv(csv_path))
    try:
        github_sync.sync()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    after = len(pd.read_csv(csv_path)) if csv_path.exists() else 0
    added = after - before
    return {"message": "Sinkronisasi selesai", "added": added, "total": after}
@app.post("/start-job")
async def start_job():
    """Menjalankan process.py sebagai subprocess di latar belakang (non-blocking)."""
    try:
        proc = subprocess.Popen(
            ["python", "backend/process.py"],
            cwd=Path(__file__).parent.parent,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return {"message": "Job dimulai di background", "pid": proc.pid}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
@app.post("/stop-job")
async def stop_job():
    """Mengirim sinyal berhenti dengan membuat file /tmp/clipper_stop."""
    try:
        Path("/tmp/clipper_stop").touch()
        return {"message": "Sinyal stop terkirim"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
@app.get("/logs")
async def get_logs(lines: int = Query(50, ge=1, le=1000)):
    """Mengembalikan N baris terakhir dari file process.log."""
    log_file = LOGS_DIR / "process.log"
    if not log_file.exists():
        return {"logs": ""}
    with open(log_file, "r") as f:
        all_lines = f.readlines()
        last_lines = all_lines[-lines:]
    return {"logs": "".join(last_lines)}
@app.post("/reset")
async def reset_status():
    """Reset semua status menjadi 0 (pending)."""
    try:
        process.reset_all()
        return {"message": "Semua status direset ke 0"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

---

## **frontend/index.html**

html

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CLIPPER Dashboard</title>
    <link rel="stylesheet" href="/frontend/style.css">
</head>
<body>
    <h1>CLIPPER Control Panel</h1>
    <div id="status">
        <h2>Status</h2>
        <pre id="status-output">Loading...</pre>
    </div>
    <div id="controls">
        <button onclick="syncNow()">Sync GitHub</button>
        <button onclick="startJob()">Start Job</button>
        <button onclick="stopJob()">Stop Job</button>
        <button onclick="resetStatus()">Reset All</button>
        <button onclick="refreshStatus()">Refresh Status</button>
    </div>
    <div id="logs">
        <h2>Logs</h2>
        <pre id="log-output">Loading...</pre>
        <button onclick="refreshLogs()">Refresh Logs</button>
    </div>
    <script src="/frontend/main.js"></script>
</body>
</html>

---

## **frontend/main.js**

javascript

const API_BASE = '';  // origin yang sama
async function fetchJSON(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text}`);
    }
    return res.json();
}
async function syncNow() {
    try {
        const data = await fetchJSON('/sync', { method: 'POST' });
        alert(`Sync selesai: ${data.added} link baru. Total: ${data.total}`);
        refreshStatus();
    } catch (e) {
        alert('Sync gagal: ' + e.message);
    }
}
async function startJob() {
    try {
        const data = await fetchJSON('/start-job', { method: 'POST' });
        alert('Job dimulai (PID: ' + data.pid + ')');
        refreshStatus();
    } catch (e) {
        alert('Start job gagal: ' + e.message);
    }
}
async function stopJob() {
    try {
        const data = await fetchJSON('/stop-job', { method: 'POST' });
        alert('Sinyal stop terkirim');
    } catch (e) {
        alert('Stop gagal: ' + e.message);
    }
}
async function resetStatus() {
    if (!confirm('Reset semua status ke 0?')) return;
    try {
        const data = await fetchJSON('/reset', { method: 'POST' });
        alert('Reset selesai');
        refreshStatus();
    } catch (e) {
        alert('Reset gagal: ' + e.message);
    }
}
async function refreshStatus() {
    try {
        const data = await fetchJSON('/status');
        let output = `Pending: ${data.pending}
In Progress: ${data.in_progress}
Done: ${data.done}
Failed: ${data.failed}
Total: ${data.total}`;
        if (data.next_link) {
            output += `\n\nLink berikutnya:\nJudul: ${data.next_link.title}\nLink: ${data.next_link.link}`;
        }
        document.getElementById('status-output').innerText = output;
    } catch (e) {
        document.getElementById('status-output').innerText = 'Gagal memuat status: ' + e.message;
    }
}
async function refreshLogs() {
    try {
        const data = await fetchJSON('/logs?lines=50');
        document.getElementById('log-output').innerText = data.logs || '(kosong)';
    } catch (e) {
        document.getElementById('log-output').innerText = 'Gagal memuat log: ' + e.message;
    }
}
// Muat pertama kali
refreshStatus();
refreshLogs();
// Refresh otomatis setiap 10 detik
setInterval(refreshStatus, 10000);
setInterval(refreshLogs, 10000);

---

## **frontend/style.css** (opsional, untuk tampilan minimal)

css

body {
    font-family: Arial, sans-serif;
    margin: 20px;
    background: #f5f5f5;
}
h1 {
    color: #333;
}
#status, #logs, #controls {
    background: white;
    padding: 15px;
    margin-bottom: 20px;
    border-radius: 5px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
pre {
    background: #eee;
    padding: 10px;
    overflow-x: auto;
    max-height: 300px;
    white-space: pre-wrap;
}
button {
    margin-right: 10px;
    padding: 8px 12px;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 3px;
    cursor: pointer;
}
button:hover {
    background: #0056b3;
}

---

### **Catatan Implementasi**

- **`/start-job`** menjalankan `process.py` sebagai subprocess terpisah agar tidak memblokir server FastAPI.
    
- **`/stop-job`** hanya membuat file sentinel `/tmp/clipper_stop`. Modifikasi pada `process.py` diperlukan agar proses memeriksa file tersebut dan berhenti secara graceful.
    
- Semua endpoint mengembalikan JSON yang sesuai dengan kebutuhan frontend.
    
- Frontend melakukan polling status dan log setiap 10 detik untuk pembaruan real-time.
    

Dengan file-file ini, sistem CLIPPER sudah memiliki backend API dan antarmuka web dasar sesuai spesifikasi.

---

Kita perlu memberikan file tes dan README sesuai permintaan. Karena proyek ini sudah memiliki banyak komponen, kita akan buat folder tests/ dan file test_github_sync.py. Juga perbarui README.md dengan instruksi instalasi dan penggunaan, menggabungkan dari CLIPPER_SPEC.

Kita akan buat struktur:

- tests/test_github_sync.py
    
- README.md (update)
    

Kita juga perlu pastikan bahwa pytest bisa dijalankan, jadi kita tambahkan pytest ke requirements (opsional, tapi bisa di dev requirements). Namun untuk sederhana, kita hanya buat test file dengan asumsi pytest sudah terinstall.

Mari kita buat.

**tests/test_github_sync.py**:

- Menguji fungsi merge_data dari github_sync (kita perlu refactor sedikit agar bisa diimpor). Dalam implementasi github_sync.py sebelumnya, merge_data didefinisikan di dalam sync? Sebenarnya ada fungsi merge_data di dalam file tersebut. Kita akan membuat test dengan mengimpor fungsi tersebut, namun karena kita tidak mengekspornya secara eksplisit, kita perlu memodifikasi github_sync.py untuk mengekspor fungsi-fungsi penting. Alternatif: kita buat test yang menjalankan modul dengan argumen dry-run dan memeriksa output, tetapi lebih baik unit test untuk logika merge. Saya asumsikan kita bisa mengimpor fungsi dari github_sync setelah kita menambahkan **all** atau mengekspornya. Atau kita bisa menulis test dengan menjalankan fungsi yang ada di dalam modul dengan mock.
    

Saya akan buat test dengan mengimpor fungsi merge_data jika ada. Jika tidak, kita bisa menulis test dengan memanggil github_sync.sync dengan mock data. Tapi lebih mudah: kita buat test yang menguji logika penggabungan dengan membuat DataFrame buatan dan memanggil fungsi merge_data yang akan kita refactor dari github_sync.py. Karena kita hanya perlu memberikan file, kita akan menulis test yang mengasumsikan fungsi tersebut ada. Saya akan menuliskan test dengan asumsi kita dapat mengimpor `merge_data` dari `backend.github_sync`. Untuk itu, kita perlu memastikan bahwa `github_sync.py` mengekspor fungsi tersebut. Dalam kode sebelumnya, merge_data adalah fungsi internal di dalam sync? Mari lihat: di kode github_sync.py yang diberikan, ada fungsi `merge_data(remote_df, local_df)` yang didefinisikan di tingkat modul. Jadi bisa diimpor. Baik.

Kita akan buat test yang memeriksa:

- Jika remote memiliki link baru, ditambahkan dengan status=0.
    
- Jika remote memiliki link yang sudah ada, hanya judul diperbarui, status tetap.
    
- Kolom lain dipertahankan.
    
- Jika remote memiliki baris dengan kolom yang hilang, ditangani.
    

Juga kita perlu mock untuk download? Tidak, kita hanya uji fungsi merge secara terpisah.

**README.md**:

- Menggabungkan dari CLIPPER_SPEC, memberikan instruksi instalasi sistem, setup environment, konfigurasi, menjalankan.
    

Mari tulis.

**Perubahan kecil pada github_sync.py**:  
Tidak perlu, karena fungsi merge_data sudah ada.

**Tambahkan pytest ke requirements**? Bisa ditambahkan di bagian dev, tapi untuk keperluan ini tidak wajib. Kita bisa sebutkan di README bahwa untuk menjalankan test, install pytest.

Sekarang kita buat file-file tersebut.

## **tests/test_github_sync.py**

python

"""
Unit tests for github_sync merge logic.
Run with: pytest tests/test_github_sync.py
"""
import pandas as pd
import sys
from pathlib import Path
# Tambahkan root ke path agar bisa import backend
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.github_sync import merge_data, ensure_columns, EXPECTED_COLUMNS
def test_merge_data_new_links():
    """Remote membawa link baru, harus ditambahkan dengan status=0."""
    local = pd.DataFrame([
        {"link": "a", "title": "A", "status": 1, "times_processed": 1, "last_processed": "2025-01-01", "notes": ""}
    ])
    remote = pd.DataFrame([
        {"link": "b", "title": "B"}
    ])
    merged = merge_data(remote, local)
    assert len(merged) == 2
    assert merged[merged["link"] == "b"].iloc[0]["status"] == 0
    assert merged[merged["link"] == "b"].iloc[0]["times_processed"] == 0
def test_merge_data_existing_link_preserve_status():
    """Link yang sudah ada, status dan metadata tetap dipertahankan, judul diperbarui."""
    local = pd.DataFrame([
        {"link": "a", "title": "Old Title", "status": 2, "times_processed": 3, "last_processed": "2025-01-01", "notes": "some note"}
    ])
    remote = pd.DataFrame([
        {"link": "a", "title": "New Title"}
    ])
    merged = merge_data(remote, local)
    assert len(merged) == 1
    row = merged.iloc[0]
    assert row["title"] == "New Title"  # judul diperbarui
    assert row["status"] == 2
    assert row["times_processed"] == 3
    assert row["last_processed"] == "2025-01-01"
    assert row["notes"] == "some note"
def test_merge_data_mixed():
    """Campuran link baru dan lama."""
    local = pd.DataFrame([
        {"link": "a", "title": "A", "status": 1, "times_processed": 1, "last_processed": "", "notes": ""},
        {"link": "b", "title": "B", "status": 0, "times_processed": 0, "last_processed": "", "notes": ""}
    ])
    remote = pd.DataFrame([
        {"link": "a", "title": "A Updated"},
        {"link": "c", "title": "C New"}
    ])
    merged = merge_data(remote, local)
    assert len(merged) == 3
    # a: status tetap 1, judul diperbarui
    a = merged[merged["link"] == "a"].iloc[0]
    assert a["status"] == 1
    assert a["title"] == "A Updated"
    # b: tetap ada (tidak di remote) tapi tidak dihapus
    b = merged[merged["link"] == "b"].iloc[0]
    assert b["status"] == 0
    # c: baru
    c = merged[merged["link"] == "c"].iloc[0]
    assert c["status"] == 0
    assert c["title"] == "C New"
def test_ensure_columns():
    """Pastikan kolom yang hilang ditambahkan."""
    df = pd.DataFrame([{"link": "x"}])
    df2 = ensure_columns(df)
    for col in EXPECTED_COLUMNS:
        assert col in df2.columns
    assert df2["title"].iloc[0] == ""
    assert df2["status"].iloc[0] == 0

---

## **README.md**

markdown

# CLIPPER - Autonomous Video Clipper & Uploader
CLIPPER adalah sistem otomatis untuk mengambil daftar link YouTube dari GitHub, mendownload, membuat klip pendek, mentranskripsi dengan Whisper, menghasilkan skrip baru dengan Ollama, merender video, dan mengunggah ke YouTube/TikTok.
## Fitur
- Sinkronisasi daftar link dari GitHub (CSV) dengan merge cerdas.
- Pipeline per video: download (yt-dlp) → ekstrak audio → transkripsi (whisper.cpp) → generate script (Ollama) → render klip 720p → upload YouTube.
- Dashboard web lokal (FastAPI + HTML/JS) untuk kontrol dan monitoring.
- Single-instance dengan lockfile, cocok untuk RAM 8GB.
- Logging lengkap.
## Instalasi
### 1. Clone repositori
```bash
git clone https://github.com/yourusername/clipper.git
cd clipper

### 2. Install dependensi sistem

bash

sudo apt update
sudo apt install -y ffmpeg git curl build-essential cmake pkg-config libsndfile1 python3-pip
sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
sudo chmod a+rx /usr/local/bin/yt-dlp

### 3. Setup virtual environment

bash

python3 -m venv ~/yt-env
source ~/yt-env/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

### 4. Install whisper.cpp (opsional, untuk transkripsi lokal)

bash

cd ~
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
make -j4
# Download model base.en
./models/download-ggml-model.sh base.en

Catatan: sesuaikan path `WHISPER_CLI_PATH` di `.env` jika perlu.

### 5. Install Ollama (opsional, untuk generate script)

bash

curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama2

### 6. Konfigurasi

Salin file contoh environment:

bash

cp .env.example .env

Edit `.env` sesuai dengan konfigurasi Anda:

- `GITHUB_RAW_URL`: URL raw GitHub CSV (contoh: `https://raw.githubusercontent.com/user/repo/main/links.csv`)
    
- `GITHUB_TOKEN`: Token GitHub (jika repositori privat)
    
- `OLLAMA_URL`: URL Ollama (default `http://localhost:11434/api/generate`)
    
- `WORKER_NAME`: Nama worker untuk identifikasi
    
- `RESET_ON_EMPTY`: `true` untuk reset status ketika antrian kosong
    
- `MAX_REPEATS`: Maksimal percobaan ulang per video
    
- `YOUTUBE_CLIENT_SECRETS`: Path ke file client_secrets.json dari Google Cloud Console
    

Buat file CSV di GitHub dengan format minimal:

csv

link,title,status
https://youtu.be/abc123,Judul Video 1,0
https://youtu.be/xyz789,Judul Video 2,0

### 7. Setup YouTube OAuth (sekali saja)

1. Buka [Google Cloud Console](https://console.cloud.google.com/).
    
2. Buat project, aktifkan YouTube Data API v3.
    
3. Buat credentials OAuth 2.0 Client ID (tipe Desktop Application).
    
4. Download JSON, simpan sebagai `backend/client_secrets.json`.
    
5. Jalankan script berikut untuk mendapatkan token:
    

bash

cd backend
python -c "from youtube_uploader import get_authenticated_service; get_authenticated_service()"

Browser akan terbuka untuk login. Setelah sukses, token tersimpan di `backend/yt_token.pkl`.

### 8. Buat struktur folder

bash

mkdir -p data backups raw transcript rendered logs

## Menjalankan Sistem

### Jalankan backend API (dashboard)

bash

source ~/yt-env/bin/activate
uvicorn backend.app:app --host 0.0.0.0 --port 8000

Akses dashboard di `http://localhost:8000/frontend/index.html`

### Jalankan worker loop (proses otomatis)

bash

./scripts/runner.sh

Atau pasang sebagai service systemd (contoh file di `systemd/clipper.service`).

### Atau gunakan cron

Tambahkan ke crontab:

text

*/10 * * * * cd /home/hasant/clipper && /home/hasant/yt-env/bin/python backend/github_sync.py && /home/hasant/yt-env/bin/python backend/process.py

## Pengujian

Install pytest:

bash

pip install pytest
pytest tests/

## Struktur Proyek

text

/home/hasant/clipper/
├── README.md
├── .env.example
├── data/
├── backups/
├── raw/
├── transcript/
├── rendered/
├── logs/
├── backend/
│   ├── app.py
│   ├── github_sync.py
│   ├── process.py
│   ├── youtube_uploader.py
│   ├── utils.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── main.js
│   └── style.css
├── scripts/
│   ├── runner.sh
│   └── install-deps.sh
├── systemd/
│   └── clipper.service
└── tests/
    └── test_github_sync.py

## Lisensi

MIT

text

Dengan menambahkan file test dan README yang komprehensif, proyek CLIPER kini siap digunakan dan dikembangkan lebih lanjut.