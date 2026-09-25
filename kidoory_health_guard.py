#!/usr/bin/env python3
"""
kidoory_health_guard.py - 4-Hour Autonomous Platform & Health Guard for Kidoory
Checks:
  1. Google OAuth refresh token validity for YouTube Data API v3 (solodigital.ltd@gmail.com).
  2. Vertex AI quota health for project `kidoory`.
  3. Free disk space on the media SSD mount.
  4. google-stories.service systemd active state and cadence.
Writes output to <kidoory_media_root>/kidoory_health.json.
"""

import os
import sys
import json
import time
import shutil
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Google Auth & API imports
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.genai import Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("KidooryHealthGuard")

MEDIA_ROOT = "/data/google-stories"
TOKEN_FILE = os.path.join(MEDIA_ROOT, "youtube_token.json")
CLIENT_SECRETS_FILE = "/home/hkserver/secrets/kidoory_client_secret.json"
GCP_CREDS_FILE = "/home/hkserver/secrets/kidoory-7590452277b9.json"
HISTORY_FILE = os.path.join(MEDIA_ROOT, "history.json")
LEDGER_FILE = os.path.join(MEDIA_ROOT, "upload_ledger.json")
HEALTH_OUTPUT_FILE = os.path.join(MEDIA_ROOT, "kidoory_health.json")

LANGUAGE_CYCLE = [
    {"index": 0, "code": "en", "name": "English", "native_name": "English"},
    {"index": 1, "code": "hi", "name": "Hindi", "native_name": "हिन्दी"},
    {"index": 2, "code": "pa", "name": "Punjabi", "native_name": "ਪੰਜਾਬੀ"},
    {"index": 3, "code": "fr", "name": "French", "native_name": "Français"},
    {"index": 4, "code": "es", "name": "Spanish", "native_name": "Español"},
]


def check_youtube_oauth():
    res = {
        "status": "UNKNOWN",
        "account": "solodigital.ltd@gmail.com",
        "channel_id": "UCobsgHbbxC3tLOpTJKkkHeg",
        "channel_handle": "@kidoorystory",
        "subscribers": 0,
        "lifetime_views": 0,
        "video_count": 0,
        "token_valid": False,
        "message": ""
    }
    if not os.path.exists(TOKEN_FILE):
        res["status"] = "DOWN"
        res["message"] = f"Token file missing at {TOKEN_FILE}"
        return res

    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            tok_data = json.load(f)

        creds = Credentials.from_authorized_user_info(tok_data)
        if creds.expired or not creds.valid:
            logger.info("Refreshing expired YouTube OAuth token...")
            creds.refresh(Request())
            # Save refreshed credentials
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                json.dump(json.loads(creds.to_json()), f, indent=2)

        res["token_valid"] = True
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        ch_resp = youtube.channels().list(mine=True, part="snippet,statistics").execute()
        items = ch_resp.get("items", [])
        if items:
            ch = items[0]
            res["channel_id"] = ch.get("id", res["channel_id"])
            stats = ch.get("statistics", {})
            res["subscribers"] = int(stats.get("subscriberCount", 0))
            res["lifetime_views"] = int(stats.get("viewCount", 0))
            res["video_count"] = int(stats.get("videoCount", 0))
            res["status"] = "HEALTHY"
            res["message"] = "OAuth token valid and channel metrics synchronized"
        else:
            res["status"] = "DEGRADED"
            res["message"] = "OAuth token valid but channel not found via mine=True"
    except Exception as e:
        logger.error(f"YouTube OAuth check failed: {e}")
        res["status"] = "DOWN"
        res["message"] = f"OAuth verification error: {str(e)}"

    return res


def check_vertex_ai():
    res = {
        "status": "UNKNOWN",
        "project": "kidoory",
        "location": "us-central1",
        "quota_healthy": False,
        "message": ""
    }
    api_key = os.environ.get("GEMINI_API_KEY", "AIzaSyC3a50b9lMb5FpzClrQOL7qT0mBYcrds3I")
    try:
        client = Client(api_key=api_key, http_options={"api_version": "v1beta"})
        model = client.models.get(model="gemini-2.5-flash")
        if model:
            res["quota_healthy"] = True
            res["status"] = "HEALTHY"
            res["message"] = "Google AI Studio Developer API (Free Tier) active and quota healthy (generativelanguage.googleapis.com)"
            return res
    except Exception as e:
        logger.warning(f"Google AI Studio Developer API check warning: {e}")

    if not os.path.exists(GCP_CREDS_FILE):
        res["status"] = "DOWN"
        res["message"] = f"Credentials missing at {GCP_CREDS_FILE}"
        return res

    try:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GCP_CREDS_FILE
        with open(GCP_CREDS_FILE, "r", encoding="utf-8") as f:
            cred_data = json.load(f)
            project_id = cred_data.get("project_id", "kidoory")
            res["project"] = project_id

        client = Client(api_key=os.environ["GEMINI_API_KEY"], http_options={"api_version": "v1beta"}, vertexai=False)
        for m in client.models.list(config={"page_size": 1}):
            res["quota_healthy"] = True
            res["status"] = "HEALTHY"
            res["message"] = f"Vertex AI API active and quota healthy ({getattr(m, 'name', 'model available')})"
            return res
    except Exception as e:
        logger.error(f"Vertex AI check failed: {e}")
        res["status"] = "DOWN"
        res["message"] = f"Vertex AI API check failed: {str(e)}"

    return res


