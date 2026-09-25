#!/usr/bin/env python3
"""
story_director.py - Autonomous Story Architect Engine
Generates an episodic narrative with autonomous decision-making using Google GenAI (gemini-2.5-flash).
"""

import os
import sys
import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from google.genai import Client, types

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("StoryDirector")

# Suppress noisy AFC warnings if any
logging.getLogger("google.genai").setLevel(logging.ERROR)

CREDENTIALS_FILE = "/home/hkserver/secrets/kidoory-7590452277b9.json"
OUTPUT_FILE = "/data/google-stories/scripts/keeper_of_the_clockwork_lantern.json"
MODEL_NAME = "gemini-2.5-flash"
TOTAL_SCENES = 16

# Pydantic Schemas
class Scene(BaseModel):
    scene_index: int = Field(description="1-based scene index.")
    narration: str = Field(description="Warm storybook narration, strictly between 60 and 80 words.")
    visual_prompt: str = Field(description="Cinematic Pixar/Studio Ghibli visual prompt with consistent character design, lighting, and camera angle.")
    choice_options: List[str] = Field(description="3 distinct potential next-step choices for Leo.")
    chosen_option: str = Field(description="The chosen option that best honors compassion, ingenuity, and emotional resonance.")
    choice_reasoning: str = Field(description="Clear explanation of why this option was selected based on compassion, ingenuity, and emotional resonance.")

class FinalReflection(BaseModel):
    moral_lesson: str = Field(description="The central moral lesson of the story.")
    sovereignty_quote: str = Field(description="An inspiring, poetic quote reflecting inner sovereignty, courage, and purpose.")

class StoryDocument(BaseModel):
    title: str
    premise: str
    total_scenes: int
    total_word_count: int
    scenes: List[Scene]
    final_reflection: FinalReflection

SCENE_BEATS = [
    {
        "index": 1,
        "title": "The Dimming Valley",
        "focus": "Introduce Leo in his warm, cluttered clockwork workshop with Pip the brass firefly. The valley below is dimming as the Great Clockwork Sun atop Mount Solarium begins to sputter."
    },
    {
        "index": 2,
        "title": "Departure into Twilight",
        "focus": "Leo packs his leather knapsack, checks his brass clockwork lantern, and sets out past the valley gates into the whispering mountain twilight."
    },
    {
        "index": 3,
        "title": "The Whispering Pines",
        "focus": "Climbing through the ancient pine forest where the fog gathers. The paths divide into steep rocky goat tracks and dark mossy hollows."
    },
    {
        "index": 4,
        "title": "The Woolly Mist-Bison",
        "focus": "Encountering a colossal, gentle Woolly Mist-Bison stranded precariously on a crumbling shale ledge in the swirling mist."
    },
    {
        "index": 5,
        "title": "A Gentle Harmony",
        "focus": "Using the warm amber pulse of the Clockwork Lantern and patience to soothe the frightened creature and coax it to safety."
    },
    {
        "index": 6,
        "title": "The Path Revealed",
        "focus": "The grateful Mist-Bison leads Leo and Pip along a secret ancient mountain terrace through the dense fog, bypassing sheer cliffs."
    },
    {
        "index": 7,
        "title": "The Chasm of Echoes",
        "focus": "Reaching an immense canyon spanned only by the ancient Rusted Gear Bridge, whose massive iron and brass cogs have seized with frost and rust."
    },
    {
        "index": 8,
        "title": "Pip into the Mechanism",
        "focus": "Pip squeezes into the narrow planetary gear train to clear the debris and lubricate the seized escapement wheel."
    },
    {
        "index": 9,
        "title": "Turning the Great Windlass",
        "focus": "Leo engages the manual counterweight windlass; the colossal bridge cogs interlock with a thunderous groan, sealing the bridge across the chasm."
    },
    {
        "index": 10,
        "title": "The Alpine Snowline",
        "focus": "Ascending into the high alpine tundra where ice crystals form in the air. A sleek, shivering Frost-Fox watches from the shadows of a frozen boulder."
    },
    {
        "index": 11,
        "title": "Warmth for the Frost-Fox",
        "focus": "Leo notices the fox's frozen paws; instead of fearing its sharp gaze, he opens the lantern's radiant warmth baffle and shares food."
    },
    {
        "index": 12,
        "title": "The Fox's Guidance",
        "focus": "The Frost-Fox leaps ahead playfully, guiding Leo across hidden frozen snow bridges that bypass treacherous wind crevices to the summit peak."
    },
    {
        "index": 13,
        "title": "The Summit Observatory",
        "focus": "Standing before the monumental glass and brass dome of Mount Solarium. Inside sits the Great Clockwork Sun, silent, frosted, and still."
    },
    {
        "index": 14,
        "title": "Diagnosing the Solar Heart",
        "focus": "Leo inspects the colossal chronometer core. The mainspring is intact, but the harmonic resonance spark chamber is dark and dead."
    },
    {
        "index": 15,
        "title": "The Spark of Compassion",
        "focus": "Leo connects his own beloved Clockwork Lantern into the solar heart cradle. Pip pulses his harmonic glow, igniting the eternal solar flame."
    },
    {
        "index": 16,
        "title": "Dawn Across the World",
        "focus": "The celestial gears turn with radiant golden luminescence. Dawn floods the mountain peaks, the valley below, and all creatures in warmth and hope."
    }
]

