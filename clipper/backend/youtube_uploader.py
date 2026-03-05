#!/usr/bin/env python3
"""
youtube_uploader.py - Upload videos to YouTube using OAuth 2.0.

Setup:
1. Go to https://console.cloud.google.com/
2. Create project, enable YouTube Data API v3
3. Create OAuth 2.0 credentials (Desktop Application)
4. Download JSON as 'client_secrets.json' in backend folder
5. Run once to authorize: python youtube_uploader.py

Environment:
- YOUTUBE_CLIENT_SECRETS: path to client_secrets.json
"""

import os
import pickle
import time
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.utils import process_logger

# Google imports
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# OAuth scopes
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Paths
TOKEN_FILE = Path(__file__).parent / "yt_token.pkl"
CLIENT_SECRETS_FILE = os.getenv("YOUTUBE_CLIENT_SECRETS", "")


def get_authenticated_service(client_secrets_file=None):
    """
    Get authenticated YouTube service.
    Handles OAuth flow, token refresh, and storage.
    """
    if client_secrets_file is None:
        client_secrets_file = CLIENT_SECRETS_FILE
    
    if not client_secrets_file or not os.path.exists(client_secrets_file):
        process_logger.error(f"Client secrets file not found: {client_secrets_file}")
        process_logger.error("Set YOUTUBE_CLIENT_SECRETS in .env")
        return None
    
    credentials = None
    
    # Load existing token
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE, 'rb') as f:
                credentials = pickle.load(f)
            process_logger.info("Loaded existing token")
        except Exception as e:
            process_logger.warning(f"Failed to load token: {e}")
    
    # Refresh or get new credentials
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                process_logger.info("Token refreshed successfully")
            except Exception as e:
                process_logger.error(f"Token refresh failed: {e}")
                credentials = None
        else:
            # Run OAuth flow
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_secrets_file, SCOPES)
                credentials = flow.run_local_server(
                    host='localhost',
                    port=8080,
                    open_browser=True
                )
                process_logger.info("OAuth flow completed")
            except Exception as e:
                process_logger.error(f"OAuth flow failed: {e}")
                return None
    
    # Save token
    if credentials:
        try:
            with open(TOKEN_FILE, 'wb') as f:
                pickle.dump(credentials, f)
            process_logger.info(f"Token saved to {TOKEN_FILE}")
        except Exception as e:
            process_logger.warning(f"Failed to save token: {e}")
    
    # Build YouTube service
    try:
        youtube = build("youtube", "v3", credentials=credentials)
        return youtube
    except Exception as e:
        process_logger.error(f"Failed to build YouTube service: {e}")
        return None


def upload_video(file_path, title, description, privacy_status="private", tags=None, max_retries=3):
    """
    Upload video to YouTube.
    
    Args:
        file_path: Path to video file
        title: Video title
        description: Video description
        privacy_status: "private", "unlisted", or "public"
        tags: List of tags
        max_retries: Maximum retry attempts
    
    Returns:
        Video ID if successful, None if failed
    """
    if not os.path.exists(file_path):
        process_logger.error(f"Video file not found: {file_path}")
        return None
    
    youtube = get_authenticated_service()
    if not youtube:
        process_logger.error("Could not get YouTube service")
        return None
    
    # Video body
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "22"  # People & Blogs
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }
    
    # Media upload
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    
    # Retry loop
    for attempt in range(1, max_retries + 1):
        try:
            process_logger.info(f"Uploading (attempt {attempt}/{max_retries}): {title}")
            
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            
            response = request.execute()
            video_id = response.get("id")
            
            process_logger.info(f"Upload successful: https://youtu.be/{video_id}")
            return video_id
            
        except HttpError as e:
            process_logger.error(f"HTTP error: {e}")
            if attempt < max_retries:
                wait_time = 2 ** attempt
                process_logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                process_logger.error("Max retries reached")
                return None
        except Exception as e:
            process_logger.error(f"Upload error: {e}")
            return None
    
    return None


def main():
    """CLI for testing upload."""
    import argparse
    
    parser = argparse.ArgumentParser(description="YouTube Video Uploader")
    parser.add_argument("video_file", help="Path to video file")
    parser.add_argument("--title", default="Test Upload", help="Video title")
    parser.add_argument("--description", default="Uploaded by CLIPPER", help="Video description")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"],
                        help="Privacy status")
    
    args = parser.parse_args()
    
    video_id = upload_video(
        args.video_file,
        args.title,
        args.description,
        args.privacy
    )
    
    if video_id:
        print(f"Upload successful: https://youtu.be/{video_id}")
    else:
        print("Upload failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
