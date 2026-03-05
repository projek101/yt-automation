#!/usr/bin/env python3
"""
github_sync.py - Synchronize YouTube links from GitHub CSV to local.
Downloads CSV from GITHUB_RAW_URL, merges with local data/links.csv.
Preserves status, times_processed, last_processed, notes for existing links.
Adds new links with status=0.
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

import requests
import pandas as pd

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.utils import DATA_DIR, BACKUPS_DIR, sync_logger

# Environment variables
GITHUB_RAW_URL = os.getenv("GITHUB_RAW_URL")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Expected CSV columns
EXPECTED_COLUMNS = ['link', 'title', 'status', 'times_processed', 'last_processed', 'notes']


def download_csv():
    """
    Download CSV from GitHub.
    Returns DataFrame if successful, None if failed.
    """
    if not GITHUB_RAW_URL:
        sync_logger.error("GITHUB_RAW_URL not set in .env")
        return None
    
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    try:
        sync_logger.info(f"Downloading CSV from {GITHUB_RAW_URL}")
        resp = requests.get(GITHUB_RAW_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        
        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))
        
        # Validate required columns
        if 'link' not in df.columns:
            sync_logger.error("Remote CSV missing 'link' column")
            return None
        
        # Add missing columns with defaults
        if 'title' not in df.columns:
            df['title'] = ''
        if 'status' not in df.columns:
            df['status'] = 0
        
        sync_logger.info(f"Download successful, {len(df)} rows found")
        return df
        
    except requests.exceptions.RequestException as e:
        sync_logger.error(f"Download failed: {e}")
    except pd.errors.EmptyDataError:
        sync_logger.error("CSV file is empty")
    except Exception as e:
        sync_logger.error(f"Unexpected error: {e}")
    
    return None


def ensure_columns(df):
    """Ensure DataFrame has all expected columns."""
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            if col in ['title', 'notes', 'last_processed']:
                df[col] = ''
            elif col in ['status', 'times_processed']:
                df[col] = 0
    return df[EXPECTED_COLUMNS]


def load_local_csv():
    """Load local CSV file, return DataFrame."""
    local_path = DATA_DIR / "links.csv"
    
    if local_path.exists():
        try:
            df = pd.read_csv(local_path)
            sync_logger.info(f"Local CSV loaded, {len(df)} rows")
            return ensure_columns(df)
        except Exception as e:
            sync_logger.error(f"Error reading local CSV: {e}")
            return pd.DataFrame(columns=EXPECTED_COLUMNS)
    else:
        sync_logger.info("Local CSV not found, will be created")
        return pd.DataFrame(columns=EXPECTED_COLUMNS)


def backup_local():
    """Backup local CSV to backups folder with timestamp."""
    local_path = DATA_DIR / "links.csv"
    
    if not local_path.exists():
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"links.{timestamp}.bak"
    backup_path = BACKUPS_DIR / backup_name
    
    shutil.copy(local_path, backup_path)
    sync_logger.info(f"Backup created: {backup_path}")
    return backup_path


def merge_data(remote_df, local_df):
    """
    Merge remote and local DataFrames.
    - Existing links: preserve status, times_processed, last_processed, notes
    - New links: add with status=0
    """
    local_links = set(local_df['link'].values)
    merged = local_df.copy()
    
    new_rows = []
    for _, row in remote_df.iterrows():
        link = row['link']
        
        if link in local_links:
            # Update title from remote, keep other fields
            merged.loc[merged['link'] == link, 'title'] = row.get('title', '')
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
            new_rows.append(new_row)
    
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        merged = pd.concat([merged, new_df], ignore_index=True)
        sync_logger.info(f"Added {len(new_rows)} new links")
    else:
        sync_logger.info("No new links to add")
    
    return merged


def save_local(df):
    """Save DataFrame to local CSV."""
    local_path = DATA_DIR / "links.csv"
    
    try:
        df.to_csv(local_path, index=False)
        sync_logger.info(f"Local CSV saved: {local_path} ({len(df)} rows)")
        return True
    except Exception as e:
        sync_logger.error(f"Error saving local CSV: {e}")
        return False


def sync(dry_run=False):
    """
    Main sync function.
    
    Args:
        dry_run: If True, don't write any files
    
    Returns:
        dict with sync results: {'success': bool, 'added': int, 'total': int}
    """
    if not GITHUB_RAW_URL:
        sync_logger.error("GITHUB_RAW_URL not set")
        return {'success': False, 'added': 0, 'total': 0}
    
    # Download remote CSV
    remote_df = download_csv()
    if remote_df is None:
        return {'success': False, 'added': 0, 'total': 0}
    
    # Load local CSV
    local_df = load_local_csv()
    local_count = len(local_df)
    
    # Backup before merging (skip in dry-run)
    if not dry_run:
        backup_local()
    
    # Merge data
    merged_df = merge_data(remote_df, local_df)
    
    # Save if not dry-run
    if not dry_run:
        save_local(merged_df)
    else:
        sync_logger.info("DRY RUN: No files written")
    
    # Calculate results
    added = len(merged_df) - local_count
    total = len(merged_df)
    
    sync_logger.info(f"Sync complete. Added: {added}, Total: {total}")
    
    return {'success': True, 'added': added, 'total': total}


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync YouTube links from GitHub")
    parser.add_argument('--dry-run', action='store_true', help='Simulate without writing files')
    args = parser.parse_args()
    
    result = sync(dry_run=args.dry_run)
    
    if result['success']:
        print(f"Sync complete: {result['added']} added, {result['total']} total")
        sys.exit(0)
    else:
        print("Sync failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
