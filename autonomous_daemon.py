#!/usr/bin/env python3
import time
import logging
import os
import json
from movie_architect import generate_bibles, load_project_state, save_project_state
from produce_episode import produce_episode
from movie_publisher import publish_episode

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MovieStudioDaemon")

def daemon_loop():
    logger.info("Starting Kidoory Movie Studio Daemon (English Only, Pixar Aesthetics)...")
    while True:
        state = load_project_state()
        stage = state.get("stage")
        logger.info(f"Current State: {stage} (Movie: {state.get('active_movie_id')} Ep: {state.get('active_episode_id')})")
        
        if stage == "BIBLE_GENERATION":
            title = generate_bibles(state.get("active_movie_id", "MOVIE_001"))
            state["stage"] = "EPISODE_PRODUCTION"
            state["movie_title"] = title
            save_project_state(state)
            
        elif stage == "EPISODE_PRODUCTION":
            try:
                produce_episode()
            except RuntimeError as e:
                if "CIRCUIT BREAKER" in str(e) or "DAILY_CAP_REACHED" in str(e):
                    logger.warning(f"Kidoory paused by circuit breaker: {e}. Sleeping 10 minutes...")
                    time.sleep(600)
                else:
                    raise
            
        elif stage == "QC_AUDIT":
            publish_episode()
            
        elif stage == "MOVIE_COMPLETE":
            # Increment movie
            curr_id = state.get("active_movie_id", "MOVIE_001")
            new_idx = int(curr_id.split("_")[1]) + 1
            new_id = f"MOVIE_{new_idx:03d}"
            state["active_movie_id"] = new_id
            state["active_episode_id"] = 1
            state["stage"] = "BIBLE_GENERATION"
            save_project_state(state)
            
        time.sleep(10)

if __name__ == "__main__":
    daemon_loop()
