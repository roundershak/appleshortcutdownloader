"""YouTube videolarinin 'en cok tekrar izlenen' (heatmap) zirvelerini ve
zaman damgali yorumlarini cikarir. python tools/yt_analyze.py id1 id2 ..."""
import json, re, subprocess, sys

TS = re.compile(r"\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b")

def fmt(s):
    s = int(s); return f"{s//3600}:{s%3600//60:02d}:{s%60:02d}"

for vid in sys.argv[1:]:
    for client in ("mweb", "web_embedded", "web", "tv"):
        r = subprocess.run(["yt-dlp", "-q", "--skip-download", "--ignore-no-formats-error", "-J", "--write-comments",
                            "--extractor-args", f"youtube:player_client={client};max_comments=300,all,0;comment_sort=top",
                            f"https://www.youtube.com/watch?v={vid}"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            break
    else:
        print(f"## {vid} ALINAMADI: {r.stderr.strip()[-200:]}"); continue
    d = json.loads(r.stdout)
    print(f"\n## {vid} | {d.get('title')} | {d.get('view_count')} izlenme | {fmt(d.get('duration') or 0)}")
    hm = d.get("heatmap") or []
    if hm:
        peaks = sorted(hm, key=lambda h: -h["value"])
        chosen = []
        for h in peaks:
            if all(abs(h["start_time"] - c["start_time"]) > 60 for c in chosen):
                chosen.append(h)
            if len(chosen) == 10: break
        print("HEATMAP zirveleri:", ", ".join(f"{fmt(h['start_time'])}({h['value']:.2f})" for h in sorted(chosen, key=lambda h: h['start_time'])))
    for ch in d.get("chapters") or []:
        print(f"  bolum {fmt(ch['start_time'])} {ch['title']}")
    cms = [c for c in (d.get("comments") or []) if TS.search(c.get("text", ""))]
    cms.sort(key=lambda c: -(c.get("like_count") or 0))
    for c in cms[:25]:
        print(f"  [{c.get('like_count')}👍] {c['text'][:220].replace(chr(10), ' / ')}")
