"""Yukleme aninda: klibi olay anina kirp (hook) + ustune buyuk baslik yazisi koy."""
from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

FONT_CANDS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]


def font():
    for f in FONT_CANDS:
        if Path(f).exists():
            return f
    return FONT_CANDS[0]


def headline(title: str) -> str:
    """Baslik yazisi: hashtag ve klavye-basma gulmeyi at, buyuk harf (Turkce)."""
    t = re.sub(r"#\S+", "", title)
    words = [w for w in t.split() if not (len(w) >= 7 and w.isupper() and sum(c in "AEIİOÖUÜ" for c in w) / len(w) < 0.3)]
    t = " ".join(words).strip(" !.")
    t = t.replace("i", "İ").replace("ı", "I").upper()
    return t


def make(src: Path, out: Path, title: str, w: int, h: int, start: float = 16.0, length: float = 24.0, crf: int = 18):
    txt = headline(title)
    lines = textwrap.wrap(txt, 20)[:3]
    fs = int(w * 0.075)
    y0 = int(h * 0.075)
    tfs = []
    draws = []
    for i, line in enumerate(lines):
        tf = out.with_name(f"{out.stem}_l{i}.txt")
        tf.write_text(line, encoding="utf-8")
        tfs.append(tf)
        draws.append(f"drawtext=fontfile={font()}:textfile={tf}:fontsize={fs}:fontcolor=white:borderw={max(4, fs // 12)}:"
                     f"bordercolor=black:x=(w-text_w)/2:y={y0 + i * int(fs * 1.2)}")
    vf = ",".join([f"scale={w}:{h}:flags=lanczos,unsharp=5:5:0.5:5:5:0.0"] + draws)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                               capture_output=True, text=True).stdout.strip() or 0)
    ss = start if dur >= start + length - 2 else max(0.0, dur - length)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.2f}", "-i", str(src), "-t", f"{length:.2f}", "-vf", vf,
                    "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-profile:v", "high", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    for tf in tfs:
        tf.unlink(missing_ok=True)
    return out
