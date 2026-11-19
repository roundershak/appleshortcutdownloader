"""Canli takibin kacirdigi bir ani yayin kaydindan elle keser, arsive koyar ve canli-log'a onayli aday olarak yazar.
python tools/manual_clip.py kes/<spec>.json
spec: {"vod","start","end","id"(UTC YYYYmmdd-HHMMSS),"title","tur":"irl|oyun","score","efsane":true}"""
import json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from clipbot import edit, kick  # noqa: E402

s = json.load(open(sys.argv[1]))
cid, tur = s["id"], s.get("tur", "irl")
work = Path(tempfile.mkdtemp())
src = kick.cut_vod(s["vod"], s["start"] - 2, s["end"] + 1, work / "src.mp4")
plan = edit.plan_layout(src, cam=s.get("cam"), layout="auto" if s.get("cam") else "full")  # cam: ustte kamera, altta oyun
print("duzen:", plan["layout"], plan["cam"], plan["game"])
out = edit.render(src, work / f"{cid}.mp4", plan, start=2, end=2 + s["end"] - s["start"])
tag = f"{tur}-{cid[:8]}"
if subprocess.run(["gh", "release", "view", tag], capture_output=True).returncode != 0:
    subprocess.run(["gh", "release", "create", tag, "--prerelease", "-t", f"{'Oyun' if tur == 'oyun' else 'IRL'} klipleri {cid[:8]}",
                    "-n", "Canli takipte kesilen tum klipler"], check=True)
subprocess.run(["gh", "release", "upload", tag, str(out), "--clobber"], check=True)
print("arsiv:", f"{tag}/{cid}.mp4")

d = ROOT / ".canli"
subprocess.run(["git", "fetch", "-q", "origin", "canli-log"], cwd=ROOT, check=True)
subprocess.run(["git", "worktree", "add", "-q", "-B", "canli-log", str(d), "origin/canli-log"], cwd=ROOT, check=True)
c = d / "canli"
dur = s["end"] - s["start"]
(c / f"{cid}.json").write_text(json.dumps({"id": cid, "score": s.get("score", 4.8), "layout": "full", "cam": None,
                                           "fallback_title": s["title"], "dur": dur, "elle": True}, ensure_ascii=False, indent=1))
(c / f"{cid}.title").write_text(s["title"])
(c / f"{cid}.tur").write_text(tur)
(c / f"{cid}.kirp").write_text(f"0 {dur}")
if s.get("efsane"):
    (c / f"{cid}.efsane").write_text("1")
(c / f"{cid}.sonuc").write_text(json.dumps({"title": s["title"], "arsiv": f"{tag}/{cid}.mp4", "score": s.get("score", 4.8),
                                            "yayin": "bekliyor"}, ensure_ascii=False))
if s.get("tiktok_now"):  # hemen TikTok taslagina da gonder
    import time
    from clipbot import tiktok
    from clipbot.__main__ import build_meta, load_streamers
    from clipbot.kick import ClipInfo
    sc = load_streamers(); cfg = {**sc["_default"], **sc["eray"]}
    m = build_meta({"title": s["title"], "hashtags": ["gta6", "gtavi"]}, ClipInfo(url="", channel="eray"), cfg)
    try:
        r = tiktok.upload(out, m["caption"], mode="draft")
    except Exception as e:  # noqa: BLE001
        r = f"HATA {e}"
    print("[sonuc] tiktok:", r)
    (c / f"{cid}.yayin").write_text(json.dumps({"title": s["title"], "zaman": time.time(), "tiktok": r}, ensure_ascii=False))
for cmd in (["add", "-A"], ["-c", "user.name=klip-bot", "-c", "user.email=klip-bot@users.noreply.github.com", "commit", "-qm", f"elle klip {cid}"]):
    subprocess.run(["git", *cmd], cwd=d, check=True)
for _ in range(4):
    subprocess.run(["git", "pull", "-q", "--rebase", "origin", "canli-log"], cwd=d)
    if subprocess.run(["git", "push", "-q", "origin", "HEAD:canli-log"], cwd=d).returncode == 0:
        print("canli-log'a yazildi:", cid); break
