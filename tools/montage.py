"""Yayin kaydindan hizli kesmeli dikey montaj (edit) yapar.
python tools/montage.py spec.json out.mp4
spec: {"vod": "<uuid>", "shots": [[bas_sn, sure_sn], ...], "audio": "mute"|"orig"}"""
import json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from clipbot import kick

spec = json.load(open(sys.argv[1])); out = Path(sys.argv[2])
work = Path(tempfile.mkdtemp())
# sinematik ton: kontrast, hafif sicak/kirmizi, kenar karartma
GRADE = ("crop=ih*9/16:ih,scale=1080:1920:flags=lanczos,"
         "eq=contrast=1.12:saturation=1.18:brightness=-0.02,"
         "colorbalance=rs=0.06:gs=-0.01:bs=-0.04:rh=0.04:bh=-0.03,"
         "vignette=PI/4.5,unsharp=5:5:0.6:5:5:0.0,fps=30,format=yuv420p")
parts = []
for i, (a, d) in enumerate(spec["shots"]):
    raw = kick.cut_vod(spec["vod"], a, a + d + 1, work / f"raw{i}.mp4")
    p = work / f"p{i}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "0.5", "-i", str(raw), "-t", str(d), "-vf", GRADE,
                    "-af", "aresample=48000", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                    "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", str(p)], check=True)
    parts.append(p); raw.unlink()
lst = work / "l.txt"; lst.write_text("".join(f"file '{p}'\n" for p in parts))
cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst)]
if spec.get("audio", "mute") == "mute":
    cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a", "-shortest"]
cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
subprocess.run(cmd, check=True)
print("montaj hazir:", out, round(out.stat().st_size / 1e6, 1), "MB")
