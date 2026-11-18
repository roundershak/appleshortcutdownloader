"""Kullanim:
  python -m clipbot run queue/<is>.json         # indir -> edit -> yukle -> sil
  python -m clipbot preview <kick-link> [--cam x,y,w,h] [--game x,y,w,h] [--at sn]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import edit, kick

ROOT = Path(__file__).resolve().parent.parent


def load_streamers() -> dict:
    return json.loads((ROOT / "config" / "streamers.json").read_text(encoding="utf-8"))


def _region(v):
    if v is None or isinstance(v, list):
        return v
    return [float(x) for x in str(v).split(",")]


def build_meta(job: dict, info: kick.ClipInfo, s: dict) -> dict:
    title = (job.get("title") or info.title or "Kick klip").strip()
    display = s.get("display") or (info.channel or "").capitalize()
    channel = s.get("kick") or info.channel
    tags = list(dict.fromkeys(s.get("tags", []) + job.get("tags", [])))
    hashtags = list(dict.fromkeys(s.get("hashtags", []) + [f"#{t.lstrip('#').replace(' ', '')}" for t in job.get("hashtags", [])]))
    yt_title = title if "#shorts" in title.lower() else f"{title} #shorts"
    if display and display.lower() not in yt_title.lower():
        yt_title = f"{title} | {display} #shorts"
    credit = f"Yayıncı: https://kick.com/{channel}" if channel else ""
    desc = s.get("yt_description") or "\n".join(x for x in [title, "", credit, "", " ".join(hashtags + ["#shorts"])] if x is not None)
    caption = job.get("caption") or f"{title} {' '.join(hashtags)}"
    return {"yt_title": yt_title[:100], "description": desc, "tags": tags, "caption": caption}


def run_job(job_path: Path) -> int:
    job = json.loads(job_path.read_text(encoding="utf-8"))
    streamers = load_streamers()
    if job.get("vod"):  # yayin tekrarindan kesit
        info = kick.ClipInfo(url=f"https://kick.com/{job.get('streamer', '')}/videos/{job['vod']}",
                             title=job.get("title"), channel=job.get("streamer"))
    else:
        info = kick.clip_info(job["url"])
    key = (job.get("streamer") or info.channel or "").lower()
    s = {**streamers["_default"], **streamers.get(key, {})}
    print(f"[job] {job_path.name}: kanal={info.channel} profil={key if key in streamers else '_default'}")

    work = Path(tempfile.mkdtemp(prefix="clip_"))
    results, failed = {}, False
    try:
        if job.get("asset"):  # canli takipten gelen, edit edilmis klip
            tag, name = job["asset"].split("/", 1)
            subprocess.run(["gh", "release", "download", tag, "-p", name, "-D", str(work)], check=True)
            out = work / name
        else:
            if job.get("vod"):
                src = kick.cut_vod(job["vod"], float(job["start"]), float(job["end"]), work / "src.mp4")
                job = {**job, "start": None, "end": None}
            else:
                src = kick.download(info, work / "src.mp4")
            plan = edit.plan_layout(src, cam=_region(job.get("cam", s.get("cam"))),
                                    game=_region(job.get("game", s.get("game"))),
                                    layout=job.get("layout", "auto"), cam_h=int(job.get("cam_h", edit.DEFAULT_CAM_H)))
            print(f"[edit] layout={plan['layout']} cam={plan['cam']} ({plan['source']}) game={plan['game']}")
            out = edit.render(src, work / "out.mp4", plan, start=job.get("start"), end=job.get("end"))
            src.unlink(missing_ok=True)
        print(f"[edit] hazir: {out.stat().st_size / 1e6:.1f} MB")
        meta = build_meta(job, info, s)
        print(f"[meta] YouTube basligi: {meta['yt_title']}\n[meta] TikTok: {meta['caption']}")

        platforms = job.get("platforms", ["youtube", "tiktok"])
        if "youtube" in platforms:
            try:
                from . import youtube
                results["youtube"] = youtube.upload(out, meta["yt_title"], meta["description"], meta["tags"],
                                                    privacy=job.get("youtube_privacy", "public"))
            except Exception as e:
                failed, results["youtube"] = True, f"HATA: {e}"
        if "tiktok" in platforms and not os.environ.get("TIKTOK_CLIENT_KEY"):
            results["tiktok"] = "atlandi (TikTok henuz bagli degil)"
        elif "tiktok" in platforms:
            try:
                from . import tiktok
                results["tiktok"] = tiktok.upload(out, meta["caption"], mode=job.get("tiktok_mode", "draft"))
            except Exception as e:
                failed, results["tiktok"] = True, f"HATA: {e}"
        if job.get("asset") and not failed:  # bulutta bekleyen kopyayi sil
            tag, name = job["asset"].split("/", 1)
            subprocess.run(["gh", "release", "delete-asset", tag, name, "-y"], capture_output=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)  # videolar hicbir yerde kalmaz
        print("[temizlik] gecici dosyalar silindi")

    for k, v in results.items():
        print(f"[sonuc] {k}: {v}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### {job_path.name}\n" + "".join(f"- **{k}**: {v}\n" for k, v in results.items()))
    return 1 if failed else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="clipbot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("jobs", nargs="+", type=Path)
    p = sub.add_parser("preview")
    p.add_argument("url")
    p.add_argument("--cam")
    p.add_argument("--game")
    p.add_argument("--layout", default="auto")
    p.add_argument("--at", type=float)
    p.add_argument("--out", type=Path, default=Path("preview.jpg"))
    p.add_argument("--keep", type=Path, help="indirilen kaynagi bu yolda tut (tekrar onizleme icin)")
    a = ap.parse_args(argv)

    if a.cmd == "run":
        return max(run_job(j) for j in a.jobs)

    streamers = load_streamers()
    info = kick.clip_info(a.url)
    s = {**streamers["_default"], **streamers.get((info.channel or "").lower(), {})}
    src = a.keep if a.keep and a.keep.exists() else kick.download(info, a.keep or Path(tempfile.mkdtemp()) / "src.mp4")
    plan = edit.plan_layout(src, cam=_region(a.cam or s.get("cam")), game=_region(a.game or s.get("game")), layout=a.layout)
    edit.preview(src, a.out, plan, at=a.at)
    print(json.dumps({"title": info.title, "channel": info.channel, "layout": plan["layout"],
                      "cam": plan["cam"], "game": plan["game"], "source": plan["source"],
                      "size": [plan["meta"]["w"], plan["meta"]["h"]], "duration": plan["meta"]["duration"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
