#!/usr/bin/env python3
"""
utils.py - Utility functions for CLIPPER.
Provides path configuration, logging setup, and lockfile functions.
"""

import os
import logging
import fcntl
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paths - base directory is ~/clipper
ROOT_DIR = Path(__file__).parent.parent
CLIPPER_HOME = Path(os.getenv("CLIPPER_HOME", os.path.expanduser("~/clipper")))

DATA_DIR = CLIPPER_HOME / "data"
LOGS_DIR = CLIPPER_HOME / "logs"
BACKUPS_DIR = CLIPPER_HOME / "backups"
RAW_DIR = CLIPPER_HOME / "raw"
TRANSCRIPT_DIR = CLIPPER_HOME / "transcript"
RENDERED_DIR = CLIPPER_HOME / "rendered"

# Lock file path
LOCK_FILE = CLIPPER_HOME / ".process.lock"

# Ensure directories exist
for d in [DATA_DIR, LOGS_DIR, BACKUPS_DIR, RAW_DIR, TRANSCRIPT_DIR, RENDERED_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def setup_logger(name, log_file):
    """
    Set up a logger with file and console handlers.
    
    Args:
        name: Logger name
        log_file: Path to log file
    
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # File handler
    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


# Create loggers
process_logger = setup_logger('process', LOGS_DIR / 'process.log')
sync_logger = setup_logger('sync', LOGS_DIR / 'sync.log')


def acquire_lock(lock_file=None):
    """
    Acquire exclusive lock to prevent multiple instances.
    
    Args:
        lock_file: Path to lock file (default: LOCK_FILE)
    
    Returns:
        File handle if successful, None otherwise
    """
    if lock_file is None:
        lock_file = LOCK_FILE
    
    try:
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        fp = open(lock_file, 'w')
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fp.write(str(os.getpid()))
        fp.flush()
        return fp
    except (IOError, OSError) as e:
        process_logger.warning(f"Could not acquire lock: {e}")
        return None


def release_lock(fp, lock_file=None):
    """
    Release lock and close file handle.
    
    Args:
        fp: File handle
        lock_file: Path to lock file (default: LOCK_FILE)
    """
    if fp:
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
            fp.close()
        except Exception as e:
            process_logger.warning(f"Error releasing lock: {e}")
    
    if lock_file is None:
        lock_file = LOCK_FILE
    
    if lock_file.exists():
        try:
            lock_file.unlink()
        except Exception as e:
            process_logger.warning(f"Could not remove lock file: {e}")
