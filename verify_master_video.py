#!/usr/bin/env python3
"""
verify_master_video.py - Closed-Loop Automated Quality Verification
Inspects /data/google-stories/final_videos/Keeper_of_the_Clockwork_Lantern.mp4:
1. Stream Validation: Checks video vs audio duration sync (<0.1s tolerance).
2. Corruption check: Runs full decode test.
3. Visual & Luminance Analysis: Extracts frames at 10%, 50%, 90% and checks 1080p geometry, mean luminance, and contrast.
"""

import os
import sys
import json
import subprocess
from PIL import Image, ImageStat

TARGET_VIDEO = "/data/google-stories/final_videos/Keeper_of_the_Clockwork_Lantern.mp4"
TEMP_DIR = "/data/google-stories/temp_segments"

def get_stream_info(video_path: str):
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        video_path
    ]
    out = subprocess.check_output(cmd).decode()
    return json.loads(out)

def check_corruption(video_path: str) -> bool:
    cmd = ["ffmpeg", "-v", "error", "-i", video_path, "-f", "null", "-"]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0 or len(res.stderr.strip()) > 0:
        print(f"Decode errors found: {res.stderr.decode()}")
        return False
    return True

def extract_frame_at(video_path: str, timestamp_s: float, out_img_path: str):
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{timestamp_s:.2f}",
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        out_img_path
    ]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def analyze_image(img_path: str):
    with Image.open(img_path) as img:
        width, height = img.size
        mode = img.mode
        # Convert to grayscale for luminance
        gray = img.convert("L")
        stat = ImageStat.Stat(gray)
        mean_lum = stat.mean[0]
        stddev_lum = stat.stddev[0]
        min_v, max_v = stat.extrema[0]

    return {
        "width": width,
        "height": height,
        "mode": mode,
        "mean_luminance": mean_lum,
        "contrast_stddev": stddev_lum,
        "extrema": (min_v, max_v)
    }

def run_verification(target_video: str = TARGET_VIDEO):
    print("\n==================================================")
    print("  AUTOMATED QUALITY VERIFICATION (STEP 7)")
    print(f"  Target: {target_video}")
    print("==================================================\n")

    if not os.path.exists(target_video):
        print(f"ERROR: Video file not found at {target_video}")
        return False

    # 1. Stream Validation
    info = get_stream_info(target_video)
    v_stream = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a_stream = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)

    if not v_stream or not a_stream:
        print("ERROR: Missing video or audio stream.")
        sys.exit(1)

    v_dur = float(v_stream.get("duration", info["format"].get("duration", 0)))
    a_dur = float(a_stream.get("duration", info["format"].get("duration", 0)))
    dur_diff = abs(v_dur - a_dur)

    print(f"[STREAM ANALYSIS]")
    print(f"  Video Codec:    {v_stream.get('codec_name')} ({v_stream.get('width')}x{v_stream.get('height')})")
    print(f"  Audio Codec:    {a_stream.get('codec_name')} ({a_stream.get('sample_rate')} Hz, {a_stream.get('channels')} ch)")
    print(f"  Video Duration: {v_dur:.3f}s")
    print(f"  Audio Duration: {a_dur:.3f}s")
    print(f"  Sync Delta:     {dur_diff:.4f}s (Tolerance: <= 0.10s)")

    sync_pass = dur_diff <= 0.10
    if sync_pass:
        print("  -> STREAM SYNC STATUS: PASSED")
    else:
        print("  -> STREAM SYNC STATUS: FAILED")

    # 2. Corruption & Frame Decode Test
    print(f"\n[CORRUPTION & INTEGRITY CHECK]")
    print("  Decoding full stream to /dev/null...")
    no_corruption = check_corruption(target_video)
    if no_corruption:
        print("  -> ZERO corrupt or dropped frames detected. PASSED.")
    else:
        print("  -> Corrupt frames encountered! FAILED.")

    # 3. Visual & Luminance Analysis at 10%, 50%, 90%
    print(f"\n[VISUAL & LUMINANCE INSPECTION]")
    os.makedirs(TEMP_DIR, exist_ok=True)
    checkpoints = [
        ("10% (Early Scene)", 0.10 * v_dur),
        ("50% (Midpoint)", 0.50 * v_dur),
        ("90% (Climax/Dawn)", 0.90 * v_dur)
    ]

    all_frames_valid = True
    for label, ts in checkpoints:
        frame_file = os.path.join(TEMP_DIR, f"qc_frame_{int(ts)}s.png")
        extract_frame_at(target_video, ts, frame_file)
        stats = analyze_image(frame_file)

        is_1080p = (stats["width"] == 1920 and stats["height"] == 1080)
        has_proper_lum = (20.0 <= stats["mean_luminance"] <= 235.0)
        has_contrast = (stats["contrast_stddev"] > 15.0)

        passed = is_1080p and has_proper_lum and has_contrast
        if not passed:
            all_frames_valid = False

        status_str = "PASSED" if passed else "FAILED"
        print(f"  Checkpoint [{label} @ {ts:.1f}s]:")
        print(f"    Resolution:   {stats['width']}x{stats['height']} ({stats['mode']}) -> {'OK' if is_1080p else 'FAIL'}")
        print(f"    Mean Luma:    {stats['mean_luminance']:.1f} / 255.0 -> {'OK' if has_proper_lum else 'FAIL'}")
        print(f"    Contrast Dev: {stats['contrast_stddev']:.1f} -> {'OK' if has_contrast else 'FAIL'}")
        print(f"    Dynamic Range: {stats['extrema'][0]} to {stats['extrema'][1]}")
        print(f"    Status:       {status_str}")

    print("\n==================================================")
    final_verdict = sync_pass and no_corruption and all_frames_valid
    if final_verdict:
        print("  FINAL INTEGRITY VERDICT: PRODUCTION READY (100% PASSED)")
    else:
        print("  FINAL INTEGRITY VERDICT: QUALITY ISSUES DETECTED")
    print("==================================================\n")
    return final_verdict

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Automated Video Quality Verification")
    parser.add_argument("--video", type=str, default=TARGET_VIDEO, help="Path to video file")
    args = parser.parse_args()
    success = run_verification(args.video)
    sys.exit(0 if success else 1)
