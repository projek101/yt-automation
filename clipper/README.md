# CLIPPER - Autonomous YouTube Clipper

CLIPPER is an automated system for downloading YouTube videos, creating short clips, transcribing with Whisper, generating new scripts with Ollama, rendering, and uploading to YouTube/TikTok.

## Features

- **GitHub Sync**: Automatically sync YouTube links from a GitHub-hosted CSV file
- **Video Pipeline**: Download → Extract Audio → Transcribe → Generate Script → Render → Upload
- **Dashboard**: Web-based UI for monitoring and control
- **Single Instance**: Lockfile prevents multiple concurrent runs
- **Comprehensive Logging**: All operations logged to files

## Quick Installation

1. Clone repository to `~/clipper`:

```
bash
   git clone https://github.com/yourusername/clipper.git ~/clipper
   cd ~/clipper

```

2. Install system dependencies:

```
bash
   chmod +x scripts/install-deps.sh
   ./scripts/install-deps.sh

```

3. Create virtual environment:

```
bash
   python3 -m venv ~/yt-env
   source ~/yt-env/bin/activate
   pip install -r backend/requirements.txt

```

4. Configure environment:

```
bash
   cp .env.example .env
   # Edit .env with your settings

```

5. Run the server:

```
bash
   uvicorn backend.app:app --host 0.0.0.0 --port 8000

```

6. Access dashboard: `http://localhost:8000/frontend/index.html`

## Project Structure

```
~/clipper/
├── README.md
├── .env.example
├── data/
│   └── links.csv          # YouTube links queue
├── backups/               # CSV backups
├── raw/                  # Downloaded videos
├── transcript/           # Transcriptions & scripts
├── rendered/             # Final video clips
├── logs/                 # Log files
├── backend/
│   ├── app.py           # FastAPI server
│   ├── github_sync.py   # GitHub sync
│   ├── process.py       # Job processor
│   ├── youtube_uploader.py
│   ├── utils.py         # Utilities
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── main.js
│   └── style.css
├── scripts/
│   ├── runner.sh        # Continuous runner
│   └── install-deps.sh
└── systemd/
    └── clipper.service
```

## CSV Format

```
csv
link,title,status,times_processed,last_processed,notes
https://youtu.be/abc123,Video Title,0,0,,
```

- **status**: 0=pending, 1=done, 2=in_progress, 3=failed

## Environment Variables

| Variable           | Description                  | Default                               |
| ------------------ | ---------------------------- | ------------------------------------- |
| `CLIPPER_HOME`     | Base directory               | `~/clipper`                           |
| `GITHUB_RAW_URL`   | GitHub CSV URL               | -                                     |
| `GITHUB_TOKEN`     | GitHub token (private repos) | -                                     |
| `OLLAMA_URL`       | Ollama API URL               | `http://localhost:11434/api/generate` |
| `OLLAMA_MODEL`     | Ollama model                 | `llama2`                              |
| `WHISPER_CLI_PATH` | whisper-cli path             | `~/whisper.cpp/build/bin/whisper-cli` |
| `MAX_REPEATS`      | Max retries per video        | `3`                                   |
| `RESET_ON_EMPTY`   | Reset when queue empty       | `true`                                |

## Usage

### Run One Job

```
bash
python backend/process.py
```

### Check Status

```
bash
python backend/process.py --status
```

### Reset All Statuses

```
bash
python backend/process.py --reset
```

### Sync from GitHub

```
bash
python backend/github_sync.py
```

### Run Continuous Loop

```
bash
./scripts/runner.sh
```

## Optional: YouTube Upload Setup

1. Go to Google Cloud Console
2. Enable YouTube Data API v3
3. Create OAuth 2.0 credentials (Desktop app)
4. Download JSON as `backend/client_secrets.json`
5. Run once to authorize:

```
bash
   python backend/youtube_uploader.py

```

## License

MIT
