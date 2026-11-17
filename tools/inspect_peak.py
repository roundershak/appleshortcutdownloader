"""Bir chat zirvesini incele: ses -> Whisper metni, ses yuksekligi, kareler.

python tools/inspect_peak.py <uuid> <zirve_sn> [--before 60] [--after 10] [--out klasor] [--model small]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import kick_vod  # noqa: E402

_model = None


def model(name="small"):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(name, device="cpu", compute_type="int8")
    return _model


def loudness(wav: Path, start: float):
    """Saniye bazli ses seviyesi (dBFS). Bagirma anlarini bulmak icin."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(wav), "-af",
                        "asetnsamples=16000,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level",
                        "-f", "null", "-"], capture_output=True, text=True)
    vals = []
    for line in r.stderr.splitlines():
        if "RMS_level=" in line:
            try:
                vals.append(float(line.split("=")[1]))
            except ValueError:
                vals.append(-90.0)
    return [(start + i, v) for i, v in enumerate(vals)]


def inspect(uuid, peak, before=60, after=10, out=Path("."), name="small", frames=True):
    out.mkdir(parents=True, exist_ok=True)
    a, b = max(0, peak - before), peak + after
    src = kick_vod.source(uuid).rsplit("/", 1)[0] + "/360p30/playlist.m3u8"
    wav = out / f"a_{int(peak)}.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-i", src, "-t", str(b - a),
                    "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    import numpy as np
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, dtype=np.float32)
    segs, _ = model(name).transcribe(audio, language="tr", vad_filter=True, beam_size=1)
    lines = [(a + s.start, s.text.strip()) for s in segs]
    loud = loudness(wav, a)
    if frames:
        tile = out / f"f_{int(peak)}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-i", src, "-t", str(b - a),
                        "-vf", f"fps=1/{max(1, (b - a) // 8)},scale=480:-2,tile=4x2", "-frames:v", "1", str(tile)])
    wav.unlink(missing_ok=True)
    return {"start": a, "end": b, "text": lines, "loud": loud}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("uuid")
    ap.add_argument("peak", type=float)
    ap.add_argument("--before", type=float, default=60)
    ap.add_argument("--after", type=float, default=10)
    ap.add_argument("--out", type=Path, default=Path("."))
    ap.add_argument("--model", default="small")
    a = ap.parse_args()
    r = inspect(a.uuid, a.peak, a.before, a.after, a.out, a.model)
    loud = sorted(r["loud"], key=lambda x: -x[1])[:5]
    print("En yuksek ses:", ", ".join(f"{kick_vod.fmt(t)}({v:.0f}dB)" for t, v in sorted(loud)))
    for t, s in r["text"]:
        print(f"{kick_vod.fmt(t)}  {s}")


if __name__ == "__main__":
    main()
