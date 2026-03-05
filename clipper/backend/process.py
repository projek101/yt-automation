#!/usr/bin/env python3
"""
process.py - Single-job runner for CLIPPER pipeline.
Processes one YouTube link: download, transcribe, generate script, render.

Usage:
    python process.py          # Run one job
    python process.py --help  # Show help

Environment variables (configurable paths):
    CLIPPER_HOME         - Base directory (default: ~/clipper)
    YT_DLP_PATH          - Path to yt-dlp binary (default: yt-dlp)
    FFMPEG_PATH          - Path to ffmpeg binary (default: ffmpeg)
    WHISPER_CLI_PATH     - Path to whisper-cli binary
    WHISPER_MODEL        - Whisper model name (default: base.en)
    OLLAMA_URL           - Ollama API URL (default: http://localhost:11434/api/generate)
    OLLAMA_MODEL         - Ollama model name (default: llama2)
    MAX_REPEATS          - Max retries per video (default: 3)
    RESET_ON_EMPTY       - Reset all statuses when queue empty (default: true)

CSV status values:
    0 - pending
    1 - done (success)
    2 - in_progress
    3 - failed
"""

import os
import sys
import subprocess
import time
import logging
import fcntl
from pathlib import Path
from datetime import datetime

# Import pandas for CSV handling
import pandas as pd

# Expand user home directory
CLIPPER_HOME = Path(os.getenv("CLIPPER_HOME", os.path.expanduser("~/clipper")))

# Configure paths relative to CLIPPER_HOME
DATA_DIR = CLIPPER_HOME / "data"
LOGS_DIR = CLIPPER_HOME / "logs"
RAW_DIR = CLIPPER_HOME / "raw"
TRANSCRIPT_DIR = CLIPPER_HOME / "transcript"
RENDERED_DIR = CLIPPER_HOME / "rendered"
LOCK_FILE = CLIPPER_HOME / ".process.lock"
CSV_FILE = DATA_DIR / "links.csv"

# Ensure directories exist
for d in [DATA_DIR, LOGS_DIR, RAW_DIR, TRANSCRIPT_DIR, RENDERED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Configure logging
LOG_FILE = LOGS_DIR / "process.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Environment-configurable command paths
YT_DLP_CMD = os.getenv("YT_DLP_PATH", "yt-dlp")
FFMPEG_CMD = os.getenv("FFMPEG_PATH", "ffmpeg")
WHISPER_CLI_PATH = os.getenv("WHISPER_CLI_PATH", os.path.expanduser("~/whisper.cpp/build/bin/whisper-cli"))
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base.en")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")
MAX_REPEATS = int(os.getenv("MAX_REPEATS", "3"))
RESET_ON_EMPTY = os.getenv("RESET_ON_EMPTY", "true").lower() == "true"

# Status constants
STATUS_PENDING = 0
STATUS_DONE = 1
STATUS_IN_PROGRESS = 2
STATUS_FAILED = 3


class ProcessError(Exception):
    """Custom exception for process errors."""
    pass


def acquire_lock():
    """
    Acquire exclusive lock to prevent multiple instances.
    Returns file handle if successful, None otherwise.
    """
    try:
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        fp = open(LOCK_FILE, 'w')
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fp.write(str(os.getpid()))
        fp.flush()
        return fp
    except (IOError, OSError) as e:
        logger.warning(f"Could not acquire lock: {e}")
        return None


def release_lock(fp):
    """Release lock and close file handle."""
    if fp:
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
            fp.close()
        except Exception as e:
            logger.warning(f"Error releasing lock: {e}")
    # Remove lock file
    if LOCK_FILE.exists():
        try:
            LOCK_FILE.unlink()
        except Exception as e:
            logger.warning(f"Could not remove lock file: {e}")


