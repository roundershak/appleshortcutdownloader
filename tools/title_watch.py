"""Basligi olmayan yeni canli klipleri bildirir. python tools/title_watch.py <min_id> <min_skor>"""
import json, subprocess, sys, time
from pathlib import Path
R = Path(__file__).resolve().parent.parent
D = R / ".canli-izle"  # set_title.sh ile ayni klasoru kullanmasin (reset --hard yaris kosulu basliklari siliyordu)
if not D.exists():
    subprocess.run(["git", "-C", str(R), "fetch", "-q", "origin", "canli-log"], capture_output=True)
    subprocess.run(["git", "-C", str(R), "worktree", "add", "-q", "--detach", str(D), "origin/canli-log"], capture_output=True)
min_id, min_s = sys.argv[1], float(sys.argv[2])
seen = set()
while True:
    subprocess.run(["git", "-C", str(D), "fetch", "-q", "origin", "canli-log"], capture_output=True)
    subprocess.run(["git", "-C", str(D), "reset", "-q", "--hard", "origin/canli-log"], capture_output=True)
    for f in sorted((D / "canli").glob("2*.json")):
        cid = f.stem
        if cid < min_id or cid in seen or (D / "canli" / f"{cid}.title").exists():
            continue
        seen.add(cid)
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        if d.get("score", 0) >= min_s:
            print(f"YENI_KLIP {cid} skor {d['score']} | {d.get('fallback_title','')}", flush=True)
    time.sleep(20)
