#!/usr/bin/env python3
"""
languages.py - English-Only Engine for Google Stories
"""

import os
import json
import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("Languages")

TARGET_LANGUAGE = "en"
LANGUAGE_CODE = "en-US"

ENGLISH_DEF = {
    "index": 0,
    "code": "en",
    "name": "English",
    "native_name": "English",
    "script": "Latin",
    "voice": "en-US-Journey-F",
    "language_code": "en-US",
    "font": "Noto Sans",
    "title_suffix": "🌟 Magical Bedtime Story for Kids",
    "chapter_header": "STORY CHAPTERS",
    "moral_header": "MORAL & INSPIRATION",
    "about_header": "ABOUT KIDOORY",
    "about_text": "Kidoory creates cinematic, heart-warming stories blending universal virtues, gentle courage, wonder, and emotional companionship. Crafted for curious young minds and peaceful bedtimes.",
    "reflection_title": "Final Reflection & Moral",
    "tags": [
        "Kidoory", "bedtime stories for kids", "animated stories", "fairy tales",
        "kids storytime", "moral stories for children", "sleep story",
        "audiobook for kids", "Pixar style animation", "Studio Ghibli aesthetic"
    ],
    "prompt_instruction": (
        "Write the entire story strictly and natively in English. All scene titles, storybook narrations, "
        "choice options, and moral reflections must be in English. "
        "Tone: Warm, gentle, lyrical, soothing bedtime storybook pacing."
    )
}

LANGUAGE_CYCLE = [ENGLISH_DEF]

def get_language(identifier: Any = None) -> Dict[str, Any]:
    return ENGLISH_DEF

def get_font_for_language(lang_code: Optional[str] = "en", sample_text: str = "") -> str:
    return "Noto Sans"

def get_next_language(history_file: str) -> Tuple[int, Dict[str, Any]]:
    return 0, ENGLISH_DEF

def advance_language_index(history_file: str, index: int):
    pass
