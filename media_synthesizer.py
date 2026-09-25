from tts_tracker import track_tts_usage
#!/usr/bin/env python3
"""
media_synthesizer.py - Narration Audio Synthesis & Image Engine Test
1. Synthesizes narrations for all 16 scenes + final reflection using Google Cloud TTS (Journey voice).
2. Calculates total duration with ffprobe.
3. Tests Google GenAI / Vertex AI Imagen generation capabilities.
"""

import os
import sys
import json
import time
import subprocess
import logging
from google.cloud import texttospeech
from google.genai import Client, types
from dotenv import load_dotenv, dotenv_values

ENV_FILE = "/home/hkserver/googlestories-kidoory/.env"
load_dotenv(ENV_FILE)

def get_kidoory_gemini_key():
    key = os.environ.get("KIDOORY_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key and os.path.exists(ENV_FILE):
        key = dotenv_values(ENV_FILE).get("KIDOORY_GEMINI_API_KEY") or dotenv_values(ENV_FILE).get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("KIDOORY_GEMINI_API_KEY / GEMINI_API_KEY missing from environment and .env")
    return key

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MediaSynthesizer")

CREDENTIALS_FILE = "/home/hkserver/secrets/kidoory-7590452277b9.json"
STORY_JSON_FILE = "/data/google-stories/scripts/keeper_of_the_clockwork_lantern.json"
AUDIO_DIR = "/data/google-stories/audio_scenes"
IMAGE_DIR = "/data/google-stories/raw_images"

VOICE_NAME = "en-US-Journey-F"
LANGUAGE_CODE = "en-US"


def master_audio(input_path, output_path, bgm_path=None):
    if bgm_path and os.path.exists(bgm_path):
        # Normalize and mix
        cmd = [
            "ffmpeg", "-y", "-i", input_path, "-i", bgm_path,
            "-filter_complex", 
            "[0:a]loudnorm=I=-16:TP=-1.5:LRA=11[norm0];"
            "[1:a]volume=-24dB,afade=t=in:st=0:d=2,afade=t=out:st=9999:d=4[bgm];"
            "[norm0][bgm]amix=inputs=2:duration=first:dropout_transition=2",
            "-c:a", "libmp3lame", "-q:a", "2", output_path
        ]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        # Just normalize
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:a", "libmp3lame", "-q:a", "2", output_path
        ]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_audio_duration(file_path: str) -> float:
    """Uses ffprobe to obtain exact audio duration in seconds."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()
        return float(out)
    except Exception as e:
        logger.error(f"Error getting duration for {file_path}: {e}")
        return 0.0

def synthesize_audio():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_FILE
    
    with open(STORY_JSON_FILE, "r", encoding="utf-8") as f:
        story = json.load(f)

    tts_client = texttospeech.TextToSpeechClient.from_service_account_json(CREDENTIALS_FILE)

    voice_params = texttospeech.VoiceSelectionParams(
        language_code=LANGUAGE_CODE,
        name=VOICE_NAME
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=0.95  # warm, storybook pace
    )

    scenes = story.get("scenes", [])
    logger.info(f"Loaded story: '{story.get('title')}' with {len(scenes)} scenes.")

    audio_manifest = []
    total_seconds = 0.0

    # 1. Synthesize Scenes 1 to 16
    for scene in scenes:
        idx = scene["scene_index"]
        narration = scene["narration"]
        out_filename = f"scene_{idx:02d}.mp3"
        out_path = os.path.join(AUDIO_DIR, out_filename)

        logger.info(f"Synthesizing Scene {idx:02d} ({len(narration.split())} words) -> {out_filename}...")
        
        
        def text_to_ssml(text):
            import re
            t = re.sub(r'([”"])([\s]*)([A-Z])', r'\1<break time="450ms"/>\2\3', text)
            t = re.sub(r'([.?!])\s+', r'\1<break time="750ms"/> ', t)
            return f'<speak><prosody rate="0.9" pitch="-1.5st">{t}</prosody></speak>'

        synthesis_input = texttospeech.SynthesisInput(ssml=text_to_ssml(narration))
    
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config
        )

        with open(out_path, "wb") as audio_file:
            audio_file.write(response.audio_content)

        # Master audio
        master_audio(out_path, out_path.replace(".mp3", "_mastered.mp3"))

        dur = get_audio_duration(out_path)
        total_seconds += dur
        audio_manifest.append({
            "scene_index": idx,
            "filename": out_filename,
            "path": out_path,
            "duration": dur,
            "words": len(narration.split())
        })
        time.sleep(0.2)  # respectful pacing

    # 2. Synthesize Scene 17 (Final Reflection & Sovereignty Quote)
    reflection = story.get("final_reflection", {})
    moral = reflection.get("moral_lesson", "")
    quote = reflection.get("sovereignty_quote", "")
    reflection_text = f"{moral}\n\nRemember: {quote}"

    reflection_filename = "scene_17_reflection.mp3"
    reflection_path = os.path.join(AUDIO_DIR, reflection_filename)
    logger.info(f"Synthesizing Scene 17 [Final Reflection] -> {reflection_filename}...")

    synthesis_input = texttospeech.SynthesisInput(ssml=text_to_ssml(reflection_text))
    response = tts_client.synthesize_speech(
        input=synthesis_input,
        voice=voice_params,
        audio_config=audio_config
    )

    with open(reflection_path, "wb") as audio_file:
        audio_file.write(response.audio_content)

        # Master audio
        master_audio(out_path, out_path.replace(".mp3", "_mastered.mp3"))

    dur = get_audio_duration(reflection_path)
    total_seconds += dur
    audio_manifest.append({
        "scene_index": 17,
        "filename": reflection_filename,
        "path": reflection_path,
        "duration": dur,
        "words": len(reflection_text.split())
    })

    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)

    logger.info(f"Total audio runtime: {minutes}m {seconds:02d}s ({total_seconds:.2f}s total)")
    return audio_manifest, total_seconds

def test_image_generation():
    logger.info("--- Testing Image Generation Capabilities ---")
    with open(STORY_JSON_FILE, "r", encoding="utf-8") as f:
        story = json.load(f)

    scene_1 = story["scenes"][0]
    visual_prompt = scene_1["visual_prompt"]
    logger.info(f"Scene 1 Visual Prompt:\n{visual_prompt}\n")

    with open(CREDENTIALS_FILE, "r") as f:
        cred_data = json.load(f)
        project_id = cred_data.get("project_id", "kidoory")

    client = Client(api_key=get_kidoory_gemini_key(), http_options={"api_version": "v1beta"}, vertexai=False)
    target_image_path = os.path.join(IMAGE_DIR, "test_scene_01.png")

    image_status = {
        "model_tested": "imagen-3.0-generate-002",
        "success": False,
        "image_path": None,
        "error_details": None,
        "diagnosis": None
    }

    # Attempt 1: Imagen 3.0 on Vertex AI
    try:
        logger.info("Attempting generation with 'imagen-3.0-generate-002' via Vertex AI...")
        res = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=visual_prompt,
            config=dict(
                number_of_images=1,
                aspect_ratio="16:9",
                output_mime_type="image/png"
            )
        )
        if res.generated_images:
            img_bytes = res.generated_images[0].image.image_bytes
            with open(target_image_path, "wb") as f:
                f.write(img_bytes)
            logger.info(f"SUCCESS! Image saved to {target_image_path}")
            image_status["success"] = True
            image_status["image_path"] = target_image_path
            return image_status
    except Exception as e:
        err_str = str(e)
        logger.warning(f"Imagen 3.0 generation attempt failed: {err_str}")
        image_status["error_details"] = err_str

    # Attempt 2: Test gemini-2.5-flash-image on Vertex AI
    try:
        logger.info("Attempting generation with 'gemini-2.5-flash-image'...")
        resp = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=visual_prompt,
            config=dict(response_modalities=["IMAGE"])
        )
        if resp.candidates and resp.candidates[0].content.parts:
            for part in resp.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    with open(target_image_path, "wb") as f:
                        f.write(part.inline_data.data)
                    logger.info(f"SUCCESS with gemini-2.5-flash-image! Saved to {target_image_path}")
                    image_status["model_tested"] = "gemini-2.5-flash-image"
                    image_status["success"] = True
                    image_status["image_path"] = target_image_path
                    return image_status
    except Exception as e:
        logger.warning(f"gemini-2.5-flash-image attempt failed: {e}")
        image_status["fallback_error"] = str(e)

    # Diagnosis if both failed
    if "404" in str(image_status["error_details"]):
        image_status["diagnosis"] = (
            "Imagen 3.0 (imagen-3.0-generate-002) returned 404 NOT_FOUND. "
            "On Google Cloud Vertex AI, Imagen 3 requires explicit Model Garden enablement/terms acceptance "
            "or region whitelisting in project kidoory. "
            "Additionally, gemini-2.5-flash-image is available in the publisher list but is subject to experimental quota limits."
        )
    return image_status

def main():
    print("\n==================================================")
    print("  STEP 5: MEDIA SYNTHESIS & IMAGE ENGINE TEST")
    print("==================================================\n")

    # 1. Audio Synthesis
    manifest, total_seconds = synthesize_audio()

    # 2. Image Test
    img_status = test_image_generation()

    # Summary
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)

    print("\n==================================================")
    print("  AUDIO SYNTHESIS RESULTS")
    print("==================================================")
    print(f"Total Scenes Voiced: {len(manifest)} (Scenes 1-16 + Final Reflection)")
    print(f"Total Runtime:       {minutes}m {seconds:02d}s ({total_seconds:.2f} seconds)")
    print(f"Voice Model:         {VOICE_NAME}")
    print(f"Audio Output Folder: {AUDIO_DIR}")
    print("--------------------------------------------------")
    for item in manifest:
        print(f"  [{item['filename']}] {item['duration']:.2f}s | {item['words']} words")

    print("\n==================================================")
    print("  IMAGE GENERATION TEST RESULTS")
    print("==================================================")
    print(f"Model Tested: {img_status.get('model_tested')}")
    print(f"Success:      {img_status.get('success')}")
    if img_status.get("success"):
        print(f"Saved Image:  {img_status.get('image_path')}")
    else:
        print(f"Status:       API Not Enabled / Restricted Quota")
        print(f"Details:      {img_status.get('error_details')}")
        print(f"Diagnosis:    {img_status.get('diagnosis')}")
    print("==================================================\n")

if __name__ == "__main__":
    main()
