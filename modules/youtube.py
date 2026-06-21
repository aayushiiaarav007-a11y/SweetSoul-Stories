"""
YouTube auto-upload for SweetSoul Stories via the YouTube Data API v3 + OAuth2.

Credentials are read from environment variables (so they can live in GitHub
Secrets) and written to local files at runtime:
  * YT_CLIENT_SECRET_JSON - the FULL contents of the OAuth client secret JSON
    downloaded from Google Cloud Console (the whole {"installed":{...}} or
    {"web":{...}} object, pasted verbatim).
  * YT_TOKEN_JSON         - the FULL contents of an authorized OAuth token JSON
    (refresh token etc.), e.g. produced by the OAuth Playground or by running
    `python upload_youtube.py --authorize` locally once.

Heavy google-api libraries are imported lazily so importing this module never
hard-fails.
"""

import json
import logging
import os

from .config import BASE_DIR, get_cfg, get_env

log = logging.getLogger("sweetsoul.youtube")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

CLIENT_SECRET_FILE = os.path.join(str(BASE_DIR), "yt_client_secret.json")
TOKEN_FILE = os.path.join(str(BASE_DIR), "yt_token.json")


def _materialize_env_json(env_name, dest_path):
    """If an env var holds JSON, write it to dest_path. Returns path or None."""
    raw = get_env(env_name)
    if not raw:
        return dest_path if os.path.exists(dest_path) else None
    try:
        # Validate it parses as JSON before writing.
        json.loads(raw)
    except Exception as exc:
        log.error("%s does not contain valid JSON (%s).", env_name, exc)
        return dest_path if os.path.exists(dest_path) else None
    try:
        with open(dest_path, "w", encoding="utf-8") as fh:
            fh.write(raw)
        log.info("Wrote %s -> %s", env_name, os.path.basename(dest_path))
        return dest_path
    except Exception as exc:
        log.error("Could not write %s (%s).", dest_path, exc)
        return dest_path if os.path.exists(dest_path) else None


def _load_credentials():
    """Build authorized OAuth credentials, refreshing if needed."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    token_path = _materialize_env_json("YT_TOKEN_JSON", TOKEN_FILE)
    if not token_path or not os.path.exists(token_path):
        log.error(
            "No YouTube token available. Provide YT_TOKEN_JSON or run "
            "`python upload_youtube.py --authorize` locally first."
        )
        return None

    try:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    except Exception as exc:
        log.error("Could not load token (%s).", exc)
        return None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_path, "w", encoding="utf-8") as fh:
                fh.write(creds.to_json())
            log.info("Refreshed YouTube OAuth token.")
        except Exception as exc:
            log.error("Token refresh failed (%s).", exc)
            return None
    return creds


def authorize():
    """Run a local OAuth flow to mint a token file (interactive, one-time)."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    secret_path = _materialize_env_json("YT_CLIENT_SECRET_JSON", CLIENT_SECRET_FILE)
    if not secret_path or not os.path.exists(secret_path):
        log.error(
            "No client secret found. Provide YT_CLIENT_SECRET_JSON or place "
            "yt_client_secret.json next to this project."
        )
        return None
    flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_FILE, "w", encoding="utf-8") as fh:
        fh.write(creds.to_json())
    log.info("Authorization complete. Token saved to %s", TOKEN_FILE)
    print("\nYT_TOKEN_JSON contents (copy this into your GitHub Secret):\n")
    print(creds.to_json())
    return TOKEN_FILE


def _build_metadata(title, description, tags):
    cfg_tags = list(get_cfg("youtube.default_tags", []))
    all_tags = list(dict.fromkeys((tags or []) + cfg_tags))[:30]
    hashtags = get_cfg(
        "youtube.hashtags",
        "#shorts #cute #puppy #baby #aww #animals #wholesome #heartwarming",
    )
    full_desc = (description or "").strip()
    if hashtags and hashtags not in full_desc:
        full_desc = (full_desc + "\n\n" + hashtags).strip()
    return {
        "snippet": {
            "title": title[:100],
            "description": full_desc[:4900],
            "tags": all_tags,
            "categoryId": str(get_cfg("youtube.category_id", "15")),
        },
        "status": {
            "privacyStatus": get_cfg("youtube.privacy_status", "public"),
            "selfDeclaredMadeForKids": bool(get_cfg("youtube.made_for_kids", False)),
        },
    }


def upload_video(video_path, title, description="", tags=None, privacy=None):
    """Upload a single video to YouTube. Returns the video id or None."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    if not os.path.exists(video_path):
        log.error("Video file not found: %s", video_path)
        return None

    creds = _load_credentials()
    if creds is None:
        return None

    body = _build_metadata(title, description, tags)
    if privacy:
        body["status"]["privacyStatus"] = privacy

    try:
        youtube = build("youtube", "v3", credentials=creds)
        media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
        request = youtube.videos().insert(
            part="snippet,status", body=body, media_body=media
        )
        log.info("Uploading '%s' to YouTube...", title)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                log.info("Upload progress: %d%%", int(status.progress() * 100))
        video_id = response.get("id")
        log.info("Uploaded! https://youtu.be/%s", video_id)
        return video_id
    except HttpError as exc:
        log.error("YouTube API error (%s).", exc)
        return None
    except Exception as exc:
        log.error("Upload failed (%s).", exc)
        return None
