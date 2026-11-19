"""YouTube Data API v3 ile Shorts yukleme (kalici refresh token)."""
from __future__ import annotations

import os
import time
from pathlib import Path


def _client():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(path: Path, title: str, description: str, tags: list[str],
           privacy: str = "public", category: str = "20") -> str:
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    yt = _client()
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": tags,
            "categoryId": category,
            "defaultLanguage": "tr",
            "defaultAudioLanguage": "tr",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
                   "embeddable": True},
    }
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp, retry = None, 0
    while resp is None:
        try:
            status, resp = req.next_chunk()
            if status:
                print(f"[youtube] %{int(status.progress() * 100)}")
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retry < 5:
                retry += 1
                time.sleep(2 ** retry)
                continue
            raise
    vid = resp["id"]
    final = resp.get("status", {}).get("privacyStatus")
    if privacy == "public" and final != "public":
        print(f"[youtube] UYARI: video '{final}' olarak kaldi. Google Cloud projesi denetlenmemis olabilir (docs/KURULUM.md).")
    return f"https://youtube.com/shorts/{vid}"
