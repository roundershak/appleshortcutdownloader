"""Kick chat dokumunden viral aday anlari bulur.

Sinyaller (her 5 sn'lik pencere icin):
  laugh  : KEKW/LULW/ICANT/OMEGALUL... emote'lari, klavye-basma gulmeler (ASDJKASJD), 😂🤣💀
  hype   : OOOO, NOWAYING, OHA, ALT F4, !!!? spamleri
  rage   : sinir/kavga/kufur tepkileri, emojiAngry
Skor: gulme orani yerel taban cizgisine gore ne kadar yukselmis + mutlak yogunluk.

python tools/chat_peaks.py vod.jsonl [--top 25]
"""
from __future__ import annotations

import argparse
import json
import re
from statistics import median

LAUGH_EMOTES = re.compile(r"\[emote:\d+:[^\]]*(KEKW|LULW|LUL|OMEGALUL|ICANT|KEKLEO|kekw|haha|HAHA|Laugh|LAUGH|xd|XD|pepeLaugh|KEKL)[^\]]*\]")
HYPE_EMOTES = re.compile(r"\[emote:\d+:[^\]]*(OOOO|NOWAY|Astonished|POGGERS|Pog|monkaS|Shock|WAJAJA)[^\]]*\]")
RAGE_EMOTES = re.compile(r"\[emote:\d+:[^\]]*(Angry|RAGE|Rage|Mad|WeirdChamp|BRUH)[^\]]*\]")
EMOTE = re.compile(r"\[emote:\d+:[^\]]+\]")
LAUGH_TXT = re.compile(r"(😂|🤣|💀|\b(?:a?ha){3,}|\b(?:j?s){3,}j?|\bxd+\b|\b(?:sj|js|aj|ja|ks|sk){3,}|kekw|asdas|sdfs|ksdj|lksd|sjsj|ajaj|ğsl|şlsd)", re.I)
HYPE_TXT = re.compile(r"\b(oha+|ooo+|alt ?f4|noluyo|yok art[iı]k|helal|efsane|clip+|klip)\b|[!?]{3,}", re.I)
RAGE_TXT = re.compile(r"(sinir|kavga|kufur|küfür|sövd|sov|bagir|bağır|cildir|çıldır|delir|kopt|kafayi|kafayı|masaya|monit[oö]r|ragele|tilt|toxic|t[oö]ksik)", re.I)
VOWELS = set("aeıioöuüAEIİOÖUÜ")


def keysmash(word: str) -> bool:
    w = re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşü]", "", word)
    if len(w) < 7:
        return False
    v = sum(ch in VOWELS for ch in w)
    return v / len(w) < 0.22 or len(set(w.lower())) <= 4


def classify(text: str):
    plain = EMOTE.sub(" ", text)
    laugh = bool(LAUGH_EMOTES.search(text) or LAUGH_TXT.search(plain) or any(keysmash(w) for w in plain.split()))
    hype = bool(HYPE_EMOTES.search(text) or HYPE_TXT.search(plain))
    rage = bool(RAGE_EMOTES.search(text) or RAGE_TXT.search(plain))
    caps = len(plain.strip()) >= 6 and plain.upper() == plain and any(c.isalpha() for c in plain)
    return laugh, hype, rage, caps


def fmt(s):
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def load(path):
    meta, rows = None, []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                break
            if i == 0:
                meta = d["meta"]
                continue
            rows.append(d)
    return meta, rows


def analyze(path, top=25, smooth=4, gap=90):
    meta, rows = load(path)
    feats = []
    for r in rows:
        n = len(r["m"])
        l = h = g = c = 0
        users = set()
        for m in r["m"]:
            a, b, d, e = classify(m["c"])
            l += a; h += b; g += d; c += e
            users.add(m["u"])
        feats.append({"off": r["off"], "n": n, "laugh": l, "hype": h, "rage": g, "caps": c, "msgs": r["m"]})

    def roll(key, i, k=smooth):
        seg = feats[i:i + k]
        tot = sum(x["n"] for x in seg) or 1
        return sum(x[key] for x in seg) / tot, tot

    series = []
    for i in range(len(feats)):
        lr, tot = roll("laugh", i)
        hr, _ = roll("hype", i)
        rr, _ = roll("rage", i)
        cr, _ = roll("caps", i)
        series.append((lr, hr, rr, cr, tot))

    scores = []
    W = 120  # +-10 dk taban cizgisi
    for i, (lr, hr, rr, cr, tot) in enumerate(series):
        lo, hi = max(0, i - W), min(len(series), i + W)
        base_l = median(s[0] for s in series[lo:hi]) if hi > lo else 0
        base_n = median(s[4] for s in series[lo:hi]) if hi > lo else 1
        activity = min(2.0, tot / max(1, base_n))
        score = (max(0, lr - base_l) * 3 + lr) * activity + hr * 0.8 + rr * 0.6 + cr * 0.3
        if tot < smooth * 6:  # chat cok bossa guvenme
            score *= 0.4
        scores.append((score, i, lr, hr, rr, base_l))

    picked = []
    for s in sorted(scores, reverse=True):
        off = feats[s[1]]["off"]
        if all(abs(off - feats[p[1]]["off"]) > gap for p in picked):
            picked.append(s)
        if len(picked) >= top:
            break
    return meta, feats, picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--json")
    a = ap.parse_args()
    meta, feats, picked = analyze(a.path, a.top)
    print(f"# {meta['title']} | {meta['start']} | {meta['duration'] / 3600:.1f} saat | {meta['views']} izlenme")
    out = []
    for rank, (score, i, lr, hr, rr, base) in enumerate(picked, 1):
        off = feats[i]["off"]
        sample = [m["c"] for f in feats[i:i + 4] for m in f["msgs"]]
        texts = [EMOTE.sub(lambda m: ":" + m.group(0).split(":")[2].rstrip("]") + ":", t) for t in sample]
        words = [t for t in texts if len(EMOTE.sub("", t).strip()) > 3][:12]
        clip_start = max(0, off - 40)  # chat tepkisi olaydan ~10-30 sn sonra gelir
        print(f"\n{rank:2d}. {fmt(off)}  skor={score:.2f}  gulme=%{lr * 100:.0f} (taban %{base * 100:.0f})  hype=%{hr * 100:.0f}  sinir=%{rr * 100:.0f}")
        print(f"    klip araligi ~ {fmt(clip_start)} - {fmt(off + 20)}  |  https://kick.com/eray/videos/{meta['uuid']}?t={int(clip_start)}")
        for w in words[:8]:
            print(f"    > {w[:110]}")
        out.append({"rank": rank, "off": off, "clip_start": clip_start, "clip_end": off + 20, "score": round(score, 3),
                    "laugh": round(lr, 3), "hype": round(hr, 3), "rage": round(rr, 3), "chat": words[:12]})
    if a.json:
        json.dump({"meta": meta, "peaks": out}, open(a.json, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
