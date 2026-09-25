#!/usr/bin/env python3
import os
import json
import logging
import subprocess
from google.genai import Client, types
from produce_story import StoryPipeline, Scene, FinalReflection, StoryDocument

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ProduceEpisode")

def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

def produce_episode():
    state = load_json("/home/hkserver/googlestories-kidoory/PROJECT_STATE.json")
    movie_id = state["active_movie_id"]
    ep_id = state["active_episode_id"]
    
    bible_dir = f"/data/google-stories/movies/{movie_id}/bibles"
    ep_map = load_json(os.path.join(bible_dir, "EPISODE_MAP.json"))
    char_bible = load_json(os.path.join(bible_dir, "CHARACTER_BIBLE.json"))
    movie_struct = load_json(os.path.join(bible_dir, "MOVIE_STRUCTURE.json"))
    
    ep_data = next((ep for ep in ep_map if ep["episode_id"] == ep_id), None)
    if not ep_data:
        logger.error(f"Episode {ep_id} not found in map.")
        return
        
    title = f"{ep_data['title']} | Ep. {ep_id} - {movie_struct.get('movie_title')} | Kidoory Bedtime Stories"
    theme = ep_data["summary"]
    
    logger.info(f"Producing {title}")
    
    # We use StoryPipeline but override the prompt
    pipeline = StoryPipeline(title=title, theme=theme, scenes=8, base_dir=f"/data/google-stories/movies/{movie_id}")
    
    # Custom script generation
    script_file = os.path.join(pipeline.scripts_dir, f"{pipeline.slug}.json")
    
    if not os.path.exists(script_file):
        prompt = f'''You are the Autonomous Story Director.
        Write Episode {ep_id} of the movie {movie_struct.get("movie_title")}.
        Episode Summary: {theme}
        Character Continuity: {json.dumps(char_bible)}
        
        CRITICAL RULES:
        1. Generate exactly 8 scenes.
        2. 'narration' MUST be 80-110 words per scene (total ~650-900 words).
        3. 'visual_prompt' MUST use: "Masterpiece 3D children's storybook illustration in the heartwarming style of modern Pixar and Studio Ghibli, 8k resolution, dreamy volumetric golden-hour lighting, cozy magical atmosphere, rich vibrant color palette, endearing character design with large soft expressive eyes, award-winning concept art, trending on ArtStation."
        4. In every 'visual_prompt', YOU MUST explicitly include the character's exact visual specifications from the Character Continuity (e.g., boots, pendant, braided hair) to prevent clothing shifts.
        5. Add negative prompt to every 'visual_prompt': "text, letters, watermarks, signature, words".
        6. Maintain strict continuity (wardrobe, items).
        '''
        
        response = pipeline.genai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=StoryDocument)
        )
        
        story_doc = response.parsed
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(response.text)
    else:
        with open(script_file, "r") as f:
            story_doc = StoryDocument(**json.load(f))
            
    audio_data = pipeline.run_stage_audio(story_doc)
    visual_data = pipeline.run_stage_visuals(story_doc)
    
    # Customize ASS subtitles for Drop Shadow in assembly
    master_mp4 = pipeline.run_stage_assembly(audio_data, visual_data)
    ok = pipeline.run_stage_verification(master_mp4)
    
    if ok:
        state["stage"] = "QC_AUDIT"
        state["latest_mp4"] = master_mp4
        with open("/home/hkserver/googlestories-kidoory/PROJECT_STATE.json", "w") as f:
            json.dump(state, f, indent=2)
        logger.info(f"Episode {ep_id} produced successfully.")

if __name__ == "__main__":
    produce_episode()
