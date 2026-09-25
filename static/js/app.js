// Kidoory Bedtime Stories Studio Frontend Controller

// Comprehensive Help Dictionary for all '?' Buttons
const HELP_TEXTS = {
  universe: {
    title: "Active Universe & Multi-Episode Series",
    content: "Kidoory Bedtime Stories operates in cinematic 'Universes' (multi-episode animated bedtime movies). Each Universe (e.g., Movie 002: 'Luna and the Lumina Dreams') contains 12 episodic chapters with persistent character visual continuity (clothing, boots, amulets) and narrative progression. All files are safely rendered to your SanDisk external SSD."
  },
  produce_btn: {
    title: "Produce Next Episode Action",
    content: "Launches the autonomous 4-stage pipeline in the background:\n1. Screenwriting: Generates 8 sequential bedtime scenes with soothing pacing using Gemini 2.5 Flash.\n2. Audio: Synthesizes high-fidelity narration using Google Cloud TTS (Neural2/Journey).\n3. Visuals: Creates 8 cinematic 3D storybook illustrations via Gemini Image Generation.\n4. Assembly: Encodes 1080p horizontal master MP4 with soft Ken Burns pan, ambient sleep music, and drop-shadow subtitles."
  },
  publish_btn: {
    title: "Publish Ready Episode",
    content: "Uploads the newest verified master MP4 from /data/google-stories/movies/ to your connected YouTube channel (@kidoorystory). Sets title, chapter timestamps, soothing bedtime tags, and enforces the daily safety cap of 5 uploads."
  },
  health_btn: {
    title: "Sync Health Guard",
    content: "Pings YouTube Data API v3 to retrieve live subscriber counts, video views, and OAuth token freshness. Also verifies external SSD mount free space and Google AI Studio Developer API availability."
  },
  channel: {
    title: "Connected YouTube Channel (@kidoorystory)",
    content: "Your official public YouTube channel for calming children's bedtime stories. Authenticated via OAuth 2.0 through your solodigital.ltd@gmail.com account using client secrets in ~/secrets/kidoory_client_secret.json."
  },
  subs: {
    title: "Subscribers",
    content: "Live subscriber count for @kidoorystory pulled directly from the YouTube Data API v3."
  },
  views: {
    title: "Lifetime Channel Views",
    content: "Total view count across all published videos on the channel."
  },
  published: {
    title: "Total Published Stories",
    content: "Total number of finished master bedtime episodes uploaded and published since channel launch."
  },
  daily_cap: {
    title: "Daily Upload Limit (5 / Day)",
    content: "YouTube limits unverified API projects to 10,000 quota units per day. Each video upload costs 1,600 units. To guarantee you never hit quota limits or risk spam flags, Kidoory enforces a strict cap of 5 videos per 24-hour cycle (8,000 units max)."
  },
  quotas: {
    title: "Zero-Cost Free Tier Quota Telemetry",
    content: "This panel tracks your real-time consumption against Google's Free Tier quotas. Kidoory is configured with GOOGLE_GENAI_USE_VERTEXAI=False to strictly use Google AI Studio's $0.00 Developer Free Tier, ensuring zero cloud expenses."
  },
  gemini_quota: {
    title: "Google Gemini 2.5 Flash Quota",
    content: "Google AI Studio grants 1,500 Requests Per Day (RPD) and 15 Requests Per Minute (RPM) at 100% free of charge. Story scripting consumes ~2 requests per episode, using less than 1% of your daily free allowance."
  },
  tts_quota: {
    title: "Google Cloud Text-to-Speech Free Tier",
    content: "Google Cloud provides 1,000,000 characters free every single month for Neural2/Journey voices. A typical 8-scene bedtime story uses ~4,500 characters. At 5 stories per day, you use ~135,000 characters/month—well within the 1M free character tier ($0.00 spent)."
  },
  youtube_quota: {
    title: "YouTube Data API v3 Quota",
    content: "Google provides 10,000 quota units every day for free. Each video insert costs 1,600 units. Daily cap of 5 uploads = 8,000 units, leaving 2,000 buffer units for channel status and comment monitoring."
  },
  video_player: {
    title: "Master Video Player",
    content: "Streams the latest rendered 1080p master video directly from the SanDisk external SSD (/data/google-stories/movies/...). You can review video pacing, narration, subtitles, and visual quality directly inside this studio."
  },
  secrets: {
    title: "API Keys & Service Secrets Security",
    content: "For security, all API keys, OAuth client secrets, and service account tokens are masked by default. Clicking 'Reveal' temporarily reveals the plaintext key in your browser for 6 seconds, after which it automatically re-masks itself."
  },
  key_gemini: {
    title: "Kidoory Gemini API Key",
    content: "Your Google AI Studio API key used for screenplay generation, scene prompts, and director decisions. Configured in .env as KIDOORY_GEMINI_API_KEY."
  },
  key_sa: {
    title: "Google Cloud Service Account",
    content: "The IAM service account (gemini-agy-linux@kidoory.iam.gserviceaccount.com) in project 'kidoory' used to authenticate Google Cloud Text-To-Speech. File: ~/secrets/kidoory-7590452277b9.json."
  },
  key_yt_client: {
    title: "YouTube OAuth Client ID",
    content: "The Google OAuth 2.0 Web Application client identifier configured in Google Cloud Console under project 'kidoory'."
  },
  key_yt_secret: {
    title: "YouTube OAuth Client Secret",
    content: "The private client secret corresponding to your YouTube OAuth application."
  },
  key_yt_token: {
    title: "YouTube OAuth Refresh Token",
    content: "The permanent offline authorization token that allows the autonomous engine to publish bedtime videos to @kidoorystory without requiring repeated manual browser logins."
  },
  history: {
    title: "Published Bedtime Stories Ledger",
    content: "The permanent audit log of all video episodes posted to YouTube, recorded in /data/google-stories/upload_ledger.json with direct links to watch on YouTube."
  },
  episodes_queue: {
    title: "Movie Universes & Episode Publishing Queue",
    content: "All rendered 1080p horizontal bedtime story master episodes across your movie series. Each episode has its companion metadata JSON with chapters, tags, and moral lessons. You can manually post any episode with one click or let the autonomous daemon publish on schedule. The Duplicate Shield prevents duplicate uploads and automatically groups all episodes under their series playlist."
  },
  post_youtube_btn: {
    title: "Post to YouTube (Manual Publish)",
    content: "Clicking 'Post to YouTube' reads the companion JSON file (SEO title, description, tags, scene chapters), checks YouTube live channel to avoid duplicate uploads, publishes the master MP4, uploads the custom thumbnail, and adds the episode to the series playlist."
  },
  playlist_info: {
    title: "Movie Series YouTube Playlist",
    content: "All episodes for this movie series are automatically organized into this dedicated YouTube playlist on @kidoorystory (e.g., 'Luna Blossom and the Dreamlight Quest 🌙 | Kidoory Bedtime Stories'). Children and parents can stream the entire bedtime journey continuously."
  },
  oauth_upgrade: {
    title: "YouTube OAuth Scopes & Permissions",
    content: "YouTube Data API requires specific OAuth scopes. 'youtube.upload' permits video publishing. 'youtube' permits playlist creation and video insertion. Use 'Authorize Playlists' to consent the full scope with solodigital.ltd@gmail.com."
  }
};

