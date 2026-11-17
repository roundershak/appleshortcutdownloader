"""Kick klip indirme."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

CLIP_RE = re.compile(r"(clip_[0-9A-Za-z]+)")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"


@dataclass
class ClipInfo:
    url: str
    title: str | None = None
    channel: str | None = None
    media_url: str | None = None


def _get_json(url: str) -> dict:
    try:  # Cloudflare'e takilmamak icin tarayici taklidi
        from curl_cffi import requests as creq

        r = creq.get(url, impersonate="chrome", timeout=30)
    except ImportError:
        import requests

        r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()


def clip_info(url: str) -> ClipInfo:
    info = ClipInfo(url=url)
    m = CLIP_RE.search(url)
    if "kick.com" in url and m:
        try:
            data = _get_json(f"https://kick.com/api/v2/clips/{m.group(1)}")
            c = data.get("clip", data)
            info.title = c.get("title")
            info.channel = (c.get("channel") or {}).get("slug")
            info.media_url = c.get("video_url") or c.get("clip_url")
        except Exception as e:  # yt-dlp'ye dusulur
            print(f"[kick] API okunamadi ({e}), yt-dlp ile denenecek")
    if not info.channel:
        cm = re.search(r"kick\.com/([^/?#]+)", url)
        if cm and cm.group(1) not in ("api", "clips"):
            info.channel = cm.group(1).lower()
    return info


def download(info: ClipInfo, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if info.media_url:
        cmd = ["ffmpeg", "-v", "error", "-y", "-user_agent", UA, "-i", info.media_url, "-c", "copy", str(out)]
        if subprocess.run(cmd).returncode == 0 and out.exists() and out.stat().st_size > 0:
            return out
        print("[kick] ffmpeg indirmesi basarisiz, yt-dlp deneniyor")
    cmd = ["yt-dlp", "-q", "--no-playlist", "-f", "bv*+ba/b", "--merge-output-format", "mp4",
           "-o", str(out), info.url]
    subprocess.run(cmd, check=True)
    if not info.title:
        r = subprocess.run(["yt-dlp", "--skip-download", "--print", "title", info.url],
                           capture_output=True, text=True)
        info.title = r.stdout.strip() or None
    return out
