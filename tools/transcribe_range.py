"""VOD araligini 10 dk'lik parcalar halinde yazıya dok + saniyelik ses seviyesi.
python tools/transcribe_range.py <uuid> <bas_sn> <bit_sn> <cikti.jsonl>"""
import json, subprocess, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import inspect_peak, kick_vod

uuid, a, b, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), Path(sys.argv[4])
src = kick_vod.source(uuid).rsplit("/", 1)[0] + "/360p30/playlist.m3u8"
m = inspect_peak.model("small")
with open(out, "w", encoding="utf-8") as f:
    t = a
    while t < b:
        L = min(600, b - t)
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", src, "-t", str(L), "-vn",
                              "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
        audio = np.frombuffer(pcm, dtype=np.float32)
        sec = audio[: len(audio) // 16000 * 16000].reshape(-1, 16000)
        rms = 20 * np.log10(np.sqrt((sec ** 2).mean(axis=1)) + 1e-9)
        for i, v in enumerate(rms):
            f.write(json.dumps({"loud": round(float(v), 1), "t": t + i}) + "\n")
        segs, _ = m.transcribe(audio, language="tr", vad_filter=True, beam_size=1)
        for s in segs:
            f.write(json.dumps({"t": round(t + s.start, 1), "e": round(t + s.end, 1), "s": s.text.strip()}, ensure_ascii=False) + "\n")
        f.flush()
        print(f"{kick_vod.fmt(t)} tamam", flush=True)
        t += L
