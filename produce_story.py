from tts_tracker import track_tts_usage, check_budget, record_usage
#!/usr/bin/env python3
"""
produce_story.py - Autonomous One-Click Master Pipeline Launcher
Generates, narrates, illustrates, edits, and verifies a complete 1080p story video.

Usage:
    python produce_story.py --title "The Clockwork Forest" --theme "Ancient automatons and forest spirits"
"""

import os
import re
import sys
import json
import time
from datetime import datetime
try:
    os.nice(10)
except Exception:
    pass

import random
import argparse
import subprocess
import shutil
import logging
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from PIL import Image, ImageStat
from google.cloud import texttospeech
from google import genai
from google.genai import types
from pipeline_journal import JobJournal, find_existing_audio, find_existing_image, is_valid_asset
from languages import get_language, get_font_for_language
from dotenv import load_dotenv, dotenv_values

ENV_FILE = "/home/hkserver/googlestories-kidoory/.env"
load_dotenv(ENV_FILE)

try:
    from usage_tracker import record_gemini_request
except Exception:
    def record_gemini_request(kind="text"):
        pass

try:
    from cloudflare_fallback import generate_image_cloudflare
except Exception:
    def generate_image_cloudflare(prompt, steps=6, timeout=90):
        return None

def get_kidoory_gemini_key():
    key = os.environ.get("KIDOORY_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key and os.path.exists(ENV_FILE):
        key = dotenv_values(ENV_FILE).get("KIDOORY_GEMINI_API_KEY") or dotenv_values(ENV_FILE).get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("KIDOORY_GEMINI_API_KEY / GEMINI_API_KEY missing from environment and .env")
    return key

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ProduceStory")

def execute_with_backoff(func, max_retries: int = 3, base_wait: float = 3.0, max_wait: float = 45.0, op_name: str = "Gemini API"):
    """Executes a callable with exponential backoff and jitter on HTTP 429 / rate limits."""
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            err_str = str(e)
            is_rate_limit = any(code in err_str for code in ["429", "RESOURCE_EXHAUSTED", "rateLimitExceeded", "quota"]) or "rate limit" in err_str.lower()
            if is_rate_limit and attempt < max_retries:
                sleep_s = min(max_wait, (base_wait * (2 ** attempt)) + random.uniform(1.0, 3.0))
                logger.warning(f"[{op_name}] HTTP 429 / Rate Limit encountered (attempt {attempt+1}/{max_retries}). Retrying in {sleep_s:.2f}s... ({err_str[:90]})")
                time.sleep(sleep_s)
            else:
                raise

# Pydantic Schemas
class Scene(BaseModel):
    scene_index: int = Field(description="1-based scene index.")
    title: str = Field(description="Short title for this scene beat.")
    narration: str = Field(description="Warm storybook narration, strictly 60 to 80 words.")
    visual_prompt: str = Field(description="Cinematic Pixar/Studio Ghibli visual description with consistent character design, lighting, and palette.")
    choice_options: List[str] = Field(default_factory=list, description="3 distinct possible choices for the character.")
    chosen_option: str = Field(description="Selected choice honoring compassion, ingenuity, and resonance.")
    choice_reasoning: str = Field(description="Reasoning for selecting this choice.")

class FinalReflection(BaseModel):
    moral_lesson: str = Field(description="Central moral lesson.")
    sovereignty_quote: str = Field(description="Memorable quote on inner sovereignty and courage.")

class StoryDocument(BaseModel):
    title: str
    english_title: Optional[str] = None
    
    language: Optional[str] = "en"
    language_code: Optional[str] = "en"
    language_name: str = "English"
    theme: str
    total_scenes: int
    total_word_count: int
    scenes: List[Scene]
    final_reflection: FinalReflection

def slugify(text: str, fallback: str = "") -> str:
    s = re.sub(r'[^a-zA-Z0-9_\-\s]', '', text).strip().lower()
    res = re.sub(r'[\s\-]+', '_', s)
    if res:
        return res
    if fallback:
        s_fb = re.sub(r'[^a-zA-Z0-9_\-\s]', '', fallback).strip().lower()
        res_fb = re.sub(r'[\s\-]+', '_', s_fb)
        if res_fb:
            return res_fb
    return f"story_{int(time.time())}"

def format_ass_time(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = min(99, int(round((seconds - int(seconds)) * 100)))
    return f"{hrs:d}:{mins:02d}:{secs:02d}.{centis:02d}"

def wrap_text(text: str, max_chars: int = 52) -> str:
    words = text.split()
    lines, curr, curr_len = [], [], 0
    for w in words:
        if curr_len + len(w) + (1 if curr else 0) > max_chars:
            lines.append(" ".join(curr))
            curr = [w]
            curr_len = len(w)
        else:
            curr.append(w)
            curr_len += len(w) + (1 if curr_len > 0 else 0)
    if curr:
        lines.append(" ".join(curr))
    return "\\N".join(lines)

class StoryPipeline:
    def __init__(self, title: str, theme: str, scenes: int, voice: str = "", base_dir: str = "/data/google-stories", creds: str = "/home/hkserver/secrets/kidoory-7590452277b9.json", english_title: str = ""):
        self.title = title
        self.english_title = english_title
        self.theme = theme
        self.num_scenes = scenes
        self.base_dir = base_dir
        self.creds_file = creds

        self.lang_info = get_language()
        self.language_code = self.lang_info["code"]
        self.language_name = self.lang_info["name"]
        self.tts_lang_code = self.lang_info["language_code"]
        self.font_family = self.lang_info["font"]

        if voice and voice.lower().startswith(self.language_code.lower() + "-"):
            self.voice_name = voice
        elif voice and self.language_code.lower() == "en" and voice.lower().startswith("en-"):
            self.voice_name = voice
        else:
            self.voice_name = self.lang_info["voice"]

        self.slug = slugify(self.english_title or self.title, fallback=self.title)

        self.scripts_dir = os.path.join(base_dir, "scripts")
        self.audio_dir = os.path.join(base_dir, "audio_scenes")
        self.images_dir = os.path.join(base_dir, "raw_images")
        today_date_str = datetime.now().strftime("%d%b%Y")
        self.final_dir = os.path.join(base_dir, "unposted", today_date_str)
        self.temp_dir = os.path.join(base_dir, "temp_segments", self.slug)

        for d in [self.scripts_dir, self.audio_dir, self.images_dir, self.final_dir, self.temp_dir]:
            os.makedirs(d, exist_ok=True)

        if os.path.exists(self.creds_file):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.creds_file
            self.tts_client = texttospeech.TextToSpeechClient.from_service_account_json(self.creds_file)
        else:
            self.tts_client = texttospeech.TextToSpeechClient()

        api_key = get_kidoory_gemini_key()
        self.genai_client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})

        self.journal = JobJournal()
        self.journal_data, self.is_resumed = self.journal.start_or_resume(title, theme, scenes, self.slug)

    def run_stage_scripting(self) -> StoryDocument:
        logger.info(f"=== STAGE 1: Autonomous Story Scripting ({self.num_scenes} scenes, Language: {self.language_name}) ===")
        self.journal.update_stage("scripting")
        script_file = os.path.join(self.scripts_dir, f"{self.slug}.json")
        if os.path.exists(script_file) and os.path.getsize(script_file) > 100:
            logger.info(f"Found existing script file: {script_file}. Loading...")
            with open(script_file, "r", encoding="utf-8") as f:
                doc = StoryDocument(**json.load(f))
            self.journal.mark_script_done(script_file)
            return doc

        director_prompt = f"""You are the Autonomous Story Director and Master Screenwriter for a world-class children's bedtime story studio.
Generate an enchanting {self.num_scenes}-scene episodic bedtime story titled '{self.title}' on the theme: '{self.theme}'.

LANGUAGE & SCRIPT MANDATE:
- Target Language: {self.language_name} ({self.lang_info['native_name']})
- Script: {self.lang_info['script']}
- {self.lang_info['prompt_instruction']}
- CRITICAL: Write the 'title', scene 'title's, 'narration's, 'choice_options', 'chosen_option', 'choice_reasoning', 'moral_lesson', and 'sovereignty_quote' NATIVELY in {self.language_name} using the {self.lang_info['script']} script! Do NOT transliterate into English Latin letters.
- Bedtime Pacing: The narration must be warm, soothing, poetic, gentle, and calming—perfect for bedtime listening.
- English Title: Provide a clean English translation of the story title in 'english_title' (3-6 words) for file slug and tracking.
- Set 'language' to '{self.language_code}' and 'language_name' to '{self.language_name}'.

VISUAL PROMPT MANDATE (CRITICAL):
- 'visual_prompt' for each scene MUST be in DETAILED ENGLISH to guide the image generation model (gemini-2.5-flash-image).
- Blend the visual splendor and environmental reverence of Studio Ghibli (painterly backdrops, clouds, water, ancient mossy machines) with the emotional character expressiveness of Pixar.
- Maintain strict character, setting, lighting, and palette consistency across all scenes.

CRITICAL RULES:
1. Generate exactly {self.num_scenes} sequential scenes.
2. For each scene, 'narration' MUST be warm, evocative storybook prose strictly between 60 and 80 words. The total story length MUST be 450 to 600 words. Narrative structure: Gentle protagonist discovery -> magical world element -> heartwarming act of kindness/courage -> serene, sleep-inducing ending.
3. 'visual_prompt' must describe visuals using EXACTLY: 'Masterpiece 3D children's storybook illustration in the heartwarming style of modern Pixar and Studio Ghibli, 8k resolution, dreamy volumetric golden-hour lighting, cozy magical atmosphere, rich vibrant color palette, endearing character design with large soft expressive eyes, award-winning concept art, trending on ArtStation.' Negative constraints to include: 'Exclude photorealistic human skin pores, uncanny valley facial distortion, creepy horror elements, dark grim aesthetics, text, watermarks, bad anatomy, deformed limbs.'
4. 'choice_options' has 3 compelling branches. The Auto-Director automatically selects 'chosen_option' and explains 'choice_reasoning' honoring compassion, ingenuity, and emotional resonance over force.
5. Create a profound 'final_reflection' with a 'moral_lesson' and 'sovereignty_quote' in {self.language_name}.
"""
        def _gen_story_doc():
            return self.genai_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=director_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=StoryDocument,
                    temperature=0.7,
                )
            )
        response = execute_with_backoff(_gen_story_doc, max_retries=3, op_name="Story Scripting")
        record_gemini_request("text")
        story_doc: StoryDocument = response.parsed
        story_doc.total_word_count = sum(len(s.narration.split()) for s in story_doc.scenes)
        story_doc.language = self.language_code
        story_doc.language_code = self.language_code
        story_doc.language_name = self.language_name
        if not story_doc.english_title and self.english_title:
            story_doc.english_title = self.english_title

        doc_dict = story_doc.model_dump()
        doc_dict["language"] = self.language_code
        doc_dict["language_code"] = self.language_code
        doc_dict["language_name"] = self.language_name
        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(doc_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"Script saved to {script_file} ({story_doc.total_word_count} total words).")
        return story_doc

    def run_stage_audio(self, story: StoryDocument) -> List[tuple]:
        logger.info(f"=== STAGE 2: Cloud TTS Audio Synthesis ({self.language_name}: {self.voice_name}) ===")
        self.journal.update_stage("audio_synthesis")
        voice_params = texttospeech.VoiceSelectionParams(language_code=self.tts_lang_code, name=self.voice_name)
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=0.92)

        audio_files = []
        for s in story.scenes:
            idx = s.scene_index
            existing = find_existing_audio(self.audio_dir, self.slug, idx)
            if existing:
                logger.info(f"[Audio Scene {idx:02d}] Existing valid audio found: {existing} ({os.path.getsize(existing)} bytes). Skipping API call.")
                self.journal.record_audio_scene(idx, existing)
                audio_files.append((idx, existing, s.narration))
                continue

            out_file = os.path.join(self.audio_dir, f"{self.slug}_scene_{idx:02d}.mp3")
            logger.info(f"Synthesizing Audio Scene {idx:02d} ({self.tts_lang_code})...")
            chars_needed = len(s.narration)
            ok, reason = check_budget(chars_needed)
            if not ok:
                raise RuntimeError(f"[CIRCUIT BREAKER] Kidoory paused: {reason}. $0.00 guarantee preserved.")

            resp = self.tts_client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=s.narration),
                voice=voice_params,
                audio_config=audio_config
            )
            record_usage(chars_needed)
            with open(out_file, "wb") as f:
                f.write(resp.audio_content)
            time.sleep(0.15)
            self.journal.record_audio_scene(idx, out_file)
            audio_files.append((idx, out_file, s.narration))

        # Final Reflection
        refl = story.final_reflection
        refl_text = f"{refl.moral_lesson}\n\n{refl.sovereignty_quote}"
        refl_idx = len(story.scenes) + 1
        existing_refl = find_existing_audio(self.audio_dir, self.slug, refl_idx) or find_existing_audio(self.audio_dir, self.slug, 17)
        if existing_refl:
            logger.info(f"[Audio Reflection] Existing valid audio found: {existing_refl} ({os.path.getsize(existing_refl)} bytes). Skipping API call.")
            self.journal.record_audio_scene(refl_idx, existing_refl)
            audio_files.append((refl_idx, existing_refl, refl_text))
        else:
            refl_file = os.path.join(self.audio_dir, f"{self.slug}_scene_{refl_idx:02d}_reflection.mp3")
            logger.info(f"Synthesizing Final Reflection Audio ({self.tts_lang_code})...")
            chars_needed = len(refl_text)
            ok, reason = check_budget(chars_needed)
            if not ok:
                raise RuntimeError(f"[CIRCUIT BREAKER] Kidoory paused: {reason}. $0.00 guarantee preserved.")

            resp = self.tts_client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=refl_text),
                voice=voice_params,
                audio_config=audio_config
            )
            record_usage(chars_needed)
            with open(refl_file, "wb") as f:
                f.write(resp.audio_content)
            self.journal.record_audio_scene(refl_idx, refl_file)
            audio_files.append((refl_idx, refl_file, refl_text))

        logger.info(f"All {len(audio_files)} audio tracks ready.")
        return audio_files

    def run_stage_visuals(self, story: StoryDocument) -> List[tuple]:
        logger.info(f"=== STAGE 3: Visual Generation with gemini-2.5-flash-image (8 Anchor Visual Scenes) ===")
        self.journal.update_stage("visual_synthesis")
        visual_files = []

        # Exactly the 8 anchor scene prompts from story.scenes
        prompts = [(s.scene_index, s.visual_prompt) for s in story.scenes]

        for idx, prompt in prompts:
            existing = find_existing_image(self.images_dir, self.slug, idx)
            if existing:
                logger.info(f"[Anchor Visual {idx:02d}] Existing valid image found: {existing} ({os.path.getsize(existing)} bytes). Skipping API call.")
                self.journal.record_visual_scene(idx, existing)
                visual_files.append((idx, existing))
                continue

            out_img = os.path.join(self.images_dir, f"{self.slug}_scene_{idx:02d}.png")
            logger.info(f"Generating Anchor Visual {idx:02d} via Google AI Studio...")
            saved = False

            candidate_models = ["gemini-2.5-flash-image", "gemini-3.1-flash-image"]
            last_err = None

            for m_name in candidate_models:
                def _call_img():
                    return self.genai_client.models.generate_content(
                        model=m_name,
                        contents=prompt,
                        config=dict(
                            response_modalities=["IMAGE"],
                        )
                    )

                try:
                    resp = execute_with_backoff(_call_img, max_retries=3, base_wait=4.0, op_name=f"Anchor Visual {idx:02d} ({m_name})")
                    record_gemini_request("image")
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
                        with open(out_img, "wb") as f:
                            f.write(img_bytes)
                        saved = True
                        logger.info(f"[Anchor Visual {idx:02d}] Successfully generated and saved to {out_img} ({len(img_bytes)} bytes) using {m_name}")
                        time.sleep(5.5)
                        break
                    else:
                        logger.warning(f"[Anchor Visual {idx:02d}] Response from {m_name} did not contain image bytes. Candidates: {getattr(resp, 'candidates', None)}")
                except Exception as e:
                    last_err = e
                    logger.error(f"[Anchor Visual {idx:02d}] Model {m_name} failed: {e}")

            if not saved:
                logger.warning(f"[Anchor Visual {idx:02d}] All Gemini image models failed ({last_err}). Trying Cloudflare Workers AI (Flux) fallback...")
                cf_bytes = generate_image_cloudflare(prompt)
                if cf_bytes:
                    with open(out_img, "wb") as f:
                        f.write(cf_bytes)
                    saved = True
                    logger.info(f"[Anchor Visual {idx:02d}] Cloudflare Flux fallback succeeded, saved to {out_img} ({len(cf_bytes)} bytes)")

            if not saved:
                logger.error(f"[Anchor Visual {idx:02d}] All candidate models AND Cloudflare fallback failed. Last error: {last_err}")
                raise RuntimeError(f"Failed to generate frame {idx:02d}: {last_err}")
            self.journal.record_visual_scene(idx, out_img)
            visual_files.append((idx, out_img))

        # Reflection segment maps to the concluding anchor visual frame
        refl_idx = len(story.scenes) + 1
        if visual_files:
            visual_files.append((refl_idx, visual_files[-1][1]))
            if refl_idx != 17:
                visual_files.append((17, visual_files[-1][1]))

        logger.info(f"All anchor visual frames ready ({len(prompts)} generated, {len(visual_files)} mapped).")
        return visual_files

    def run_stage_assembly(self, audio_data: List[tuple], visual_data: List[tuple]) -> str:
        logger.info("=== STAGE 4: Master Video Assembly ===")
        self.journal.update_stage("video_assembly")
        safe_title = self.title.replace(' ', '_').replace('/', '_')
        master_mp4 = os.path.join(self.final_dir, f"{safe_title}.mp4")

        segments = []
        vis_map = {idx: path for idx, path in visual_data}

        for idx, aud_path, narration in audio_data:
            img_path = vis_map[idx]
            seg_mp4 = os.path.join(self.temp_dir, f"segment_{idx:02d}.mp4")
            ass_path = os.path.join(self.temp_dir, f"segment_{idx:02d}.ass")

            if os.path.exists(seg_mp4) and os.path.getsize(seg_mp4) > 100_000:
                logger.info(f"[Segment {idx:02d}] Reusing existing rendered video segment: {seg_mp4} ({os.path.getsize(seg_mp4)} bytes).")
                self.journal.record_segment(idx, seg_mp4)
                segments.append(seg_mp4)
                continue

            # Duration
            out = subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", aud_path
            ]).decode().strip()
            duration = float(out)
            total_frames = int(round(duration * 30))

            # ASS subtitles with Indic punctuation & dynamic font support
            raw_sents = [s.strip() for s in re.split(r'(?<=[.!?।॥])\s+', narration.strip()) if s.strip()] or [narration]
            weights = [max(1, len(s.split())) for s in raw_sents]
            tot_w = sum(weights)
            usable = max(1.0, duration - 0.8)

            font_name = "Poppins"

            events = []
            cur_t = 0.4
            for s, w in zip(raw_sents, weights):
                d_s = (w / tot_w) * usable
                events.append(f"Dialogue: 0,{format_ass_time(cur_t)},{format_ass_time(cur_t + d_s)},Default,,0,0,0,,{wrap_text(s)}")
                cur_t += d_s

            ass_text = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},38,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3.0,2.0,2,100,100,65,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(events) + "\n"

            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_text)

            # Ken Burns
            var = idx % 4
            if var == 0:
                zp = f"z='min(zoom+0.0005,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1920x1080:fps=30"
            elif var == 1:
                zp = f"z='1.12':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/{total_frames})':d={total_frames}:s=1920x1080:fps=30"
            elif var == 2:
                zp = f"z='if(lte(zoom,1.0),1.15,max(1.001,zoom-0.0005))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1920x1080:fps=30"
            else:
                zp = f"z='1.12':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(on/{total_frames})':d={total_frames}:s=1920x1080:fps=30"

            filter_c = f"[0:v]scale=2160:2160,zoompan={zp},ass='{ass_path}',format=yuv420p[v]"
            cmd = [
                "ffmpeg", "-y", "-threads", "4", "-loop", "1", "-t", f"{duration:.3f}",
                "-i", img_path, "-i", aud_path,
                "-filter_complex", filter_c,
                "-map", "[v]", "-map", "1:a",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k", "-shortest",
                seg_mp4
            ]
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.journal.record_segment(idx, seg_mp4)
            segments.append(seg_mp4)

        # Concat
        list_txt = os.path.join(self.temp_dir, "concat.txt")
        with open(list_txt, "w", encoding="utf-8") as f:
            for s in segments:
                f.write(f"file '{s}'\n")

        subprocess.check_call([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_txt, "-c", "copy", master_mp4
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        logger.info(f"Master Video successfully created: {master_mp4}")

        # Save metadata JSON directly to final_videos alongside MP4
        final_json = os.path.join(self.final_dir, f"{safe_title}.json")
        script_file = os.path.join(self.scripts_dir, f"{self.slug}.json")
        if os.path.exists(script_file):
            try:
                with open(script_file, "r", encoding="utf-8") as sf:
                    meta_content = json.load(sf)
                meta_content["title"] = self.title
                if self.english_title:
                    meta_content["english_title"] = self.english_title
                meta_content["language"] = self.language_code
                meta_content["language_code"] = self.language_code
                meta_content["language_name"] = self.language_name
                with open(final_json, "w", encoding="utf-8") as ff:
                    json.dump(meta_content, ff, indent=2, ensure_ascii=False)
                logger.info(f"Master Metadata JSON saved to: {final_json}")
            except Exception as e:
                logger.warning(f"Error enriching metadata JSON ({e}), copying raw")
                shutil.copy2(script_file, final_json)

        if self.slug and self.slug != safe_title:
            slug_mp4 = os.path.join(self.final_dir, f"{self.slug}.mp4")
            try:
                if not os.path.exists(slug_mp4):
                    os.symlink(master_mp4, slug_mp4)
            except Exception:
                pass

        return master_mp4

    def run_stage_verification(self, master_mp4: str) -> bool:
        logger.info("=== STAGE 5: Production Verification ===")
        self.journal.update_stage("verification")
        # Verify streams
        out = subprocess.check_output([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", master_mp4
        ]).decode()
        data = json.loads(out)
        v_dur = float(next(s for s in data["streams"] if s["codec_type"] == "video")["duration"])
        a_dur = float(next(s for s in data["streams"] if s["codec_type"] == "audio")["duration"])
        sync_ok = abs(v_dur - a_dur) <= 0.10

        # Decode
        dec_res = subprocess.run(["ffmpeg", "-v", "error", "-i", master_mp4, "-f", "null", "-"], stderr=subprocess.PIPE)
        no_corrupt = (dec_res.returncode == 0 and len(dec_res.stderr.strip()) == 0)

        # QC frame
        qc_png = os.path.join(self.temp_dir, "qc.png")
        subprocess.check_call(["ffmpeg", "-y", "-ss", f"{v_dur/2:.2f}", "-i", master_mp4, "-vframes", "1", qc_png],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with Image.open(qc_png) as img:
            lum = ImageStat.Stat(img.convert("L")).mean[0]
            geom_ok = (img.size == (1920, 1080))

        logger.info(f"Verification Results: Sync={sync_ok}, NoCorruption={no_corrupt}, 1080p={geom_ok}, Mid-Luma={lum:.1f}")
        ok = sync_ok and no_corrupt and geom_ok
        self.journal.complete_job(master_mp4, ok)
        return ok

def main():
    parser = argparse.ArgumentParser(description="Autonomous Story Video Producer")
    parser.add_argument("--title", type=str, default="", help="Story Title")
    parser.add_argument("--english-title", type=str, default="", help="Story English Title (translation for slugs)")
    parser.add_argument("--disabled_language", type=str, default="en", help="Language code or name (en, hi, pa, fr, es)")
    parser.add_argument("--theme", type=str, default="", help="Story Theme / Premise")
    parser.add_argument("--scenes", type=int, default=8, help="Number of scenes (default: 8)")
    parser.add_argument("--voice", type=str, default="", help="Google Cloud TTS voice (default: auto per language)")
    parser.add_argument("--base-dir", type=str, default="/data/google-stories", help="Storage directory on SanDisk drive")
    parser.add_argument("--credentials", type=str, default="/home/hkserver/secrets/kidoory-7590452277b9.json", help="Path to GCP credentials")
    parser.add_argument("--resume", action="store_true", help="Resume unfinished job from current_job.json")
    args = parser.parse_args()

    # Check for unfinished job resumption
    if args.resume or (not args.title and not args.theme):
        unfinished = JobJournal.get_unfinished_job()
        if unfinished:
            logger.info(f"Auto-resuming unfinished job from journal: '{unfinished['title']}' at stage '{unfinished.get('stage')}'")
            args.title = unfinished["title"]
            args.theme = unfinished.get("theme", "")
            args.scenes = unfinished.get("total_scenes", args.scenes)
            
            args.english_title = unfinished.get("english_title", args.english_title)
        elif not args.title:
            parser.error("No active unfinished job found. Please specify --title and --theme.")

    pipeline = StoryPipeline(
        title=args.title,
        english_title=args.english_title,
        
        theme=args.theme,
        scenes=args.scenes,
        voice=args.voice,
        base_dir=args.base_dir,
        creds=args.credentials
    )

    story = pipeline.run_stage_scripting()
    audio_data = pipeline.run_stage_audio(story)
    visual_data = pipeline.run_stage_visuals(story)
    master_mp4 = pipeline.run_stage_assembly(audio_data, visual_data)
    ok = pipeline.run_stage_verification(master_mp4)

    print("\n" + "="*50)
    print(f"  PRODUCTION PIPELINE COMPLETED")
    print(f"  Title:     {args.title}")
    print(f"  Language:  {pipeline.language_name} ({pipeline.language_code})")
    print(f"  Output:    {master_mp4}")
    print(f"  Size:      {os.path.getsize(master_mp4)/(1024*1024):.2f} MB")
    print(f"  QC Status: {'PASSED (Ready for Distribution)' if ok else 'WARNING: QC ISSUES'}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
