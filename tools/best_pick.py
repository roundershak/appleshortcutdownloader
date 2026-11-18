"""Son N saatte kesilen kliplerden en iyisini secip YouTube + TikTok'a yukler.
Kaynak: canli-log dalindaki canli/<id>.json|.title|.sonuc, video: GitHub Release arsivi.
python tools/best_pick.py <canli-log klasoru> [--hours 4]"""
import argparse, json, os, subprocess, sys, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from clipbot.__main__ import build_meta, load_streamers  # noqa: E402
from clipbot.kick import ClipInfo  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("logdir", type=Path)
ap.add_argument("--hours", type=float, default=24)
ap.add_argument("--irl-per-day", type=int, default=2)
a = ap.parse_args()
d = a.logdir / "canli"
now = time.time()
irl_done = 0
for y in d.glob("2*.yayin"):
    cid0 = y.stem
    t0 = datetime.strptime(cid0, "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc).timestamp()
    j0 = d / f"{cid0}.json"
    tur0 = d / f"{cid0}.tur"
    k0 = tur0.read_text().strip() if tur0.exists() else (json.loads(j0.read_text()).get("layout") == "split" and "oyun" or "irl") if j0.exists() else "oyun"
    if now - t0 < 24 * 3600 and k0 == "irl":
        irl_done += 1
cands = []
for j in d.glob("2*.json"):
    cid = j.stem
    t = datetime.strptime(cid, "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc).timestamp()
    if now - t > a.hours * 3600:
        continue
    meta = json.loads(j.read_text())
    son = json.loads((d / f"{cid}.sonuc").read_text()) if (d / f"{cid}.sonuc").exists() else {}
    title_f = d / f"{cid}.title"
    title = title_f.read_text().strip() if title_f.exists() else None
    if title and title.upper() == "ATLA":
        continue
    if (d / f"{cid}.yayin").exists() or not str(son.get("arsiv", "")).startswith(("arsiv-", "oyun-", "irl-")):
        continue
    tur_f = d / f"{cid}.tur"  # Claude'un isaretledigi tur, yoksa duzenden tahmin
    kind = tur_f.read_text().strip() if tur_f.exists() else ("oyun" if meta.get("layout") == "split" else "irl")
    if kind == "irl" and irl_done >= a.irl_per_day:
        continue  # gunde en fazla 2 IRL, en az 4 oyun
    # Claude'un onayladigi (baslik yazdigi) klipler once, sonra skor
    cands.append((1 if title else 0, meta.get("score", 0), cid, title or meta.get("fallback_title"), son["arsiv"]))
if not cands:
    print("Bu pencerede yayinlanacak klip yok"); sys.exit(0)
cands.sort(reverse=True)
ok_, score, cid, title, asset = cands[0]
print(f"son 24 saatte yayinlanan IRL: {irl_done}")
print(f"SECILEN: {cid} skor={score} onayli={bool(ok_)} baslik={title}  (aday sayisi {len(cands)})")
tag, name = asset.split("/", 1)
work = Path(tempfile.mkdtemp())
subprocess.run(["gh", "release", "download", tag, "-p", name, "-D", str(work)], check=True)
out = work / name
s = load_streamers(); cfg = {**s["_default"], **s["eray"]}
m = build_meta({"title": title, "hashtags": ["gta6", "gtavi"], "tags": ["gta 6", "gta vi", "eray gta 6"]},
               ClipInfo(url="", channel="eray"), cfg)
res = {}
try:
    from clipbot import youtube
    res["youtube"] = youtube.upload(out, m["yt_title"], m["description"], m["tags"])
except Exception as e:  # noqa: BLE001
    res["youtube"] = f"HATA {e}"
if os.environ.get("TIKTOK_CLIENT_KEY"):
    try:
        from clipbot import tiktok
        res["tiktok"] = tiktok.upload(out, m["caption"], mode="draft")
    except Exception as e:  # noqa: BLE001
        res["tiktok"] = f"HATA {e}"
print("SONUC", json.dumps(res, ensure_ascii=False))
(d / f"{cid}.yayin").write_text(json.dumps({"title": m["yt_title"], **res}, ensure_ascii=False))
if os.environ.get("GITHUB_STEP_SUMMARY"):
    open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(f"### {m['yt_title']}\n" + "".join(f"- {k}: {v}\n" for k, v in res.items()))
sys.exit(0 if not str(res.get("youtube", "")).startswith("HATA") else 1)
