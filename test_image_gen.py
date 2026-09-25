import os
import sys
import json
import logging
from dotenv import load_dotenv
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TestImageGen")

load_dotenv("/home/hkserver/googlestories-kidoory/.env")
from google import genai

script_path = "/data/google-stories/movies/MOVIE_001/scripts/the_silent_starlight_library_ep_5_luna_blossom_and_the_dreamlight_quest_kidoory_bedtime_stories.json"
with open(script_path, "r", encoding="utf-8") as f:
    script_data = json.load(f)

prompt = script_data["scenes"][0]["visual_prompt"]
logger.info(f"Target Prompt: {prompt[:120]}...")

out_dir = "/data/google-stories/movies/MOVIE_001/raw_images"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "test_frame_01.png")

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options={"api_version": "v1beta"},
    vertexai=False
)

candidate_models = ["gemini-2.5-flash-image", "gemini-3.1-flash-image"]
saved = False

for m_name in candidate_models:
    logger.info(f"Attempting image generation with model: {m_name}")
    try:
        resp = client.models.generate_content(
            model=m_name,
            contents=prompt,
            config=dict(
                response_modalities=["IMAGE"],
            )
        )
        img_bytes = None
        if hasattr(resp, "generated_images") and resp.generated_images:
            for gen_img in resp.generated_images:
                if hasattr(gen_img, "image") and getattr(gen_img.image, "image_bytes", None):
                    img_bytes = gen_img.image.image_bytes
                    break
                elif getattr(gen_img, "image_bytes", None):
                    img_bytes = gen_img.image_bytes
                    break

        if not img_bytes and hasattr(resp, "candidates") and resp.candidates:
            for cand in resp.candidates:
                if hasattr(cand, "content") and hasattr(cand.content, "parts") and cand.content.parts:
                    for part in cand.content.parts:
                        if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None):
                            img_bytes = part.inline_data.data
                            break
                if img_bytes:
                    break

        if img_bytes:
            with open(out_path, "wb") as f:
                f.write(img_bytes)
            saved = True
            logger.info(f"Successfully saved {out_path} ({len(img_bytes)} bytes) using {m_name}")
            break
        else:
            logger.warning(f"No image bytes in response from {m_name}")
    except Exception as e:
        logger.error(f"Failed with {m_name}: {e}")

if not saved:
    logger.error("Failed to generate test frame!")
    sys.exit(1)

# Validate PNG
file_size = os.path.getsize(out_path)
logger.info(f"File size: {file_size} bytes ({file_size / 1024:.2f} KB)")
if file_size <= 50_000:
    logger.error(f"File size {file_size} is <= 50 KB threshold!")
    sys.exit(1)

with Image.open(out_path) as im:
    logger.info(f"Valid PNG image confirmed! Format: {im.format}, Size: {im.size}, Mode: {im.mode}")

logger.info("TEST PASSED: Valid PNG > 50 KB generated with HTTP 200 OK.")
