#!/usr/bin/env python3
"""One-shot YouTube reconnect using a local-server OAuth flow.

Designed for the SSH port-forward method: run this ON THE SERVER, then from
your laptop open an SSH tunnel (ssh -L 8080:localhost:8080 hkserver@SERVER)
and open the printed URL in your laptop browser. The redirect to
localhost:8080 is captured automatically through the tunnel -- no copy/paste,
no "localhost refused to connect" error.

After authorization it saves the token and runs the same repair the dashboard
does (recreate playlists, drain the pending queue, mark videos Made for Kids).
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from youtube_publisher import (
    SCOPES,
    DEDICATED_CLIENT_SECRETS,
    DEDICATED_TOKEN_FILE,
    repair_youtube_state,
)

# Port 8080 on this server is taken by a Docker container, so we use a
# free high port. It is a loopback/desktop OAuth client, so Google accepts
# any localhost port for the redirect. Override with RECONNECT_OAUTH_PORT.
PORT = int(os.environ.get("RECONNECT_OAUTH_PORT", "8723"))


def main():
    flow = InstalledAppFlow.from_client_secrets_file(DEDICATED_CLIENT_SECRETS, SCOPES)

    creds = flow.run_local_server(
        host="localhost",
        port=PORT,
        open_browser=False,
        access_type="offline",
        prompt="consent",
        authorization_prompt_message=(
            "\n" + "=" * 75 +
            f"\n  Make sure your SSH tunnel is up:  ssh -L {PORT}:localhost:{PORT} hkserver@<SERVER-IP>"
            "\n  Then open THIS URL in the browser on your laptop:\n\n  {url}\n\n" +
            "=" * 75 + "\n  Waiting for you to approve in the browser...\n"
        ),
        success_message=(
            "Authorization complete. Close this browser tab and return to the terminal."
        ),
    )

    os.makedirs(os.path.dirname(os.path.abspath(DEDICATED_TOKEN_FILE)), exist_ok=True)
    with open(DEDICATED_TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    granted = list(getattr(creds, "scopes", None) or [])
    print("\n  Token saved:", DEDICATED_TOKEN_FILE)
    print("  Scopes granted:", len(granted))
    for s in granted:
        print("   -", s)

    print("\n  Running repair (playlists / pending queue / Made-for-Kids)...")
    try:
        yt = build("youtube", "v3", credentials=creds)
        repair = repair_youtube_state(yt)
        print("  Repair result:", repair)
    except Exception as e:
        print("  Repair step error:", str(e)[:200])

    print("\n  Done. YouTube is reconnected.\n")


if __name__ == "__main__":
    main()
