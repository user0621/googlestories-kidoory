"""Cloudflare Workers AI fallback for image generation.

Used when the primary Gemini image models fail to return image bytes. Runs the
free-tier-friendly Flux model on Cloudflare Workers AI. Reads credentials from
the environment (CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN), which
produce_story.py has already loaded from .env via load_dotenv.

Returns PNG bytes on success or None on any failure -- it never raises into the
caller, so it can be a safe drop-in fallback.
"""
import os
import io
import base64
import logging

logger = logging.getLogger(__name__)

FLUX_MODEL = "@cf/black-forest-labs/flux-1-schnell"


def cloudflare_configured() -> bool:
    return bool(os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN"))


def generate_image_cloudflare(prompt: str, steps: int = 6, timeout: int = 90):
    """Generate one image via Cloudflare Flux. Returns PNG bytes or None."""
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not account or not token:
        logger.warning("Cloudflare image fallback not configured (missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN).")
        return None
    if not prompt:
        return None

    try:
        import requests
        url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{FLUX_MODEL}"
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"prompt": prompt[:2048], "steps": max(1, min(int(steps), 8))},
            timeout=timeout,
        )
        if resp.status_code != 200:
            logger.error(f"Cloudflare Flux HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        if not data.get("success"):
            logger.error(f"Cloudflare Flux returned success=false: {data.get('errors')}")
            return None
        b64 = (data.get("result") or {}).get("image")
        if not b64:
            logger.error("Cloudflare Flux response contained no image field.")
            return None
        raw = base64.b64decode(b64)
    except Exception as e:
        logger.error(f"Cloudflare Flux fallback failed: {e}")
        return None

    # Flux returns JPEG; convert to PNG so it matches the pipeline's .png files.
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"Could not convert Flux image to PNG ({e}); using raw bytes.")
        return raw