def run_safe_command(cmd, cwd=None, timeout=3600, check=True):
    """
    Safely execute a subprocess command with timeout and error handling.
    
    Args:
        cmd: Command string to execute
        cwd: Working directory (optional)
        timeout: Timeout in seconds (default: 1 hour)
        check: If True, return False on non-zero exit code
    
    Returns:
        tuple: (success: bool, stdout: str, stderr: str)
    """
    logger.info(f"Executing: {cmd}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            logger.error(f"Command failed with exit code {result.returncode}")
            logger.error(f"STDERR: {result.stderr[:500] if result.stderr else 'None'}")
            if check:
                return False, result.stdout, result.stderr
        else:
            logger.info(f"Command succeeded")
            if result.stdout:
                logger.debug(f"STDOUT: {result.stdout[:200]}")
        
        return result.returncode == 0, result.stdout, result.stderr
        
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {cmd}")
        return False, "", "Timeout"
    except FileNotFoundError as e:
        logger.error(f"Command not found: {e}")
        return False, "", str(e)
    except Exception as e:
        logger.exception(f"Exception executing command: {e}")
        return False, "", str(e)


def load_csv():
    """Load CSV data into DataFrame."""
    import pandas as pd
    
    if not CSV_FILE.exists():
        logger.warning(f"CSV file not found: {CSV_FILE}")
        return None
    
    try:
        df = pd.read_csv(CSV_FILE)
        # Ensure required columns exist
        required_cols = ['link', 'title', 'status', 'times_processed', 'last_processed', 'notes']
        for col in required_cols:
            if col not in df.columns:
                if col in ['notes', 'title', 'last_processed']:
                    df[col] = ''
                else:
                    df[col] = 0
        return df
    except Exception as e:
        logger.error(f"Error reading CSV: {e}")
        return None


def save_csv(df):
    """Save DataFrame to CSV."""
    import pandas as pd
    
    try:
        df.to_csv(CSV_FILE, index=False)
        return True
    except Exception as e:
        logger.error(f"Error saving CSV: {e}")
        return False


def get_next_pending():
    """
    Get the next pending link (status=0).
    Returns (index, row) tuple or (None, None) if no pending links.
    """
    df = load_csv()
    if df is None or df.empty:
        return None, None
    
    pending = df[df['status'] == STATUS_PENDING]
    if pending.empty:
        return None, df
    
    idx = pending.index[0]
    return idx, df.loc[idx]


def mark_in_progress(idx, df):
    """Mark a link as in progress (status=2)."""
    df.loc[idx, 'status'] = STATUS_IN_PROGRESS
    save_csv(df)
    logger.info(f"Marked index {idx} as in_progress")


def mark_done(idx, df, success=True, notes=""):
    """
    Mark a link as done or failed.
    
    Args:
        idx: DataFrame index
        df: DataFrame
        success: True if successful, False if failed
        notes: Additional notes to add
    """
    if success:
        df.loc[idx, 'status'] = STATUS_DONE
    else:
        df.loc[idx, 'status'] = STATUS_FAILED
    
    # Increment times_processed
    current_times = df.loc[idx, 'times_processed']
    df.loc[idx, 'times_processed'] = current_times + 1
    
    # Update last_processed timestamp
    df.loc[idx, 'last_processed'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Append notes if provided
    if notes:
        existing_notes = str(df.loc[idx, 'notes']) if pd.notna(df.loc[idx, 'notes']) else ""
        if existing_notes:
            df.loc[idx, 'notes'] = f"{existing_notes}; {notes}"
        else:
            df.loc[idx, 'notes'] = notes
    
    save_csv(df)
    status_str = "success" if success else "failed"
    logger.info(f"Marked index {idx} as {status_str}")


def reset_all_statuses():
    """Reset all statuses to 0 (pending)."""
    df = load_csv()
    if df is not None and not df.empty:
        df['status'] = STATUS_PENDING
        save_csv(df)
        logger.info("All statuses reset to 0 (pending)")


def safe_filename(text, max_length=100):
    """Create a safe filename from text."""
    keep = "".join(c for c in text if c.isalnum() or c in (' ', '-', '_')).strip()
    safe = keep.replace(' ', '_')[:max_length]
    return safe or "untitled"


def download_video(link, output_path):
    """Download video using yt-dlp."""
    # Ensure output has correct extension
    output_template = str(output_path) + ".%(ext)s"
    cmd = f'{YT_DLP_CMD} -f "best[height<=720]" -o "{output_template}" "{link}"'
    
    success, stdout, stderr = run_safe_command(cmd)
    
    if success:
        # Find the actual downloaded file
        possible_files = list(RAW_DIR.glob(f"{output_path.stem}.*"))
        if possible_files:
            return possible_files[0]
        # Check for any new video files
        video_files = list(RAW_DIR.glob("*.mp4")) + list(RAW_DIR.glob("*.mkv"))
        if video_files:
            return max(video_files, key=lambda p: p.stat().st_mtime)
    
    return None


def extract_audio(video_path, audio_path):
    """Extract audio from video using ffmpeg."""
    cmd = f'{FFMPEG_CMD} -i "{video_path}" -ar 16000 -ac 1 -c:a pcm_s16le "{audio_path}" -y'
    success, _, _ = run_safe_command(cmd)
    return success


def transcribe_audio(audio_path, output_base):
    """
    Transcribe audio using whisper-cli.
    Returns transcript text or None on failure.
    """
    if not os.path.exists(WHISPER_CLI_PATH):
        logger.error(f"whisper-cli not found at: {WHISPER_CLI_PATH}")
        logger.error("Set WHISPER_CLI_PATH environment variable")
        return None
    
    cmd = f'{WHISPER_CLI_PATH} -f "{audio_path}" -otxt -of "{output_base}" -m {WHISPER_MODEL}'
    success, _, _ = run_safe_command(cmd)
    
    if not success:
        return None
    
    # Whisper outputs .txt file
    txt_file = f"{output_base}.txt"
    if not os.path.exists(txt_file):
        logger.error(f"Transcript file not found: {txt_file}")
        return None
    
    try:
        with open(txt_file, 'r', encoding='utf-8') as f:
            transcript = f.read().strip()
        logger.info(f"Transcription complete: {len(transcript)} characters")
        return transcript
    except Exception as e:
        logger.error(f"Error reading transcript: {e}")
        return None


def generate_script(transcript):
    """
    Generate a video script using Ollama.
    Returns generated script text or None on failure.
    """
    import requests
    
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
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        script = data.get("response", "").strip()
        logger.info(f"Script generated: {len(script)} characters")
        return script
    except requests.exceptions.ConnectionError:
        logger.error(f"Could not connect to Ollama at {OLLAMA_URL}")
        logger.error("Make sure Ollama is running and OLLAMA_URL is correct")
        return None
    except requests.exceptions.Timeout:
        logger.error("Ollama request timed out")
        return None
    except Exception as e:
        logger.error(f"Ollama request failed: {e}")
        return None


def render_clip(video_path, output_path, duration=60):
    """
    Render a clip from the video.
    Takes first 'duration' seconds, scales to 720p.
    """
    # Get video duration first
    probe_cmd = f'{FFMPEG_CMD} -i "{video_path}" -f null -'
    _, stdout, _ = run_safe_command(probe_cmd, check=False)
    
    # Try to get duration from ffprobe
    duration_cmd = f'{FFMPEG_CMD} -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{video_path}"'
    success, duration_str, _ = run_safe_command(duration_cmd, check=False)
    
    if success:
        try:
            total_duration = float(duration_str.strip())
            if total_duration < duration:
                duration = int(total_duration)
                logger.info(f"Video duration {total_duration}s is less than {duration}s, using all")
        except (ValueError, TypeError):
            logger.warning("Could not determine video duration, using default")
    
    cmd = (
        f'{FFMPEG_CMD} -i "{video_path}" -t {duration} '
        f'-vf scale=1280:720 -preset veryfast -c:a aac -b:a 128k '
        f'"{output_path}" -y'
    )
    
    return run_safe_command(cmd)


def process_one():
    """
    Process a single pending link.
    This is the main pipeline: download -> extract audio -> transcribe -> generate script -> render.
    """
    lock = acquire_lock()
    if not lock:
        logger.warning("Another process is running, exiting")
        return
    
    try:
        idx, row = get_next_pending()
        
        if idx is None:
            logger.info("No pending links found")
            df = load_csv()
            if RESET_ON_EMPTY and df is not None and not df.empty:
                reset_all_statuses()
            return
        
        link = row['link']
        title = row.get('title', 'No Title') or 'No Title'
        
        logger.info(f"Processing: {title}")
        logger.info(f"Link: {link}")
        
        mark_in_progress(idx, load_csv())
        
        # Check if max repeats reached
        times_processed = row.get('times_processed', 0)
        if pd.notna(times_processed) and times_processed >= MAX_REPEATS:
            mark_done(idx, load_csv(), success=False, notes="Max repeats reached")
            logger.warning(f"Skipping {link} - max repeats ({MAX_REPEATS}) reached")
            return
        
        # Create safe filename base
        safe_title = safe_filename(title)
        timestamp = int(time.time())
        base_name = f"{safe_title}_{timestamp}"
        
        # Define output paths
        video_path = RAW_DIR / f"{base_name}.mp4"
        audio_path = RAW_DIR / f"{base_name}.wav"
        transcript_base = TRANSCRIPT_DIR / base_name
        rendered_path = RENDERED_DIR / f"{base_name}.mp4"
        
        # Step 1: Download video
        logger.info("Step 1: Downloading video...")
        downloaded_path = download_video(link, video_path)
        
        if not downloaded_path or not downloaded_path.exists():
            mark_done(idx, load_csv(), success=False, notes="Download failed")
            logger.error("Video download failed")
            return
        
        logger.info(f"Video downloaded: {downloaded_path}")
        
        # Step 2: Extract audio
        logger.info("Step 2: Extracting audio...")
        if not extract_audio(str(downloaded_path), str(audio_path)):
            mark_done(idx, load_csv(), success=False, notes="Audio extraction failed")
            return
        
        if not audio_path.exists():
            mark_done(idx, load_csv(), success=False, notes="Audio file not created")
            return
        
        logger.info(f"Audio extracted: {audio_path}")
        
        # Step 3: Transcribe audio
        logger.info("Step 3: Transcribing audio...")
        transcript = transcribe_audio(str(audio_path), str(transcript_base))
        
        if transcript is None:
            mark_done(idx, load_csv(), success=False, notes="Transcription failed")
            return
        
        if not transcript:
            mark_done(idx, load_csv(), success=False, notes="Empty transcript")
            return
        
        logger.info(f"Transcript: {transcript[:100]}...")
        
        # Step 4: Generate script with Ollama
        logger.info("Step 4: Generating script with Ollama...")
        script = generate_script(transcript)
        
        if script is None:
            mark_done(idx, load_csv(), success=False, notes="Script generation failed")
            return
        
        logger.info(f"Generated script: {script[:100]}...")
        
        # Save script to file
        script_file = TRANSCRIPT_DIR / f"{base_name}_script.txt"
        try:
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(script)
        except Exception as e:
            logger.warning(f"Could not save script file: {e}")
        
        # Step 5: Render clip
        logger.info("Step 5: Rendering clip...")
        if not render_clip(str(downloaded_path), str(rendered_path)):
            mark_done(idx, load_csv(), success=False, notes="Rendering failed")
            return
        
        if not rendered_path.exists():
            mark_done(idx, load_csv(), success=False, notes="Rendered file not created")
            return
        
        logger.info(f"Rendered video: {rendered_path}")
        
        # Mark as success
        mark_done(idx, load_csv(), success=True, notes=f"Output: {rendered_path}")
        logger.info(f"Successfully processed: {title}")
        
    except Exception as e:
        logger.exception(f"Unexpected error in process_one: {e}")
        # Try to mark as failed if we have idx
        try:
            df = load_csv()
            if 'idx' in locals() and idx is not None and df is not None:
                mark_done(idx, df, success=False, notes=f"Exception: {str(e)[:100]}")
        except Exception:
            pass
    finally:
        release_lock(lock)


def main():
    """Main entry point when run directly."""
    import argparse
    
    parser = argparse.ArgumentParser(description="CLIPPER single-job processor")
    parser.add_argument('--reset', action='store_true', help='Reset all statuses to pending')
    parser.add_argument('--status', action='store_true', help='Show current status')
    args = parser.parse_args()
    
    if args.reset:
        reset_all_statuses()
        print("All statuses have been reset to 0 (pending)")
        return
    
    if args.status:
        df = load_csv()
        if df is None or df.empty:
            print("No links in queue")
            return
        
        pending = len(df[df['status'] == STATUS_PENDING])
        in_progress = len(df[df['status'] == STATUS_IN_PROGRESS])
        done = len(df[df['status'] == STATUS_DONE])
        failed = len(df[df['status'] == STATUS_FAILED])
        
        print(f"Queue Status:")
        print(f"  Pending: {pending}")
        print(f"  In Progress: {in_progress}")
        print(f"  Done: {done}")
        print(f"  Failed: {failed}")
        print(f"  Total: {len(df)}")
        return
    
    # Run one job
    logger.info("=" * 50)
    logger.info("Starting CLIPPER job processor")
    logger.info("=" * 50)
    process_one()
    logger.info("Job processor finished")


if __name__ == "__main__":
    main()
