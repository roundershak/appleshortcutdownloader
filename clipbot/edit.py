"""Dikey (9:16) Shorts/TikTok edit: ustte kamera, altta ekran."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

OUT_W, OUT_H = 1080, 1920
DEFAULT_CAM_H = 640  # ust panel yuksekligi; alt panel = 1920 - bu


def probe(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    s = d["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return {"w": int(s["width"]), "h": int(s["height"]),
            "fps": float(num) / float(den or 1), "duration": float(d["format"]["duration"])}


def _even(v: float) -> int:
    return int(v // 2) * 2


def fit_region(x, y, w, h, aspect, W, H):
    """Bolgeyi hedef en/boy oranina gore ortalayarak kirpar (cover)."""
    if w / h > aspect:
        nw = h * aspect
        x += (w - nw) / 2
        w = nw
    else:
        nh = w / aspect
        y += (h - nh) / 2
        h = nh
    w, h = min(w, W), min(h, H)
    x = min(max(0, x), W - w)
    y = min(max(0, y), H - h)
    return _even(x), _even(y), max(2, _even(w)), max(2, _even(h))


def detect_face(path: Path, meta: dict, samples: int = 16, region=None):
    """Klipten kareler alip en tutarli yuzu bulur. (x, y, w, h) piksel ya da None.
    region verilirse sadece o bolgenin icindeki yuzler sayilir."""
    import cv2

    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(str(path))
    W, H, dur = meta["w"], meta["h"], meta["duration"]
    boxes = []
    for i in range(samples):
        cap.set(cv2.CAP_PROP_POS_MSEC, (dur * (i + 0.5) / samples) * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        faces = casc.detectMultiScale(gray, 1.1, 6, minSize=(int(H * 0.06), int(H * 0.06)))
        for f in faces:
            b = tuple(map(int, f))
            if region:
                rx, ry, rw, rh = region
                cx, cy = b[0] + b[2] / 2, b[1] + b[3] / 2
                if not (rx <= cx <= rx + rw and ry <= cy <= ry + rh):
                    continue
            boxes.append(b)
    cap.release()
    if not boxes:
        return None
    # merkezleri yakin olan kutulari grupla, en cok gorunen grubu sec
    clusters: list[list[tuple]] = []
    for b in boxes:
        cx, cy = b[0] + b[2] / 2, b[1] + b[3] / 2
        for c in clusters:
            r = c[0]
            if abs(cx - (r[0] + r[2] / 2)) < W * 0.08 and abs(cy - (r[1] + r[3] / 2)) < H * 0.12:
                c.append(b)
                break
        else:
            clusters.append([b])
    best = max(clusters, key=lambda c: (len(c), sum(b[2] * b[3] for b in c)))
    if len(best) < max(2, samples // 5):
        return None
    med = lambda k: sorted(b[k] for b in best)[len(best) // 2]
    return med(0), med(1), med(2), med(3)


def cam_from_face(face, aspect, W, H, bounds=None):
    """Yuzun etrafinda kamera kadraji. bounds (x,y,w,h) verilirse onun icinde kalir."""
    bx, by, bw, bh = bounds or (0, 0, W, H)
    fx, fy, fw, fh = face
    ch = min(bh, fh * (3.2 if fh < H * 0.2 else 2.3))
    cw = ch * aspect
    if cw > bw:
        cw, ch = bw, bw / aspect
    cx = fx + fw / 2
    top = fy + fh * 0.55 - ch * 0.45
    x = min(max(bx, cx - cw / 2), bx + bw - cw)
    y = min(max(by, top), by + bh - ch)
    return fit_region(x, y, cw, ch, aspect, W, H)


def _frac(region, W, H):
    x, y, w, h = region
    if max(region) <= 1.0:  # oran verilmis
        return x * W, y * H, w * W, h * H
    return x, y, w, h


def plan_layout(src: Path, cam=None, game=None, layout="auto", cam_h=DEFAULT_CAM_H) -> dict:
    meta = probe(src)
    W, H = meta["w"], meta["h"]
    bot_h = OUT_H - cam_h
    game_aspect = OUT_W / bot_h
    cam_aspect = OUT_W / cam_h

    if game:
        g = fit_region(*_frac(game, W, H), game_aspect, W, H)
    else:
        g = fit_region(0, 0, W, H, game_aspect, W, H)

    plan = {"meta": meta, "layout": layout, "cam_h": cam_h, "game": g, "cam": None, "source": None}
    if layout == "full":
        return plan
    if cam:
        region = _frac(cam, W, H)
        rx, ry, rw, rh = region
        plan["cam"] = fit_region(rx, ry, rw, rh, cam_aspect, W, H)
        plan["source"] = "preset"
        # bolge hedef orandan belirgin farkliysa (orn. dikey panel) yuzu ortala
        if abs((rw / rh) - cam_aspect) / cam_aspect > 0.25:
            face = detect_face(src, meta, region=region)
            if face:
                plan["cam"] = cam_from_face(face, cam_aspect, W, H, bounds=region)
                plan["source"] = f"preset+face {face}"
    else:
        face = detect_face(src, meta)
        if face:
            plan["cam"] = cam_from_face(face, cam_aspect, W, H)
            plan["source"] = f"face {face}"
    plan["layout"] = "split" if plan["cam"] else "full"
    return plan


def _filters(plan: dict) -> str:
    if plan["layout"] == "split":
        cx, cy, cw, ch = plan["cam"]
        gx, gy, gw, gh = plan["game"]
        return (
            f"[0:v]split=2[a][b];"
            f"[a]crop={cw}:{ch}:{cx}:{cy},scale={OUT_W}:{plan['cam_h']}:flags=lanczos,unsharp=5:5:0.8:5:5:0.0,setsar=1[top];"
            f"[b]crop={gw}:{gh}:{gx}:{gy},scale={OUT_W}:{OUT_H - plan['cam_h']}:flags=lanczos,setsar=1[bot];"
            f"[top][bot]vstack=inputs=2,format=yuv420p[v]"
        )
    # kamera yoksa: bulanik arka plan + ortada video
    return (
        f"[0:v]split=2[a][b];"
        f"[a]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,crop={OUT_W}:{OUT_H},"
        f"boxblur=30:3,eq=brightness=-0.08[bg];"
        f"[b]crop=ih*4/3:ih:iw-ih*4/3:0,scale={OUT_W}:810:flags=lanczos,unsharp=5:5:0.5:5:5:0.0[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p[v]"
    )


def render(src: Path, out: Path, plan: dict, start=None, end=None, max_len=180.0) -> Path:
    fps = min(60.0, plan["meta"]["fps"] or 30.0)
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if start:
        cmd += ["-ss", str(start)]
    if end:
        cmd += ["-to", str(end)]
    cmd += ["-i", str(src), "-filter_complex", _filters(plan), "-map", "[v]", "-map", "0:a?",
            "-t", str(max_len), "-r", f"{fps:g}",
            "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high",
            "-maxrate", "16M", "-bufsize", "32M", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    return out


def preview(src: Path, out: Path, plan: dict, at: float | None = None) -> Path:
    t = at if at is not None else plan["meta"]["duration"] / 3
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(src),
           "-filter_complex", _filters(plan) + ";[v]scale=540:-2[p]", "-map", "[p]",
           "-frames:v", "1", str(out)]
    subprocess.run(cmd, check=True)
    return out


def box_edge_score(img, c):
    """Kamera kutusu gercek bir cerceve mi? Kenarlarda keskin duz cizgi orani (0-1)."""
    import cv2
    import numpy as np
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(int)
    H, W = g.shape
    x, y, w, h = [int(v) for v in c]
    sc = []
    if x + w + 3 < W:
        sc.append((np.abs(g[y + 5:y + h - 5, x + w + 2] - g[y + 5:y + h - 5, x + w - 3]) > 18).mean())
    if x > 3:
        sc.append((np.abs(g[y + 5:y + h - 5, x - 3] - g[y + 5:y + h - 5, x + 2]) > 18).mean())
    if y > 3:
        sc.append((np.abs(g[y - 3, x + 5:x + w - 5] - g[y + 2, x + 5:x + w - 5]) > 18).mean())
    if y + h + 3 < H:
        sc.append((np.abs(g[y + h + 2, x + 5:x + w - 5] - g[y + h - 3, x + 5:x + w - 5]) > 18).mean())
    return float(min(sc)) if sc else 0.0
