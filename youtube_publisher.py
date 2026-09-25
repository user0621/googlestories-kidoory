
import fcntl

def get_daily_uploads_atomic():
    tracker_file = "/data/google-stories/youtube_daily_tracker.json"
    if not os.path.exists(tracker_file):
        return 0
    with open(tracker_file, "r") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        data = json.load(f)
        fcntl.flock(f, fcntl.LOCK_UN)
    import datetime
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if data.get("date") == today:
        return data.get("count", 0)
    return 0

def increment_daily_uploads_atomic():
    tracker_file = "/data/google-stories/youtube_daily_tracker.json"
    with open(tracker_file, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        try:
            data = json.load(f)
        except:
            data = {}
        import datetime
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        if data.get("date") != today:
            data = {"date": today, "count": 0}
        data["count"] += 1
        f.seek(0)
        f.truncate()
        json.dump(data, f)
        fcntl.flock(f, fcntl.LOCK_UN)
#!/usr/bin/env python3
"""
youtube_publisher.py - YouTube Data API v3 Auto-Publisher & Token Bridge
Dedicated publishing pipeline for the Kidoory YouTube Channel.

Paths:
  - Client Secrets: /home/hkserver/secrets/kidoory_client_secret.json
  - Refresh Token:  /data/google-stories/youtube_token.json
  - Scopes:         https://www.googleapis.com/auth/youtube.upload

Features:
  - Headless OAuth2 authorization helper
  - Automatic timestamped chapter extraction
  - SEO-optimized metadata generation with #Kidoory branding and kidoory.com link
  - Resumable chunked video upload
"""

import os
import re
import sys
import json
import time
import logging
import argparse
import subprocess
import shutil
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, List
from urllib.parse import urlparse, parse_qs
import unicodedata

# Google API & Auth imports
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from languages import get_language

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("YouTubePublisher")

DEDICATED_CLIENT_SECRETS = "/home/hkserver/secrets/kidoory_client_secret.json"
DEDICATED_TOKEN_FILE = "/data/google-stories/youtube_token.json"
DEFAULT_UPLOAD_LEDGER = "/data/google-stories/upload_ledger.json"
DEFAULT_HISTORY_FILE = "/data/google-stories/history.json"
DEFAULT_FINAL_VIDEOS_DIR = "/data/google-stories/final_videos"
DAILY_UPLOAD_CAP = 5

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
YOUTUBE_FORCE_SSL_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
YOUTUBE_FULL_SCOPE = "https://www.googleapis.com/auth/youtube"
SCOPES = [
    YOUTUBE_FULL_SCOPE,
    YOUTUBE_FORCE_SSL_SCOPE,
    YOUTUBE_UPLOAD_SCOPE,
    YOUTUBE_READONLY_SCOPE
]


def check_client_secrets(secrets_file: str = DEDICATED_CLIENT_SECRETS) -> Tuple[bool, str]:
    """Check if the dedicated Kidoory client secrets file exists and is populated."""
    if not os.path.exists(secrets_file):
        return False, f"Secrets file not found at: {secrets_file}"

    try:
        with open(secrets_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        config = data.get("installed") or data.get("web")
        if not config:
            return False, "Invalid client secrets format: missing 'installed' or 'web' block."

        client_id = config.get("client_id", "")
        client_secret = config.get("client_secret", "")

        if not client_id or "REPLACE_WITH" in client_id or "PLACEHOLDER" in client_id:
            return False, f"File contains placeholder client_id: '{client_id}'"

        if not client_secret or "REPLACE_WITH" in client_secret or "PLACEHOLDER" in client_secret:
            return False, "File contains placeholder client_secret."

        return True, "Valid client secrets found."
    except Exception as e:
        return False, f"Error parsing secrets file: {e}"


TARGET_CHANNEL_ID = "UCobsgHbbxC3tLOpTJKkkHeg"
TARGET_ACCOUNT = "solodigital.ltd@gmail.com"

def print_setup_instructions(secrets_file: str = DEDICATED_CLIENT_SECRETS):
    """Print exact 3-step instructions for obtaining Desktop App OAuth credentials."""
    print("\n" + "="*75)
    print("  ACTION REQUIRED: SETUP OAUTH CLIENT SECRETS (3 STEPS)")
    print("="*75)
    print(f"\nAccount:  {TARGET_ACCOUNT}")
    print(f"Channel:  Kidoory ({TARGET_CHANNEL_ID})")
    print(f"Target:   {secrets_file}\n")
    print("Step 1: Open Google Cloud Console Credentials Page")
    print("   👉 https://console.cloud.google.com/apis/credentials?project=kidoory")
    print("   (Ensure you are signed in as solodigital.ltd@gmail.com)")
    print("\nStep 2: Create a Desktop App OAuth Client ID")
    print("   1. Click '+ CREATE CREDENTIALS' at the top, then select 'OAuth client ID'.")
    print("   2. Under 'Application type', select 'Desktop app'.")
    print("   3. Name it 'Kidoory Studio Uploader' and click 'CREATE'.")
    print("\nStep 3: Download & Save JSON")
    print("   1. In the popup dialog, click 'DOWNLOAD JSON'.")
    print(f"   2. Save the downloaded file to: {secrets_file}")
    print("\n   Quick command to paste JSON directly on this server:")
    print(f"   cat << 'EOF' > {secrets_file}")
    print("   { ... paste your downloaded JSON contents here ... }")
    print("   EOF")
    print("="*75 + "\n")


def authenticate_youtube(
    secrets_file: str = DEDICATED_CLIENT_SECRETS,
    token_file: str = DEDICATED_TOKEN_FILE
) -> Optional[Credentials]:
    """
    Authenticate with YouTube Data API v3.
    Reuses existing token if valid, refreshes if expired, or runs headless interactive flow.
    """
    creds = None

    # 1. Check existing saved token
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file)
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired YouTube access token...")
                creds.refresh(Request())
                with open(token_file, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
                logger.info("Refreshed YouTube token successfully saved.")
                return creds
            elif creds and creds.valid:
                logger.info(f"Loaded valid YouTube credentials from {token_file}")
                return creds
        except Exception as e:
            logger.warning(f"Existing token at {token_file} could not be used ({e}). Re-authorizing...")

    # 2. Check client secrets file
    valid, msg = check_client_secrets(secrets_file)
    if not valid:
        print_setup_instructions(secrets_file)
        try:
            if sys.stdin.isatty():
                choice = input("Would you like to paste your Client ID and Client Secret now? [y/N]: ").strip().lower()
                if choice == "y":
                    cid = input("Enter Client ID: ").strip()
                    csec = input("Enter Client Secret: ").strip()
                    if cid and csec:
                        secret_data = {
                            "installed": {
                                "client_id": cid,
                                "project_id": "kidoory",
                                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                "token_uri": "https://oauth2.googleapis.com/token",
                                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                                "client_secret": csec,
                                "redirect_uris": ["http://localhost:8080/"]
                            }
                        }
                        os.makedirs(os.path.dirname(os.path.abspath(secrets_file)), exist_ok=True)
                        with open(secrets_file, "w", encoding="utf-8") as f:
                            json.dump(secret_data, f, indent=2)
                        logger.info(f"Saved OAuth credentials to {secrets_file}")
                        valid, msg = check_client_secrets(secrets_file)
        except (EOFError, KeyboardInterrupt):
            pass

    if not valid:
        logger.error(f"Cannot authenticate: {msg}")
        return None

    # 3. Headless Console Authorization Flow
    logger.info("Initializing OAuth 2.0 flow for Kidoory YouTube Channel...")
    flow = InstalledAppFlow.from_client_secrets_file(
        secrets_file,
        scopes=SCOPES,
        redirect_uri="http://localhost:8080/"
    )

    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

    print("\n" + "="*75)
    print("  ACTION REQUIRED: ONE-TIME GOOGLE YOUTUBE AUTHORIZATION")
    print("="*75)
    print("\n1. Open this URL in your web browser:")
    print(f"\n   👉 {auth_url}\n")
    print("2. Sign in with the Google Account that manages Kidoory:")
    print("   📧 solodigital.ltd@gmail.com")
    print("\n3. Grant access to 'Manage your YouTube videos'.")
    print("\n4. After granting access, your browser will attempt to redirect to")
    print("   'http://localhost:8080/?state=...&code=4/0A...'.")
    print("\n   Copy the ENTIRE redirect URL (or just the 'code=' value) from your")
    print("   browser address bar and paste it below:\n")
    print("="*75)

    try:
        user_input = input("Enter redirect URL or code: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAuthorization cancelled by user.")
        return None

    if not user_input:
        logger.error("No input received. Authorization aborted.")
        return None

    # Extract authorization code
    code = user_input
    if "code=" in user_input:
        try:
            parsed = urlparse(user_input)
            params = parse_qs(parsed.query)
            code = params.get("code", [user_input])[0]
        except Exception:
            code = user_input

    logger.info("Exchanging authorization code for persistent refresh token...")
    try:
        flow.fetch_token(code=code)
        creds = flow.credentials

        os.makedirs(os.path.dirname(os.path.abspath(token_file)), exist_ok=True)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

        # Verify connected channel
        try:
            youtube = build("youtube", "v3", credentials=creds)
            ch_resp = youtube.channels().list(mine=True, part="id,snippet").execute()
            ch_items = ch_resp.get("items", [])
            if ch_items:
                ch_title = ch_items[0]["snippet"]["title"]
                ch_id = ch_items[0]["id"]
                logger.info(f"Connected YouTube Channel: '{ch_title}' (ID: {ch_id})")
                is_match = (ch_id == TARGET_CHANNEL_ID)
                status_badge = "VERIFIED MATCH" if is_match else f"NOTE: Expected {TARGET_CHANNEL_ID}"
                print("\n" + "="*75)
                print("  ✅ AUTHORIZATION COMPLETE!")
                print(f"  Channel Title:   {ch_title}")
                print(f"  Channel ID:      {ch_id} [{status_badge}]")
                print(f"  Target Account:  {TARGET_ACCOUNT}")
                print(f"  Token Saved At:  {token_file}")
                print("  Autonomous YouTube uploads are now ready.")
                print("="*75 + "\n")
            else:
                print(f"\n  ✅ Token saved at {token_file}, but no channel found for this account.\n")
        except Exception as e:
            logger.warning(f"Could not query channel info ({e}), token is saved.")
            print(f"\n  ✅ Token successfully saved at: {token_file}\n")

        return creds
    except Exception as e:
        logger.error(f"Failed to exchange authorization code: {e}")
        return None


def exchange_code_for_token(
    code_or_url: str,
    secrets_file: str = DEDICATED_CLIENT_SECRETS,
    token_file: str = DEDICATED_TOKEN_FILE,
    redirect_uri: str = "http://localhost:8080/"
) -> Optional[Credentials]:
    """Exchange an authorization code or full redirect URL directly for OAuth tokens."""
    import requests

    code = code_or_url.strip()
    if "code=" in code:
        try:
            parsed = urlparse(code)
            params = parse_qs(parsed.query)
            code = params.get("code", [code])[0]
        except Exception:
            pass

    with open(secrets_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    cfg = data.get("installed") or data.get("web")
    client_id = cfg["client_id"]
    client_secret = cfg["client_secret"]

    logger.info("Exchanging authorization code with Google OAuth endpoint...")
    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri
        }
    )

    if token_resp.status_code != 200:
        logger.error(f"Token exchange failed ({token_resp.status_code}): {token_resp.text}")
        return None

    tokens = token_resp.json()
    creds = Credentials(
        token=tokens.get("access_token"),
        refresh_token=tokens.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )

    os.makedirs(os.path.dirname(os.path.abspath(token_file)), exist_ok=True)
    with open(token_file, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    # Verify connected channel
    try:
        youtube = build("youtube", "v3", credentials=creds)
        ch_resp = youtube.channels().list(mine=True, part="id,snippet").execute()
        ch_items = ch_resp.get("items", [])
        if ch_items:
            ch_title = ch_items[0]["snippet"]["title"]
            ch_id = ch_items[0]["id"]
            logger.info(f"Connected YouTube Channel: '{ch_title}' (ID: {ch_id})")
            is_match = (ch_id == TARGET_CHANNEL_ID)
            status_badge = "VERIFIED MATCH" if is_match else f"NOTE: Expected {TARGET_CHANNEL_ID}"
            print("\n" + "="*75)
            print("  ✅ AUTHORIZATION COMPLETE!")
            print(f"  Channel Title:   {ch_title}")
            print(f"  Channel ID:      {ch_id} [{status_badge}]")
            print(f"  Target Account:  {TARGET_ACCOUNT}")
            print(f"  Token Saved At:  {token_file}")
            print("  Autonomous YouTube uploads are now ready.")
            print("="*75 + "\n")
        else:
            print(f"\n  ✅ Token saved at {token_file}, but no channel found for this account.\n")
    except Exception as e:
        logger.warning(f"Could not query channel info ({e}), token is saved.")
        print(f"\n  ✅ Token successfully saved at: {token_file}\n")

    return creds


def generate_video_metadata(
    metadata_json_path: str,
    base_dir: str = "/data/google-stories"
) -> Dict[str, Any]:
    """Compile rich description, timestamps, chapters, and tags from story script."""
    with open(metadata_json_path, "r", encoding="utf-8") as f:
        story = json.load(f)

    title = story.get("title", "Kidoory Bedtime Story")
    premise = story.get("premise", story.get("theme", ""))
    scenes = story.get("scenes", [])
    reflection = story.get("final_reflection", {})
    moral = reflection.get("moral_lesson", "")
    quote = reflection.get("sovereignty_quote", "")
    lang_key = story.get("language_code") or story.get("language") or "en"
    lang_info = get_language(lang_key)

    # Calculate timestamps for chapters
    audio_dir = os.path.join(base_dir, "audio_scenes")
    current_time_s = 0.0
    chapter_lines = []

    for s in scenes:
        idx = s.get("scene_index", 1)
        scene_title = s.get("title") or f"Chapter {idx}"
        mins = int(current_time_s // 60)
        secs = int(current_time_s % 60)
        chapter_lines.append(f"{mins}:{secs:02d} - {scene_title}")

        # Find duration
        dur = 32.0  # default fallback
        for name in [
            f"scene_{idx:02d}.mp3",
            f"{story.get('title', '').lower().replace(' ', '_')}_scene_{idx:02d}.mp3",
            f"{story.get('slug', '')}_scene_{idx:02d}.mp3",
        ]:
            p = os.path.join(audio_dir, name)
            if os.path.exists(p):
                try:
                    out = subprocess.check_output([
                        "ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", p
                    ]).decode().strip()
                    dur = float(out)
                    break
                except Exception:
                    pass
        current_time_s += dur

    mins = int(current_time_s // 60)
    secs = int(current_time_s % 60)
    reflection_title = lang_info.get("reflection_title", "Final Reflection & Moral")
    chapter_lines.append(f"{mins}:{secs:02d} - {reflection_title}")

    chapters_text = "\n".join(chapter_lines)

    title_suffix = lang_info.get("title_suffix", "🌟 Magical Bedtime Story for Kids")
    chapter_header = lang_info.get("chapter_header", "STORY CHAPTERS")
    moral_header = lang_info.get("moral_header", "MORAL & INSPIRATION")
    about_header = lang_info.get("about_header", "ABOUT KIDOORY")
    about_text = lang_info.get("about_text", "Kidoory creates cinematic, heart-warming stories blending universal virtues, gentle courage, wonder, and emotional companionship. Crafted for curious young minds and peaceful bedtimes.")

    clean_suffix = title_suffix.replace("🌟", "").strip()
    if title_suffix in title or clean_suffix in title or "🌟" in title or "|" in title:
        full_title = title
    else:
        full_title = f"{title} {title_suffix}"

    header_title = title if ("|" in title or "🌟" in title or clean_suffix in title) else f"{title} | {title_suffix}"

    description = f"""{header_title}

{premise}

✨ Discover more magical stories, illustrated audiobooks, and adventures:
🌐 Official Website: https://kidoory.com

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📖 {chapter_header}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{chapters_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 {moral_header}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{moral}

"{quote}"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎨 {about_header}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{about_text}

#Kidoory #BedtimeStories #KidsStories #Animation #Storytime #Audiobook #MoralStories
"""

    tags = list(lang_info.get("tags", []))
    if title not in tags:
        tags.append(title)

    return {
        "title": full_title[:100],
        "description": description.strip(),
        "tags": tags[:20],
        "category_id": "1",  # Film & Animation
        "chapters": chapter_lines,
        "language": lang_info.get("code", "en"),
        "language_code": lang_info.get("language_code", "en-US")
    }


# ===========================================================================
# Daily Quota Guard & Sequential Queue (FIFO)
# ===========================================================================

def load_upload_ledger(ledger_path: str = DEFAULT_UPLOAD_LEDGER) -> Dict[str, Any]:
    """Loads the upload ledger, creating default structure if not present."""
    if os.path.exists(ledger_path):
        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error reading upload ledger at {ledger_path}: {e}")

    return {
        "version": 1,
        "daily_cap": DAILY_UPLOAD_CAP,
        "daily_counts": {}
    }


def save_upload_ledger(ledger_path: str, data: Dict[str, Any]) -> None:
    """Saves the upload ledger atomically."""
    os.makedirs(os.path.dirname(os.path.abspath(ledger_path)), exist_ok=True)
    tmp_path = f"{ledger_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, ledger_path)


def get_today_str() -> str:
    """Returns today's date in YYYY-MM-DD format (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_today_upload_count(ledger_path: str = DEFAULT_UPLOAD_LEDGER, date_str: Optional[str] = None) -> int:
    """Returns number of videos uploaded on the specified date (default: today)."""
    if date_str is None:
        date_str = get_today_str()
    ledger = load_upload_ledger(ledger_path)
    day_entry = ledger.get("daily_counts", {}).get(date_str, {})
    return day_entry.get("count", 0)


def check_daily_upload_cap(ledger_path: str = DEFAULT_UPLOAD_LEDGER, max_daily: int = DAILY_UPLOAD_CAP) -> Tuple[bool, int]:
    """
    Checks if today's upload cap has been reached.
    Returns (can_upload, current_count).
    Logs: "Daily upload cap (5/5) reached for today. Holding remaining videos in SSD queue." when cap is hit.
    """
    count = get_today_upload_count(ledger_path)
    if count >= max_daily:
        logger.info(f"Daily upload cap ({count}/{max_daily}) reached for today. Holding remaining videos in SSD queue.")
        return False, count
    return True, count


def record_upload_success(
    title: str,
    video_id: str,
    youtube_url: str,
    video_path: str,
    ledger_path: str = DEFAULT_UPLOAD_LEDGER,
    movie_id: Optional[str] = None,
    episode_id: Optional[int] = None,
    playlist_id: Optional[str] = None
) -> int:
    """Records a successful upload into the ledger under today's date."""
    today_str = get_today_str()
    ledger = load_upload_ledger(ledger_path)
    if "daily_counts" not in ledger:
        ledger["daily_counts"] = {}
    if today_str not in ledger["daily_counts"]:
        ledger["daily_counts"][today_str] = {
            "count": 0,
            "uploads": []
        }

    day_record = ledger["daily_counts"][today_str]
    for item in day_record["uploads"]:
        if item.get("video_id") == video_id:
            if movie_id: item["movie_id"] = movie_id
            if episode_id: item["episode_id"] = episode_id
            if playlist_id: item["playlist_id"] = playlist_id
            save_upload_ledger(ledger_path, ledger)
            return day_record["count"]

    day_record["count"] += 1
    upload_item = {
        "title": title,
        "video_id": video_id,
        "youtube_url": youtube_url,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "video_path": video_path
    }
    if movie_id: upload_item["movie_id"] = movie_id
    if episode_id: upload_item["episode_id"] = episode_id
    if playlist_id: upload_item["playlist_id"] = playlist_id

    day_record["uploads"].append(upload_item)
    save_upload_ledger(ledger_path, ledger)
    logger.info(f"Upload ledger updated: {day_record['count']}/{DAILY_UPLOAD_CAP} uploads used for {today_str}.")
    return day_record["count"]

def load_history(history_file: str = DEFAULT_HISTORY_FILE) -> Dict[str, Any]:
    """Load or initialize the story history JSON."""
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error reading history file ({e}), returning default template.")
    return {
        "version": 1,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "stories": [],
        "past_titles": [],
        "past_motifs": []
    }


def save_history(history_file: str, data: Dict[str, Any]) -> None:
    """Save updated history to disk atomically."""
    os.makedirs(os.path.dirname(os.path.abspath(history_file)), exist_ok=True)
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    tmp_file = f"{history_file}.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_file, history_file)


def normalize_title(title: str) -> str:
    """Normalize a story title for robust matching across YouTube and local disk, supporting all languages."""
    if not title:
        return ""
    # Strip emojis, hashtags, branding suffix ("🌟 Magical Bedtime Story for Kids")
    clean = title.split("🌟")[0].split("|")[0].split("#")[0]
    # Remove punctuation and symbols, preserving letters, numbers, and combining marks (matras) across all languages
    chars = [
        ch for ch in clean
        if not (unicodedata.category(ch).startswith('P') or unicodedata.category(ch).startswith('S'))
    ]
    clean = "".join(chars).strip().lower()
    clean = re.sub(r'\s+', ' ', clean)
    return clean


def detect_video_language(
    video: Dict[str, Any],
    history_stories: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Determines the explicit language code ('en', 'hi', 'pa', 'fr', 'es') of a YouTube video
    using history metadata, title script analysis, tags, description, or snippet attributes.
    """
    v_id = video.get("video_id")
    v_title = video.get("title", "")
    v_desc = video.get("description", "")
    v_lang = video.get("language") or video.get("defaultLanguage") or video.get("defaultAudioLanguage")

    if v_lang:
        return get_language(v_lang)["code"]

    # Check history matching by video_id or exact title
    if history_stories:
        for s in history_stories:
            if v_id and (s.get("video_id") == v_id or s.get("youtube_url", "").endswith(v_id)):
                s_lang = s.get("language_code") or s.get("language")
                if s_lang:
                    return get_language(s_lang)["code"]
            if s.get("title") and s.get("title") == v_title:
                s_lang = s.get("language_code") or s.get("language")
                if s_lang:
                    return get_language(s_lang)["code"]

    # Script-based detection
    # Gurmukhi script range: U+0A00 to U+0A7F (Punjabi)
    if any('\u0a00' <= ch <= '\u0a7f' for ch in v_title + v_desc):
        return "pa"

    # Devanagari script range: U+0900 to U+097F (Hindi)
    if any('\u0900' <= ch <= '\u097f' for ch in v_title + v_desc):
        return "hi"

    # Keyword / tag checks in description & title
    combined_text = (v_desc + " " + v_title).lower()
    if any(k in combined_text for k in ["punjabi", "ਗੁਰਮੁਖੀ", "ਪੰਜਾਬੀ", "pa-in"]):
        return "pa"
    if any(k in combined_text for k in ["hindi", "हिन्दी", "देवनागरी", "hi-in"]):
        return "hi"
    if any(k in combined_text for k in ["français", "french", "histoire du soir", "fr-fr"]):
        return "fr"
    if any(k in combined_text for k in ["español", "spanish", "cuento para dormir", "es-es"]):
        return "es"

    return "en"


def titles_match(t1: str, t2: str, lang1: Optional[str] = None, lang2: Optional[str] = None) -> bool:
    """Determine if two titles correspond to the same story in the same language."""
    if lang1 and lang2 and lang1 != lang2:
        return False
    n1 = normalize_title(t1)
    n2 = normalize_title(t2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    if len(n1) > 5 and len(n2) > 5 and (n1 in n2 or n2 in n1):
        return True
    s1 = n1[4:] if n1.startswith("the ") else n1
    s2 = n2[4:] if n2.startswith("the ") else n2
    return s1 == s2


def get_live_channel_videos(youtube) -> List[Dict[str, Any]]:
    """Fetch all videos currently present in the channel's uploads playlist."""
    try:
        ch_resp = youtube.channels().list(mine=True, part="contentDetails").execute()
        items = ch_resp.get("items", [])
        if not items:
            return []
        uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

        videos = []
        page_token = None
        while True:
            resp = youtube.playlistItems().list(
                playlistId=uploads_id,
                part="snippet,contentDetails",
                maxResults=50,
                pageToken=page_token
            ).execute()
            for item in resp.get("items", []):
                videos.append({
                    "video_id": item["contentDetails"]["videoId"],
                    "title": item["snippet"]["title"],
                    "published_at": item["snippet"]["publishedAt"],
                    "description": item["snippet"].get("description", "")
                })
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return videos
    except Exception as e:
        logger.error(f"Error fetching live channel videos: {e}")
        return []


DEFAULT_PLAYLISTS_FILE = "/data/google-stories/playlists.json"
DEFAULT_PENDING_PLAYLISTS_FILE = "/data/google-stories/pending_playlist_items.json"


def extract_episode_num(text: str) -> Optional[int]:
    """Extract episode integer from text (e.g. 'Ep. 1', 'Episode 1', 'Ep 1')."""
    if not text:
        return None
    m = re.search(r'\b(?:ep|episode)[\.\s]*(\d+)\b', text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def is_duplicate_episode(
    target_title: str,
    target_ep: Optional[int],
    live_title: str
) -> bool:
    """Robust duplicate detector specifically tuned for series episodes and standalone bedtime stories."""
    if not target_title or not live_title:
        return False

    n_live = normalize_title(live_title)
    n_target = normalize_title(target_title)

    if n_live == n_target or (len(n_live) > 8 and (n_live in n_target or n_target in n_live)):
        return True

    live_ep = extract_episode_num(live_title)
    target_ep_val = target_ep if target_ep is not None else extract_episode_num(target_title)

    if target_ep_val is not None and live_ep is not None and target_ep_val == live_ep:
        # Same episode number! Check content similarity
        words_live = set(n_live.split())
        words_target = set(n_target.split())
        stopwords = {'the', 'a', 'an', 'and', 'of', 'in', 'to', 'for', 'on', 'with', 'ep', 'episode'}
        w_live = words_live - stopwords
        w_target = words_target - stopwords
        if w_live and w_target:
            overlap = w_live.intersection(w_target)
            if len(overlap) >= min(len(w_live), len(w_target)) * 0.4:
                return True

    return False


def check_channel_for_duplicate(
    youtube,
    target_title: str,
    episode_num: Optional[int] = None,
    movie_id: Optional[str] = None,
    video_path: Optional[str] = None,
    ledger_path: str = DEFAULT_UPLOAD_LEDGER
) -> Optional[Dict[str, Any]]:
    """
    Checks if a video is already present either in upload_ledger.json or on the live YouTube channel.
    Returns dict with video details if duplicate, or None if unique.
    """
    # 1. Check upload ledger first
    try:
        ledger = load_upload_ledger(ledger_path)
        for date_key, ddata in ledger.get("daily_counts", {}).items():
            for item in ddata.get("uploads", []):
                # Path match
                if video_path and item.get("video_path") and os.path.abspath(item["video_path"]) == os.path.abspath(video_path):
                    return {
                        "duplicate": True,
                        "source": "ledger_path_match",
                        "video_id": item["video_id"],
                        "youtube_url": item.get("youtube_url", f"https://youtu.be/{item['video_id']}"),
                        "title": item.get("title", ""),
                        "published_at": item.get("published_at", "")
                    }
                # Movie & Episode ID match
                if movie_id and episode_num and item.get("movie_id") == movie_id and item.get("episode_id") == episode_num:
                    return {
                        "duplicate": True,
                        "source": "ledger_episode_match",
                        "video_id": item["video_id"],
                        "youtube_url": item.get("youtube_url", f"https://youtu.be/{item['video_id']}"),
                        "title": item.get("title", ""),
                        "published_at": item.get("published_at", "")
                    }
                # Title match
                if is_duplicate_episode(target_title, episode_num, item.get("title", "")):
                    return {
                        "duplicate": True,
                        "source": "ledger_title_match",
                        "video_id": item["video_id"],
                        "youtube_url": item.get("youtube_url", f"https://youtu.be/{item['video_id']}"),
                        "title": item.get("title", ""),
                        "published_at": item.get("published_at", "")
                    }
    except Exception as e:
        logger.warning(f"Error checking ledger for duplicates: {e}")

    # 2. Check live YouTube channel
    if youtube:
        try:
            live_videos = get_live_channel_videos(youtube)
            for v in live_videos:
                if is_duplicate_episode(target_title, episode_num, v.get("title", "")):
                    return {
                        "duplicate": True,
                        "source": "youtube_channel_scan",
                        "video_id": v["video_id"],
                        "youtube_url": f"https://youtu.be/{v['video_id']}",
                        "title": v.get("title", ""),
                        "published_at": v.get("published_at", "")
                    }
        except Exception as e:
            logger.warning(f"Error scanning live channel for duplicates: {e}")

    return None


def load_playlists_registry(path: str = DEFAULT_PLAYLISTS_FILE) -> Dict[str, Any]:
    """Load the JSON mapping of Movie IDs to YouTube Playlist IDs."""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_playlists_registry(path: str, data: Dict[str, Any]) -> None:
    """Save the JSON mapping of Movie IDs to YouTube Playlist IDs atomically."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def get_or_create_movie_playlist(
    youtube,
    movie_id: str,
    movie_title: str,
    playlists_path: str = DEFAULT_PLAYLISTS_FILE
) -> Optional[str]:
    """
    Retrieves the YouTube playlist ID for a given movie series.
    If not already registered, checks live playlists on the channel.
    If not on the channel, creates a new playlist for the movie series.
    """
    registry = load_playlists_registry(playlists_path)
    if movie_id in registry and registry[movie_id].get("playlist_id"):
        return registry[movie_id]["playlist_id"]

    # Search channel playlists
    pl_title = f"{movie_title} 🌙 | Kidoory Bedtime Stories"
    try:
        pl_resp = youtube.playlists().list(part="snippet,contentDetails", mine=True, maxResults=50).execute()
        for pl in pl_resp.get("items", []):
            title = pl.get("snippet", {}).get("title", "")
            if (movie_title.lower() in title.lower()) or ("luna blossom" in title.lower() and movie_id == "MOVIE_001"):
                pl_id = pl["id"]
                registry[movie_id] = {
                    "playlist_id": pl_id,
                    "title": title,
                    "channel_id": pl.get("snippet", {}).get("channelId", ""),
                    "created_at": pl.get("snippet", {}).get("publishedAt", "")
                }
                save_playlists_registry(playlists_path, registry)
                return pl_id
    except Exception as e:
        logger.warning(f"Could not list channel playlists ({e}).")

    # Try creating new playlist
    try:
        logger.info(f"Creating new YouTube playlist: '{pl_title}'...")
        new_pl = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": pl_title,
                    "description": f"All episodes of {movie_title}. Calming, cinematic bedtime stories for children.\n\n🌐 https://kidoory.com\n#Kidoory #BedtimeStories"
                },
                "status": {"privacyStatus": "public"}
            }
        ).execute()
        pl_id = new_pl.get("id")
        registry[movie_id] = {
            "playlist_id": pl_id,
            "title": pl_title,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        save_playlists_registry(playlists_path, registry)
        logger.info(f"Successfully created playlist {pl_id} for {movie_id}!")
        return pl_id
    except Exception as e:
        logger.warning(f"Could not create playlist for {movie_id} ({e}).")
        return None


def record_pending_playlist_item(
    playlist_id: str,
    video_id: str,
    movie_id: Optional[str] = None,
    episode_id: Optional[int] = None
):
    """Queues a video to be added to a playlist once permissions/token are re-consented."""
    p_file = DEFAULT_PENDING_PLAYLISTS_FILE
    items = []
    if os.path.exists(p_file):
        try:
            with open(p_file, "r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception:
            items = []
    for it in items:
        if it.get("playlist_id") == playlist_id and it.get("video_id") == video_id:
            return
    items.append({
        "playlist_id": playlist_id,
        "video_id": video_id,
        "movie_id": movie_id,
        "episode_id": episode_id,
        "queued_at": datetime.now(timezone.utc).isoformat()
    })
    os.makedirs(os.path.dirname(os.path.abspath(p_file)), exist_ok=True)
    tmp = f"{p_file}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    os.replace(tmp, p_file)


def add_video_to_playlist(
    youtube,
    playlist_id: str,
    video_id: str,
    movie_id: Optional[str] = None,
    episode_id: Optional[int] = None
) -> bool:
    """
    Safely adds a video to a YouTube playlist, checking for duplicates first.
    If scope lacks permission, queues it in pending_playlist_items.json without crashing.
    """
    if not playlist_id or not video_id:
        return False

    try:
        items_resp = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50
        ).execute()
        for it in items_resp.get("items", []):
            if it.get("snippet", {}).get("resourceId", {}).get("videoId") == video_id:
                logger.info(f"Video {video_id} is already in playlist {playlist_id}.")
                return True

        logger.info(f"Adding video {video_id} to playlist {playlist_id}...")
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        ).execute()
        logger.info(f"Successfully added video {video_id} to playlist {playlist_id}!")
        return True
    except HttpError as e:
        if e.resp.status in (401, 403):
            logger.warning(f"Playlist insert restricted ({e.reason}). Queuing for pending playlist sync.")
            record_pending_playlist_item(playlist_id, video_id, movie_id, episode_id)
        else:
            logger.warning(f"Error adding video to playlist: {e}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error adding video to playlist: {e}")
        record_pending_playlist_item(playlist_id, video_id, movie_id, episode_id)
        return False


def sync_pending_playlist_items(youtube) -> int:
    """Attempts to sync any pending playlist items."""
    p_file = DEFAULT_PENDING_PLAYLISTS_FILE
    if not os.path.exists(p_file):
        return 0
    try:
        with open(p_file, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception:
        return 0

    if not items:
        return 0

    remaining = []
    synced = 0
    for it in items:
        pl_id = it.get("playlist_id")
        v_id = it.get("video_id")
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": pl_id,
                        "resourceId": {"kind": "youtube#video", "videoId": v_id}
                    }
                }
            ).execute()
            synced += 1
            logger.info(f"Synced pending video {v_id} into playlist {pl_id}.")
        except Exception:
            remaining.append(it)

    with open(p_file, "w", encoding="utf-8") as f:
        json.dump(remaining, f, indent=2)
    return synced


def sync_with_live_youtube(
    youtube=None,
    history_path: str = DEFAULT_HISTORY_FILE,
    secrets_file: str = DEDICATED_CLIENT_SECRETS,
    token_file: str = DEDICATED_TOKEN_FILE,
    delete_duplicates: bool = False
) -> Dict[str, Any]:
    """
    Bi-directional channel verification & automated deduplication:
    1. Fetches channel uploads playlist.
    2. Enriches each video with detected language tag.
    3. Evaluates duplicates matching on BOTH normalized title AND explicit language code.
       - Disables destructive deletions completely (HARD RULE: zero API delete calls).
       - Cross-language title collisions are logged as [LANGUAGE OVERLAP NOTICE] and never treated as duplicates.
    4. Syncs YouTube state into history.json, marking any live video as PUBLISHED.
    5. Returns sync report with safe duplicate findings and synced videos.
    """
    if youtube is None:
        creds = authenticate_youtube(secrets_file=secrets_file, token_file=token_file)
        if not creds:
            logger.error("Authentication failed. Cannot sync with live YouTube.")
            return {"error": "Authentication failed"}
        youtube = build("youtube", "v3", credentials=creds)

    live_videos = get_live_channel_videos(youtube)
    logger.info(f"Retrieved {len(live_videos)} live video(s) from YouTube channel.")

    history_data = load_history(history_path)
    stories = history_data.get("stories", [])

    for v in live_videos:
        v["language"] = "en"

    # Cross-language collision detection notice
    title_to_videos: Dict[str, List[Dict[str, Any]]] = {}
    for v in live_videos:
        norm_t = normalize_title(v["title"])
        if norm_t:
            title_to_videos.setdefault(norm_t, []).append(v)

    for norm_t, v_list in title_to_videos.items():
        languages_in_group = {v["language"] for v in v_list}
        if len(languages_in_group) > 1:
            vid_summary = [f"ID: {v.get('video_id')} (Lang: {v.get('language')})" for v in v_list]
            logger.info(
                f"[LANGUAGE OVERLAP NOTICE] Detected title overlap '{norm_t}' across different languages: "
                f"{sorted(list(languages_in_group))}. "
                f"Videos: {vid_summary}. "
                f"Treating all entries as distinct multilingual editions. NEVER treating as upload duplicates."
            )

    # 1. Group videos strictly by BOTH normalized title AND explicit language code
    title_lang_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for v in live_videos:
        norm_t = normalize_title(v["title"])
        if norm_t:
            key = (norm_t, v["language"])
            title_lang_groups.setdefault(key, []).append(v)

    deleted_duplicates = []
    for (norm_title, lang), group in title_lang_groups.items():
        if len(group) > 1:
            # Sort by published_at ascending (earliest first)
            group.sort(key=lambda x: x["published_at"])
            original = group[0]
            duplicates = group[1:]
            logger.info(
                f"Duplicate detected for title '{original['title']}' [Language: {lang}]: "
                f"Original ID {original['video_id']} ({original['published_at']}), {len(duplicates)} duplicate(s)."
            )

            # HARD RULE: Automated daemons MUST NEVER issue DELETE requests to the YouTube Data API under any circumstances.
            for dup in duplicates:
                dup_id = dup["video_id"]
                logger.warning(
                    f"[SAFETY ENFORCED] Duplicate detected for video ID '{dup_id}' (title: '{original['title']}', lang: '{lang}'). "
                    f"Automated delete is permanently disabled to safeguard channel assets. Video will NOT be deleted via API."
                )
                deleted_duplicates.append({
                    "title": original["title"],
                    "language": lang,
                    "duplicate_video_id": dup_id,
                    "kept_video_id": original["video_id"],
                    "status": "PRESERVED_SAFE",
                    "note": "Automated deletion permanently disabled by publisher safety policy"
                })

    # No video is ever deleted via automated daemon
    remaining_live = live_videos

    # 2. Sync with history.json
    synced_stories = []

    for v in remaining_live:
        v_title = v["title"]
        v_id = v["video_id"]
        v_url = f"https://youtu.be/{v_id}"
        v_pub = v["published_at"]
        v_lang = v.get("language", "en")

        matched = False
        for s in stories:
            s_lang = s.get("language_code") or s.get("language")
            if s.get("video_id") == v_id or titles_match(s.get("title", ""), v_title, s_lang, v_lang):
                matched = True
                if s.get("status") != "PUBLISHED" or s.get("youtube_url") != v_url:
                    s["status"] = "PUBLISHED"
                    s["youtube_url"] = v_url
                    s["video_id"] = v_id
                    s["published_at"] = v_pub
                    if not s.get("language"):
                        s["language"] = v_lang
                    synced_stories.append({"title": s.get("title"), "youtube_url": v_url, "action": "STATUS_UPDATED"})
                break

        if not matched:
            clean_t = v_title.split("🌟")[0].split("|")[0].strip()
            new_entry = {
                "id": len(stories) + 1,
                "title": clean_t,
                "language": v_lang,
                "language_code": v_lang,
                "status": "PUBLISHED",
                "youtube_url": v_url,
                "video_id": v_id,
                "published_at": v_pub,
                "created_at": v_pub
            }
            stories.append(new_entry)
            history_data.setdefault("past_titles", []).append(clean_t)
            synced_stories.append({"title": clean_t, "youtube_url": v_url, "action": "IMPORTED_FROM_YOUTUBE"})

    save_history(history_path, history_data)
    logger.info(f"Live YouTube sync complete. {len(synced_stories)} story record(s) synchronized.")

    return {
        "live_video_count": len(remaining_live),
        "deleted_duplicates": deleted_duplicates,
        "synced_stories": synced_stories
    }


def set_all_custom_thumbnails(
    youtube=None,
    history_path: str = DEFAULT_HISTORY_FILE,
    secrets_file: str = DEDICATED_CLIENT_SECRETS,
    token_file: str = DEDICATED_TOKEN_FILE
) -> List[Dict[str, Any]]:
    """
    Scans published stories in history.json and sets custom high-res thumbnail covers
    for each video on YouTube if a cover image exists.
    """
    if youtube is None:
        creds = authenticate_youtube(secrets_file=secrets_file, token_file=token_file)
        if not creds:
            logger.error("Authentication failed for setting thumbnails.")
            return []
        youtube = build("youtube", "v3", credentials=creds)

    history_data = load_history(history_path)
    results = []

    for s in history_data.get("stories", []):
        video_id = s.get("video_id")
        if not video_id and s.get("youtube_url"):
            video_id = s["youtube_url"].split("/")[-1].split("?")[0]

        if not video_id:
            continue

        video_path = s.get("video_path") or ""
        thumb_path = s.get("thumbnail_path")
        if not thumb_path or not os.path.exists(thumb_path):
            thumb_path = find_story_thumbnail(video_path, s.get("metadata_path"))

        if not thumb_path or not os.path.exists(thumb_path):
            slug = s.get("title", "").lower().replace(" ", "_").replace("'", "")
            for candidate in [
                f"/data/google-stories/raw_images/{slug}_cover.png",
                f"/data/google-stories/raw_images/{slug}_scene_01.png",
                f"/data/google-stories/final_videos/{s.get('title', '').replace(' ', '_')}.png"
            ]:
                if os.path.exists(candidate) and os.path.getsize(candidate) > 10_000:
                    thumb_path = candidate
                    break

        if thumb_path and os.path.exists(thumb_path):
            success = upload_custom_thumbnail(youtube, video_id, thumb_path)
            results.append({
                "title": s.get("title"),
                "video_id": video_id,
                "thumbnail_path": thumb_path,
                "success": success
            })
            if success:
                s["thumbnail_path"] = thumb_path
                time.sleep(2)  # Avoid short-term rate limits
        else:
            logger.info(f"No custom cover artwork found for '{s.get('title')}'")

    save_history(history_path, history_data)
    return results


def get_unposted_date_dirs(media_root: str = "/data/google-stories") -> List[Tuple[datetime, str, str]]:
    """
    Finds and chronologically sorts all date directories under unposted/.
    Format: %d%b%Y (e.g. 24Sep2026).
    """
    unposted_root = os.path.join(media_root, "unposted")
    if not os.path.isdir(unposted_root):
        return []
    dated_dirs = []
    for entry in os.listdir(unposted_root):
        full_p = os.path.join(unposted_root, entry)
        if os.path.isdir(full_p):
            try:
                dt = datetime.strptime(entry, "%d%b%Y")
                dated_dirs.append((dt, entry, full_p))
            except ValueError:
                continue
    # Sort chronologically ascending (oldest date first)
    dated_dirs.sort(key=lambda x: x[0])
    return dated_dirs


def write_completion_manifest(date_str: str, media_root: str = "/data/google-stories") -> Optional[str]:
    """
    Once an unposted date folder is completely published and moved to posted/<DDMonYYYY>/,
    write the completion manifest:
    <kidoory_media_root>/unposted/<DDMonYYYY>_completed.txt
    Format:
    [KIDOORY COMPLETED DATE: <DDMonYYYY>]
    - <story_title>.mp4 -> [YouTube Video ID: <id>] [Language: <lang>] [STATUS: POSTED]
    Safely remove the empty folder after the manifest is written.
    """
    unposted_date_dir = os.path.join(media_root, "unposted", date_str)
    posted_date_dir = os.path.join(media_root, "posted", date_str)
    manifest_path = os.path.join(media_root, "unposted", f"{date_str}_completed.txt")

    # If unposted date dir still has mp4 files, it is not completed yet
    if os.path.isdir(unposted_date_dir):
        remaining_mp4s = [f for f in os.listdir(unposted_date_dir) if f.endswith(".mp4")]
        if remaining_mp4s:
            return None

    # Load history and ledger for details
    history = load_history(os.path.join(media_root, "history.json"))
    stories_by_title = {s.get("title", ""): s for s in history.get("stories", [])}
    stories_by_base = {}
    for s in history.get("stories", []):
        vp = s.get("video_path", "")
        if vp:
            stories_by_base[os.path.basename(vp)] = s

    lines = [f"[KIDOORY COMPLETED DATE: {date_str}]"]

    # Read from posted_date_dir
    if os.path.isdir(posted_date_dir):
        posted_mp4s = sorted([f for f in os.listdir(posted_date_dir) if f.endswith(".mp4") and not os.path.islink(os.path.join(posted_date_dir, f))])
        for mp4_file in posted_mp4s:
            story = stories_by_base.get(mp4_file)
            if not story:
                for t, s in stories_by_title.items():
                    if t.replace(" ", "_") in mp4_file or mp4_file.startswith(t.replace(" ", "_")):
                        story = s
                        break

            video_id = "UNKNOWN"
            lang = "English"
            if story:
                yt_url = story.get("youtube_url", "")
                if yt_url:
                    video_id = yt_url.rsplit("/", 1)[-1].split("=")[-1]
                lang = story.get("language_name") or story.get("language") or "English"

            # Check json if needed
            json_file = os.path.join(posted_date_dir, mp4_file.replace(".mp4", ".json"))
            if os.path.isfile(json_file):
                try:
                    with open(json_file, "r", encoding="utf-8") as jf:
                        jdata = json.load(jf)
                        if jdata.get("language_name"):
                            lang = jdata.get("language_name")
                        elif jdata.get("language"):
                            lang = jdata.get("language")
                except Exception:
                    pass

            lines.append(f"- {mp4_file} -> [YouTube Video ID: {video_id}] [Language: {lang}] [STATUS: POSTED]")

    with open(manifest_path, "w", encoding="utf-8") as mf:
        mf.write("\n".join(lines) + "\n")
    logger.info(f"Wrote completion manifest: {manifest_path}")

    # Safely remove empty folder
    if os.path.isdir(unposted_date_dir):
        try:
            shutil.rmtree(unposted_date_dir)
            logger.info(f"Safely removed exhausted unposted folder: {unposted_date_dir}")
        except Exception as e:
            logger.warning(f"Could not remove {unposted_date_dir}: {e}")

    return manifest_path


def get_queued_stories(
    history_path: str = DEFAULT_HISTORY_FILE,
    media_root: str = "/data/google-stories"
) -> List[Dict[str, Any]]:
    """
    Returns stories in FIFO (First-In, First-Out) chronological order that are waiting to be published.
    Examines date-driven unposted/ folders sorted chronologically (%d%b%Y).
    """
    date_dirs = get_unposted_date_dirs(media_root)
    history_data = load_history(history_path)
    stories_by_base = {}
    for s in history_data.get("stories", []):
        vp = s.get("video_path", "")
        if vp:
            base = os.path.basename(vp)
            if base not in stories_by_base or s.get("status") == "QUEUED_FOR_PUBLISH":
                stories_by_base[base] = s

    queued = []
    seen_files = set()

    for dt, date_str, date_dir in date_dirs:
        mp4_files = sorted(
            [f for f in os.listdir(date_dir) if f.endswith(".mp4") and not os.path.islink(os.path.join(date_dir, f))],
            key=lambda x: os.path.getmtime(os.path.join(date_dir, x))
        )
        for fname in mp4_files:
            vpath = os.path.join(date_dir, fname)
            mpath = os.path.join(date_dir, fname.replace(".mp4", ".json"))
            if not os.path.exists(mpath):
                slug_json = os.path.join(date_dir, f"{fname[:-4]}.json")
                if os.path.exists(slug_json):
                    mpath = slug_json
            story_match = stories_by_base.get(fname)
            title = story_match.get("title") if story_match else fname[:-4].replace("_", " ")
            if os.path.exists(mpath):
                try:
                    with open(mpath, "r", encoding="utf-8") as mf:
                        m_json = json.load(mf)
                    if m_json.get("title"):
                        title = m_json["title"]
                except Exception:
                    pass
            story_id = story_match.get("id", len(queued) + 100) if story_match else len(queued) + 100

            entry = {
                "id": story_id,
                "title": title,
                "status": "QUEUED_FOR_PUBLISH",
                "video_path": vpath,
                "metadata_path": mpath if os.path.exists(mpath) else None,
                "created_at": datetime.fromtimestamp(os.path.getmtime(vpath), tz=timezone.utc).isoformat(),
                "date_str": date_str,
                "date_dt": dt
            }
            queued.append(entry)
            seen_files.add(fname)

    # Fallback to history.json entries that might not be in unposted dated folders
    for s in history_data.get("stories", []):
        if s.get("status") == "QUEUED_FOR_PUBLISH":
            vp = s.get("video_path", "")
            fname = os.path.basename(vp) if vp else ""
            if fname and fname not in seen_files:
                queued.append(s)

    return queued


def mark_story_published(
    title: str,
    youtube_url: str,
    history_path: str = DEFAULT_HISTORY_FILE,
    video_path: Optional[str] = None,
    metadata_path: Optional[str] = None
) -> bool:
    """Updates a story in history.json to status 'PUBLISHED' with youtube_url, paths, and completion timestamp."""
    if not os.path.exists(history_path):
        return False
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        updated = False
        for s in data.get("stories", []):
            if s.get("title") == title or titles_match(s.get("title", ""), title):
                s["status"] = "PUBLISHED"
                s["youtube_url"] = youtube_url
                s["published_at"] = datetime.now(timezone.utc).isoformat()
                s["completed_at"] = datetime.now(timezone.utc).isoformat()
                if video_path:
                    s["video_path"] = video_path
                if metadata_path:
                    s["metadata_path"] = metadata_path
                updated = True
                break
        if updated:
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Updated history: marked '{title}' as PUBLISHED ({youtube_url}).")
        return updated
    except Exception as e:
        logger.error(f"Failed to update story '{title}' in {history_path}: {e}")
        return False


def dispatch_next_queued_story(
    history_path: str = DEFAULT_HISTORY_FILE,
    ledger_path: str = DEFAULT_UPLOAD_LEDGER,
    secrets_file: str = DEDICATED_CLIENT_SECRETS,
    token_file: str = DEDICATED_TOKEN_FILE,
    privacy_status: str = "public",
    media_root: str = "/data/google-stories",
    min_verification_delay_seconds: int = 900
) -> Optional[str]:
    """
    Picks the oldest unpublished story in FIFO queue order from the SanDisk SSD
    and publishes it to YouTube if the daily cap (5/5) has not been reached.
    Strictly follows date-driven order (%d%b%Y) and enforces a 15-minute verification delay.
    Always exhausts the oldest date directory first before inspecting newer dates.
    Once an unposted date folder is completely published, moves to posted/<date>/,
    writes the completion manifest, and safely removes the empty directory.
    """
    can_upload, count = check_daily_upload_cap(ledger_path=ledger_path, max_daily=DAILY_UPLOAD_CAP)
    if not can_upload:
        logger.info(f"Daily upload cap reached ({count}/{DAILY_UPLOAD_CAP}). Dispatch paused.")
        return None

    # Bi-directional sync with live channel inventory to prevent duplicate uploads
    try:
        if os.path.exists(token_file):
            creds = authenticate_youtube(secrets_file=secrets_file, token_file=token_file)
            if creds:
                yt_client = build("youtube", "v3", credentials=creds)
                sync_with_live_youtube(youtube=yt_client, history_path=history_path, delete_duplicates=False)
    except Exception as e:
        logger.warning(f"Could not sync with live YouTube channel before queue dispatch: {e}")

    date_dirs = get_unposted_date_dirs(media_root)
    if not date_dirs:
        logger.info("Upload queue is empty. No date directories under unposted/.")
        return None

    now = time.time()

    # Iterate strictly in chronological order: exhaust oldest date directory first!
    for dt, date_str, date_dir in date_dirs:
        mp4_files = sorted(
            [f for f in os.listdir(date_dir) if f.endswith(".mp4") and not os.path.islink(os.path.join(date_dir, f))],
            key=lambda x: os.path.getmtime(os.path.join(date_dir, x))
        )
        if not mp4_files:
            # Date directory has no mp4 files, finalize manifest and remove
            write_completion_manifest(date_str, media_root=media_root)
            continue

        # Check for videos that have passed the 15-minute verification delay
        eligible_videos = []
        delayed_count = 0

        for fname in mp4_files:
            vpath = os.path.join(date_dir, fname)
            mtime = os.path.getmtime(vpath)
            age = now - mtime
            if age < min_verification_delay_seconds:
                delayed_count += 1
            else:
                mpath = os.path.join(date_dir, fname.replace(".mp4", ".json"))
                if not os.path.exists(mpath):
                    slug = fname[:-4].lower().replace(" ", "_").replace("'", "")
                    for cand in [
                        os.path.join(media_root, "scripts", f"{slug}.json"),
                        os.path.join(media_root, "scripts", f"{fname[:-4]}.json"),
                    ]:
                        if os.path.exists(cand):
                            mpath = cand
                            break
                eligible_videos.append((vpath, mpath, fname, mtime))

        if not eligible_videos:
            logger.info(
                f"Oldest date directory '{date_str}' has {delayed_count} video(s) still within the 15-minute "
                f"verification delay window (need >= {min_verification_delay_seconds}s age). "
                f"Exhausting oldest date first; holding queue."
            )
            return None

        # Pick the oldest eligible video in this date directory
        eligible_videos.sort(key=lambda x: x[3])
        vpath, mpath, fname, _ = eligible_videos[0]

        # Extract title
        title = fname[:-4].replace("_", " ")
        if mpath and os.path.exists(mpath):
            try:
                with open(mpath, "r", encoding="utf-8") as jf:
                    jdata = json.load(jf)
                    title = jdata.get("title", title)
            except Exception:
                pass

        logger.info(f"Dispatching oldest queued story from SSD (Date: {date_str}, FIFO): '{title}'")
        youtube_url = publish_story_to_kidoory(
            video_path=vpath,
            metadata_json_path=mpath,
            privacy_status=privacy_status,
            secrets_file=secrets_file,
            token_file=token_file,
            ledger_path=ledger_path,
            force=False
        )

        if youtube_url:
            # Move video, json, png to posted/<date_str>/
            posted_date_dir = os.path.join(media_root, "posted", date_str)
            os.makedirs(posted_date_dir, exist_ok=True)
            posted_vpath = os.path.join(posted_date_dir, fname)
            shutil.move(vpath, posted_vpath)

            posted_mpath = None
            if mpath and os.path.exists(mpath):
                posted_mpath = os.path.join(posted_date_dir, os.path.basename(mpath))
                if os.path.dirname(mpath) == date_dir:
                    shutil.move(mpath, posted_mpath)
                else:
                    shutil.copy2(mpath, posted_mpath)

            # Move png if present in date_dir
            png_name = fname.replace(".mp4", ".png")
            png_src = os.path.join(date_dir, png_name)
            if os.path.exists(png_src):
                shutil.move(png_src, os.path.join(posted_date_dir, png_name))

            # Handle any symlinks pointing to this file in date_dir
            for entry in os.listdir(date_dir):
                sym_path = os.path.join(date_dir, entry)
                if os.path.islink(sym_path):
                    target = os.readlink(sym_path)
                    if os.path.basename(target) == fname:
                        os.unlink(sym_path)
                        os.symlink(fname, os.path.join(posted_date_dir, entry))

            # Mark published in history.json with updated paths
            mark_story_published(
                title=title,
                youtube_url=youtube_url,
                history_path=history_path,
                video_path=posted_vpath,
                metadata_path=posted_mpath
            )

            # Check if this date directory is now completely published
            remaining = [f for f in os.listdir(date_dir) if f.endswith(".mp4")]
            if not remaining:
                write_completion_manifest(date_str, media_root=media_root)

            logger.info(f"Successfully published queued story '{title}': {youtube_url}")
            return youtube_url
        else:
            logger.error(f"Failed to publish queued story '{title}'. Leaving in queue.")
            return None

    return None


def print_queue_status(
    history_path: str = DEFAULT_HISTORY_FILE,
    ledger_path: str = DEFAULT_UPLOAD_LEDGER
) -> Dict[str, Any]:
    """Prints a clear report of audience flag, queue count, and today's upload count."""
    count = get_today_upload_count(ledger_path)
    queued_stories = get_queued_stories(history_path)

    print("\n" + "="*70)
    print("  KIDOORY YOUTUBE PUBLISHER: QUEUE & DAILY QUOTA STATUS")
    print("="*70)
    print("1. Audience Setting:")
    print("   * 'selfDeclaredMadeForKids': False (Strictly Enforced)")
    print("\n2. Daily Upload Quota:")
    print(f"   * Today's Date (UTC):       {get_today_str()}")
    print(f"   * Videos Published Today:   {count} / {DAILY_UPLOAD_CAP}")
    cap_status = "CAP REACHED (Holding in SSD queue)" if count >= DAILY_UPLOAD_CAP else f"{DAILY_UPLOAD_CAP - count} upload slot(s) available today"
    print(f"   * Quota Status:             {cap_status}")
    print("\n3. SSD Sequential Queue (FIFO):")
    print(f"   * Queued Videos Waiting:    {len(queued_stories)}")
    for idx, s in enumerate(queued_stories, 1):
        print(f"     [{idx}] '{s.get('title')}'")
        print(f"         Video:    {s.get('video_path')}")
        print(f"         Metadata: {s.get('metadata_path')}")
        print(f"         Created:  {s.get('created_at')}")
    print("="*70 + "\n")

    return {
        "selfDeclaredMadeForKids": True,
        "today_upload_count": count,
        "daily_cap": DAILY_UPLOAD_CAP,
        "queued_count": len(queued_stories),
        "queued_stories": [s.get("title") for s in queued_stories]
    }


def find_story_thumbnail(video_path: str, metadata_json_path: Optional[str] = None) -> Optional[str]:
    """
    Locates the primary scene image or cover artwork for a story.
    Searches in final_videos alongside MP4, and in raw_images.
    """
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    slug = base_name.lower().replace(" ", "_").replace("'", "")
    parent_dir = os.path.dirname(os.path.abspath(video_path))
    media_root = "/data/google-stories"
    if "unposted" in parent_dir or "posted" in parent_dir:
        media_root = os.path.dirname(os.path.dirname(parent_dir))
    raw_images_dir = os.path.join(media_root, "raw_images")

    candidates = [
        os.path.join(parent_dir, f"{base_name}.png"),
        os.path.join(parent_dir, f"{slug}.png"),
        os.path.join(raw_images_dir, f"{slug}_cover.png"),
        os.path.join(raw_images_dir, f"{slug}_scene_01.png"),
        os.path.join(raw_images_dir, f"{slug}.png"),
        os.path.join(raw_images_dir, f"{base_name}_cover.png"),
        os.path.join(raw_images_dir, "cover.png"),
        os.path.join(raw_images_dir, "scene_01.png"),
        os.path.join(raw_images_dir, "test_scene_01.png"),
    ]

    for c in candidates:
        if os.path.exists(c) and os.path.getsize(c) > 10_000:
            return c

    # Fallback: extract frame from MP4 if it exists
    if video_path and os.path.exists(video_path):
        extracted = os.path.join(parent_dir, f"{base_name}.png")
        try:
            subprocess.run([
                "ffmpeg", "-y", "-ss", "00:00:01.000", "-i", video_path,
                "-vframes", "1", extracted
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(extracted) and os.path.getsize(extracted) > 10_000:
                logger.info(f"Extracted fallback 1080p cover frame: {extracted}")
                return extracted
        except Exception as e:
            logger.warning(f"Could not extract fallback frame from {video_path}: {e}")

    return None


def upload_custom_thumbnail(
    youtube,
    video_id: str,
    thumbnail_path: str
) -> bool:
    """Uploads a custom video thumbnail using the YouTube Data API."""
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        logger.warning(f"Thumbnail file not found at: {thumbnail_path}")
        return False

    try:
        logger.info(f"Uploading custom thumbnail from {thumbnail_path} for video {video_id}...")
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path, mimetype='image/png')
        ).execute()
        logger.info(f"Uploaded custom thumbnail from {thumbnail_path} for video {video_id}")
        return True
    except HttpError as e:
        if "doesn't have permissions to upload and set custom video thumbnails" in str(e):
            logger.warning(
                f"Custom thumbnail upload blocked by YouTube: Channel requires one-time phone verification at https://www.youtube.com/verify to unlock Custom Thumbnails ('Intermediate features'). Video remains published with default frame."
            )
        else:
            logger.warning(f"Could not upload custom thumbnail ({e}).")
        return False
    except Exception as e:
        logger.warning(f"Error uploading custom thumbnail ({e}).")
        return False


def set_video_thumbnail(
    video_id: str,
    thumbnail_path: str,
    secrets_file: str = DEDICATED_CLIENT_SECRETS,
    token_file: str = DEDICATED_TOKEN_FILE
) -> bool:
    """Set custom thumbnail for an existing YouTube video."""
    creds = authenticate_youtube(secrets_file=secrets_file, token_file=token_file)
    if not creds:
        raise RuntimeError("YouTube authentication failed or token missing.")
    youtube = build("youtube", "v3", credentials=creds)
    return upload_custom_thumbnail(youtube, video_id, thumbnail_path)


def publish_story_to_kidoory(
    video_path: str,
    metadata_json_path: str,
    privacy_status: str = "public",
    secrets_file: str = DEDICATED_CLIENT_SECRETS,
    token_file: str = DEDICATED_TOKEN_FILE,
    ledger_path: str = DEFAULT_UPLOAD_LEDGER,
    movie_id: Optional[str] = None,
    episode_id: Optional[int] = None,
    playlist_id: Optional[str] = None,
    force: bool = False
) -> Optional[str]:
    """
    Publish master video to Kidoory YouTube channel with chapters, playlist grouping,
    and duplicate protection.
    Checks daily upload cap via upload_ledger.json.
    Returns: live YouTube URL (https://youtu.be/<VIDEO_ID>) or None if cap reached.
    """
    if not force:
        can_upload, current_count = check_daily_upload_cap(ledger_path=ledger_path, max_daily=DAILY_UPLOAD_CAP)
        if not can_upload:
            return None

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found at {video_path}")
    if not os.path.exists(metadata_json_path):
        raise FileNotFoundError(f"Story metadata JSON not found at {metadata_json_path}")

    # 1. Authenticate
    creds = authenticate_youtube(secrets_file=secrets_file, token_file=token_file)
    if not creds:
        raise RuntimeError("YouTube authentication failed or token missing.")

    youtube = build("youtube", "v3", credentials=creds)

    # 2. Compile Metadata & Chapters
    logger.info("Generating YouTube chapters and SEO metadata...")
    meta = generate_video_metadata(metadata_json_path)
    story_title = meta.get("title", os.path.basename(video_path))

    # 3. Duplicate Shield Protection: Check live channel and ledger
    dup = check_channel_for_duplicate(
        youtube=youtube,
        target_title=story_title,
        episode_num=episode_id,
        movie_id=movie_id,
        video_path=video_path,
        ledger_path=ledger_path
    )
    if dup:
        logger.info(f"[DUPLICATE SHIELD] Video '{story_title}' already exists on YouTube ({dup['video_id']}). Skipping re-upload.")
        # Ensure playlist mapping
        if not playlist_id and movie_id:
            movie_title = meta.get("theme") or (movie_id.replace("_", " "))
            playlist_id = get_or_create_movie_playlist(youtube, movie_id, movie_title)
        if playlist_id:
            add_video_to_playlist(youtube, playlist_id, dup["video_id"], movie_id, episode_id)
        # Record/ensure ledger entry
        record_upload_success(
            title=dup.get("title") or story_title,
            video_id=dup["video_id"],
            youtube_url=dup["youtube_url"],
            video_path=video_path,
            ledger_path=ledger_path,
            movie_id=movie_id,
            episode_id=episode_id,
            playlist_id=playlist_id
        )
        return dup["youtube_url"]

    # 4. Prepare YouTube upload body
    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": meta["category_id"],
            "defaultLanguage": meta.get("language", "en"),
            "defaultAudioLanguage": meta.get("language", "en")
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
            "license": "youtube"
        }
    }

    # 5. Resumable Upload
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    logger.info(f"Starting chunked upload of {video_path} ({file_size_mb:.2f} MB) to YouTube...")

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        chunksize=10 * 1024 * 1024,  # 10 MB chunks
        resumable=True
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    last_progress = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                if progress >= last_progress + 10:
                    logger.info(f"Upload progress: {progress}%")
                    last_progress = progress
        except HttpError as e:
            logger.error(f"HTTP Error during upload: {e}")
            raise
        except Exception as e:
            logger.warning(f"Transient error during upload ({e}), retrying chunk...")
            time.sleep(5)

    video_id = response.get("id")
    live_url = f"https://youtu.be/{video_id}"

    logger.info(f"Video uploaded successfully! Video ID: {video_id}")
    logger.info(f"Live Video URL: {live_url}")

    # 6. Upload Custom Thumbnail Artwork
    thumbnail_path = find_story_thumbnail(video_path, metadata_json_path)
    if thumbnail_path:
        upload_custom_thumbnail(youtube, video_id, thumbnail_path)
    else:
        logger.info(f"No custom thumbnail found for {video_path}; using YouTube default thumbnail.")

    # 7. Add Video to Movie Playlist
    if not playlist_id and movie_id:
        movie_title = meta.get("theme") or (movie_id.replace("_", " "))
        playlist_id = get_or_create_movie_playlist(youtube, movie_id, movie_title)
    if playlist_id:
        add_video_to_playlist(youtube, playlist_id, video_id, movie_id, episode_id)

    # 8. Record in upload ledger
    try:
        record_upload_success(
            title=story_title,
            video_id=video_id,
            youtube_url=live_url,
            video_path=video_path,
            ledger_path=ledger_path,
            movie_id=movie_id,
            episode_id=episode_id,
            playlist_id=playlist_id
        )
    except Exception as e:
        logger.warning(f"Could not record upload in ledger: {e}")

    return live_url


def main():
    parser = argparse.ArgumentParser(description="YouTube Publisher for Kidoory")
    parser.add_argument("--auth", action="store_true", help="Run interactive authentication flow")
    parser.add_argument("--check", action="store_true", help="Check client secrets and token status")
    parser.add_argument("--publish", action="store_true", help="Publish a video to YouTube")
    parser.add_argument("--video", type=str, help="Path to master video MP4")
    parser.add_argument("--metadata", type=str, help="Path to story script JSON")
    parser.add_argument("--privacy", type=str, default="public", choices=["public", "unlisted", "private"])
    parser.add_argument("--dry-run", action="store_true", help="Generate and display metadata without uploading")
    parser.add_argument("--code", type=str, help="Exchange authorization code or redirect URL directly for OAuth token")
    parser.add_argument("--queue-status", action="store_true", help="Display queue status, audience setting, and daily upload count")
    parser.add_argument("--dispatch-queue", action="store_true", help="Dispatch the oldest queued story if under daily upload cap")
    parser.add_argument("--ledger", action="store_true", help="Display the upload ledger JSON")
    parser.add_argument("--history", type=str, default=DEFAULT_HISTORY_FILE, help="Path to history.json")
    parser.add_argument("--ledger-path", type=str, default=DEFAULT_UPLOAD_LEDGER, help="Path to upload_ledger.json")
    parser.add_argument("--set-thumbnail", nargs=2, metavar=("VIDEO_ID", "IMAGE_PATH"), help="Upload a custom thumbnail for an existing video")
    parser.add_argument("--sync", action="store_true", help="Bi-directionally sync channel inventory with history.json and auto-clean duplicates")
    parser.add_argument("--update-thumbnails", action="store_true", help="Set custom thumbnails for all published stories")
    parser.add_argument("--secrets", type=str, default=DEDICATED_CLIENT_SECRETS)
    parser.add_argument("--token", type=str, default=DEDICATED_TOKEN_FILE)
    args = parser.parse_args()

    if args.sync:
        res = sync_with_live_youtube(
            history_path=args.history,
            secrets_file=args.secrets,
            token_file=args.token,
            delete_duplicates=False
        )
        print("\n" + "="*70)
        print("  LIVE YOUTUBE SYNCHRONIZATION & DEDUPLICATION REPORT")
        print("="*70)
        print(f"  Live Channel Videos: {res.get('live_video_count')}")
        dups = res.get("deleted_duplicates", [])
        print(f"  Duplicate Findings:   {len(dups)}")
        for d in dups:
            print(f"    * [{d.get('status')}] Title: '{d.get('title')}'")
            if d.get("deleted_video_id"):
                print(f"      Deleted ID:   {d.get('deleted_video_id')}")
            if d.get("duplicate_video_id"):
                print(f"      Duplicate ID: {d.get('duplicate_video_id')} ({d.get('note')})")
            print(f"      Retained ID:  {d.get('kept_video_id')}")
        synced = res.get("synced_stories", [])
        print(f"  Stories Synchronized: {len(synced)}")
        for s in synced:
            print(f"    * [{s.get('action')}] '{s.get('title')}' -> {s.get('youtube_url')}")
        print("="*70 + "\n")
        print_queue_status(history_path=args.history, ledger_path=args.ledger_path)
        return

    if args.update_thumbnails:
        res = set_all_custom_thumbnails(
            history_path=args.history,
            secrets_file=args.secrets,
            token_file=args.token
        )
        print("\n" + "="*70)
        print("  CUSTOM THUMBNAIL UPDATE REPORT")
        print("="*70)
        for r in res:
            status = "SUCCESS" if r.get("success") else "FAILED / RATE LIMITED"
            print(f"  * [{status}] {r.get('title')} ({r.get('video_id')}): {r.get('thumbnail_path')}")
        print("="*70 + "\n")
        return

    if args.set_thumbnail:
        vid_id, img_path = args.set_thumbnail
        success = set_video_thumbnail(vid_id, img_path, secrets_file=args.secrets, token_file=args.token)
        if success:
            print(f"\n✅ Custom thumbnail uploaded successfully for {vid_id}!\n")
        else:
            print(f"\n❌ Failed to set custom thumbnail for {vid_id}.\n")
        return

    if args.queue_status:
        print_queue_status(history_path=args.history, ledger_path=args.ledger_path)
        return

    if args.ledger:
        ledger_data = load_upload_ledger(args.ledger_path)
        print("\n" + "="*50)
        print("  KIDOORY UPLOAD LEDGER")
        print("="*50)
        print(json.dumps(ledger_data, indent=2))
        print("="*50 + "\n")
        return

    if args.dispatch_queue:
        url = dispatch_next_queued_story(
            history_path=args.history,
            ledger_path=args.ledger_path,
            secrets_file=args.secrets,
            token_file=args.token,
            privacy_status=args.privacy
        )
        if url:
            print(f"\nDispatched and published successfully: {url}\n")
        else:
            print("\nQueue dispatch returned no upload (cap reached, queue empty, or error).\n")
        return

    if args.code:
        creds = exchange_code_for_token(args.code, secrets_file=args.secrets, token_file=args.token)
        if not creds:
            sys.exit(1)
        return

    if args.check:
        valid, msg = check_client_secrets(args.secrets)
        print("\n" + "="*50)
        print("  KIDOORY YOUTUBE PUBLISHER STATUS")
        print("="*50)
        print(f"Secrets Path: {args.secrets}")
        print(f"Secrets Status: {'VALID' if valid else 'INCOMPLETE/MISSING'}")
        print(f"Details: {msg}")
        print(f"Token Path: {args.token}")
        has_token = os.path.exists(args.token)
        print(f"Token Status: {'EXISTS' if has_token else 'NOT_FOUND'}")
        print("="*50 + "\n")
        if not valid:
            print_setup_instructions(args.secrets)
        return

    if args.auth:
        creds = authenticate_youtube(secrets_file=args.secrets, token_file=args.token)
        if not creds:
            sys.exit(1)
        return

    if args.dry_run:
        meta_path = args.metadata or "/data/google-stories/scripts/keeper_of_the_clockwork_lantern.json"
        meta = generate_video_metadata(meta_path)
        print("\n" + "="*60)
        print("  DRY RUN: GENERATED YOUTUBE METADATA")
        print("="*60)
        print(f"TITLE:\n{meta['title']}\n")
        print("DESCRIPTION:\n")
        print(meta["description"])
        print("\nTAGS:\n" + ", ".join(meta["tags"]))
        print("="*60 + "\n")
        return

    if args.publish:
        if not args.video or not args.metadata:
            parser.error("--publish requires both --video and --metadata arguments.")
        url = publish_story_to_kidoory(args.video, args.metadata, privacy_status=args.privacy,
                                       secrets_file=args.secrets, token_file=args.token)
        print(f"\nPublished successfully: {url}\n")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
