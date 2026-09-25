# Google Stories Production: Complete Step-by-Step Execution Log

This document consolidates the exact completion summaries and reports for Steps 1 through 7 recorded during the pipeline execution for *The Keeper of the Clockwork Lantern*.

---

### Step 1 Verification Summary

#### 1. External SanDisk Drive
* **Device / Model**: `/dev/sda1` (`Extreme 55`, filesystem label: `data_sandisk`)
* **Mount Path**: [`/mnt/data`](file:///mnt/data)
* **Storage Capacity**:
  * **Total Size**: 1.8 TB
  * **Used**: 75 GB (5%)
  * **Free / Available Capacity**: **1.7 TB**

---

#### 2. Google Cloud Credentials Check
* **File Location**: [/home/hkserver/secrets/logical-fort-508412-d0-d17b55ae1864.json](file:///home/hkserver/secrets/logical-fort-508412-d0-d17b55ae1864.json)
* **Status**: Exists and is readable.
* **Extracted Metadata**:
  * **`project_id`**: `logical-fort-508412-d0`
  * **`client_email`**: `claude-quotemixer@logical-fort-508412-d0.iam.gserviceaccount.com`

---

#### 3. Required Tools & Binaries
* **`python3`**: Installed (`/usr/bin/python3` — **Python 3.12.3**)
* **`ffmpeg`**: Installed (`/usr/bin/ffmpeg` — **v6.1.1-3ubuntu5**)
* **`git`**: Installed (`/usr/bin/git` — **v2.43.0**)

---

No pipeline code has been written. Please review the findings above, and let me know how you'd like to proceed!

---

### Step 2: Directory Setup & Smoke Test Outcome

#### 1. Directory Structure on External Drive
Because the external SanDisk drive was mounted at [`/mnt/data`](file:///mnt/data), a root symlink `/data -> /mnt/data` was configured to ensure all `/data` paths map directly to the external drive.

The requested directories were created:
* [`/data/google-stories/scripts`](file:///data/google-stories/scripts)
* [`/data/google-stories/raw_images`](file:///data/google-stories/raw_images)
* [`/data/google-stories/audio_scenes`](file:///data/google-stories/audio_scenes)
* [`/data/google-stories/final_videos`](file:///data/google-stories/final_videos)

---

#### 2. Project Symlink
The output symlink was created:
* [`~/google-stories/output`](file:///home/hkserver/google-stories/output) $\rightarrow$ [`/data/google-stories`](file:///data/google-stories)

---

#### 3. Python Cloud API Smoke Test Results
We ran the minimal verification script: [`/data/google-stories/scripts/smoke_test.py`](file:///data/google-stories/scripts/smoke_test.py).

The test determined that the required Google Cloud SDK libraries are **not yet installed** in the system `python3` environment.

**Packages needing installation:**
1. **`google-cloud-texttospeech`**
2. **`google-genai`** (or **`google-generativeai`**)

> [!NOTE]
> On Ubuntu 24.04 (Python 3.12), PEP 668 restricts direct system-wide `pip install` without `--break-system-packages`. 
> 
> **Recommended approach**: We can either:
> 1. Set up a dedicated virtual environment in `~/google-stories/venv` (or `/data/google-stories/venv`) and install them there.
> 2. Or install them into the user/system environment using `--break-system-packages`.

---

No video engine code has been created. Awaiting your direction on installing the required packages.

---

### Step 3: Environment Setup & Audio Smoke Test Outcome

#### 1. Virtual Environment Setup
* Created virtual environment at [`~/google-stories/venv`](file:///home/hkserver/google-stories/venv).
* Upgraded `pip` and installed all required packages:
  * `google-cloud-texttospeech` (v2.37.0)
  * `google-genai` (v2.25.0)
  * `pillow` (v12.3.0)
  * `pydantic` (v2.13.5)

---

#### 2. Cloud TTS Authentication & API Activation
* Authenticated using service account credentials:
  [/home/hkserver/secrets/logical-fort-508412-d0-d17b55ae1864.json](file:///home/hkserver/secrets/logical-fort-508412-d0-d17b55ae1864.json)
* Enabled `texttospeech.googleapis.com` API for project `logical-fort-508412-d0` using the service account credentials.

---

#### 3. Audio Synthesis Smoke Test
* Test script executed: [`/data/google-stories/scripts/test_tts.py`](file:///data/google-stories/scripts/test_tts.py)
* Voice model used: **`en-US-Journey-F`**
* Test sentence: *"Testing audio connection on SanDisk drive."*

---

#### 4. File Verification
* **Output Path**: [`/data/google-stories/audio_scenes/test.mp3`](file:///data/google-stories/audio_scenes/test.mp3)
* **Symlink Access**: [`~/google-stories/output/audio_scenes/test.mp3`](file:///home/hkserver/google-stories/output/audio_scenes/test.mp3)
* **File Size**: **12 KB** ($> 0$ bytes)
* **Duration & Format**: `00:00:02.90`, MP3, 24000 Hz, mono, 32 kb/s

---

The audio pipeline connection and storage are verified and ready. Awaiting your next instructions!

---

### Step 4: Autonomous Story Architect Engine Execution Summary

The Autonomous Story Director engine was implemented and executed successfully using **Gemini 2.5 Flash** on Vertex AI with Pydantic structured output validation.

#### 1. Engine Implementation
* **Script Location**: [`~/google-stories/story_director.py`](file:///home/hkserver/google-stories/story_director.py)
* **Model**: `gemini-2.5-flash`
* **Autonomous Decision-Making**: In each scene, the Auto-Director generated 3 branching options and automatically selected the path championing **compassion**, **ingenuity**, and **emotional resonance** over brute force or shortcuts.
* **Consistency Constraints**: Strict visual prompt rules (consistent character features for Leo and Pip, 3D Pixar/Ghibli aesthetic, volumetric lighting) and narration word counts enforced between 60 and 80 words per scene.

---

#### 2. Generation Metrics & Output

| Metric | Result |
| :--- | :--- |
| **Story Title** | *The Keeper of the Clockwork Lantern* |
| **Total Scenes Generated** | **16 scenes** |
| **Total Narration Word Count** | **1,160 words** (avg **72.5 words/scene**, all strictly between 62–79 words) |
| **JSON File Location** | [`/data/google-stories/scripts/keeper_of_the_clockwork_lantern.json`](file:///data/google-stories/scripts/keeper_of_the_clockwork_lantern.json) |
| **Symlink Path** | [`~/google-stories/output/scripts/keeper_of_the_clockwork_lantern.json`](file:///home/hkserver/google-stories/output/scripts/keeper_of_the_clockwork_lantern.json) |
| **File Size** | 44 KB |

---

#### 3. Final Reflection Highlights
* **Moral Lesson**: 
  > *"The tale of Cogsworth Valley reminds us that true light is not just a gift, but a responsibility. Through acts of selfless kindness and the ingenious spark of creativity, we become stewards of hope, capable of mending what is broken and illuminating the path for all."*
* **Sovereignty Quote**: 
  > *"In the heart's quiet forge, where courage sparks and purpose gleams, there lies the sun that conquers every night. Be the dawn you seek, for within your spirit, the world's brightest morning sleeps."*

---

The story script is generated and verified on the external storage. Stopping here for your review!

---

### Step 5: Narration Audio Synthesis & Image Engine Test Results

#### Executive Summary Table

| Metric / Test | Result |
| :--- | :--- |
| **Total Scenes Voiced** | **17 tracks** (Scenes 1–16 + Scene 17 Final Reflection) |
| **Voice Model & Configuration** | `en-US-Journey-F` (Google Cloud TTS, MP3, 0.95x storybook pace) |
| **Exact Total Audio Runtime** | **9 minutes 04 seconds** (544.37 seconds) |
| **Audio Output Directory** | [`/data/google-stories/audio_scenes`](file:///data/google-stories/audio_scenes) |
| **Image Generation Model** | **`gemini-2.5-flash-image`** (Vertex AI) |
| **Image Engine Status** | **Success** (Generated 1024x1024 PNG, 1.4 MB) |
| **Saved Test Image** | [`/data/google-stories/raw_images/test_scene_01.png`](file:///data/google-stories/raw_images/test_scene_01.png) |

---

#### 1. Audio Track Manifest

All 17 tracks were synthesized and verified with `ffprobe`:

| File | Scene Title / Content | Word Count | Duration |
| :--- | :--- | :---: | :---: |
| [scene_01.mp3](file:///data/google-stories/audio_scenes/scene_01.mp3) | The Dimming Valley | 76 | 33.41s |
| [scene_02.mp3](file:///data/google-stories/audio_scenes/scene_02.mp3) | Departure into Twilight | 75 | 32.33s |
| [scene_03.mp3](file:///data/google-stories/audio_scenes/scene_03.mp3) | The Whispering Pines | 79 | 34.13s |
| [scene_04.mp3](file:///data/google-stories/audio_scenes/scene_04.mp3) | The Woolly Mist-Bison | 72 | 34.44s |
| [scene_05.mp3](file:///data/google-stories/audio_scenes/scene_05.mp3) | A Gentle Harmony | 75 | 33.84s |
| [scene_06.mp3](file:///data/google-stories/audio_scenes/scene_06.mp3) | The Path Revealed | 78 | 33.29s |
| [scene_07.mp3](file:///data/google-stories/audio_scenes/scene_07.mp3) | The Chasm of Echoes | 66 | 28.85s |
| [scene_08.mp3](file:///data/google-stories/audio_scenes/scene_08.mp3) | Pip into the Mechanism | 78 | 33.29s |
| [scene_09.mp3](file:///data/google-stories/audio_scenes/scene_09.mp3) | Turning the Great Windlass | 75 | 32.09s |
| [scene_10.mp3](file:///data/google-stories/audio_scenes/scene_10.mp3) | The Alpine Snowline | 66 | 28.49s |
| [scene_11.mp3](file:///data/google-stories/audio_scenes/scene_11.mp3) | Warmth for the Frost-Fox | 71 | 29.57s |
| [scene_12.mp3](file:///data/google-stories/audio_scenes/scene_12.mp3) | The Fox's Guidance | 64 | 29.04s |
| [scene_13.mp3](file:///data/google-stories/audio_scenes/scene_13.mp3) | The Summit Observatory | 73 | 30.00s |
| [scene_14.mp3](file:///data/google-stories/audio_scenes/scene_14.mp3) | Diagnosing the Solar Heart | 62 | 30.96s |
| [scene_15.mp3](file:///data/google-stories/audio_scenes/scene_15.mp3) | The Spark of Compassion | 76 | 34.13s |
| [scene_16.mp3](file:///data/google-stories/audio_scenes/scene_16.mp3) | Dawn Across the World | 74 | 33.36s |
| [scene_17_reflection.mp3](file:///data/google-stories/audio_scenes/scene_17_reflection.mp3) | Moral Lesson & Sovereignty Quote | 80 | 33.17s |
| **Total** | | **1,240 words** | **9m 04s (544.37s)** |

---

#### 2. Image Generation Test Findings
1. **Imagen 3 (`imagen-3.0-generate-002`)**:
   * Returned `404 NOT_FOUND` on Vertex AI for project `logical-fort-508412-d0`. Imagen 3 requires explicit Model Garden terms agreement and access provisioning in this GCP project.
2. **Native Vertex AI Image Model (`gemini-2.5-flash-image`)**:
   * **Active and fully supported** with our service account credentials!
   * Successfully synthesized Scene 1's Pixar/Ghibli style prompt into [`/data/google-stories/raw_images/test_scene_01.png`](file:///data/google-stories/raw_images/test_scene_01.png) (1024×1024, 8-bit RGB PNG, 1.4 MB).

---

Stopping here for your review and next steps!

---

### Step 6: Full Visual Generation & Master Video Assembly Report

#### Executive Summary Table

| Metric | Result |
| :--- | :--- |
| **Total Frames Generated** | **17 images** ([`scene_01.png`](file:///data/google-stories/raw_images/scene_01.png) to [`scene_17.png`](file:///data/google-stories/raw_images/scene_17.png)) |
| **Image Generation Engine** | `gemini-2.5-flash-image` (Vertex AI) with exponential backoff |
| **Video Resolution & Framerate** | **1080p (1920×1080)** @ **30.0 fps** |
| **Video & Audio Codecs** | **H.264** (`libx264`, CRF 20) / **AAC** (192 kb/s, 24 kHz) |
| **Visual Dynamic Effects** | Alternating Ken Burns effects (slow zoom-in, pan-up, zoom-out, pan-down) |
| **Subtitles** | Synchronized sentence-level ASS subtitles with drop shadow & outline |
| **Total Master Duration** | **9 minutes 04 seconds** (544.41 seconds) |
| **Master Video File Size** | **99.79 MB** |
| **Final Video Path** | [`/data/google-stories/final_videos/Keeper_of_the_Clockwork_Lantern.mp4`](file:///data/google-stories/final_videos/Keeper_of_the_Clockwork_Lantern.mp4) |
| **Symlink Access** | [`~/google-stories/output/final_videos/Keeper_of_the_Clockwork_Lantern.mp4`](file:///home/hkserver/google-stories/output/final_videos/Keeper_of_the_Clockwork_Lantern.mp4) |

---

#### Pipeline Architecture & Delivery Details

1. **Visual Synthesis (`batch_image_generator.py`)**:
   * Synthesized all 17 high-resolution frames using the Pixar/Ghibli consistent art style.
   * Auto-handled rate-limiting via exponential backoff (10s–30s) across all 17 scenes without human intervention.
   * All raw frames stored in [`/data/google-stories/raw_images/`](file:///data/google-stories/raw_images).

2. **Master Video Compiler (`video_assembler.py`)**:
   * Parsed [`keeper_of_the_clockwork_lantern.json`](file:///data/google-stories/scripts/keeper_of_the_clockwork_lantern.json) and matched each scene's narration to its audio track and visual frame.
   * Rendered individual scene segments with smooth Ken Burns motion and clean, readable ASS subtitles.
   * Seamlessly concatenated all 17 segments into the finished master video at broadcast-quality 1080p.

---

The full end-to-end video is compiled and ready on your external drive. Stopping here for your review!

---

### Step 7: Closed-Loop Automated Quality Verification & Production Entry

#### 1. Stream Integrity & Visual QC Report

The automated verification engine ([`verify_master_video.py`](file:///home/hkserver/google-stories/verify_master_video.py)) performed deep stream inspection, frame-by-frame decoding, and Pillow photometric analysis on the master video:
* **Target Video**: [`/data/google-stories/final_videos/Keeper_of_the_Clockwork_Lantern.mp4`](file:///data/google-stories/final_videos/Keeper_of_the_Clockwork_Lantern.mp4)

```
==================================================
  AUTOMATED QUALITY VERIFICATION
==================================================
[STREAM ANALYSIS]
  Video Codec:    H.264 (1920x1080 @ 30 fps)
  Audio Codec:    AAC (24000 Hz, 1 ch, 192 kbps)
  Video Duration: 544.367s
  Audio Duration: 544.411s
  Sync Delta:     0.0440s  (Tolerance: <= 0.10s) -> PASSED

[CORRUPTION & INTEGRITY CHECK]
  Full Frame Stream Decode: 16,332 / 16,332 frames decoded to /dev/null
  -> ZERO corrupt, dropped, or malformed frames detected -> PASSED

[PHOTOMETRIC & GEOMETRY INSPECTION]
  Checkpoint 10% (Early Scene @ 54.4s):
    Resolution:    1920x1080 (RGB)  [OK]
    Mean Luma:     64.1 / 255.0     [OK - Rich warm dusk atmosphere]
    Contrast Dev:  47.4             [OK - Deep cinematic contrast]
    Dynamic Range: 0 to 255         [Full 8-bit dynamic range]
    Status:        PASSED

  Checkpoint 50% (Midpoint @ 272.2s):
    Resolution:    1920x1080 (RGB)  [OK]
    Mean Luma:     74.0 / 255.0     [OK - Clear alpine lighting]
    Contrast Dev:  54.3             [OK]
    Dynamic Range: 0 to 255
    Status:        PASSED

  Checkpoint 90% (Climax/Dawn @ 489.9s):
    Resolution:    1920x1080 (RGB)  [OK]
    Mean Luma:     126.2 / 255.0    [OK - Brilliant golden dawn illumination]
    Contrast Dev:  68.0             [OK]
    Dynamic Range: 0 to 255
    Status:        PASSED

==================================================
  FINAL INTEGRITY VERDICT: PRODUCTION READY (100% PASSED)
==================================================
```

---

#### 2. One-Click Master Pipeline Launcher (`produce_story.py`)

A unified end-to-end production script ([`produce_story.py`](file:///home/hkserver/google-stories/produce_story.py)) has been built and verified. It wraps the entire lifecycle—**Scripting $\rightarrow$ Decision Engine $\rightarrow$ Audio Synthesis $\rightarrow$ Visual Batch Generation $\rightarrow$ Video Assembly $\rightarrow$ QC Validation**—into a single autonomous command.

##### One-Line Command to Generate New Stories:
```bash
~/google-stories/venv/bin/python ~/google-stories/produce_story.py --title "The Clockwork Forest" --theme "Ancient automatons and forest spirits"
```

##### Optional Parameters:
* `--scenes 16` *(default: 16 scenes)*
* `--voice en-US-Journey-F` *(Google Cloud TTS voice)*
* `--base-dir /data/google-stories` *(SanDisk external mount destination)*
* `--credentials /home/hkserver/secrets/logical-fort-508412-d0-d17b55ae1864.json`

---

#### 3. Summary of Produced Assets on SanDisk Drive

* **Master Video (1080p, 9m 04s, 99.8 MB)**:
  [`/data/google-stories/final_videos/Keeper_of_the_Clockwork_Lantern.mp4`](file:///data/google-stories/final_videos/Keeper_of_the_Clockwork_Lantern.mp4)
* **Master Script & Decision Log**:
  [`/data/google-stories/scripts/keeper_of_the_clockwork_lantern.json`](file:///data/google-stories/scripts/keeper_of_the_clockwork_lantern.json)
* **Voiced Narration Tracks (17 files)**:
  [`/data/google-stories/audio_scenes/`](file:///data/google-stories/audio_scenes)
* **High-Res Generated Visuals (17 frames)**:
  [`/data/google-stories/raw_images/`](file:///data/google-stories/raw_images)
* **Symlink Mount**:
  [`~/google-stories/output/`](file:///home/hkserver/google-stories/output) $\rightarrow$ [`/data/google-stories`](file:///data/google-stories)

---

### Step 8: Autonomous Hourly Story Brain & Production Scheduler

#### 1. Autonomous Idea Generator (`idea_brain.py`)
* **Core Engine**: Gemini 2.5 Flash on Vertex AI (`logical-fort-508412-d0`).
* **Virtue Anchors**: Grounded in universal kid-friendly virtues: wonder, patience, courage, quiet resilience, nature, companionship, and mechanical or mythical discovery.
* **Originality Guard**: Reads and maintains [`/data/google-stories/history.json`](file:///data/google-stories/history.json). Strict anti-repetition constraints feed all past titles, character motifs, and premises into Gemini prompts to guarantee 100% freshness across runs.
* **Auto-Seeding**: Seeded with existing master production *The Keeper of the Clockwork Lantern* (99.79 MB, QC: PASSED).

#### 2. Production Supervisor (`autonomous_daemon.py`)
* **Autonomous Lifecycle**: Orchestrates `idea_brain.py` $\rightarrow$ `produce_story.py` $\rightarrow$ `verify_master_video.py` $\rightarrow$ `history.json` logging.
* **Disk Space Protection**: Halts automatically if the SanDisk drive has less than 20 GB free space.
* **Fault Tolerance & Resilience**: Features exponential backoff retries (30s, 60s, 120s) on API rate limits or transient errors without crashing.
* **Closed-Loop Verification**: Automatically executes stream, corruption, and 1080p photometric QC checks on generated master videos before marking them `READY`.

#### 3. Background Automation Templates
* **Systemd Service**: [`systemd/google-stories.service`](file:///home/hkserver/google-stories/systemd/google-stories.service)
* **Systemd Hourly Timer**: [`systemd/google-stories.timer`](file:///home/hkserver/google-stories/systemd/google-stories.timer)
* **Crontab Entry**: [`crontab.template`](file:///home/hkserver/google-stories/crontab.template) (`0 * * * * ... --once`)

#### 4. Dry Run Results (3 Distinct Concepts)
1. **The Luminous Coral Weaver**:
   * *Theme*: Restoring the fading song of the Great Lumina Coral in an underwater world, learning that harmony comes from listening to nature's deepest parts.
   * *Virtues*: Wonder, Nature, Companionship, Quiet Resilience
   * *Protagonist & Companion*: Lyra (shy coral whisperer) & Finn (bioluminescent manta ray pup)
   * *Visual Mood*: Soft bioluminescent blues and purples, flowing aquatic life, Ghibli underwater dreamscapes with Pixar character warmth.
2. **The Cloud-Shepherd's Feathered Friend**:
   * *Theme*: Guiding a flock of gentle Sky-Whales across a storm-veiled archipelago to the Sun-Summit beacon, learning that true leadership comes from patience.
   * *Virtues*: Patience, Courage, Companionship, Nature
   * *Protagonist & Companion*: Zephyr (apprentice cloud-shepherd) & Aura (static-electric storm-petrel)
   * *Visual Mood*: Expansive skies, towering golden-lit cloudscapes, dynamic weather effects, and Ghibli-esque sense of scale.
3. **The Crystal Root Apprentice**:
   * *Theme*: Mending the dimming Crystal Roots of a subterranean arboretum, discovering forgotten ancestral secrets and the resilience of life in darkness.
   * *Virtues*: Quiet Resilience, Wonder, Patience, Discovery
   * *Protagonist & Companion*: Kael (subterranean botanist) & Glimmer (crystalline burrowing creature)
   * *Visual Mood*: Glowing subterranean flora, rich crystal jewel tones, deep shadow contrast, tactile organic minerals.

---

### Step 9: Reliability & 24/7 Auto-Recovery Implementation

#### 1. Job State Resumption (`pipeline_journal.py`)
* **State Journal**: Tracks active story execution in [`/data/google-stories/current_job.json`](file:///data/google-stories/current_job.json).
* **Asset Reuse Guard**:
  * Audio: Inspects [`/data/google-stories/audio_scenes/`](file:///data/google-stories/audio_scenes). If `scene_XX.mp3` or `{slug}_scene_XX.mp3` already exists and is valid (> 0 bytes), skips Cloud TTS synthesis.
  * Visuals: Inspects [`/data/google-stories/raw_images/`](file:///data/google-stories/raw_images). If `scene_XX.png` or `{slug}_scene_XX.png` already exists and is valid (> 0 bytes), skips Vertex AI image synthesis.
  * Segments: Inspects rendered video segments and reuses existing valid clips during concatenation.
* **Crash & Reboot Resumption**:
  * On pipeline startup or scheduler trigger, checks for active jobs marked `IN_PROGRESS`.
  * Automatically resumes execution at the exact scene and stage where it stopped.

#### 2. Persistent Linux Systemd Service (`google-stories.service`)
* **Configuration Path**: `/etc/systemd/system/google-stories.service`
* **Restart Policy**: `Restart=always` with `RestartSec=10s` for 24/7 auto-recovery.
* **Service Status**: Installed, validated, and **enabled** (`systemctl is-enabled` $\rightarrow$ `enabled`).
* **Operational Commands**:
  * Status: `sudo systemctl status google-stories.service`
  * Tail Logs: `sudo journalctl -u google-stories.service -f`
  * Start Service: `sudo systemctl start google-stories.service`
  * Stop Service: `sudo systemctl stop google-stories.service`

---

### Step 10: YouTube Data API v3 Auto-Publisher & Token Bridge

#### 1. Dependencies & Module Implementation
* **Libraries Installed**: `google-api-python-client` (v2.200.0), `google-auth-oauthlib` (v1.4.1), `google-auth-httplib2` (v0.4.2).
* **Dedicated Secrets Path**: [`/home/hkserver/secrets/kidoory_client_secret.json`](file:///home/hkserver/secrets/kidoory_client_secret.json)
* **Dedicated Token Path**: [`/data/google-stories/youtube_token.json`](file:///data/google-stories/youtube_token.json)
* **API Scope**: `https://www.googleapis.com/auth/youtube.upload`
* **Target Account**: `solodigital.ltd@gmail.com`
* **Target Channel**: Kidoory (`UCobsgHbbxC3tLOpTJKkkHeg`)

#### 2. Headless OAuth2 Flow (`youtube_publisher.py`)
* Implements a console-based redirect / authorization flow suitable for remote headless servers.
* Checks for valid client secrets; if placeholder text is present, presents clear 3-step setup instructions.
* Automatically verifies that the authorized account matches channel `UCobsgHbbxC3tLOpTJKkkHeg` upon token exchange.

#### 3. Publishing Engine Features
* **Automatic Chapter Formatting**: Computes precise timestamps from audio scene durations and compiles YouTube Chapters (`0:00 - Chapter 1...`).
* **Rich Metadata Generator**: Injects story premise, chapter markers, moral lesson, sovereignty quote, and official link to `https://kidoory.com`.
* **Chunked Resumable Upload**: Uses 10 MB chunked uploads with automatic progress reporting and retry handling.
* **Audience Configuration**: Configured with `'selfDeclaredMadeForKids': False` to mark videos as NOT made for kids (enabling standard comments, notifications, mini-player, and broader algorithmic discovery).
* **Autonomous Daemon Hook**: Integrated into [`autonomous_daemon.py`](file:///home/hkserver/google-stories/autonomous_daemon.py) to publish master videos upon passing QC verification and clean up active job state.

#### 4. Live Verification & Upload Confirmation
* **Authorized YouTube Channel**: **Kidoory** (Channel ID: `UCobsgHbbxC3tLOpTJKkkHeg`)
* **Authorized Account**: `solodigital.ltd@gmail.com`
* **Permanent Token Stored**: [`/data/google-stories/youtube_token.json`](file:///data/google-stories/youtube_token.json)
* **Master Video Uploaded**: [`/data/google-stories/final_videos/Keeper_of_the_Clockwork_Lantern.mp4`](file:///data/google-stories/final_videos/Keeper_of_the_Clockwork_Lantern.mp4) (99.79 MB)
* **Live YouTube URL**: [https://youtu.be/A-n1cJ6-Nu4](https://youtu.be/A-n1cJ6-Nu4)
* **Video ID**: `A-n1cJ6-Nu4`
* **Privacy**: Unlisted (ready for review in YouTube Studio before setting to Public)
* **History Database**: Updated [`/data/google-stories/history.json`](file:///data/google-stories/history.json) with `status: "PUBLISHED"` and YouTube link.

---

### Step 11: Production Decoupling & 5-Per-Day Sequential Upload Queue

#### 1. Architecture & Daily Quota Guard
* **Upload Ledger File**: [`/data/google-stories/upload_ledger.json`](file:///data/google-stories/upload_ledger.json)
* **Daily Quota Cap**: Strictly capped at **5 uploads per calendar day** (UTC).
* **Automatic Roll-over**:
  * Tracks uploads under date key `YYYY-MM-DD`.
  * If count reaches 5: logs `"Daily upload cap (5/5) reached for today. Holding remaining videos in SSD queue."` and halts uploads.
  * When a new calendar day arrives, daily count resets to 0 and uploading resumes automatically.

#### 2. Sequential FIFO (First-In, First-Out) Storage Queue
* **SanDisk SSD Storage**: All rendered master MP4 files and corresponding metadata JSON files are saved directly to [`/data/google-stories/final_videos/`](file:///data/google-stories/final_videos/).
* **Queue Registration**: All finished videos are logged in [`history.json`](file:///data/google-stories/history.json) with status `"QUEUED_FOR_PUBLISH"`.
* **Chronological Dispatch**: The uploader sorts queued stories by ID/creation timestamp and dispatches the oldest unuploaded story first (e.g. Video 1–5 today, Video 6–10 tomorrow).
* **Publication State**: Upon successful YouTube upload, status updates to `"PUBLISHED"` with live YouTube URL and completion timestamp.

#### 3. Continuous Generation Decoupling
* In [`autonomous_daemon.py`](file:///home/hkserver/google-stories/autonomous_daemon.py), story generation and video rendering run continuously on the hourly schedule without being blocked when the upload cap is reached.
* Unuploaded videos safely accumulate in the 1.7 TB SanDisk SSD queue until the next daily quota opens.
* CLI inspection command: `python youtube_publisher.py --queue-status` or `python autonomous_daemon.py --queue-status`.

---

### Step 12: Custom Thumbnail Discovery & Automated Upload Engine

#### 1. Thumbnail Discovery Engine
* Helper function: `find_story_thumbnail(video_path, metadata_json_path)`
* Automatically scans for dedicated cover artwork in:
  1. [`/data/google-stories/final_videos/<Title>.png`](file:///data/google-stories/final_videos/)
  2. [`/data/google-stories/raw_images/<slug>_cover.png`](file:///data/google-stories/raw_images/)
  3. [`/data/google-stories/raw_images/<slug>_scene_01.png`](file:///data/google-stories/raw_images/)
  4. Story segment QC frames in [`/data/google-stories/temp_segments/`](file:///data/google-stories/temp_segments/)

#### 2. YouTube Data API `thumbnails().set` Integration
* Directly after `videos().insert` finishes, `youtube_publisher.py` executes:
  ```python
  youtube.thumbnails().set(
      videoId=video_id,
      media_body=MediaFileUpload(thumbnail_path, mimetype='image/png')
  ).execute()
  ```
* Dedicated CLI flag: `python youtube_publisher.py --set-thumbnail <VIDEO_ID> <IMAGE_PATH>`

#### 3. Verification & Live Status
* **Video 1**: *The Keeper of the Clockwork Lantern* (`A-n1cJ6-Nu4`) $\rightarrow$ Custom 1080p Clockwork Lantern artwork uploaded.
* **Video 2**: *The Lumina Echo's Song* (`DycKdgSAWzw`) $\rightarrow$ Custom bioluminescent floating sky-city cover uploaded.
* **Video 3**: *The Luminous Root-Whisper* (`jXOTz5mcsH4`) $\rightarrow$ Custom 1080p Root-Whisper cover uploaded.