// Help Modal Controls
function showHelp(topicKey) {
  const modal = document.getElementById("helpModal");
  const title = document.getElementById("helpTitle");
  const content = document.getElementById("helpContent");
  const item = HELP_TEXTS[topicKey];

  if (item) {
    title.innerText = item.title;
    content.innerText = item.content;
    modal.style.display = "flex";
  }
}

function closeHelp(e) {
  if (e) e.stopPropagation();
  const modal = document.getElementById("helpModal");
  modal.style.display = "none";
}

// Reveal Key with Auto-Hiding Timer
const revealTimers = {};

async function revealKey(secretName) {
  const inputEl = document.getElementById(`input_${secretName}`);
  const btnEl = document.getElementById(`btn_${secretName}`);
  const timerTag = document.getElementById(`timer_${secretName}`);

  if (!inputEl) return;

  // If already revealing, cancel existing timer
  if (revealTimers[secretName]) {
    clearInterval(revealTimers[secretName]);
  }

  btnEl.disabled = true;
  btnEl.innerText = "Fetching...";

  try {
    const res = await fetch("/api/secrets/reveal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ secret_name: secretName })
    });

    if (!res.ok) throw new Error("Unauthorized or not found");

    const data = await res.json();
    inputEl.type = "text";
    inputEl.value = data.value;

    let secondsLeft = 6;
    timerTag.style.display = "block";
    timerTag.innerText = `Auto-masking in ${secondsLeft}s...`;
    btnEl.innerText = "Revealed";

    revealTimers[secretName] = setInterval(() => {
      secondsLeft -= 1;
      if (secondsLeft <= 0) {
        clearInterval(revealTimers[secretName]);
        delete revealTimers[secretName];
        inputEl.type = "password";
        timerTag.style.display = "none";
        btnEl.innerText = "👁️ Show";
        btnEl.disabled = false;
      } else {
        timerTag.innerText = `Auto-masking in ${secondsLeft}s...`;
      }
    }, 1000);

  } catch (err) {
    btnEl.innerText = "Error";
    btnEl.disabled = false;
    alert("Could not reveal secret: " + err.message);
  }
}

