#!/usr/bin/env python3
"""
idea_brain.py - Autonomous Story Idea Generator & Concept Brain
Uses Gemini 2.5 Flash on Vertex AI to generate 100% original, virtuous,
and evocative story concepts while tracking history to prevent duplication.

Virtues grounded in: wonder, patience, courage, quiet resilience, nature,
companionship, and mechanical or mythical discovery.
"""

import os
import sys
import json
import logging
import random
import argparse
from datetime import datetime, timezone
from typing import List, Optional, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from languages import get_language

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

try:
    os.nice(10)
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("IdeaBrain")

DEFAULT_CREDS = "/home/hkserver/secrets/kidoory-7590452277b9.json"
DEFAULT_HISTORY_FILE = "/data/google-stories/history.json"
DEFAULT_BASE_DIR = "/data/google-stories"


class StoryConcept(BaseModel):
    title: str = Field(description="Evocative, memorable children's story title (3-6 words) written natively in the target language and script.")
    english_title: str = Field(default="", description="Clean English translation of the story title (3-6 words) for file slug and tracking.")
    language: str = Field(default="en", description="Language code (en).")
    language_code: str = Field(default="en-US", description="Language code (en-US).")
    language_name: str = Field(default="English", description="Full language name.")
    theme: str = Field(description="Rich narrative premise and episodic quest summary (2-3 sentences) detailing the journey, key discovery, and emotional heart.")
    virtues: List[str] = Field(description="2-4 core virtues grounded in wonder, patience, courage, quiet resilience, nature, or companionship.")
    motifs: List[str] = Field(description="3-6 unique motifs, artifacts, or mythical/mechanical elements that distinguish this story.")
    protagonist: str = Field(description="Name and brief description of the young hero or apprentice.")
    companion: str = Field(description="Name and brief description of the loyal animal, automaton, or elemental companion.")
    visual_mood: str = Field(description="Masterpiece 3D children's storybook illustration in the heartwarming style of modern Pixar and Studio Ghibli, 8k resolution, dreamy volumetric golden-hour lighting, cozy magical atmosphere, rich vibrant color palette, endearing character design with large soft expressive eyes, award-winning concept art, trending on ArtStation. HARD NEGATIVE: Exclude photorealistic human skin pores, uncanny valley facial distortion, creepy horror elements, dark grim aesthetics, text, watermarks, bad anatomy, deformed limbs.")
    setting: str = Field(description="The unique world, mountain, sea, or enchanted environment.")


class StoryConceptBatch(BaseModel):
    concepts: List[StoryConcept] = Field(description="List of distinct, unique story concepts.")


def load_history(history_file: str) -> dict:
    """Load or initialize the story history JSON."""
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "last_language_index" not in data:
                    data["last_language_index"] = 0
                return data
        except Exception as e:
            logger.warning(f"Error reading history file ({e}), creating fresh template.")

    return {
        "version": 1,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "last_language_index": 0,
        "stories": [],
        "past_titles": [],
        "past_motifs": []
    }


def save_history(history_file: str, data: dict):
    """Save updated history to disk atomically."""
    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    tmp_file = history_file + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_file, history_file)
    logger.info(f"Updated history saved to {history_file} ({len(data.get('stories', []))} total entries).")


