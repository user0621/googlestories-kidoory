import os
import json
import time
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, Response, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import dotenv_values

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


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def dashboard_index(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    state = load_json_safe(STATE_FILE)
    health = load_json_safe(HEALTH_FILE)
    tts_usage = load_json_safe(TTS_USAGE_FILE)
    upload_ledger = load_json_safe(UPLOAD_LEDGER_FILE)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "state": state,
        "health": health,
        "tts_usage": tts_usage,
        "upload_ledger": upload_ledger,
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
    # Check in movies or data dir
    candidate = MOVIES_DIR / path
    if not candidate.exists():
        candidate = DATA_DIR / path
    if candidate.exists() and candidate.is_file():
        return FileResponse(str(candidate), media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Video file not found")


if __name__ == "__main__":
    import uvicorn
    port = int(config.get("PORT", 5009))
    uvicorn.run("kidoory_web:app", host="0.0.0.0", port=port, reload=False)
