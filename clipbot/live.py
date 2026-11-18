"""Canli yayin takibi: chat'i neredeyse anlik dinler, gulme/hype/sinir patlamasi
olunca olayin bitmesini bekler, son ~35-40 sn'yi kayittan keser, dikey edit yapar ve yukler.

python -m clipbot.live --channel eray --game gta6 [--max-hours 5.6] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from chat_peaks import classify  # noqa: E402

from . import edit  # noqa: E402

WORK = Path(os.environ.get("LIVE_WORK", "/tmp/live"))
LOG_BRANCH = "canli-log"
UA_IMP = "chrome"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def _sess():
    from curl_cffi import requests as creq
    return creq.Session(impersonate=UA_IMP)


S = None


def api(url):
    global S
    for i in range(4):
        try:
            S = S or _sess()
            r = S.get(url, timeout=20)
            if r.status_code == 200:
                return r.json()
        except Exception as e:  # noqa: BLE001
            log("api hata", e)
            S = None
        time.sleep(2 + 2 * i)
    return None


def channel_state(slug):
    d = api(f"https://kick.com/api/v2/channels/{slug}") or {}
    return d.get("id"), bool(d.get("livestream")), d.get("playback_url"), (d.get("livestream") or {}).get("session_title")


# ---------------------------------------------------------------- kayit
class Recorder:
    def __init__(self, url):
        self.url = url
        self.dir = WORK / "rec"
        shutil.rmtree(self.dir, ignore_errors=True)
        self.dir.mkdir(parents=True)
        self.proc = None
        self.n = 0

    def start(self):
        self.n += 1
        pl = self.dir / f"r{self.n}.m3u8"
        self.proc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-i", self.url, "-map", "0:p:0:v", "-map", "0:p:0:a", "-sn", "-dn",
             "-c", "copy", "-f", "hls",
             "-hls_time", "4", "-hls_list_size", "150", "-hls_flags", "delete_segments+program_date_time",
             "-hls_segment_filename", str(self.dir / f"r{self.n}_%06d.ts"), str(pl)])
        log("kayit basladi", pl.name)

    def alive(self):
        return self.proc and self.proc.poll() is None

    def stop(self):
        if self.alive():
            self.proc.terminate()

    def segments(self):
        out = []
        for pl in sorted(self.dir.glob("r*.m3u8")):
            pdt = dur = None
            for line in pl.read_text().splitlines():
                if line.startswith("#EXTINF:"):
                    dur = float(line[8:].rstrip(","))
                elif line.startswith("#EXT-X-PROGRAM-DATE-TIME:"):
                    pdt = datetime.strptime(line.split(":", 1)[1][:23], "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc).timestamp()
                elif line and not line.startswith("#") and pdt is not None:
                    f = self.dir / line
                    if f.exists():
                        out.append((pdt, pdt + dur, f))
                    pdt = None
        return out

    def loudness(self, n=2):
        """Son n segmentin ortalama ses seviyesi (dB)."""
        segs = self.segments()[-n:]
        vals = []
        for _, _, f in segs:
            r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(f), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                               capture_output=True, text=True)
            m = re.search(r"mean_volume: (-?[\d.]+) dB", r.stderr)
            if m:
                vals.append(float(m.group(1)))
        return sum(vals) / len(vals) if vals else None

    def cut(self, a, b, out: Path):
        segs = [s for s in self.segments() if s[1] > a and s[0] < b]
        if not segs:
            return None
        lst = out.with_suffix(".txt")
        lst.write_text("".join(f"file '{s[2]}'\n" for s in segs))
        off = max(0.0, a - segs[0][0])
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-ss", f"{off:.2f}", "-t", f"{b - a:.2f}", "-c", "copy", str(out)], check=True)
        lst.unlink(missing_ok=True)
        return out


# ---------------------------------------------------------------- chat
class Chat:
    """Her 5 sn'lik pencereyi ~10 sn gecikmeyle ceker (Kick tekrar API'si)."""

    def __init__(self, chan_id, lag=10):
        self.chan_id, self.lag = chan_id, lag
        self.win = deque(maxlen=200)  # (t, n, laugh, hype, rage, texts)
        now = time.time() - lag
        self.next_t = now - now % 5

    def poll(self):
        while time.time() - self.lag >= self.next_t + 5:
            t = self.next_t
            ts = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            d = api(f"https://kick.com/api/v2/channels/{self.chan_id}/messages?start_time={ts}") or {}
            msgs = d.get("data", {}).get("messages", [])
            n = l = h = g = 0
            texts = []
            for m in msgs:
                a, b, c, _ = classify(m.get("content", ""))
                n += 1; l += a; h += b; g += c
                txt = re.sub(r"\[emote:\d+:([^\]]+)\]", r":\1:", m.get("content", ""))
                texts.append(txt[:80])
            self.win.append((t, n, l, h, g, texts))
            self.next_t += 5


# ---------------------------------------------------------------- tespit
class Detector:
    def __init__(self, k=4):
        self.k = k
        self.active = None  # dict
        self.cool_until = 0

    def rates(self, win):
        seg = list(win)[-self.k:]
        n = sum(x[1] for x in seg) or 1
        return (sum(x[2] for x in seg) / n, sum(x[3] for x in seg) / n, sum(x[4] for x in seg) / n, n)

    def baseline(self, win):
        w = list(win)
        if len(w) < 24:
            return None
        lrs = []
        for i in range(max(0, len(w) - 120), len(w) - self.k):
            seg = w[i:i + self.k]
            n = sum(x[1] for x in seg) or 1
            lrs.append(sum(x[2] for x in seg) / n)
        return median(lrs) if lrs else None

    def hype_base(self, win):
        w = list(win)[-120:]
        vals = [x[3] / max(1, x[1]) for x in w]
        return median(vals) if vals else 0

    def step(self, win):
        """Biten olay varsa dondurur."""
        if len(win) < self.k:
            return None
        base = self.baseline(win)
        if base is None:
            return None
        lr, hr, rr, n = self.rates(win)
        t = win[-1][0]
        thr = max(0.45, base + 0.22)
        hb = self.hype_base(win)
        hot = (lr >= thr or (hr + rr) >= max(0.35, hb + 0.3)) and n >= 30
        if self.active is None:
            if hot and t >= self.cool_until:
                start = win[-self.k][0]
                self.active = {"t0": start, "peak": lr, "peak_t": t, "base": base, "hype": hr, "rage": rr,
                               "texts": [], "cold": 0}
                log(f"OLAY basladi gulme=%{lr*100:.0f} taban=%{base*100:.0f} hype=%{hr*100:.0f} sinir=%{rr*100:.0f}")
            return None
        a = self.active
        a["texts"] += [x for x in win[-1][5] if len(re.sub(r":[^:]+:", "", x).strip()) > 2][:5]
        if lr > a["peak"]:
            a["peak"], a["peak_t"] = lr, t
        a["hype"] = max(a["hype"], hr); a["rage"] = max(a["rage"], rr)
        a["cold"] = a["cold"] + 1 if lr < base + 0.10 and (hr + rr) < 0.2 else 0
        if a["cold"] >= 3 or t - a["t0"] > 75:
            a["t1"] = t
            self.active = None
            self.cool_until = t + 30
            a["score"] = round(a["peak"] * 2 + max(0, a["peak"] - a["base"]) * 3 + a["hype"] + a["rage"], 3)
            log(f"OLAY bitti sure={a['t1'] - a['t0']:.0f}sn skor={a['score']}")
            return a
        return None


# ---------------------------------------------------------------- isleme
_whisper = None


def transcribe(path: Path):
    global _whisper
    try:
        import numpy as np
        from faster_whisper import WhisperModel
        _whisper = _whisper or WhisperModel("small", device="cpu", compute_type="int8")
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                             capture_output=True).stdout
        segs, _ = _whisper.transcribe(np.frombuffer(pcm, dtype=np.float32), language="tr", vad_filter=True, beam_size=1)
        return [(round(s.start, 1), s.text.strip()) for s in segs]
    except Exception as e:  # noqa: BLE001
        log("whisper yok/hata", e)
        return []


SMASH = ["ASDKJASLDKJ", "ŞLSDKFJSLDKF", "QKFNEQOJIKGB", "SDFJKLSDFJKL", "AKSJDHAKSJD", "ĞPAŞSLDKAŞS"]
SWEAR = re.compile(r"\b(amk|amına|siktir|orospu|piç|yarra|gerizekal|aptal|salak|mal)\w*", re.I)


def fallback_title(ev, lines, game_name, who="eray"):
    rage = ev["rage"] > 0.12 or any(SWEAR.search(s) for _, s in lines)
    quote = ""
    cands = [s.strip(" .") for _, s in lines if 6 <= len(s) <= 38 and not SWEAR.search(s)]
    if cands:
        quote = max(cands, key=lambda s: (s.count("!") + s.count("?"), len(s))).lower()
    g = f" {game_name}'da" if game_name else ""
    e = who
    if rage:
        opts = [f"{e}{g} sinir krizi geçirdi!!", f"{e}{g} çıldırdı {random.choice(SMASH)}", f"{e}{g} kopuyor!!"]
    elif ev["hype"] > 0.15:
        opts = [f"{e}{g} chat'i kopardı!!", f"{e}{g} böyle bir şey görmedi!!"]
    else:
        opts = [f"{e}{g} yine olay çıkardı {random.choice(SMASH)}", f"{e}{g} chat'i güldürmekten öldürdü {random.choice(SMASH)}"]
    if quote and random.random() < 0.6:
        return f'{e}{g}: "{quote}" {random.choice(SMASH) if not rage else "!!"}'.strip()
    return random.choice(opts)


def git(*a, check=True):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=check)


def publish_log(cid, meta: dict, jpg: Path | None):
    """Ozet + onizlemeyi canli-log dalina yazar (Claude baslik verebilsin diye)."""
    try:
        d = ROOT / ".canli"
        if not d.exists():
            git("fetch", "-q", "origin", LOG_BRANCH, check=False)
            r = git("worktree", "add", "-q", str(d), f"origin/{LOG_BRANCH}", check=False)
            if r.returncode != 0:
                git("worktree", "add", "-q", "--detach", str(d), check=False)
                subprocess.run(["git", "checkout", "-q", "--orphan", LOG_BRANCH], cwd=d)
                subprocess.run(["git", "rm", "-rqf", "."], cwd=d)
        (d / "canli").mkdir(exist_ok=True)
        (d / "canli" / f"{cid}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
        if jpg and jpg.exists():
            shutil.copy(jpg, d / "canli" / f"{cid}.jpg")
        for c in (["add", "-A"], ["commit", "-qm", f"canli {cid}"]):
            subprocess.run(["git", *c], cwd=d, capture_output=True)
        for _ in range(3):
            subprocess.run(["git", "pull", "-q", "--rebase", "origin", LOG_BRANCH], cwd=d, capture_output=True)
            if subprocess.run(["git", "push", "-q", "origin", f"HEAD:{LOG_BRANCH}"], cwd=d, capture_output=True).returncode == 0:
                return d
    except Exception as e:  # noqa: BLE001
        log("log yazilamadi", e)
    return None


def wait_title(cid, timeout):
    d = ROOT / ".canli"
    end = time.time() + timeout
    while time.time() < end:
        subprocess.run(["git", "pull", "-q", "--rebase", "origin", LOG_BRANCH], cwd=d, capture_output=True)
        f = d / "canli" / f"{cid}.title"
        if f.exists():
            t = f.read_text().strip()
            if t:
                return t
        time.sleep(20)
    return None


class Publisher:
    def __init__(self, args, streamer_cfg):
        self.args, self.cfg = args, streamer_cfg
        self.yt_count, self.yt_day, self.last_yt = 0, None, 0
        self.tt_count = 0

    def choose_cam(self, src: Path):
        """Eray'in kamera kutusunu bul: yuz, karelerin cogunda ve kamera boyutunda olmali."""
        import cv2
        meta = edit.probe(src)
        W, H, dur = meta["w"], meta["h"], meta["duration"]
        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        cands = [edit._frac(c, W, H) for c in self.cfg.get("cam_candidates", [])]
        hits = [0] * len(cands)
        edges = [[] for _ in cands]
        n = 12
        cap = cv2.VideoCapture(str(src))
        for i in range(n):
            cap.set(cv2.CAP_PROP_POS_MSEC, dur * (i + 0.5) / n * 1000)
            ok, fr = cap.read()
            if not ok:
                continue
            for j, (x, y, w, h) in enumerate(cands):
                x, y, w, h = int(x), int(y), int(w), int(h)
                edges[j].append(edge_score := edit.box_edge_score(fr, (x, y, w, h)))
                roi = cv2.equalizeHist(cv2.cvtColor(fr[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY))
                faces = casc.detectMultiScale(roi, 1.1, 5, minSize=(int(H * 0.035), int(H * 0.035)),
                                              maxSize=(int(H * 0.14), int(H * 0.14)))
                if len(faces):
                    hits[j] += 1
        cap.release()
        if cands:
            j = max(range(len(cands)), key=lambda k: hits[k])
            e = median(edges[j]) if edges[j] else 0
            log("kamera adaylari:", hits, "cerceve:", round(e, 2))
            if hits[j] >= n * 0.6 and e >= 0.45:  # yuz + gercek kamera cercevesi
                return {"cam": self.cfg["cam_candidates"][j]}
        # kamera kutusu yok (IRL, tam ekran video, kamera kapali) -> bulanik arka planli tam ekran
        return {"layout": "full"}

    def grab(self, ev, rec: Recorder):
        """Olay biter bitmez ham kesiti kayittan al (hizli, -c copy)."""
        cid = datetime.fromtimestamp(ev["t0"], timezone.utc).strftime("%Y%m%d-%H%M%S")
        if ev.get("t1", ev["t0"]) - ev["t0"] > 30 and ev.get("peak_t"):
            # uzun olay: chat'in en cok guldugu ani ortala (tepki olaydan ~10 sn sonra gelir)
            a = ev["peak_t"] - 32
            b = ev["peak_t"] + 8
        else:
            a = ev["t0"] - 30
            b = min(max(ev["t0"] + 8, ev["t1"] - 12), a + 42)
        if b - a < 30:
            b = a + 32
        for _ in range(30):
            segs = rec.segments()
            if segs and segs[-1][1] >= b + 2:
                break
            time.sleep(2)
        d = WORK / cid
        d.mkdir(parents=True, exist_ok=True)
        try:
            ev["src"] = rec.cut(a, b, d / "src.mp4")
        except Exception as e:  # noqa: BLE001
            log(cid, "kesit alinamadi", e); ev["src"] = None
        ev["cid"], ev["a"], ev["b"] = cid, a, b
        return ev

    def handle(self, ev, rec: Recorder):
        cid, a, b = ev["cid"], ev["a"], ev["b"]
        d = WORK / cid
        try:
            src = ev.get("src")
            if not src:
                log(cid, "kayitta bu aralik yok, atlandi")
                return
            choice = self.choose_cam(src)
            plan = edit.plan_layout(src, cam=choice.get("cam"), layout=choice.get("layout", "auto"))
            jpg = edit.preview(src, d / "p.jpg", plan, at=(b - a) * 0.6)
            out = edit.render(src, d / "out.mp4", plan)
            src.unlink(missing_ok=True)
            lines = transcribe(out)
            title = fallback_title(ev, lines, self.args.game_name, self.args.channel.lower())
            meta = {"id": cid, "score": ev["score"], "peak": ev["peak"], "base": ev["base"], "hype": ev["hype"],
                    "rage": ev["rage"], "chat": ev["texts"][:15], "speech": lines, "layout": plan["layout"],
                    "cam": plan["cam"], "fallback_title": title, "dur": round(b - a, 1)}
            log(cid, "hazir", json.dumps({k: meta[k] for k in ("score", "layout", "fallback_title")}, ensure_ascii=False))
            kind = "oyun" if plan["layout"] == "split" else "irl"
            arc = None if self.args.dry_run else self.archive(cid, out, kind)
            log(cid, "arsiv:", arc)
            publish = ev["score"] >= self.args.auto_publish  # Claude cevap vermezse sadece cok guclu anlar
            # best modunda yayin sonra secilir; basligi beklemek kuyrugu tikar
            if publish_log(cid, meta, jpg) and self.args.title_wait > 0 and self.args.publish_mode == "immediate":
                t = wait_title(cid, self.args.title_wait)
                if t:
                    if t.strip().upper() == "ATLA":
                        publish = False
                    else:
                        title, publish = t, True
            if publish and self.args.publish_mode == "immediate":
                self.upload(cid, out, title, ev)
            else:
                log(cid, "arsivlendi; en iyi secimi (4 saatte bir) bekliyor")
                self.note(cid, {"title": title, "arsiv": arc, "score": ev["score"], "yayin": "bekliyor"})
        except Exception as e:  # noqa: BLE001
            log(cid, "HATA", e)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def archive(self, cid, out, kind="oyun"):
        """Her klibi gunluk arsive koyar: oyun-YYYYMMDD / irl-YYYYMMDD."""
        tag = f"{kind}-" + cid[:8]
        try:
            if subprocess.run(["gh", "release", "view", tag], capture_output=True).returncode != 0:
                subprocess.run(["gh", "release", "create", tag, "--prerelease", "-t", f"{'Oyun' if kind == 'oyun' else 'IRL'} klipleri {cid[:8]}",
                                "-n", "Canli takipte kesilen tum klipler"], capture_output=True, check=True)
            asset = Path(out).with_name(f"{cid}.mp4")
            shutil.copy(out, asset)
            r = subprocess.run(["gh", "release", "upload", tag, str(asset), "--clobber"], capture_output=True, text=True)
            asset.unlink(missing_ok=True)
            return f"{tag}/{cid}.mp4" if r.returncode == 0 else f"HATA {r.stderr[:120]}"
        except Exception as e:  # noqa: BLE001
            return f"HATA {e}"

    def stash(self, cid, out, title, platforms=("youtube", "tiktok")):
        """Yuklenemeyen klibi GitHub Release'e koyar ve hazir/ kuyruguna is dosyasi ekler."""
        tag = "canli-" + cid[:8]
        env = {**os.environ}
        try:
            if subprocess.run(["gh", "release", "view", tag], capture_output=True, env=env).returncode != 0:
                subprocess.run(["gh", "release", "create", tag, "--prerelease", "-t", tag, "-n", "Canli klipler (yuklenince silinir)"],
                               capture_output=True, env=env, check=True)
            asset = Path(out).with_name(f"{cid}.mp4")
            shutil.copy(out, asset)
            subprocess.run(["gh", "release", "upload", tag, str(asset), "--clobber"], capture_output=True, env=env, check=True)
            job = {"asset": f"{tag}/{cid}.mp4", "streamer": self.args.channel, "title": title,
                   "hashtags": self.args.hashtags, "tags": self.args.tags, "platforms": list(platforms),
                   "tiktok_mode": "draft", "youtube_privacy": "public"}
            (ROOT / "hazir").mkdir(exist_ok=True)
            (ROOT / "hazir" / f"{cid}-canli.json").write_text(json.dumps(job, ensure_ascii=False, indent=1))
            git("add", f"hazir/{cid}-canli.json")
            git("commit", "-qm", f"canli klip kuyruga: {cid}")
            for _ in range(3):
                git("pull", "-q", "--rebase", check=False)
                if git("push", "-q", check=False).returncode == 0:
                    break
            return f"release {tag}/{cid}.mp4 + hazir/"
        except Exception as e:  # noqa: BLE001
            return f"HATA saklanamadi {e}"

    def note(self, cid, data):
        d = ROOT / ".canli"
        if d.exists():
            (d / "canli" / f"{cid}.sonuc").write_text(json.dumps(data, ensure_ascii=False))
            subprocess.run(["git", "add", "-A"], cwd=d); subprocess.run(["git", "commit", "-qm", f"sonuc {cid}"], cwd=d, capture_output=True)
            subprocess.run(["git", "pull", "-q", "--rebase", "origin", LOG_BRANCH], cwd=d, capture_output=True)
            subprocess.run(["git", "push", "-q", "origin", f"HEAD:{LOG_BRANCH}"], cwd=d, capture_output=True)

    def upload(self, cid, out, title, ev):
        from .__main__ import build_meta
        from .kick import ClipInfo
        job = {"title": title, "hashtags": self.args.hashtags, "tags": self.args.tags}
        m = build_meta(job, ClipInfo(url="", channel=self.args.channel), self.cfg)
        res = {}
        if self.args.dry_run:
            log(cid, "DRY-RUN, yuklenmedi:", m["yt_title"])
            if not getattr(self, "_stash_tested", False):
                self._stash_tested = True
                tag = "test-" + cid
                r1 = subprocess.run(["gh", "release", "create", tag, "--prerelease", "-t", tag, "-n", "test"], capture_output=True, text=True)
                r2 = subprocess.run(["gh", "release", "upload", tag, str(out)], capture_output=True, text=True)
                r3 = subprocess.run(["gh", "release", "delete", tag, "-y", "--cleanup-tag"], capture_output=True, text=True)
                log("SAKLAMA TESTI", r1.returncode, r2.returncode, r3.returncode, (r1.stderr + r2.stderr + r3.stderr)[:300])
            return
        day = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 8 * 3600))  # YouTube kotasi PT gece yarisi
        if day != self.yt_day:
            self.yt_day, self.yt_count = day, 0
        yt_ok = (os.environ.get("YT_REFRESH_TOKEN") and self.yt_count < self.args.yt_daily
                 and (time.time() - self.last_yt > self.args.yt_gap * 60 or ev["score"] >= self.args.yt_strong))
        if yt_ok:
            try:
                from . import youtube
                res["youtube"] = youtube.upload(out, m["yt_title"], m["description"], m["tags"])
                self.yt_count += 1; self.last_yt = time.time()
            except Exception as e:  # noqa: BLE001
                res["youtube"] = f"HATA {e}"
        if os.environ.get("TIKTOK_CLIENT_KEY") and self.tt_count < self.args.tt_daily:
            try:
                from . import tiktok
                res["tiktok"] = tiktok.upload(out, m["caption"], mode="draft")
                self.tt_count += 1
            except Exception as e:  # noqa: BLE001
                res["tiktok"] = f"HATA {e}"
        ok = lambda k: isinstance(res.get(k), str) and not res[k].startswith("HATA")
        missing = [k for k in ("youtube", "tiktok") if not ok(k)
                   and (k == "youtube" or os.environ.get("TIKTOK_CLIENT_KEY"))]
        if missing:  # YouTube kotasi doldu / hata: klip kaybolmasin, sonra yuklenecek
            res["saklandi"] = self.stash(cid, out, title, missing)
        log(cid, "YUKLEME", json.dumps(res, ensure_ascii=False), "|", m["yt_title"])
        d = ROOT / ".canli"
        if d.exists():
            (d / "canli" / f"{cid}.sonuc").write_text(json.dumps({"title": title, **res}, ensure_ascii=False))
            subprocess.run(["git", "add", "-A"], cwd=d); subprocess.run(["git", "commit", "-qm", f"sonuc {cid}"], cwd=d, capture_output=True)
            subprocess.run(["git", "pull", "-q", "--rebase", "origin", LOG_BRANCH], cwd=d, capture_output=True)
            subprocess.run(["git", "push", "-q", "origin", f"HEAD:{LOG_BRANCH}"], cwd=d, capture_output=True)