// Action Trigger Controller
async function triggerAction(actionName) {
  const banner = document.getElementById("actionBanner");
  const bannerText = document.getElementById("actionBannerText");

  banner.style.display = "flex";
  bannerText.innerText = `Starting ${actionName}...`;

  let endpoint = "/api/actions/" + actionName;
  if (actionName === "health") endpoint = "/api/actions/health-check";

  try {
    const res = await fetch(endpoint, { method: "POST" });
    const data = await res.json();

    if (res.status === 409) {
      alert(data.message);
      banner.style.display = "none";
      return;
    }

    bannerText.innerText = data.message;
    pollActionProgress();
  } catch (err) {
    banner.style.display = "none";
    alert("Action failed: " + err.message);
  }
}

// Poll action status until complete
function pollActionProgress() {
  const interval = setInterval(async () => {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      const banner = document.getElementById("actionBanner");
      const bannerText = document.getElementById("actionBannerText");

      if (data.running_action) {
        banner.style.display = "flex";
        bannerText.innerText = `Running: ${data.running_action}...`;
      } else {
        clearInterval(interval);
        banner.style.display = "none";
        refreshDashboard();
      }
    } catch (e) {
      clearInterval(interval);
    }
  }, 3000);
}

// Refresh Dashboard Data
async function refreshDashboard() {
  try {
    const [statusRes, healthRes, quotaRes] = await Promise.all([
      fetch("/api/status"),
      fetch("/api/health"),
      fetch("/api/quotas")
    ]);

    if (statusRes.ok) {
      const sData = await statusRes.json();
      if (sData.state) {
        document.getElementById("stageBadge").innerText = sData.state.stage || "IDLE";
        document.getElementById("movieTitle").innerText = sData.state.movie_title || "Luna and the Lumina Dreams";
        document.getElementById("activeMovieId").innerText = sData.state.active_movie_id || "MOVIE_002";
        document.getElementById("activeEpId").innerText = `Episode ${sData.state.active_episode_id || 6}`;
        document.getElementById("latestFilename").innerText = sData.state.latest_mp4 || "";
      }
    }

    if (healthRes.ok) {
      const hData = await healthRes.json();
      if (hData.metrics) {
        document.getElementById("metricSubs").innerText = hData.metrics.subscribers || 0;
        document.getElementById("metricViews").innerText = hData.metrics.lifetime_views || 0;
        document.getElementById("metricTotalStories").innerText = hData.metrics.total_published_stories || 22;
        document.getElementById("metricTodayUploads").innerText = `${hData.metrics.today_uploads || 0} / 5`;
      }
    }

    if (quotaRes.ok) {
      const qData = await quotaRes.json();
      if (qData.tts) {
        document.getElementById("ttsDailyUsed").innerText = qData.tts.daily_used.toLocaleString();
        document.getElementById("ttsBar").style.width = `${Math.min(100, qData.tts.daily_pct)}%`;
      }
      if (qData.youtube) {
        document.getElementById("ytUnitsUsed").innerText = qData.youtube.units_used.toLocaleString();
      }
    }
  } catch (err) {
    console.error("Dashboard refresh error:", err);
  }
}

// Movie Tabs Switcher
function switchMovieTab(movieId) {
  document.querySelectorAll(".movie-episodes-panel").forEach(p => {
    p.style.display = "none";
  });
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.classList.remove("active");
  });

  const targetPanel = document.getElementById(`panel_${movieId}`);
  const targetBtn = document.getElementById(`tab_btn_${movieId}`);
  if (targetPanel) targetPanel.style.display = "block";
  if (targetBtn) targetBtn.classList.add("active");
}