def seed_existing_stories(history_file: str, base_dir: str):
    """Seed existing completed stories from disk if not already in history."""
    data = load_history(history_file)
    existing_titles = {s.get("title") for s in data.get("stories", [])}

    scripts_dir = os.path.join(base_dir, "scripts")
    final_dir = os.path.join(base_dir, "final_videos")

    if os.path.exists(scripts_dir):
        for fname in os.listdir(scripts_dir):
            if fname.endswith(".json") and not fname.startswith("history"):
                fpath = os.path.join(scripts_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        s_data = json.load(f)
                    title = s_data.get("title")
                    if title and title not in existing_titles:
                        candidates = [
                            os.path.join(final_dir, f"{title.replace(' ', '_')}.mp4"),
                            os.path.join(final_dir, f"{title[4:].replace(' ', '_')}.mp4") if title.startswith("The ") else "",
                        ]
                        video_path = next((c for c in candidates if c and os.path.exists(c)), None)
                        has_video = video_path is not None
                        file_size_mb = round(os.path.getsize(video_path) / (1024 * 1024), 2) if has_video else None
                        
                        entry = {
                            "id": len(data.get("stories", [])) + 1,
                            "title": title,
                            "theme": s_data.get("premise", s_data.get("theme", "")),
                            "virtues": ["compassion", "ingenuity", "courage", "companionship"],
                            "motifs": ["clockwork lantern", "Great Clockwork Sun", "Cogsworth Valley", "Mist-Bison", "Frost-Fox"],
                            "protagonist": "Leo, apprentice lantern-maker",
                            "companion": "Pip, mechanical brass firefly",
                            "visual_mood": "Pixar meets Studio Ghibli, volumetric amber dusk, tactile brass",
                            "setting": "Cogsworth Valley & Mount Solarium",
                            "moral_lesson": s_data.get("final_reflection", {}).get("moral_lesson", ""),
                            "sovereignty_quote": s_data.get("final_reflection", {}).get("sovereignty_quote", ""),
                            "video_path": video_path,
                            "file_size_mb": file_size_mb,
                            "status": "READY" if has_video else "SCRIPTED",
                            "qc_verified": True if has_video else False,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                        data.setdefault("stories", []).append(entry)
                        data.setdefault("past_titles", []).append(title)
                        for m in entry["motifs"]:
                            if m not in data.setdefault("past_motifs", []):
                                data["past_motifs"].append(m)
                        existing_titles.add(title)
                        logger.info(f"Seeded existing story into history: '{title}'")
                except Exception as e:
                    logger.warning(f"Could not parse script {fpath}: {e}")

    save_history(history_file, data)
    return data


class IdeaBrain:
    def __init__(self, creds_file: str = DEFAULT_CREDS, history_file: str = DEFAULT_HISTORY_FILE):
        self.creds_file = creds_file
        self.history_file = history_file
        if os.path.exists(self.creds_file):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.creds_file

        api_key = os.environ.get("GEMINI_API_KEY", "AIzaSyC3a50b9lMb5FpzClrQOL7qT0mBYcrds3I")
        self.client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
        # Ensure base directories and seeds exist
        self.history = seed_existing_stories(self.history_file, os.path.dirname(self.history_file))

    def generate_concepts(self, count: int = 1) -> List[StoryConcept]:
        """Generate fresh, non-repetitive story concepts using Gemini 2.5 Flash."""
        self.history = load_history(self.history_file)
        past_titles = [s.get("title") for s in self.history.get("stories", [])]
        past_motifs = self.history.get("past_motifs", [])

        lang = get_language()

        prompt = f"""You are the Lead Story Architect and Visionary Brain for an autonomous animation studio.
Your mission is to invent {count} completely original, captivating, and emotionally rich children's bedtime story concept(s).

LANGUAGE & SCRIPT MANDATE:
- Target Language: {lang['name']} ({lang['native_name']})
- Script: {lang['script']}
- {lang['prompt_instruction']}
- CRITICAL: Write the 'title', 'theme', 'protagonist', 'companion', 'setting' fields NATIVELY in {lang['name']} using the {lang['script']} script! Do NOT transliterate English into Latin letters.
- Bedtime Pacing: The story must be calming, gentle, imaginative, and comforting—perfect for bedtime listening.
- English Title: Provide a clean English translation of the story title in 'english_title' (3-6 words) for filesystem slugs and tracking.
- Set 'language' to '{lang['code']}' and 'language_name' to '{lang['name']}'.

CORE PILLARS:
1. VIRTUES: Ground every concept in universal and kid-friendly virtues: wonder, patience, courage, quiet resilience, nature, companionship, and mechanical or mythical discovery.
2. AESTHETICS: Blend the visual splendor and environmental reverence of Studio Ghibli (painterly backdrops, clouds, water, ancient mossy machines) with the emotional character expressiveness of Pixar.
3. ADVENTURE & QUEST: Each story should feature an apprentice or gentle seeker accompanied by a unique companion on a journey of mending, discovery, or rekindling harmony.

CRITICAL ANTI-REPETITION CONSTRAINTS (100% ORIGINALITY MANDATE):
The following story titles and motifs have ALREADY been produced. You MUST NOT use or closely imitate them:
- Past Titles: {past_titles}
- Past Motifs / Characters: {past_motifs}

Generate {count} completely distinct, innovative concept(s). Each concept must explore completely new environments (e.g. bioluminescent deep reefs, floating cloud archipelagos, ancient star-glass deserts, subterranean crystal arboretums, wandering observatory islands) and novel companions.
"""

        def _gen_concepts():
            return self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=StoryConceptBatch,
                    temperature=0.85,
                )
            )
        response = execute_with_backoff(_gen_concepts, max_retries=3, op_name="Idea Brain Concept Generation")

        batch: StoryConceptBatch = response.parsed
        for c in batch.concepts:
            if not c.language:
                c.language = lang["code"]
            c.language_code = getattr(c, "language_code", None) or c.language or lang["code"]
            if not c.language_name:
                c.language_name = lang["name"]
        return batch.concepts

    def record_concept(self, concept: StoryConcept, status: str = "PROPOSED", video_path: Optional[str] = None, metadata_path: Optional[str] = None):
        """Append a newly generated or produced story concept to the history database."""
        data = load_history(self.history_file)
        lang_code = getattr(concept, "language_code", getattr(concept, "language", "en"))
        entry = {
            "id": len(data.get("stories", [])) + 1,
            "title": concept.title,
            "english_title": getattr(concept, "english_title", "") or concept.title,
            "language": getattr(concept, "language", "en"),
            "language_code": lang_code,
            "language_name": getattr(concept, "language_name", "English"),
            "theme": concept.theme,
            "virtues": concept.virtues,
            "motifs": concept.motifs,
            "protagonist": concept.protagonist,
            "companion": concept.companion,
            "visual_mood": concept.visual_mood,
            "setting": concept.setting,
            "video_path": video_path,
            "metadata_path": metadata_path,
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        data.setdefault("stories", []).append(entry)
        if concept.title not in data.setdefault("past_titles", []):
            data["past_titles"].append(concept.title)
        if entry["english_title"] and entry["english_title"] not in data.setdefault("past_titles", []):
            data["past_titles"].append(entry["english_title"])
        for m in concept.motifs:
            if m not in data.setdefault("past_motifs", []):
                data["past_motifs"].append(m)

        save_history(self.history_file, data)
        self.history = data
        return entry


def main():
    parser = argparse.ArgumentParser(description="Autonomous Story Idea Generator")
    parser.add_argument("--count", type=int, default=1, help="Number of distinct concepts to generate (default: 1)")
    parser.add_argument("--language", type=str, default=None, help="Language code or name (en, hi, pa, fr, es)")
    parser.add_argument("--dry-run", action="store_true", help="Generate concepts without adding them to history")
    parser.add_argument("--save", action="store_true", help="Explicitly save generated concept(s) to history")
    parser.add_argument("--history-file", type=str, default=DEFAULT_HISTORY_FILE, help="Path to history.json")
    parser.add_argument("--credentials", type=str, default=DEFAULT_CREDS, help="GCP service account JSON path")
    args = parser.parse_args()

    brain = IdeaBrain(creds_file=args.credentials, history_file=args.history_file)
    logger.info(f"Generating {args.count} concept(s) with Gemini 2.5 Flash (language={args.language}, dry_run={args.dry_run})...")

    concepts = brain.generate_concepts(count=args.count, language=args.language)

    print("\n" + "="*70)
    print(f"  AUTONOMOUS STORY BRAIN: {len(concepts)} CONCEPT(S) GENERATED")
    print("="*70)

    for i, c in enumerate(concepts, 1):
        print(f"\n[CONCEPT {i}] ({c.language.upper()} - {c.language_name}): {c.title}")
        if c.english_title:
            print(f"  * English Title:  {c.english_title}")
        print(f"  * Theme / Premise: {c.theme}")
        print(f"  * Core Virtues:   {', '.join(c.virtues)}")
        print(f"  * Protagonist:    {c.protagonist}")
        print(f"  * Companion:      {c.companion}")
        print(f"  * Setting:        {c.setting}")
        print(f"  * Motifs:         {', '.join(c.motifs)}")
        print(f"  * Visual Mood:    {c.visual_mood}")

        if args.save and not args.dry_run:
            brain.record_concept(c, status="SAVED_CONCEPT")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