# ---------------------------------------------------------------- ana dongu
_last_slot = {"v": time.strftime("%Y%m%d%H", time.gmtime()) if time.gmtime().tm_min >= 7 else ""}


def slot_tick():
    """Yukleme saatlerinde (UTC 11,13,15,17,19,21 :07) en iyi klip secimini tetikle; yayin kapaliyken de."""
    g = time.gmtime()
    slot = time.strftime("%Y%m%d%H", g)
    if g.tm_hour in (11, 13, 15, 17, 19, 21) and g.tm_min >= 7 and slot != _last_slot["v"]:
        _last_slot["v"] = slot
        r = subprocess.run(["gh", "workflow", "run", "best.yml", "-f", "hours=24"], capture_output=True, text=True, cwd=ROOT)
        log("en iyi klip secimi tetiklendi", r.returncode, r.stderr[:100])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="eray")
    ap.add_argument("--game-name", default="gta 6")
    ap.add_argument("--hashtags", nargs="*", default=["gta6", "gtavi"])
    ap.add_argument("--tags", nargs="*", default=["gta 6", "gta vi", "eray gta 6"])
    ap.add_argument("--max-hours", type=float, default=5.6)
    ap.add_argument("--offline-stop-min", type=float, default=25)
    ap.add_argument("--wait-live-hours", type=float, default=5.5)
    ap.add_argument("--title-wait", type=int, default=240, help="Claude'un baslik yazmasi icin beklenecek sn")
    ap.add_argument("--yt-daily", type=int, default=6)
    ap.add_argument("--yt-gap", type=float, default=60, help="YouTube yuklemeleri arasi min dk")
    ap.add_argument("--yt-strong", type=float, default=2.6)
    ap.add_argument("--tt-daily", type=int, default=5)
    ap.add_argument("--publish-mode", default="best", choices=["best", "immediate"],
                    help="best: 4 saatte bir en iyi klip yuklenir (best.yml); immediate: aninda")
    ap.add_argument("--auto-publish", type=float, default=2.8, help="Claude cevap vermezse bu skorun ustu yayinlanir")
    ap.add_argument("--shout-db", type=float, default=9.0, help="ses ortalamanin bu kadar dB ustune cikarsa olay")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg_all = json.loads((ROOT / "config" / "streamers.json").read_text(encoding="utf-8"))
    cfg = {**cfg_all["_default"], **cfg_all.get(args.channel, {})}
    t_start = time.time()
    deadline = t_start + args.max_hours * 3600

    # yayin acilana kadar bekle
    chan_id, live, url, title = channel_state(args.channel)
    while not live:
        if time.time() > t_start + args.wait_live_hours * 3600:
            log("yayin acilmadi, cikiliyor"); return 2  # zincir devam etsin
        log("yayin kapali, bekleniyor"); slot_tick(); time.sleep(60)
        chan_id, live, url, title = channel_state(args.channel)
    log("YAYIN ACIK:", title)

    rec = Recorder(url); rec.start()
    chat = Chat(chan_id)
    det = Detector()
    pub = Publisher(args, cfg)
    jobs = queue.Queue()

    def worker():
        while True:
            ev = jobs.get()
            if ev is None:
                return
            pub.handle(ev, rec)

    th = threading.Thread(target=worker, daemon=True); th.start()
    offline_since = None
    last_state = 0
    last_loud, loud_hist, shout_hits = 0, deque(maxlen=225), 0
    last_slot = time.strftime("%Y%m%d%H", time.gmtime()) if time.gmtime().tm_min >= 7 else ""
    while time.time() < deadline:
        chat.poll()
        if chat.win:
            ev = det.step(chat.win)
            if ev:
                threading.Thread(target=lambda e=ev: jobs.put(pub.grab(e, rec)), daemon=True).start()
        # Eray'in bagirmasi / ani ses patlamasi (OHAAA anlari): chat tetiklemese de yakala
        if rec.alive() and time.time() - last_loud > 8:
            last_loud = time.time()
            lv = rec.loudness()
            if lv is not None:
                loud_hist.append(lv)
                med = median(loud_hist) if len(loud_hist) >= 30 else None
                if med is not None and lv - med >= args.shout_db and det.active is None and time.time() >= det.cool_until:
                    shout_hits += 1
                    if shout_hits >= 2:
                        now = time.time() - 4
                        lr, hr, rr, n = det.rates(chat.win) if chat.win else (0, 0, 0, 0)
                        ev = {"t0": now - 10, "t1": now + 10, "peak": lr, "base": det.baseline(chat.win) or 0,
                              "hype": hr, "rage": rr, "texts": [], "score": round(1.5 + (lv - med) / 10 + lr, 3), "shout": round(lv - med, 1)}
                        log(f"SES PATLAMASI +{lv - med:.1f} dB")
                        det.cool_until = time.time() + 45
                        shout_hits = 0
                        threading.Thread(target=lambda e=ev: (time.sleep(12), jobs.put(pub.grab(e, rec))), daemon=True).start()
                else:
                    shout_hits = 0
        if not rec.alive():
            time.sleep(min(60, 5 * rec.n))  # art arda hata olursa yavasla
            _, live, url, _ = channel_state(args.channel)
            if live and url:
                offline_since = None
                rec.url = url; rec.start()
            else:
                offline_since = offline_since or time.time()
                if time.time() - offline_since > args.offline_stop_min * 60:
                    # Durma: yayin ara verdi; isleri bitir, zincir yeni calismada tekrar acilmasini bekler
                    log("yayin kapali (ara?), bekleme moduna geciliyor")
                    jobs.put(None); th.join(timeout=900); return 2
        slot_tick()
        if time.time() - last_state > 600:
            last_state = time.time()
            lr = det.rates(chat.win)[0] if chat.win else 0
            log(f"durum: kuyruk={jobs.qsize()} gulme=%{lr*100:.0f} yt={pub.yt_count} tt={pub.tt_count}")
            try:  # Claude'un saglik kontrolu icin canli-log'a nabiz yaz
                d = ROOT / ".canli"
                if d.exists() or publish_log("_durum", {}, None):
                    base = det.baseline(chat.win)
                    (d / "canli" / "_durum.json").write_text(json.dumps({
                        "zaman": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "kayit": rec.alive(),
                        "gulme": round(lr, 2), "taban": round(base or 0, 2), "kuyruk": jobs.qsize(),
                        "yt": pub.yt_count, "tt": pub.tt_count, "olay_aktif": det.active is not None}))
                    subprocess.run(["git", "add", "-A"], cwd=d); subprocess.run(["git", "commit", "-qm", "durum"], cwd=d, capture_output=True)
                    subprocess.run(["git", "pull", "-q", "--rebase", "origin", LOG_BRANCH], cwd=d, capture_output=True)
                    subprocess.run(["git", "push", "-q", "origin", f"HEAD:{LOG_BRANCH}"], cwd=d, capture_output=True)
            except Exception as e:  # noqa: BLE001
                log("durum yazilamadi", e)
        time.sleep(2)
    log("sure doldu, zincirdeki sonraki calismaya devrediliyor")
    rec.stop(); jobs.put(None); th.join(timeout=900)
    return 2


if __name__ == "__main__":
    sys.exit(main())
