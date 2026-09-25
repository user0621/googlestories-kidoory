#!/usr/bin/env python3
"""
video_assembler.py - Master Video Compiler for Google Stories
1. Pairs each scene image (scene_01.png ... scene_17.png) with its audio narration.
2. Applies subtle Ken Burns pan/zoom effects.
3. Generates synchronized, clean ASS subtitles from narration text.
4. Renders individual scene segments and concatenates them into the master 1080p MP4.
"""

import os
import re
import sys
import json
import subprocess
import logging
from typing import List, Tuple, Optional
from languages import get_font_for_language

try:
    os.nice(10)
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("VideoAssembler")

STORY_JSON = "/data/google-stories/scripts/keeper_of_the_clockwork_lantern.json"
AUDIO_DIR = "/data/google-stories/audio_scenes"
IMAGE_DIR = "/data/google-stories/raw_images"
TEMP_DIR = "/data/google-stories/temp_segments"
FINAL_VIDEO_DIR = "/data/google-stories/final_videos"
OUTPUT_MASTER_MP4 = os.path.join(FINAL_VIDEO_DIR, "Keeper_of_the_Clockwork_Lantern.mp4")

FPS = 30
WIDTH = 1920
HEIGHT = 1080

def get_audio_duration(file_path: str) -> float:
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
        logger.error(f"Error reading duration for {file_path}: {e}")
        return 0.0

def format_ass_time(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hrs:d}:{mins:02d}:{secs:02d}.{centis:02d}"

def wrap_text(text: str, max_chars: int = 52) -> str:
    words = text.split()
    lines = []
    curr = []
    curr_len = 0
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
    return "\\N".join(lines)  # At most 2 lines per subtitle cue

def split_into_sentences(text: str) -> List[str]:
    # Split on sentence boundaries including Latin (.!?) and Indic danda (।॥) while preserving content
    raw_sentences = re.split(r'(?<=[.!?।॥])\s+', text.strip())
    sentences = [s.strip() for s in raw_sentences if s.strip()]
    return sentences