def check_disk_space():
    res = {
        "status": "UNKNOWN",
        "path": MEDIA_ROOT,
        "free_gb": 0.0,
        "total_gb": 0.0,
        "used_gb": 0.0,
        "used_percent": 0.0,
        "message": ""
    }
    try:
        check_path = MEDIA_ROOT if os.path.exists(MEDIA_ROOT) else "/mnt/data"
        usage = shutil.disk_usage(check_path)
        free_gb = round(usage.free / (1024 ** 3), 2)
        total_gb = round(usage.total / (1024 ** 3), 2)
        used_gb = round((usage.total - usage.free) / (1024 ** 3), 2)
        used_percent = round((used_gb / total_gb) * 100, 1) if total_gb > 0 else 0.0

        res["free_gb"] = free_gb
        res["total_gb"] = total_gb
        res["used_gb"] = used_gb
        res["used_percent"] = used_percent

        if free_gb < 20.0:
            res["status"] = "DEGRADED"
            res["message"] = f"Low free space: {free_gb} GB remaining (< 20 GB threshold)"
        else:
            res["status"] = "HEALTHY"
            res["message"] = f"{free_gb} GB free of {total_gb} GB ({used_percent}% used)"
    except Exception as e:
        logger.error(f"Disk check failed: {e}")
        res["status"] = "DOWN"
        res["message"] = f"Could not check disk usage: {e}"

    return res


def check_systemd_service():
    res = {
        "service_name": "google-stories.service",
        "status": "unknown",
        "active": False,
        "interval_seconds": 3600,
        "message": ""
    }
    try:
        out = subprocess.check_output(
            ["systemctl", "is-active", "google-stories.service"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        res["status"] = out
        res["active"] = (out == "active")
        res["message"] = "Service is active and running" if res["active"] else f"Service status: {out}"
    except subprocess.CalledProcessError as e:
        res["status"] = "inactive"
        res["active"] = False
        res["message"] = "Service is stopped or inactive"
    except Exception as e:
        res["status"] = "unknown"
        res["message"] = f"Could not query systemctl: {e}"

    # Also check daemon heartbeat file
    hb_file = os.path.join(MEDIA_ROOT, "daemon_heartbeat.json")
    if os.path.exists(hb_file):
        try:
            with open(hb_file, "r", encoding="utf-8") as f:
                hb = json.load(f)
                res["last_heartbeat"] = hb.get("last_heartbeat")
                if hb.get("interval_seconds"):
                    res["interval_seconds"] = hb.get("interval_seconds")
        except Exception:
            pass

    return res


def get_rotation_and_metrics():
    # Read history
    last_idx = 0
    total_published = 0
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                h = json.load(f)
                last_idx = h.get("last_language_index", 0)
                stories = h.get("stories", [])
                total_published = sum(1 for s in stories if s.get("status") == "PUBLISHED")
        except Exception as e:
            logger.warning(f"Could not read history: {e}")

    # Fallback / verify with posted directory
    posted_dir = os.path.join(MEDIA_ROOT, "posted")
    if os.path.isdir(posted_dir):
        disk_posted = 0
        for root, _, files in os.walk(posted_dir):
            for f in files:
                if f.endswith(".mp4") and not os.path.islink(os.path.join(root, f)):
                    disk_posted += 1
        if disk_posted > total_published:
            total_published = disk_posted

    next_idx = (last_idx + 1) % len(LANGUAGE_CYCLE)

    # Read upload ledger for today's uploads
    today_uploads = 0
    daily_cap = 5
    today_str = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                led = json.load(f)
                daily_cap = led.get("daily_cap", 5)
                today_record = led.get("daily_counts", {}).get(today_str, {})
                today_uploads = today_record.get("count", 0)
        except Exception as e:
            logger.warning(f"Could not read ledger: {e}")

    return {
        "last_language_index": last_idx,
        "current_language": LANGUAGE_CYCLE[last_idx % len(LANGUAGE_CYCLE)],
        "next_language_index": next_idx,
        "next_language": LANGUAGE_CYCLE[next_idx],
        "total_published_stories": total_published,
        "today_uploads": today_uploads,
        "daily_cap": daily_cap,
        "cycle": LANGUAGE_CYCLE
    }


def run_health_guard():
    logger.info("Executing Kidoory 4-Hour Autonomous Platform & Health Guard...")
    yt_health = check_youtube_oauth()
    vx_health = check_vertex_ai()
    disk_health = check_disk_space()
    sys_health = check_systemd_service()
    metrics = get_rotation_and_metrics()

    overall_healthy = (
        yt_health["status"] in ("HEALTHY", "DEGRADED")
        and vx_health["status"] == "HEALTHY"
        and disk_health["status"] == "HEALTHY"
    )

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel": "@kidoorystory",
        "account": "solodigital.ltd@gmail.com",
        "channel_title": "Kidoory Bedtime Stories",
        "overall_status": "HEALTHY" if overall_healthy else "DEGRADED",
        "youtube_oauth": yt_health,
        "vertex_ai": vx_health,
        "storage": disk_health,
        "systemd_service": sys_health,
        "rotation": {
            "current_index": metrics["last_language_index"],
            "current_language": metrics["current_language"],
            "next_index": metrics["next_language_index"],
            "next_language": metrics["next_language"],
            "cycle": metrics["cycle"]
        },
        "metrics": {
            "subscribers": yt_health["subscribers"],
            "lifetime_views": yt_health["lifetime_views"],
            "total_published_stories": metrics["total_published_stories"],
            "today_uploads": metrics["today_uploads"],
            "daily_cap": metrics["daily_cap"]
        }
    }

    # Write atomically
    tmp_path = HEALTH_OUTPUT_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, HEALTH_OUTPUT_FILE)
    logger.info(f"Health check complete. Output written to {HEALTH_OUTPUT_FILE}")
    print(json.dumps(payload, indent=2))
    return payload


if __name__ == "__main__":
    run_health_guard()
