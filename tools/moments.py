"""Chat + ses + konusma metnini birlestirip viral anlari siralar.

Skor bilesenleri (5 sn'lik pencere, ~20 sn yumusatma):
  chat_gulme : KEKW/klavye-basma orani (mutlak + yerel tabana gore artis)
  chat_hype  : OOOO/OHA/!!! orani
  bagirma    : ses seviyesinin yerel medyanin kac dB ustunde oldugu
  kufur/kavga: konusma metninde kufur, 'lan/oglum', 'aaaa' gibi patlamalar

python tools/moments.py chat.jsonl transcript.jsonl [--top 20] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).parent))
from chat_peaks import classify, load  # noqa: E402

SWEAR = re.compile(r"\b(amk|amına|amina|aq|siktir|sik|sikey|orospu|piç|pic|yarra|yarak|göt|got|ibne|şerefsiz|serefsiz|gerizekal|salak|aptal|mal)\w*", re.I)
HEAT = re.compile(r"\b(lan|oğlum|oglum|kanka|abi|dur|yapma|ne yapıyorsun|nap|bitti|alt ?f4|kapat|gel buraya|vur|öldür|oldur)\b", re.I)
SCREAM = re.compile(r"(a{4,}|o{4,}|ah{2,}|ahaha|haha)", re.I)


def fmt(s):
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chat")
    ap.add_argument("transcript")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--json")
    ap.add_argument("--delay", type=float, default=8, help="chat tepkisinin olaydan kac sn sonra geldigi")
    a = ap.parse_args()

    meta, rows = load(a.chat)
    loud, speech = {}, []
    for line in open(a.transcript, encoding="utf-8"):
        d = json.loads(line)
        if "loud" in d:
            loud[int(d["t"])] = d["loud"]
        else:
            speech.append(d)
    if not loud:
        sys.exit("transcript bos")
    t0, t1 = min(loud), max(loud)

    win = {}
    for r in rows:
        off = r["off"] - a.delay  # chat'i olay anina geri kaydir
        if not (t0 <= off <= t1):
            continue
        k = int(off // 5) * 5
        w = win.setdefault(k, {"n": 0, "laugh": 0, "hype": 0, "rage": 0, "chat": []})
        for m in r["m"]:
            l, h, g, c = classify(m["c"])
            w["n"] += 1; w["laugh"] += l; w["hype"] += h; w["rage"] += g
            if len(re.sub(r"\[emote:[^\]]+\]", "", m["c"]).strip()) > 3:
                w["chat"].append(m["c"])
    for s in speech:
        k = int(s["t"] // 5) * 5
        w = win.setdefault(k, {"n": 0, "laugh": 0, "hype": 0, "rage": 0, "chat": []})
        w.setdefault("speech", []).append(s["s"])

    keys = sorted(k for k in win if t0 <= k <= t1)
    loud_med = median(loud.values())
    feats = []
    for k in keys:
        w = win[k]
        seg = [win.get(k + d, {}) for d in (0, 5, 10, 15)]
        n = sum(x.get("n", 0) for x in seg) or 1
        lr = sum(x.get("laugh", 0) for x in seg) / n
        hr = sum(x.get("hype", 0) for x in seg) / n
        lv = [loud.get(k + i, -90) for i in range(-5, 15)]
        shout = max(0.0, sorted(lv)[-3] - loud_med)  # en yuksek 3. saniye (tek tik sesleri ele)
        text = " ".join(" ".join(win.get(k + d, {}).get("speech", [])) for d in (-10, -5, 0, 5))
        sw = len(SWEAR.findall(text)); he = len(HEAT.findall(text)); sc = len(SCREAM.findall(text))
        feats.append({"k": k, "lr": lr, "hr": hr, "shout": shout, "sw": sw, "he": he, "sc": sc, "n": n})

    out = []
    for i, f in enumerate(feats):
        lo, hi = max(0, i - 60), min(len(feats), i + 60)
        base = median(x["lr"] for x in feats[lo:hi])
        f["score"] = (f["lr"] * 2 + max(0, f["lr"] - base) * 3 + f["hr"]
                      + min(f["shout"], 15) / 6 + min(f["sw"], 4) * 0.25 + min(f["he"], 6) * 0.08 + min(f["sc"], 3) * 0.2)
    picked = []
    for f in sorted(feats, key=lambda x: -x["score"]):
        if all(abs(f["k"] - p["k"]) > 75 for p in picked):
            picked.append(f)
        if len(picked) >= a.top:
            break
    print(f"# {meta['title']}  (ses medyani {loud_med:.0f} dB)")
    for r, f in enumerate(picked, 1):
        k = f["k"]
        chat = [c for d in (0, 5, 10, 15) for c in win.get(k + d, {}).get("chat", [])][:6]
        lines = [s for s in speech if k - 35 <= s["t"] <= k + 15]
        print(f"\n{r:2d}. {fmt(k)} skor={f['score']:.2f} gulme=%{f['lr']*100:.0f} hype=%{f['hr']*100:.0f} "
              f"bagirma=+{f['shout']:.0f}dB kufur={f['sw']} gerilim={f['he']}")
        print("   chat: " + " | ".join(c[:60] for c in chat))
        for s in lines:
            print(f"   {fmt(s['t'])}  {s['s']}")
        out.append({**{x: f[x] for x in ("k", "score", "lr", "hr", "shout", "sw", "he")},
                    "chat": chat, "speech": [(s["t"], s["s"]) for s in lines]})
    if a.json:
        json.dump({"meta": meta, "moments": out}, open(a.json, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
