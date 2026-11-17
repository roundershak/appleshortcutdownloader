"""TikTok Content Posting API (dogrudan paylasim veya taslak/inbox)."""
from __future__ import annotations

import math
import os
import subprocess
import time
from pathlib import Path

import requests

API = "https://open.tiktokapis.com/v2"


def _save_secret(name: str, value: str) -> None:
    """Yenilenen token'i GitHub Secret olarak kaydeder (GH_PAT gerekir)."""
    pat, repo = os.environ.get("GH_PAT"), os.environ.get("GITHUB_REPOSITORY")
    if not (pat and repo):
        print(f"[tiktok] UYARI: {name} degisti ama GH_PAT yok, secret guncellenemedi.")
        return
    r = subprocess.run(["gh", "secret", "set", name, "--repo", repo, "--body", value],
                       env={**os.environ, "GH_TOKEN": pat}, capture_output=True, text=True)
    print(f"[tiktok] {name} secret'i guncellendi" if r.returncode == 0 else f"[tiktok] secret yazilamadi: {r.stderr}")


def _mask(v: str) -> None:
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::add-mask::{v}")


def access_token() -> str:
    key, secret = os.environ["TIKTOK_CLIENT_KEY"], os.environ["TIKTOK_CLIENT_SECRET"]
    refresh = os.environ.get("TIKTOK_REFRESH_TOKEN")
    if refresh:
        data = {"client_key": key, "client_secret": secret, "grant_type": "refresh_token",
                "refresh_token": refresh}
    else:  # ilk kurulum: tek seferlik yetki kodu
        code = os.environ.get("TIKTOK_AUTH_CODE")
        if not code:
            raise RuntimeError("TIKTOK_REFRESH_TOKEN veya TIKTOK_AUTH_CODE secret'i yok")
        data = {"client_key": key, "client_secret": secret, "grant_type": "authorization_code",
                "code": code, "redirect_uri": os.environ["TIKTOK_REDIRECT_URI"]}
    r = requests.post(f"{API}/oauth/token/", data=data, timeout=30,
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    j = r.json()
    if "access_token" not in j:
        raise RuntimeError(f"TikTok token alinamadi: {j.get('error')} {j.get('error_description')}")
    _mask(j["access_token"])
    new_refresh = j.get("refresh_token")
    if new_refresh and new_refresh != refresh:
        _mask(new_refresh)
        _save_secret("TIKTOK_REFRESH_TOKEN", new_refresh)
    return j["access_token"]


def _post(token: str, path: str, body: dict) -> dict:
    r = requests.post(f"{API}{path}", json=body, timeout=60,
                      headers={"Authorization": f"Bearer {token}",
                               "Content-Type": "application/json; charset=UTF-8"})
    j = r.json()
    err = j.get("error", {})
    if err.get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok {path}: {err.get('code')} {err.get('message')}")
    return j.get("data", {})


def _chunks(size: int):
    if size <= 64 * 1024 * 1024:
        return size, 1
    chunk = 10 * 1024 * 1024
    return chunk, size // chunk  # son parca kalani da icerir


def upload(path: Path, caption: str, mode: str = "direct", privacy: str = "PUBLIC_TO_EVERYONE") -> str:
    token = access_token()
    size = path.stat().st_size
    chunk, count = _chunks(size)
    source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count}

    if mode == "direct":
        info = _post(token, "/post/publish/creator_info/query/", {})
        options = info.get("privacy_level_options", [])
        if privacy not in options:
            print(f"[tiktok] '{privacy}' kullanilamiyor (secenekler: {options}). Uygulama denetlenmemis olabilir.")
            privacy = "SELF_ONLY" if "SELF_ONLY" in options else options[0]
        body = {"post_info": {"title": caption[:2200], "privacy_level": privacy,
                              "disable_duet": False, "disable_comment": False, "disable_stitch": False,
                              "video_cover_timestamp_ms": 1000},
                "source_info": source}
        data = _post(token, "/post/publish/video/init/", body)
    else:  # taslak: TikTok uygulamasina bildirim gelir, sen paylasirsin
        data = _post(token, "/post/publish/inbox/video/init/", {"source_info": source})

    upload_url, publish_id = data["upload_url"], data["publish_id"]
    with open(path, "rb") as f:
        for i in range(count):
            start = i * chunk
            end = size - 1 if i == count - 1 else start + chunk - 1
            f.seek(start)
            part = f.read(end - start + 1)
            r = requests.put(upload_url, data=part, timeout=300, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(part)),
                "Content-Range": f"bytes {start}-{end}/{size}"})
            if r.status_code not in (200, 201, 206):
                raise RuntimeError(f"TikTok yukleme parcasi {i + 1}/{count} basarisiz: {r.status_code} {r.text[:200]}")
            print(f"[tiktok] parca {i + 1}/{count} yuklendi")

    for _ in range(40):  # ~4 dk durum takibi
        time.sleep(6)
        st = _post(token, "/post/publish/status/fetch/", {"publish_id": publish_id})
        s = st.get("status")
        if s in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            ids = st.get("publicaly_available_post_id") or []
            extra = f" post_id={ids[0]}" if ids else ""
            return f"{s} (privacy={privacy if mode == 'direct' else 'taslak'}){extra}"
        if s == "FAILED":
            raise RuntimeError(f"TikTok paylasimi basarisiz: {st.get('fail_reason')}")
    return f"isleniyor (publish_id={publish_id})"
