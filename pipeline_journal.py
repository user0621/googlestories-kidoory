#!/usr/bin/env python3
"""
pipeline_journal.py - Job State Resumption & Asset Integrity Engine
Maintains active pipeline state in /data/google-stories/current_job.json.
Enables instant crash/reboot resumption by skipping already synthesized
audio scenes, visual frames, or compiled segments.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PipelineJournal")

DEFAULT_JOB_FILE = "/data/google-stories/current_job.json"


def is_valid_asset(path: Optional[str], min_bytes: int = 1000) -> bool:
    """Check if an asset exists and has valid non-zero content."""
    if not path or not os.path.exists(path):
        return False
    try:
        return os.path.getsize(path) >= min_bytes
    except OSError:
        return False


def find_existing_audio(audio_dir: str, slug: str, scene_idx: int, min_bytes: int = 4000) -> Optional[str]:
    """Check for existing valid audio files under slug-prefixed names."""
    if scene_idx == 17:
        candidates = [
            os.path.join(audio_dir, f"{slug}_scene_17_reflection.mp3"),
            os.path.join(audio_dir, f"{slug}_scene_17.mp3"),
        ]
        if slug.startswith("keeper_of_the_clockwork_lantern"):
            candidates.extend([
                os.path.join(audio_dir, "scene_17_reflection.mp3"),
                os.path.join(audio_dir, "scene_17.mp3"),
            ])
    else:
        candidates = [
            os.path.join(audio_dir, f"{slug}_scene_{scene_idx:02d}.mp3"),
        ]
        if slug.startswith("keeper_of_the_clockwork_lantern"):
            candidates.append(os.path.join(audio_dir, f"scene_{scene_idx:02d}.mp3"))

    for c in candidates:
        if is_valid_asset(c, min_bytes):
            return c
    return None


def find_existing_image(images_dir: str, slug: str, scene_idx: int, min_bytes: int = 50_000) -> Optional[str]:
    """Check for existing valid image files under slug-prefixed names."""
    candidates = [
        os.path.join(images_dir, f"{slug}_scene_{scene_idx:02d}.png"),
        os.path.join(images_dir, f"{slug}_cover.png"),
    ]
    if slug.startswith("keeper_of_the_clockwork_lantern"):
        candidates.append(os.path.join(images_dir, f"scene_{scene_idx:02d}.png"))

    for c in candidates:
        if is_valid_asset(c, min_bytes):
            return c
    return None


class JobJournal:
    def __init__(self, job_file: str = DEFAULT_JOB_FILE):
        self.job_file = job_file
        self.data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.job_file):
            try:
                with open(self.job_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read existing job journal ({e}), initializing empty.")
                self.data = {}
        else:
            self.data = {}

    def _save(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.job_file)), exist_ok=True)
        self.data["updated_at"] = datetime.now(timezone.utc).isoformat()
        tmp_file = self.job_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, self.job_file)

    @classmethod
    def get_unfinished_job(cls, job_file: str = DEFAULT_JOB_FILE) -> Optional[Dict[str, Any]]:
        """Return unfinished job data if a job is currently in progress."""
        if not os.path.exists(job_file):
            return None
        try:
            with open(job_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                if d.get("status") == "IN_PROGRESS":
                    return d
        except Exception:
            pass
        return None

    def start_or_resume(self, title: str, theme: str, total_scenes: int, slug: str) -> Tuple[Dict[str, Any], bool]:
        """
        Start a new job or resume an existing active job.
        Returns: (job_dict, is_resumed: bool)
        """
        current_status = self.data.get("status")
        current_title = self.data.get("title")

        if current_status == "IN_PROGRESS" and (current_title == title or not title):
            logger.info(f"RESUMING active job: '{current_title}' from stage '{self.data.get('stage')}'")
            return self.data, True

        # Initialize fresh job
        self.data = {
            "title": title,
            "theme": theme,
            "slug": slug,
            "total_scenes": total_scenes,
            "status": "IN_PROGRESS",
            "stage": "scripting",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "completed_scenes": {
                "script": False,
                "audio": {},
                "visuals": {},
                "segments": {}
            },
            "master_video": None,
            "qc_passed": False
        }
        self._save()
        logger.info(f"Initialized new production job in journal: '{title}' ({total_scenes} scenes)")
        return self.data, False

    def update_stage(self, stage: str):
        self.data["stage"] = stage
        self._save()
        logger.info(f"Job stage updated: [{stage.upper()}]")

    def mark_script_done(self, script_path: str):
        self.data.setdefault("completed_scenes", {})["script"] = True
        self.data["script_path"] = script_path
        self._save()

    def record_audio_scene(self, scene_idx: int, path: str):
        completed = self.data.setdefault("completed_scenes", {}).setdefault("audio", {})
        completed[str(scene_idx)] = path
        self._save()

    def record_visual_scene(self, scene_idx: int, path: str):
        completed = self.data.setdefault("completed_scenes", {}).setdefault("visuals", {})
        completed[str(scene_idx)] = path
        self._save()

    def record_segment(self, scene_idx: int, path: str):
        completed = self.data.setdefault("completed_scenes", {}).setdefault("segments", {})
        completed[str(scene_idx)] = path
        self._save()

    def complete_job(self, video_path: str, qc_passed: bool):
        self.data["status"] = "COMPLETED"
        self.data["stage"] = "finished"
        self.data["master_video"] = video_path
        self.data["qc_passed"] = qc_passed
        self.data["completed_at"] = datetime.now(timezone.utc).isoformat()
        self._save()
        logger.info(f"Job '{self.data.get('title')}' marked as COMPLETED in journal.")

    def fail_job(self, error_message: str):
        self.data["status"] = "FAILED"
        self.data["error"] = error_message
        self.data["failed_at"] = datetime.now(timezone.utc).isoformat()
        self._save()
        logger.error(f"Job '{self.data.get('title')}' marked as FAILED in journal: {error_message}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline Journal CLI")
    parser.add_argument("--status", action="store_true", help="Print active job status")
    parser.add_argument("--clear", action="store_true", help="Clear current active job")
    args = parser.parse_args()

    journal = JobJournal()
    if args.clear:
        if os.path.exists(DEFAULT_JOB_FILE):
            os.remove(DEFAULT_JOB_FILE)
            print("Cleared active job journal.")
    elif args.status:
        job = JobJournal.get_unfinished_job()
        if job:
            print("\nACTIVE UNFINISHED JOB:")
            print(json.dumps(job, indent=2))
        else:
            print("\nNo unfinished job currently in progress.")


if __name__ == "__main__":
    main()
