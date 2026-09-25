import os
import re

path = "/home/hkserver/myentrykey-auto-youtube/kidoory_engine/youtube_publisher.py"
with open(path, "r") as f:
    content = f.read()

# Make daily upload tracking atomic with file lock
atomic_func = """
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
"""

if "import fcntl" not in content:
    content = atomic_func + content

with open(path, "w") as f:
    f.write(content)
