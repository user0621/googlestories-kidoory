#!/usr/bin/env python3
"""
Lightweight Gemini (Google AI Studio) request counter for live telemetry.

Records every generate_content call the production pipeline makes so the
dashboard can show real "requests today" instead of a hardcoded number.
Stored at /data/google-stories/gemini_usage.json. All writes are atomic and
never raise into the caller (telemetry must never break generation).
"""
import os
import json
from datetime import datetime

GEMINI_USAGE_FILE = "/data/google-stories/gemini_usage.json"

# Google AI Studio Developer (free) tier limits for gemini-2.5-flash
DAILY_REQUEST_LIMIT = 1500
RPM_LIMIT = 15


def _load(path=GEMINI_USAGE_FILE):
    today = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return {"today": today, "daily_requests": {today: {"text": 0, "image": 0, "total": 0}}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    if "daily_requests" not in data or not isinstance(data.get("daily_requests"), dict):
        data["daily_requests"] = {}
    if today not in data["daily_requests"]:
        data["daily_requests"][today] = {"text": 0, "image": 0, "total": 0}
    data["today"] = today
    return data


def _save(data, path=GEMINI_USAGE_FILE):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        pass


def record_gemini_request(kind: str = "text", path: str = GEMINI_USAGE_FILE):
    """Increment today's Gemini request count. kind is 'text' or 'image'. Never raises."""
    try:
        data = _load(path)
        today = data["today"]
        bucket = data["daily_requests"].setdefault(today, {"text": 0, "image": 0, "total": 0})
        if kind not in ("text", "image"):
            kind = "text"
        bucket[kind] = bucket.get(kind, 0) + 1
        bucket["total"] = bucket.get("total", 0) + 1
        _save(data, path)
    except Exception:
        pass


def get_gemini_usage(path: str = GEMINI_USAGE_FILE) -> dict:
    """Return today's Gemini request usage for the dashboard. Never raises."""
    try:
        data = _load(path)
        today = data["today"]
        bucket = data["daily_requests"].get(today, {"text": 0, "image": 0, "total": 0})
        return {
            "today": today,
            "requests_today": bucket.get("total", 0),
            "text_today": bucket.get("text", 0),
            "image_today": bucket.get("image", 0),
            "daily_limit": DAILY_REQUEST_LIMIT,
            "rpm_limit": RPM_LIMIT,
        }
    except Exception:
        return {
            "today": datetime.now().strftime("%Y-%m-%d"),
            "requests_today": 0, "text_today": 0, "image_today": 0,
            "daily_limit": DAILY_REQUEST_LIMIT, "rpm_limit": RPM_LIMIT,
        }
