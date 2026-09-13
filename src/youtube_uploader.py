import random
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from src.models import VideoMetadata


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
RETRIABLE_CODES = {500, 502, 503, 504}


def authorize(client_secret: Path, token_file: Path) -> Credentials:
    credentials = None
    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials or not credentials.valid:
        if not client_secret.exists():
            raise FileNotFoundError(f"YouTube OAuth file not found: {client_secret}")
        credentials = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES).run_local_server(port=0)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def upload_video(video: Path, thumbnail: Path, metadata: VideoMetadata, privacy: str, credentials: Credentials) -> dict:
    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {"title": metadata.title, "description": metadata.description, "tags": metadata.tags, "categoryId": "27"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
        },
        media_body=MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True),
    )
    response = None
    retries = 0
    while response is None:
        try:
            _, response = request.next_chunk()
        except HttpError as exc:
            if exc.resp.status not in RETRIABLE_CODES or retries >= 5:
                raise
            time.sleep((2**retries) + random.random())
            retries += 1
    video_id = response["id"]
    thumbnail_error = None
    try:
        youtube.thumbnails().set(
            videoId=video_id, media_body=MediaFileUpload(str(thumbnail))
        ).execute()
    except HttpError as exc:
        # The video already exists at this point. Preserve its ID so a retry
        # never creates a duplicate merely because custom thumbnails are off.
        thumbnail_error = str(exc)
    return {
        "youtube_video_id": video_id,
        "youtube_url": f"https://youtu.be/{video_id}",
        "thumbnail_error": thumbnail_error,
    }
