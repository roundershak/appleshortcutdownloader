"""Kick VOD yardimcilari: konusma metni (TR altyazi) ve parca indirme.

python tools/kick_vod.py text <uuid> <bas_sn> <bit_sn>
python tools/kick_vod.py cut  <uuid> <bas_sn> <bit_sn> <cikti.mp4>
"""
from __future__ import annotations

import re
import subprocess
import sys
from functools import lru_cache

from curl_cffi import requests as creq

S = creq.Session(impersonate="chrome")


@lru_cache(None)
def source(uuid: str) -> str:
    return S.get(f"https://kick.com/api/v1/video/{uuid}", timeout=30).json()["source"]


@lru_cache(None)
def sub_index(uuid: str, lang="tr"):
    base = source(uuid).rsplit("/", 1)[0] + f"/subtitles/{lang}/"
    txt = S.get(base + "playlist.m3u8", timeout=30).text
    segs, t = [], 0.0
    dur = None
    for line in txt.splitlines():
        if line.startswith("#EXTINF:"):
            dur = float(line[8:].split(",")[0])
        elif line and not line.startswith("#"):
            segs.append((t, t + dur, base + line))
            t += dur
    return segs


def _ts(s):
    h, m, rest = s.split(":") if s.count(":") == 2 else ("0", *s.split(":"))
    return int(h) * 3600 + int(m) * 60 + float(rest)


def text(uuid: str, start: float, end: float):
    out = []
    for a, b, url in sub_index(uuid):
        if b < start or a > end:
            continue
        vtt = S.get(url, timeout=30).text
        for m in re.finditer(r"([\d:.]+) --> ([\d:.]+)[^\n]*\n(.+?)(?:\n\n|\Z)", vtt, re.S):
            t0 = _ts(m.group(1))
            # IVS altyazilari mutlak (VOD basindan) zaman kullanir; degilse segment basina ekle
            if t0 < a - 30:
                t0 += a
            if start <= t0 <= end:
                out.append((t0, " ".join(m.group(3).split())))
    out.sort()
    # IVS altyazilari kelime kelime buyur: bir sonrakinin on eki olan satirlari at
    dedup = [(t0, s) for i, (t0, s) in enumerate(out)
             if not (i + 1 < len(out) and out[i + 1][1].startswith(s))]
    return dedup


def cut(uuid: str, start: float, end: float, out: str, quality="1080p60"):
    src = source(uuid).rsplit("/", 1)[0] + f"/{quality}/playlist.m3u8"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-i", src, "-t", str(end - start),
                    "-c", "copy", out], check=True)
    return out


def fmt(s):
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


if __name__ == "__main__":
    cmd, uuid, a, b = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
    if cmd == "text":
        for t0, s in text(uuid, a, b):
            print(f"{fmt(t0)}  {s}")
    else:
        cut(uuid, a, b, sys.argv[5])
