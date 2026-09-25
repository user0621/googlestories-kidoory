#!/usr/bin/env python3
import os
import re
import glob
import json
import logging
import subprocess
from typing import Optional, Tuple, Dict, Any

from youtube_publisher import (
    publish_story_to_kidoory,
    check_channel_for_duplicate,
    authenticate_youtube,
    get_or_create_movie_playlist,
    add_video_to_playlist,
    load_playlists_registry
)
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MoviePublisher")

PROJECT_STATE_FILE = "/home/hkserver/googlestories-kidoory/PROJECT_STATE.json"
MOVIES_DIR = "/mnt/data/google-stories/movies"

def load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def atomic_save(path: str, data: Dict[str, Any]):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

def run_qc_audit(mp4_path: str) -> bool:
    """Validate video file existence, minimum duration, and sound stream."""
    if not mp4_path or not os.path.exists(mp4_path):
        logger.error(f"QC Fail: File not found at {mp4_path}")
        return False
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", mp4_path
        ])
        duration = float(out.decode().strip())
        if duration < 120:  # At least 2 minutes for a bedtime episode
            logger.error(f"QC Fail: Duration {duration:.1f}s is less than 120s minimum threshold.")
            return False

        # Verify audio stream is present
        audio_check = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_type", "-of", "default=noprint_wrappers=1:nokey=1", mp4_path
        ], capture_output=True, text=True)
        if "audio" not in audio_check.stdout:
            logger.error(f"QC Fail: No audio stream found in {mp4_path}")
            return False

        logger.info(f"QC Audit Passed for {os.path.basename(mp4_path)} (Duration: {duration:.1f}s)")
        return True
    except Exception as e:
        logger.error(f"QC Exception: {e}")
        return False