// Manual Post Episode to YouTube
async function postEpisode(movieId, episodeId) {
  const btn = document.getElementById(`btn_post_${movieId}_${episodeId}`);
  if (!btn) return;

  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner" style="width:14px; height:14px; display:inline-block; vertical-align:middle; margin-right:6px;"></span> Publishing...`;

  try {
    const res = await fetch("/api/episodes/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ movie_id: movieId, episode_id: episodeId })
    });

    const data = await res.json();

    if (data.status === "published") {
      const statusCell = document.getElementById(`status_cell_${movieId}_${episodeId}`);
      const actionCell = document.getElementById(`action_cell_${movieId}_${episodeId}`);
      if (statusCell) statusCell.innerHTML = `<span class="chip success">✅ Published</span>`;
      if (actionCell) {
        actionCell.innerHTML = `<a href="${data.youtube_url}" target="_blank" class="btn quiet ext-btn">▶ Watch Video ↗</a>`;
      }
      alert(`🎉 Episode ${episodeId} successfully published to YouTube!\nVideo URL: ${data.youtube_url}`);
      refreshDashboard();
    } else if (data.status === "already_published") {
      const statusCell = document.getElementById(`status_cell_${movieId}_${episodeId}`);
      const actionCell = document.getElementById(`action_cell_${movieId}_${episodeId}`);
      if (statusCell) statusCell.innerHTML = `<span class="chip success">✅ Published</span>`;
      if (actionCell) {
        actionCell.innerHTML = `<a href="${data.youtube_url}" target="_blank" class="btn quiet ext-btn">▶ Watch Video ↗</a>`;
      }
      alert(`🛡️ [Duplicate Shield]\n${data.message}\nVideo URL: ${data.youtube_url}`);
      refreshDashboard();
    } else if (data.status === "limit_reached") {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
      alert(`⚠️ Daily Upload Limit Reached\n${data.message}`);
    } else {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
      alert(`❌ Publishing failed: ${data.message || "Unknown error"}`);
    }
  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = originalHtml;
    alert(`❌ Request error: ${err.message}`);
  }
}

// OAuth Scope Upgrade Modal Handlers
async function openOAuthUpgradeModal() {
  const modal = document.getElementById("oauthModal");
  const linkBtn = document.getElementById("oauthLinkBtn");
  if (!modal) return;

  try {
    const res = await fetch("/api/youtube/auth-url");
    if (res.ok) {
      const data = await res.json();
      if (linkBtn && data.auth_url) {
        linkBtn.href = data.auth_url;
      }
    }
  } catch (e) {
    console.error("Could not fetch auth URL:", e);
  }

  modal.style.display = "flex";
}

function closeOAuthModal(e) {
  if (e) e.stopPropagation();
  const modal = document.getElementById("oauthModal");
  if (modal) modal.style.display = "none";
}

async function submitAuthCode() {
  const input = document.getElementById("oauthCodeInput");
  const btn = document.getElementById("btnSubmitCode");
  if (!input || !input.value.trim()) {
    alert("Please enter the authorization code or redirect URL.");
    return;
  }

  btn.disabled = true;
  btn.innerText = "Exchanging & Syncing...";

  try {
    const res = await fetch("/api/youtube/auth-code", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: input.value.trim() })
    });

    const data = await res.json();
    if (res.ok && data.status === "ok") {
      alert(`✅ Success!\n${data.message}`);
      closeOAuthModal();
      refreshDashboard();
    } else {
      alert(`❌ Authorization error:\n${data.detail || data.message || "Failed to exchange code"}`);
    }
  } catch (err) {
    alert(`❌ Request failed: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.innerText = "Submit & Sync Playlists";
  }
}

// Live Clock
function updateClock() {
  const clockEl = document.getElementById("liveClock");
  if (clockEl) {
    const now = new Date();
    clockEl.innerText = now.toUTCString().slice(17, 25) + " UTC";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  setInterval(updateClock, 1000);
  updateClock();
  fetch("/api/status").then(r => r.json()).then(d => {
    if (d.running_action) pollActionProgress();
  }).catch(() => {});
});
