import os
import re
import glob
import json
import time
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, Response, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import dotenv_values

from movie_publisher import publish_movie_episode, find_movie_episode_files
from youtube_publisher import (
    exchange_code_for_token,
    sync_pending_playlist_items,
    authenticate_youtube,
    SCOPES,
    DEDICATED_CLIENT_SECRETS
)

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
config = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}

STUDIO_PASSWORD = config.get("STUDIO_PASSWORD", "ouNl14uRyPuiMeyKyRyF")
COOKIE_NAME = "kidoory_studio_session"
SECRET_KEY = config.get("SECRET_KEY", "kidoory-secure-session-key-2026-bedtime")

DATA_DIR = Path(config.get("DATA_DIR", "/data/google-stories"))
MOVIES_DIR = Path(config.get("MOVIES_DIR", "/mnt/data/google-stories/movies"))
STATE_FILE = BASE_DIR / "PROJECT_STATE.json"
HEALTH_FILE = DATA_DIR / "kidoory_health.json"
TTS_USAGE_FILE = DATA_DIR / "tts_usage.json"
UPLOAD_LEDGER_FILE = DATA_DIR / "upload_ledger.json"
PLAYLISTS_FILE = DATA_DIR / "playlists.json"

app = FastAPI(
    title="Kidoory Bedtime Stories Studio",
    description="Autonomous Bedtime Stories Engine for @kidoorystory"
)

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Simple session verification
def is_authenticated(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    return token == f"authenticated_{STUDIO_PASSWORD}"

def require_auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=303, headers={"Location": "/login"})

def load_json_safe(path: Path) -> Dict[str, Any]:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

# Background action lock
action_lock = threading.Lock()
current_running_action = None

def run_action_background(cmd: list, action_name: str):
    global current_running_action
    def worker():
        global current_running_action
        try:
            current_running_action = action_name
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            subprocess.run(cmd, cwd=str(BASE_DIR), env=env, check=False)
        finally:
            current_running_action = None

    t = threading.Thread(target=worker, daemon=True)
    t.start()


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login_submit(request: Request, password: str = Form(...)):
    if password == STUDIO_PASSWORD:
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key=COOKIE_NAME,
            value=f"authenticated_{STUDIO_PASSWORD}",
            httponly=True,
            samesite="lax",
            max_age=86400 * 7
        )
        return response
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid studio password. Please try again."})


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


def get_all_episodes_data() -> List[Dict[str, Any]]:
    ledger = load_json_safe(UPLOAD_LEDGER_FILE)
    playlists = load_json_safe(PLAYLISTS_FILE)

    published_map = {}
    for date_str, ddata in ledger.get("daily_counts", {}).items():
        for item in ddata.get("uploads", []):
            m_id = item.get("movie_id")
            ep_id = item.get("episode_id")
            if m_id and ep_id:
                published_map[(m_id, int(ep_id))] = item
            if item.get("video_path"):
                published_map[os.path.basename(item["video_path"])] = item
            if item.get("video_id") == "MsPp4P_tr5k":
                published_map[("MOVIE_001", 1)] = item

    movies_data = []
    movie_dirs = sorted([d for d in MOVIES_DIR.glob("MOVIE_*") if d.is_dir()])
    if not movie_dirs:
        movie_dirs = [MOVIES_DIR / "MOVIE_001", MOVIES_DIR / "MOVIE_002"]

    for m_dir in movie_dirs:
        if not m_dir.exists():
            continue
        m_id = m_dir.name
        struct = load_json_safe(m_dir / "bibles" / "MOVIE_STRUCTURE.json")
        ep_map_list = load_json_safe(m_dir / "bibles" / "EPISODE_MAP.json") or []
        ep_titles = {e.get("episode_id"): e.get("title") for e in ep_map_list if isinstance(e, dict)}
        movie_title = struct.get("movie_title", m_id)
        pl_info = playlists.get(m_id, {})
        pl_id = pl_info.get("playlist_id")

        mp4s = glob.glob(f"{m_dir}/**/*.mp4", recursive=True)
        episodes = []
        seen_eps = set()
        for mp4 in sorted(mp4s):
            if any(x in mp4 for x in ["temp_segments", "raw_images", "audio_scenes"]):
                continue
            base = os.path.basename(mp4)
            m = re.search(r'[_\s]Ep\.?[_\s]*(\d+)', base, re.IGNORECASE)
            ep_id = int(m.group(1)) if m else None
            if not ep_id or ep_id in seen_eps:
                continue
            seen_eps.add(ep_id)

            json_path = mp4[:-4] + ".json"
            has_json = os.path.exists(json_path)
            ep_title = ep_titles.get(ep_id, base.replace("_", " ").replace(".mp4", ""))

            pub_info = published_map.get((m_id, ep_id)) or published_map.get(base)
            is_published = bool(pub_info)

            episodes.append({
                "episode_id": ep_id,
                "title": ep_title,
                "filename": base,
                "mp4_path": mp4,
                "json_path": json_path if has_json else None,
                "size_mb": round(os.path.getsize(mp4) / (1024 * 1024), 1),
                "is_published": is_published,
                "video_id": pub_info.get("video_id") if pub_info else None,
                "youtube_url": pub_info.get("youtube_url") if pub_info else None,
                "playlist_id": pl_id
            })

        episodes.sort(key=lambda x: x["episode_id"])
        movies_data.append({
            "movie_id": m_id,
            "movie_title": movie_title,
            "playlist_id": pl_id,
            "playlist_url": f"https://www.youtube.com/playlist?list={pl_id}" if pl_id else None,
            "total_rendered": len(episodes),
            "published_count": sum(1 for e in episodes if e["is_published"]),
            "episodes": episodes
        })

    return movies_data


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def dashboard_index(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    state = load_json_safe(STATE_FILE)
    health = load_json_safe(HEALTH_FILE)
    tts_usage = load_json_safe(TTS_USAGE_FILE)
    upload_ledger = load_json_safe(UPLOAD_LEDGER_FILE)
    movies_data = get_all_episodes_data()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "state": state,
        "health": health,
        "tts_usage": tts_usage,
        "upload_ledger": upload_ledger,
        "movies_data": movies_data,
        "running_action": current_running_action
    })


