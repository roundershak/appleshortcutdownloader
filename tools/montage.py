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
GRADE = ("crop=ih*9/16:ih:max(0\\,min(iw-ih*9/16\\,iw*{cx}-ih*9/32)):0,scale=1080:1920:flags=lanczos,"
         "eq=contrast=1.15:saturation=1.2:brightness=-0.03,"
         "colorbalance=rs=0.06:gs=-0.01:bs=-0.04:rh=0.04:bh=-0.03,"
         "vignette=PI/4.5,unsharp=5:5:0.6:5:5:0.0,fps=30,format=yuv420p")
FULL = ("split=2[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:3,eq=brightness=-0.08[bg];"
        "[b]scale=1080:-2:flags=lanczos,unsharp=5:5:0.5:5:5:0.0[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,fps=30,format=yuv420p")
parts = []
hls = kick.vod_source(spec["vod"]).rsplit("/", 1)[0] + "/1080p60/playlist.m3u8"
for i, shot in enumerate(spec["shots"]):
    a, d = shot[0], shot[1]
    cx = shot[2] if len(shot) > 2 else 0.5
    p = work / f"p{i}.mp4"
    n = round(d * 30)
    aud = ["-an"] if spec.get("audio", "mute") == "mute" else [
        "-af", f"atrim=0:{n / 30},apad,atrim=0:{n / 30},aresample=48000,afade=t=in:d=0.08,afade=t=out:st={max(0, n / 30 - 0.1)}:d=0.1", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-i", hls, "-frames:v", str(n), "-vf", FULL if spec.get("layout") == "full" else GRADE.format(cx=cx),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "17", *aud, str(p)], check=True)
    got = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v", "-show_entries",
                              "stream=nb_read_frames", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip() or 0)
    if got != n:
        print(f"uyari: kesit {i} {got}/{n} kare")
    parts.append(p)
lst = work / "l.txt"; lst.write_text("".join(f"file '{p}'\n" for p in parts))
cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst)]
if spec.get("audio", "mute") == "mute":
    cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a", "-shortest"]
else:
    cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
subprocess.run(cmd, check=True)
print("montaj hazir:", out, round(out.stat().st_size / 1e6, 1), "MB")