def enforce_word_count(client: Client, narration: str, min_words: int = 60, max_words: int = 80) -> str:
    """Adjusts narration to strictly fall within min_words and max_words if necessary."""
    words = narration.split()
    if min_words <= len(words) <= max_words:
        return narration

    logger.warning(f"Word count ({len(words)}) outside target [{min_words}, {max_words}]. Refining...")
    refine_prompt = f"""Rewrite the following story narration so that it has STRICTLY between {min_words} and {max_words} words.
Maintain the exact warm storybook style, poetic imagery, and plot details. Do not output anything other than the revised text.

Narration:
"{narration}"
"""
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=refine_prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
            )
        )
        revised = response.text.strip().strip('"')
        new_count = len(revised.split())
        logger.info(f"Refined narration word count: {new_count}")
        return revised
    except Exception as e:
        logger.error(f"Failed to refine word count: {e}")
        return narration

def generate_story():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_FILE

    # Extract project_id from credentials file
    with open(CREDENTIALS_FILE, "r") as f:
        cred_data = json.load(f)
        project_id = cred_data.get("project_id", "kidoory")

    logger.info(f"Connecting to Vertex AI (project={project_id}, model={MODEL_NAME})...")
    client = Client(api_key=os.environ.get("GEMINI_API_KEY"), http_options={"api_version": "v1beta"})

    title = "The Keeper of the Clockwork Lantern"
    premise = (
        "In the shadowed realm of Cogsworth Valley beneath Mount Solarium, twelve-year-old apprentice "
        "lantern-maker Leo and his brass firefly companion Pip embark on an epic ascent to reignite the "
        "fallen Great Clockwork Sun. Along their journey, they encounter a Woolly Mist-Bison, conquer the "
        "Rusted Gear Bridge, befriend a wary Frost-Fox, and rekindle the light of the world through compassion "
        "and ingenuity."
    )

    character_consistency = (
        "Visual style consistency rules:\n"
        "- Art Style: Cinematic 3D animation, blending Pixar character expressiveness and warmth with "
        "Studio Ghibli painterly backgrounds and whimsical steampunk machinery. Volumetric amber/dusk lighting, "
        "soft atmospheric fog, rich tactile textures, 8k resolution.\n"
        "- Leo: 12-year-old boy, curly auburn hair, brass aviator goggles on forehead, patched teal woolen coat, "
        "leather tool belt, carrying a warm glowing brass clockwork lantern with visible rotating gears inside.\n"
        "- Pip: A thumb-sized mechanical brass firefly with delicate filigree wings, warm glowing amber abdomen, and curious expressive eyes.\n"
    )

    scenes: List[Scene] = []
    accumulated_story_context = []

    print(f"\n==================================================")
    print(f"  AUTONOMOUS STORY ARCHITECT: {title.upper()}")
    print(f"  Target: {TOTAL_SCENES} Scenes | Autonomous Director Loop")
    print(f"==================================================\n")

    for beat in SCENE_BEATS:
        idx = beat["index"]
        beat_title = beat["title"]
        focus = beat["focus"]

        logger.info(f"--- Generating Scene {idx}/{TOTAL_SCENES}: {beat_title} ---")

        context_summary = "\n".join(accumulated_story_context[-3:]) if accumulated_story_context else "Journey starting."

        is_final_scene = (idx == TOTAL_SCENES)

        scene_prompt = f"""You are the Autonomous Story Director and Master Storyteller.
Story Title: {title}
Core Premise: {premise}

{character_consistency}

Current Narrative Goal for Scene {idx} ({beat_title}):
{focus}

Previous Story Progression:
{context_summary}

INSTRUCTIONS FOR GENERATION:
1. 'scene_index': Must be exactly {idx}.
2. 'narration': Write a warm, evocative storybook narration. CRITICAL: The narration MUST be STRICTLY between 60 and 80 words long. Count the words carefully!
3. 'visual_prompt': Highly detailed image generation prompt following the visual consistency rules. Describe the camera angle, Leo and Pip's actions, emotional expressions, lighting, and environmental atmosphere.
4. 'choice_options':
   {"Provide an empty list [] as this is the climactic resolution." if is_final_scene else "Provide exactly 3 distinct, compelling possible choices for what action Leo should take next."}
5. 'chosen_option':
   {"The grand restoration of light and hope." if is_final_scene else "You are the Autonomous Story Director. Evaluate all 3 options and automatically select the ONE path that best honors compassion, ingenuity, and emotional resonance over force, recklessness, or shortcuts."}
6. 'choice_reasoning':
   {"The journey reaches its poetic fulfillment through selfless sacrifice and craftsmanship." if is_final_scene else "Explain deeply why this chosen option best exemplifies compassion, ingenuity, and emotional resonance."}
"""

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=scene_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Scene,
                    temperature=0.7,
                )
            )
            scene_data: Scene = response.parsed

            # Validate and adjust word count if needed
            scene_data.narration = enforce_word_count(client, scene_data.narration, min_words=60, max_words=80)
            word_count = len(scene_data.narration.split())

            scenes.append(scene_data)

            # Update context for subsequent scenes
            context_entry = (
                f"Scene {idx} ({beat_title}): {scene_data.narration}\n"
                f"Chosen Decision: {scene_data.chosen_option} (Reason: {scene_data.choice_reasoning})"
            )
            accumulated_story_context.append(context_entry)

            print(f"Scene {idx:02d} [{beat_title}] Generated ({word_count} words)")
            print(f"  Narration: {scene_data.narration}")
            if not is_final_scene:
                print(f"  Choices:")
                for opt in scene_data.choice_options:
                    print(f"    - {opt}")
                print(f"  -> Chosen: {scene_data.chosen_option}")
                print(f"  -> Reasoning: {scene_data.choice_reasoning}\n")
            else:
                print(f"  -> Finale Resolution Reached!\n")

        except Exception as e:
            logger.error(f"Error generating scene {idx}: {e}")
            raise e

    # Generate Final Reflection
    logger.info("Generating Final Reflection (Moral Lesson & Sovereignty Quote)...")
    reflection_prompt = f"""Based on the complete 16-scene journey of '{title}', synthesize a profound Final Reflection.
Story Summary:
{accumulated_story_context[-1]}

Requirements:
- moral_lesson: A heartwarming, 2-3 sentence moral lesson about kindness, creativity, and stewardship.
- sovereignty_quote: A powerful, poetic quote celebrating inner sovereignty, purpose, and the light within.
"""
    reflection_response = client.models.generate_content(
        model=MODEL_NAME,
        contents=reflection_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=FinalReflection,
            temperature=0.6,
        )
    )
    final_reflection: FinalReflection = reflection_response.parsed

    total_words = sum(len(s.narration.split()) for s in scenes)

    story_doc = StoryDocument(
        title=title,
        premise=premise,
        total_scenes=len(scenes),
        total_word_count=total_words,
        scenes=scenes,
        final_reflection=final_reflection
    )

    # Save to JSON
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(story_doc.model_dump(), f, indent=2, ensure_ascii=False)

    logger.info(f"Story saved successfully to: {OUTPUT_FILE}")
    print(f"\n==================================================")
    print(f"  GENERATION COMPLETE")
    print(f"  Title: {story_doc.title}")
    print(f"  Total Scenes: {story_doc.total_scenes}")
    print(f"  Total Narration Word Count: {story_doc.total_word_count} words")
    print(f"  Average Words / Scene: {story_doc.total_word_count / story_doc.total_scenes:.1f}")
    print(f"  Output File: {OUTPUT_FILE}")
    print(f"  Moral Lesson: {final_reflection.moral_lesson}")
    print(f"  Sovereignty Quote: \"{final_reflection.sovereignty_quote}\"")
    print(f"==================================================\n")

if __name__ == "__main__":
    generate_story()