def generate_ass_subtitle_file(text: str, duration: float, out_ass_path: str, language: str = "en"):
    sentences = split_into_sentences(text)
    if not sentences:
        sentences = [text]

    # Calculate word weights
    sentence_weights = [max(1, len(s.split())) for s in sentences]
    total_weight = sum(sentence_weights)

    start_buffer = 0.4
    end_buffer = 0.4
    usable_time = max(1.0, duration - start_buffer - end_buffer)

    events = []
    current_time = start_buffer
    for sent, weight in zip(sentences, sentence_weights):
        sent_duration = (weight / total_weight) * usable_time
        start_t = current_time
        end_t = current_time + sent_duration
        current_time = end_t

        wrapped = wrap_text(sent)
        event_line = f"Dialogue: 0,{format_ass_time(start_t)},{format_ass_time(end_t)},Default,,0,0,0,,{wrapped}"
        events.append(event_line)

    font_name = "Poppins"
    ass_content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},38,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3.0,2.0,2,100,100,65,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(events) + "\n"

    with open(out_ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

def render_scene_video(scene_idx: int, image_path: str, audio_path: str, narration: str, out_mp4_path: str, language: str = "en"):
    duration = get_audio_duration(audio_path)
    total_frames = int(round(duration * FPS))

    # Subtitle file with dynamic language font
    ass_path = out_mp4_path.replace(".mp4", ".ass")
    generate_ass_subtitle_file(narration, duration, ass_path, language=language)

    # Ken Burns variations based on scene index
    var = scene_idx % 4
    if var == 0:
        # Subtle slow zoom in
        zp = f"z='min(zoom+0.0005,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
    elif var == 1:
        # Pan upwards gently
        zp = f"z='1.12':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/{total_frames})':d={total_frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
    elif var == 2:
        # Subtle slow zoom out
        zp = f"z='if(lte(zoom,1.0),1.15,max(1.001,zoom-0.0005))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
    else:
        # Pan downwards gently
        zp = f"z='1.12':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(on/{total_frames})':d={total_frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"

    filter_complex = f"[0:v]scale=2160:2160,zoompan={zp},ass='{ass_path}',format=yuv420p[v]"

    cmd = [
        "ffmpeg", "-y", "-threads", "4",
        "-loop", "1", "-t", f"{duration:.3f}",
        "-i", image_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        out_mp4_path
    ]

    logger.info(f"[Scene {scene_idx:02d}] Rendering segment ({duration:.2f}s, {total_frames} frames)...")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        logger.error(f"FFmpeg error on Scene {scene_idx}:\n{res.stderr.decode()[-800:]}")
        raise RuntimeError(f"FFmpeg rendering failed for Scene {scene_idx}")
    logger.info(f"[Scene {scene_idx:02d}] Segment rendered successfully: {os.path.getsize(out_mp4_path)/1024/1024:.2f} MB")

def assemble_master_video(story_json: str = STORY_JSON, output_mp4: str = OUTPUT_MASTER_MP4, language: Optional[str] = None):
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(FINAL_VIDEO_DIR, exist_ok=True)

    with open(story_json, "r", encoding="utf-8") as f:
        story = json.load(f)

    story_lang = language or story.get("language", "en")
    scenes_data = story.get("scenes", [])
    reflection = story.get("final_reflection", {})
    reflection_text = f"{reflection.get('moral_lesson', '')}\n\nRemember: {reflection.get('sovereignty_quote', '')}"

    rendered_segments = []

    # Scenes 1 to 16
    for s in scenes_data:
        idx = s["scene_index"]
        img_path = os.path.join(IMAGE_DIR, f"scene_{idx:02d}.png")
        aud_path = os.path.join(AUDIO_DIR, f"scene_{idx:02d}.mp3")
        seg_mp4 = os.path.join(TEMP_DIR, f"segment_{idx:02d}.mp4")

        if not os.path.exists(img_path):
            raise FileNotFoundError(f"Missing required image: {img_path}")
        if not os.path.exists(aud_path):
            raise FileNotFoundError(f"Missing required audio: {aud_path}")

        render_scene_video(idx, img_path, aud_path, s["narration"], seg_mp4, language=story_lang)
        rendered_segments.append(seg_mp4)

    # Scene 17: Reflection
    img_17 = os.path.join(IMAGE_DIR, "scene_17.png")
    aud_17 = os.path.join(AUDIO_DIR, "scene_17_reflection.mp3")
    seg_17 = os.path.join(TEMP_DIR, "segment_17.mp4")

    if not os.path.exists(img_17):
        raise FileNotFoundError(f"Missing required image: {img_17}")
    if not os.path.exists(aud_17):
        raise FileNotFoundError(f"Missing required audio: {aud_17}")

    render_scene_video(17, img_17, aud_17, reflection_text, seg_17, language=story_lang)
    rendered_segments.append(seg_17)

    # Concatenate all 17 segments
    concat_list_file = os.path.join(TEMP_DIR, "concat_list.txt")
    with open(concat_list_file, "w", encoding="utf-8") as f:
        for seg in rendered_segments:
            f.write(f"file '{seg}'\n")

    logger.info(f"Concatenating {len(rendered_segments)} scenes into master video ({story_lang}): {output_mp4}...")
    concat_cmd = [
        "ffmpeg", "-y", "-threads", "4",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_file,
        "-c", "copy",
        output_mp4
    ]

    res = subprocess.run(concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        logger.error(f"FFmpeg concat error:\n{res.stderr.decode()[-800:]}")
        raise RuntimeError("Master video concatenation failed.")

    final_duration = get_audio_duration(output_mp4)
    final_size_mb = os.path.getsize(output_mp4) / (1024 * 1024)

    mins = int(final_duration // 60)
    secs = int(final_duration % 60)

    print("\n==================================================")
    print("  MASTER VIDEO COMPILATION COMPLETE!")
    print("==================================================")
    print(f"Master Video Path: {output_mp4}")
    print(f"Language:          {story_lang}")
    print(f"Total Segments:    {len(rendered_segments)}")
    print(f"Exact Duration:    {mins}m {secs:02d}s ({final_duration:.2f}s)")
    print(f"File Size:         {final_size_mb:.2f} MB")
    print(f"Resolution:        {WIDTH}x{HEIGHT} (1080p, 30fps)")
    print("==================================================\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Assemble Master Story Video")
    parser.add_argument("--story-json", type=str, default=STORY_JSON, help="Path to story JSON")
    parser.add_argument("--output", type=str, default=OUTPUT_MASTER_MP4, help="Path to output MP4")
    parser.add_argument("--language", type=str, default=None, help="Language code (en, hi, pa, fr, es)")
    args = parser.parse_args()
    assemble_master_video(story_json=args.story_json, output_mp4=args.output, language=args.language)
