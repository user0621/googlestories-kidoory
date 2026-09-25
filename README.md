# Kidoory Bedtime Stories Studio 🌙✨

Autonomous, zero-cost, multi-episode animated bedtime story production pipeline and management studio for YouTube channel **[@kidoorystory](https://www.youtube.com/@kidoorystory)**.

## Architecture & System Overview
- **Web Studio Dashboard:** Port `5009` (`http://<server-ip>:5009`)
- **Connected Channel:** `@kidoorystory` (UCobsgHbbxC3tLOpTJKkkHeg)
- **GCP Project:** `kidoory` (Service Account: `gemini-agy-linux@kidoory.iam.gserviceaccount.com`)
- **Aesthetic:** High-fidelity 3D children's storybook illustration in the heartwarming style of modern Pixar and Studio Ghibli.
- **Format:** 8–10 minute horizontal master videos (1080p, 16:9) with calm, sleep-inducing narration and drop-shadow subtitles.
- **Storage:** Persisted directly to SanDisk External SSD at `/mnt/data/google-stories/movies`.

## Zero-Cost Free Tier Guard ($0.00)
- **Google Gemini 2.5 Flash:** Google AI Studio Developer Tier (`GOOGLE_GENAI_USE_VERTEXAI=False`) with 1,500 daily requests and 15 RPM.
- **Google Cloud TTS:** Neural2 / Journey voices with 1,000,000 free characters every month.
- **YouTube Data API v3:** 10,000 units/day quota with a strict daily cap of 5 video uploads.

## Systemd Services
- `googlestories-kidoory-web.service`: Web studio dashboard on port 5009.
- `googlestories-kidoory-daemon.service`: Autonomous 24x7 story generation daemon.
- `googlestories-kidoory-guard.timer`: 4-hour platform health and channel synchronization.

## Directory Structure
```
googlestories-kidoory/
├── kidoory_web.py           # FastAPI Web Studio (Port 5009)
├── autonomous_daemon.py     # Production daemon
├── produce_episode.py       # Episodic story generator
├── produce_story.py         # 4-stage pipeline (Script -> Audio -> Visuals -> Assembly)
├── movie_architect.py       # Cinematic series bible generator
├── movie_publisher.py       # YouTube uploader & QC auditor
├── video_assembler.py       # FFmpeg 1080p Ken Burns assembly
├── tts_tracker.py           # Free tier TTS character budget enforcer
├── kidoory_health_guard.py  # 4-hour metrics synchronizer
├── templates/               # Jinja2 dashboard templates with '?' tooltips
├── static/                  # Twilight theme CSS and interactive JS
├── movies -> /mnt/data/google-stories/movies  # SanDisk SSD storage
└── output -> /data/google-stories             # Shared data storage
```
