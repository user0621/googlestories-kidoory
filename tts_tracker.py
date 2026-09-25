#!/usr/bin/env python3
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger("KidooryTTSTracker")

DAILY_LIMIT = 35_000
TTS_LIMIT = 950_000
TRACKER_FILE = "/data/google-stories/tts_usage.json"

def _load_ledger(tracker_path=TRACKER_FILE):
    current_month = datetime.now().strftime("%Y-%m")
    current_day = datetime.now().strftime("%Y-%m-%d")
    
    if not os.path.exists(tracker_path) or os.path.getsize(tracker_path) == 0:
        return {
            "month": current_month,
            "monthly_usage": 0,
            "daily_usage": {current_day: 0}
        }
        
    try:
        with open(tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to read ledger {tracker_path}: {e}, resetting ledger.")
        data = {}
        
    # Reset if month rolled over
    if data.get("month") != current_month:
        data["month"] = current_month
        data["monthly_usage"] = 0
        data["daily_usage"] = {}
        
    if "daily_usage" not in data or not isinstance(data["daily_usage"], dict):
        data["daily_usage"] = {}
        
    if current_day not in data["daily_usage"]:
        data["daily_usage"][current_day] = 0
        
    if "monthly_usage" not in data:
        data["monthly_usage"] = data.get("chars", 0)
        
    return data

def _save_ledger(data, tracker_path=TRACKER_FILE):
    os.makedirs(os.path.dirname(tracker_path), exist_ok=True)
    tmp_path = tracker_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, tracker_path)

def check_budget(chars_needed: int, tracker_path=TRACKER_FILE):
    data = _load_ledger(tracker_path)
    current_day = datetime.now().strftime("%Y-%m-%d")
    daily_current = data["daily_usage"].get(current_day, 0)
    monthly_current = data.get("monthly_usage", 0)
    
    if daily_current + chars_needed > DAILY_LIMIT:
        return False, "DAILY_CAP_REACHED"
        
    if monthly_current + chars_needed > TTS_LIMIT:
        return False, "MONTHLY_CAP_REACHED"
        
    return True, "OK"

def record_usage(chars: int, tracker_path=TRACKER_FILE):
    data = _load_ledger(tracker_path)
    current_day = datetime.now().strftime("%Y-%m-%d")
    
    data["daily_usage"][current_day] = data["daily_usage"].get(current_day, 0) + chars
    data["monthly_usage"] = data.get("monthly_usage", 0) + chars
    data["chars"] = data["monthly_usage"]  # For backwards compatibility
    
    _save_ledger(data, tracker_path)
    return data

def get_usage(tracker_path=TRACKER_FILE):
    data = _load_ledger(tracker_path)
    current_day = datetime.now().strftime("%Y-%m-%d")
    return {
        "month": data.get("month"),
        "monthly_usage": data.get("monthly_usage", 0),
        "monthly_limit": TTS_LIMIT,
        "today": current_day,
        "daily_usage": data["daily_usage"].get(current_day, 0),
        "daily_limit": DAILY_LIMIT
    }

def track_tts_usage(char_count: int, tracker_path=TRACKER_FILE):
    ok, reason = check_budget(char_count, tracker_path)
    if not ok:
        raise RuntimeError(f"[CIRCUIT BREAKER] Kidoory paused: {reason}. $0.00 guarantee preserved.")
    record_usage(char_count, tracker_path)