@app.get("/api/status")
async def api_status(request: Request):
    require_auth(request)
    state = load_json_safe(STATE_FILE)
    return {
        "state": state,
        "running_action": current_running_action,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/health")
async def api_health(request: Request):
    require_auth(request)
    health = load_json_safe(HEALTH_FILE)
    return health


@app.get("/api/quotas")
async def api_quotas(request: Request):
    require_auth(request)
    tts_usage = load_json_safe(TTS_USAGE_FILE)
    upload_ledger = load_json_safe(UPLOAD_LEDGER_FILE)
    
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_uploads_data = upload_ledger.get("daily_counts", {}).get(today_str, {})
    today_uploads_count = today_uploads_data.get("count", 0)

    # Gemini Developer API Free Tier Limits:
    # 15 RPM (Requests Per Minute), 1,500 RPD (Requests Per Day), Free of charge ($0.00)
    # Cloud TTS: 1,000,000 characters free / month for Neural2/Journey
    daily_chars = tts_usage.get("daily_characters", 0)
    monthly_chars = tts_usage.get("monthly_characters", 0)
    daily_limit_chars = tts_usage.get("daily_limit", 35000)
    monthly_limit_chars = tts_usage.get("monthly_limit", 950000)

    # YouTube Data API v3 Free Tier: 10,000 units/day.
    # Upload video costs 1600 units each.
    yt_units_used = today_uploads_count * 1600
    yt_units_remaining = max(0, 10000 - yt_units_used)

    return {
        "gemini": {
            "tier": "Google AI Studio Developer (100% Free Tier)",
            "model_text": "gemini-2.5-flash",
            "model_image": "gemini-2.5-flash-image",
            "daily_requests_limit": 1500,
            "rpm_limit": 15,
            "cost_usd": 0.00,
            "cost_status": "Strict Zero Cost Enforced (GOOGLE_GENAI_USE_VERTEXAI=False)"
        },
        "tts": {
            "provider": "Google Cloud Text-to-Speech (Neural2 / Journey)",
            "daily_used": daily_chars,
            "daily_limit": daily_limit_chars,
            "daily_pct": round((daily_chars / daily_limit_chars) * 100, 1) if daily_limit_chars else 0,
            "monthly_used": monthly_chars,
            "monthly_limit": monthly_limit_chars,
            "monthly_pct": round((monthly_chars / monthly_limit_chars) * 100, 1) if monthly_limit_chars else 0,
            "monthly_free_tier": 1000000,
            "cost_usd": 0.00
        },
        "youtube": {
            "quota_units_limit": 10000,
            "units_used": yt_units_used,
            "units_remaining": yt_units_remaining,
            "today_uploads": today_uploads_count,
            "daily_cap": upload_ledger.get("daily_cap", 5)
        }
    }


@app.get("/api/secrets")
async def api_secrets(request: Request):
    require_auth(request)
    k_key = config.get("KIDOORY_GEMINI_API_KEY") or config.get("GEMINI_API_KEY", "")
    
    def mask(val: str, prefix_len=6, suffix_len=4) -> str:
        if not val:
            return "Not Configured"
        if len(val) <= prefix_len + suffix_len:
            return "••••••••"
        return f"{val[:prefix_len]}••••••••••••••••{val[-suffix_len:]}"

    client_secret_path = Path("/home/hkserver/secrets/kidoory_client_secret.json")
    client_id = ""
    client_secret = ""
    if client_secret_path.exists():
        try:
            with open(client_secret_path) as f:
                cdata = json.load(f)
                client_id = cdata.get("installed", {}).get("client_id", "")
                client_secret = cdata.get("installed", {}).get("client_secret", "")
        except Exception:
            pass

    token_path = DATA_DIR / "youtube_token.json"
    refresh_token = ""
    access_token = ""
    if token_path.exists():
        try:
            with open(token_path) as f:
                tdata = json.load(f)
                refresh_token = tdata.get("refresh_token", "")
                access_token = tdata.get("token", "")
        except Exception:
            pass

    return {
        "gemini_api_key": {
            "masked": mask(k_key, 6, 4),
            "label": "Kidoory Gemini API Key (Google AI Studio Free Tier)",
            "configured": bool(k_key)
        },
        "service_account": {
            "masked": "gemini-agy-linux@kidoory.iam.gserviceaccount.com",
            "label": "Google Cloud Service Account (Text-To-Speech)",
            "path": "/home/hkserver/secrets/kidoory-7590452277b9.json",
            "configured": os.path.exists("/home/hkserver/secrets/kidoory-7590452277b9.json")
        },
        "youtube_client_id": {
            "masked": mask(client_id, 10, 10),
            "label": "YouTube Data API OAuth Client ID",
            "configured": bool(client_id)
        },
        "youtube_client_secret": {
            "masked": mask(client_secret, 6, 3),
            "label": "YouTube OAuth Client Secret",
            "configured": bool(client_secret)
        },
        "youtube_refresh_token": {
            "masked": mask(refresh_token, 6, 4),
            "label": "YouTube OAuth Refresh Token (@kidoorystory)",
            "configured": bool(refresh_token)
        }
    }


@app.post("/api/secrets/reveal")
async def api_reveal_secret(request: Request, payload: dict):
    require_auth(request)
    secret_name = payload.get("secret_name")
    k_key = config.get("KIDOORY_GEMINI_API_KEY") or config.get("GEMINI_API_KEY", "")

    if secret_name == "gemini_api_key":
        return {"value": k_key}
    elif secret_name == "service_account":
        return {"value": "gemini-agy-linux@kidoory.iam.gserviceaccount.com"}
    elif secret_name in ["youtube_client_id", "youtube_client_secret"]:
        client_secret_path = Path("/home/hkserver/secrets/kidoory_client_secret.json")
        if client_secret_path.exists():
            with open(client_secret_path) as f:
                cdata = json.load(f).get("installed", {})
                return {"value": cdata.get("client_id" if secret_name == "youtube_client_id" else "client_secret", "")}
    elif secret_name in ["youtube_refresh_token", "youtube_access_token"]:
        token_path = DATA_DIR / "youtube_token.json"
        if token_path.exists():
            with open(token_path) as f:
                tdata = json.load(f)
                return {"value": tdata.get("refresh_token" if secret_name == "youtube_refresh_token" else "token", "")}

    raise HTTPException(status_code=400, detail="Unknown secret name")


@app.post("/api/actions/produce")
async def action_produce(request: Request):
    require_auth(request)
    global current_running_action
    if current_running_action:
        return JSONResponse({"status": "busy", "message": f"Action '{current_running_action}' is already in progress."}, status_code=409)

    python_bin = BASE_DIR / ".venv" / "bin" / "python"
    cmd = [str(python_bin), str(BASE_DIR / "produce_episode.py")]
    run_action_background(cmd, "Produce Episode")
    return {"status": "started", "message": "Episode production launched in background."}


@app.post("/api/actions/publish")
async def action_publish(request: Request):
    require_auth(request)
    global current_running_action
    if current_running_action:
        return JSONResponse({"status": "busy", "message": f"Action '{current_running_action}' is already in progress."}, status_code=409)

    python_bin = BASE_DIR / ".venv" / "bin" / "python"
    cmd = [str(python_bin), str(BASE_DIR / "movie_publisher.py")]
    run_action_background(cmd, "Publish Episode")
    return {"status": "started", "message": "Episode publisher launched in background."}


@app.post("/api/actions/health-check")
async def action_health_check(request: Request):
    require_auth(request)
    global current_running_action
    if current_running_action:
        return JSONResponse({"status": "busy", "message": f"Action '{current_running_action}' is already in progress."}, status_code=409)

    python_bin = BASE_DIR / ".venv" / "bin" / "python"
    cmd = [str(python_bin), str(BASE_DIR / "kidoory_health_guard.py")]
    run_action_background(cmd, "Health Guard Check")
    return {"status": "started", "message": "Health Guard inspection running."}


@app.get("/media/latest")
async def media_latest(request: Request):
    require_auth(request)
    state = load_json_safe(STATE_FILE)
    latest_mp4 = state.get("latest_mp4")
    if latest_mp4 and os.path.exists(latest_mp4):
        return FileResponse(latest_mp4, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="No latest video found")


@app.get("/media/video/{path:path}")
async def media_video(request: Request, path: str):
    require_auth(request)
    candidate = MOVIES_DIR / path
    if not candidate.exists():
        candidate = DATA_DIR / path
    if candidate.exists() and candidate.is_file():
        return FileResponse(str(candidate), media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Video file not found")


@app.get("/api/episodes")
async def api_episodes(request: Request):
    """Returns all discovered movies and episodes with rendered status and YouTube metadata."""
    require_auth(request)
    return {"status": "ok", "movies": get_all_episodes_data()}


@app.post("/api/episodes/publish")
async def api_publish_episode(request: Request, payload: dict):
    """
    Manually triggers publishing for an episode.
    Reads companion JSON, checks channel for duplicates, uploads MP4 with custom thumbnail,
    assigns video to series playlist, and logs to ledger.
    """
    require_auth(request)
    movie_id = payload.get("movie_id")
    episode_id = payload.get("episode_id")
    mp4_path = payload.get("mp4_path")
    json_path = payload.get("json_path")
    privacy = payload.get("privacy", "public")
    force = payload.get("force", False)

    if not movie_id or episode_id is None:
        raise HTTPException(status_code=400, detail="movie_id and episode_id are required")

    try:
        res = publish_movie_episode(
            movie_id=movie_id,
            episode_id=int(episode_id),
            mp4_path=mp4_path,
            json_path=json_path,
            privacy_status=privacy,
            force=force
        )
        return res
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/playlists")
async def api_playlists(request: Request):
    """Returns the current playlists registry and pending playlist sync items."""
    require_auth(request)
    playlists = load_json_safe(PLAYLISTS_FILE)
    pending = load_json_safe(Path("/data/google-stories/pending_playlist_items.json"))
    return {
        "playlists": playlists,
        "pending_items": pending if isinstance(pending, list) else []
    }


@app.get("/api/youtube/auth-url")
async def api_youtube_auth_url(request: Request):
    """Generates the Google OAuth authorization URL for YouTube playlist management."""
    require_auth(request)
    client_secret_path = Path(DEDICATED_CLIENT_SECRETS)
    if not client_secret_path.exists():
        raise HTTPException(status_code=404, detail="Client secrets file not found")

    client_id = ""
    with open(client_secret_path) as f:
        cdata = json.load(f).get("installed", {})
        client_id = cdata.get("client_id", "")

    from urllib.parse import quote
    scopes_str = quote(" ".join(SCOPES))
    auth_url = (
        f"https://accounts.google.com/o/oauth2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri=http://localhost:8080/&"
        f"scope={scopes_str}&"
        f"response_type=code&"
        f"access_type=offline&"
        f"prompt=consent"
    )
    return {
        "auth_url": auth_url,
        "account": "solodigital.ltd@gmail.com",
        "channel": "Kidoory (@kidoorystory)",
        "scopes": SCOPES
    }


@app.post("/api/youtube/auth-code")
async def api_youtube_auth_code(request: Request, payload: dict):
    """Exchanges an authorization code or redirect URL to upgrade YouTube OAuth credentials."""
    require_auth(request)
    code_or_url = payload.get("code") or payload.get("code_or_url", "")
    if not code_or_url:
        raise HTTPException(status_code=400, detail="Authorization code or redirect URL is required")

    creds = exchange_code_for_token(code_or_url)
    if not creds:
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code with Google OAuth endpoint.")

    # Authenticate and sync any pending playlist items
    synced = 0
    try:
        from googleapiclient.discovery import build
        yt = build("youtube", "v3", credentials=creds)
        synced = sync_pending_playlist_items(yt)
    except Exception as e:
        pass

    return {
        "status": "ok",
        "message": f"YouTube credentials upgraded with playlist permissions! Synced {synced} pending playlist items."
    }


if __name__ == "__main__":
    import uvicorn
    port = int(config.get("PORT", 5009))
    uvicorn.run("kidoory_web:app", host="0.0.0.0", port=port, reload=False)
