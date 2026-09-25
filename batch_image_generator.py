#!/usr/bin/env python3
"""
batch_image_generator.py - Batch Visual Synthesis for Google Stories
Generates frames scene_01.png to scene_17.png using gemini-2.5-flash-image on Vertex AI.
Includes retry logic, exponential backoff for rate limits, and progress reporting.
"""

import os
import sys
import json
import time
import logging
from google.genai import Client
from pipeline_journal import find_existing_image, is_valid_asset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BatchImageGen")

CREDENTIALS_FILE = "/home/hkserver/secrets/kidoory-7590452277b9.json"
STORY_JSON_FILE = "/data/google-stories/scripts/keeper_of_the_clockwork_lantern.json"
IMAGE_DIR = "/data/google-stories/raw_images"
MODEL_NAME = "gemini-2.5-flash-image"

SCENE_17_PROMPT = (
    "Masterpiece 3D children's storybook illustration in the heartwarming style of modern Pixar and Studio Ghibli, 8k resolution, dreamy volumetric golden-hour lighting, cozy magical atmosphere, rich vibrant color palette, endearing character design with large soft expressive eyes, award-winning concept art, trending on ArtStation. "
    "A glorious panoramic sunrise view from Mount Solarium overlooking Cogsworth Valley. "
    "The Great Clockwork Sun radiates warm, gentle golden light and soft celestial god-rays across "
    "emerald pine forests and mountain mists. On a sunlit rocky promontory, 12-year-old Leo (curly auburn hair, "
    "aviator goggles, patched teal coat) sits peacefully beside the gentle Woolly Mist-Bison and the gleaming white Frost-Fox. "
    "Pip the tiny brass firefly hovers near Leo's shoulder, glowing with joyful golden warmth. "
    "Peaceful, awe-inspiring, heartwarming atmosphere, rich textures, 8k resolution."
)

def generate_all_images():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_FILE
    with open(CREDENTIALS_FILE, "r") as f:
        cred = json.load(f)
        project_id = cred.get("project_id", "kidoory")

    client = Client(api_key=os.environ["GEMINI_API_KEY"], http_options={"api_version": "v1beta"}, vertexai=False)

    with open(STORY_JSON_FILE, "r", encoding="utf-8") as f:
        story = json.load(f)

    # Collect prompts for scenes 1 to 17
    scenes_to_render = []
    for s in story.get("scenes", []):
        scenes_to_render.append((s["scene_index"], s["visual_prompt"]))
    scenes_to_render.append((17, SCENE_17_PROMPT))

    os.makedirs(IMAGE_DIR, exist_ok=True)
    logger.info(f"Starting Visual Batch Synthesis: {len(scenes_to_render)} scenes target.")

    success_count = 0
    for idx, prompt in scenes_to_render:
        existing = find_existing_image(IMAGE_DIR, "keeper_of_the_clockwork_lantern", idx, min_bytes=1000)
        out_path = existing if existing else os.path.join(IMAGE_DIR, f"scene_{idx:02d}.png")

        # Check if already exists and valid (> 0 bytes)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            logger.info(f"[Scene {idx:02d}/17] Already exists ({os.path.getsize(out_path)/1024:.1f} KB at {out_path}). Skipping generation.")
            success_count += 1
            continue

        logger.info(f"[Scene {idx:02d}/17] Synthesizing frame...")
        max_retries = 6
        base_backoff = 10

        saved = False
        for attempt in range(max_retries):
            try:
                start_t = time.time()
                resp = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=prompt
                )
                if resp.candidates and resp.candidates[0].content.parts:
                    for part in resp.candidates[0].content.parts:
                        if getattr(part, "inline_data", None) and part.inline_data.data:
                            with open(out_path, "wb") as f_out:
                                f_out.write(part.inline_data.data)
                            elapsed = time.time() - start_t
                            logger.info(f"[Scene {idx:02d}/17] Successfully saved to {out_path} ({os.path.getsize(out_path)/1024:.1f} KB in {elapsed:.1f}s)")
                            saved = True
                            success_count += 1
                            break
                if saved:
                    time.sleep(5.5)  # Spacing between calls to eliminate 429s
                    break
                else:
                    logger.warning(f"[Scene {idx:02d}/17] No inline image data received on attempt {attempt+1}.")
            except Exception as e:
                err_str = str(e)
                wait_time = base_backoff * (attempt + 1)
                logger.warning(f"[Scene {idx:02d}/17] Attempt {attempt+1}/{max_retries} failed: {err_str[:120]}. Backing off {wait_time}s...")
                time.sleep(wait_time)

        if not saved:
            logger.error(f"[Scene {idx:02d}/17] FAILED to generate after {max_retries} attempts.")
            sys.exit(1)

    logger.info(f"Visual Batch Synthesis COMPLETE! {success_count}/17 frames ready in {IMAGE_DIR}.")

if __name__ == "__main__":
    generate_all_images()
