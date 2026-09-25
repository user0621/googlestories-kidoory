#!/usr/bin/env python3
import os
import json
import logging
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
logger = logging.getLogger("MovieArchitect")

CREDENTIALS_FILE = "/home/hkserver/secrets/kidoory-7590452277b9.json"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_FILE

def load_project_state():
    state_path = "/home/hkserver/googlestories-kidoory/PROJECT_STATE.json"
    if os.path.exists(state_path):
        with open(state_path, "r") as f:
            return json.load(f)
    return {"active_movie_id": None, "active_episode_id": 1, "stage": "BIBLE_GENERATION"}

def save_project_state(state):
    state_path = "/home/hkserver/googlestories-kidoory/PROJECT_STATE.json"
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)

def generate_bibles(movie_id):
    logger.info(f"Generating Bibles for {movie_id}...")
    bible_dir = f"/data/google-stories/movies/{movie_id}/bibles"
    os.makedirs(bible_dir, exist_ok=True)
    
    client = Client(api_key=get_kidoory_gemini_key(), http_options={"api_version": "v1beta"}, vertexai=False)

    prompt = """
    You are the Master Story Architect for a 12-episode children's bedtime movie arc (Pixar/Ghibli style).
    Create a detailed schema-valid JSON object containing the following bibles:
    {
      "WORLD_BIBLE": {"setting": "...", "rules_of_magic": "..."},
      "CHARACTER_BIBLE": {"protagonist": {"name": "...", "traits": "...", "wardrobe": "...", "wound": "..."}},
      "RELATIONSHIP_BIBLE": {"dynamic": "..."},
      "STORY_BIBLE": {"core_theme": "...", "arc": "..."},
      "EMOTION_BIBLE": {"emotional_curve": "..."},
      "VISUAL_BIBLE": {"aesthetic": "...", "colors": "..."},
      "MOVIE_STRUCTURE": {"total_episodes": 12, "movie_title": "..."},
      "EPISODE_MAP": [
         {"episode_id": 1, "title": "...", "summary": "...", "bridge_to_next": "..."},
         ...up to 12 episodes...
      ]
    }
    Make sure to provide exactly 12 episodes in the EPISODE_MAP. Ensure JSON is valid.
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    
    data = json.loads(response.text.strip('` \n'))
    
    for bible_name, bible_content in data.items():
        file_path = os.path.join(bible_dir, f"{bible_name}.json")
        with open(file_path, "w") as f:
            json.dump(bible_content, f, indent=2)
            
    logger.info(f"Generated all Bibles in {bible_dir}")
    return data.get("MOVIE_STRUCTURE", {}).get("movie_title", "Unknown Title")

if __name__ == "__main__":
    state = load_project_state()
    movie_id = state.get("active_movie_id", "MOVIE_001")
    title = generate_bibles(movie_id)
    
    # Update state
    state["stage"] = "EPISODE_PRODUCTION"
    state["movie_title"] = title
    save_project_state(state)
    logger.info(f"Movie Architect Finished for {movie_id}: {title}")