def find_movie_episode_files(movie_id: str, episode_id: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Scans the movie directory to find the rendered MP4 and companion metadata JSON for an episode.
    """
    movie_path = os.path.join(MOVIES_DIR, movie_id)
    if not os.path.exists(movie_path):
        return None, None

    # Check unposted, posted, and root movie subdirectories
    search_dirs = [
        os.path.join(movie_path, "unposted"),
        os.path.join(movie_path, "posted"),
        movie_path
    ]

    for sdir in search_dirs:
        if not os.path.exists(sdir):
            continue
        for root, _, files in os.walk(sdir):
            if "temp_segments" in root or "raw_images" in root or "audio_scenes" in root:
                continue
            for file in files:
                if not file.endswith(".mp4"):
                    continue
                # Regex match for Ep. X or Episode X
                m = re.search(r'[_\s]Ep\.?[_\s]*(\d+)', file, re.IGNORECASE)
                if m and int(m.group(1)) == episode_id:
                    mp4_path = os.path.join(root, file)
                    json_path = os.path.splitext(mp4_path)[0] + ".json"
                    if not os.path.exists(json_path):
                        # Try scripts directory fallback
                        scripts_dir = os.path.join(movie_path, "scripts")
                        candidate_jsons = glob.glob(os.path.join(scripts_dir, f"*ep*{episode_id}*.json"))
                        if candidate_jsons:
                            json_path = candidate_jsons[0]
                    return mp4_path, (json_path if os.path.exists(json_path) else None)

    return None, None

def publish_movie_episode(
    movie_id: str,
    episode_id: int,
    mp4_path: Optional[str] = None,
    json_path: Optional[str] = None,
    privacy_status: str = "public",
    force: bool = False
) -> Dict[str, Any]:
    """
    Publishes a single movie episode with automated playlist assignment,
    SEO metadata ingestion from companion JSON, and strict YouTube channel deduplication.
    """
    if not mp4_path or not json_path:
        found_mp4, found_json = find_movie_episode_files(movie_id, episode_id)
        mp4_path = mp4_path or found_mp4
        json_path = json_path or found_json

    if not mp4_path or not os.path.exists(mp4_path):
        return {
            "status": "error",
            "message": f"Rendered MP4 file for {movie_id} Episode {episode_id} was not found on SSD."
        }

    if not json_path or not os.path.exists(json_path):
        return {
            "status": "error",
            "message": f"Companion metadata JSON for {movie_id} Episode {episode_id} was not found."
        }

    # 1. Run Quality Audit
    if not run_qc_audit(mp4_path):
        return {
            "status": "error",
            "message": f"Video QC audit failed for {os.path.basename(mp4_path)}."
        }

    # 2. Resolve Movie Series & YouTube Playlist ID
    creds = authenticate_youtube()
    if not creds:
        return {
            "status": "error",
            "message": "YouTube OAuth authentication failed or credentials missing."
        }
    yt = build("youtube", "v3", credentials=creds)

    # Check playlist mapping
    struct_file = os.path.join(MOVIES_DIR, movie_id, "bibles", "MOVIE_STRUCTURE.json")
    struct_data = load_json(struct_file)
    movie_title = struct_data.get("movie_title") or f"Luna Bedtime Story Series {movie_id}"
    playlist_id = get_or_create_movie_playlist(yt, movie_id, movie_title)

    # 3. Check Duplicate Shield on Channel & Ledger
    metadata = load_json(json_path)
    target_title = metadata.get("title", os.path.basename(mp4_path))

    dup = check_channel_for_duplicate(
        youtube=yt,
        target_title=target_title,
        episode_num=episode_id,
        movie_id=movie_id,
        video_path=mp4_path
    )

    if dup:
        vid = dup["video_id"]
        live_url = dup["youtube_url"]
        logger.info(f"[DUPLICATE SHIELD] {movie_id} Episode {episode_id} already exists on YouTube ({vid}).")
        # Ensure it is added to the series playlist
        if playlist_id:
            add_video_to_playlist(yt, playlist_id, vid, movie_id, episode_id)

        return {
            "status": "already_published",
            "movie_id": movie_id,
            "episode_id": episode_id,
            "video_id": vid,
            "youtube_url": live_url,
            "playlist_id": playlist_id,
            "title": dup.get("title", target_title),
            "message": f"Episode {episode_id} is already published on YouTube ({vid}). Skipped re-upload."
        }

    # 4. Upload to YouTube
    logger.info(f"Publishing {movie_id} Ep. {episode_id} to YouTube channel...")
    live_url = publish_story_to_kidoory(
        video_path=mp4_path,
        metadata_json_path=json_path,
        privacy_status=privacy_status,
        movie_id=movie_id,
        episode_id=episode_id,
        playlist_id=playlist_id,
        force=force
    )

    if not live_url:
        return {
            "status": "limit_reached",
            "message": "Daily upload limit (5/5) reached for today. Upload held in SSD queue."
        }

    vid = live_url.split("/")[-1]
    return {
        "status": "published",
        "movie_id": movie_id,
        "episode_id": episode_id,
        "video_id": vid,
        "youtube_url": live_url,
        "playlist_id": playlist_id,
        "title": target_title,
        "message": f"Episode {episode_id} published successfully to YouTube!"
    }

def publish_episode():
    """Autonomous entry point called by autonomous_daemon.py at QC_AUDIT stage."""
    state = load_json(PROJECT_STATE_FILE)
    movie_id = state.get("active_movie_id", "MOVIE_001")
    ep_id = state.get("active_episode_id", 1)
    stage = state.get("stage", "QC_AUDIT")

    logger.info(f"Autonomous MoviePublisher invoked: {movie_id} Ep {ep_id} (Stage: {stage})")
    mp4_path = state.get("latest_mp4")

    res = publish_movie_episode(
        movie_id=movie_id,
        episode_id=ep_id,
        mp4_path=mp4_path
    )

    logger.info(f"Publish result: {res.get('status')} - {res.get('message')}")

    if res.get("status") in ("published", "already_published"):
        # Advance Episode cleanly
        if ep_id < 12:
            state["active_episode_id"] = ep_id + 1
            state["stage"] = "EPISODE_PRODUCTION"
            # Point latest_mp4 to next episode if already rendered on disk
            next_mp4, _ = find_movie_episode_files(movie_id, ep_id + 1)
            if next_mp4:
                state["latest_mp4"] = next_mp4
        else:
            state["stage"] = "MOVIE_COMPLETE"
            logger.info(f"Movie {movie_id} complete! Archiving...")

        atomic_save(PROJECT_STATE_FILE, state)

if __name__ == "__main__":
    publish_episode()
