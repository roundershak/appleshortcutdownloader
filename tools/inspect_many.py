"""chat_peaks JSON'undaki ilk N zirveyi incele ve rapor yaz.
python tools/inspect_many.py peaks.json out_dir N"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import inspect_peak, kick_vod

d = json.load(open(sys.argv[1])); out = Path(sys.argv[2]); n = int(sys.argv[3])
u = d["meta"]["uuid"]; res = []
for p in d["peaks"][:n]:
    r = inspect_peak.inspect(u, p["off"], before=60, after=10, out=out)
    loud = sorted(r["loud"], key=lambda x: -x[1])[:4]
    print(f"\n=== #{p['rank']} {kick_vod.fmt(p['off'])} gulme=%{p['laugh']*100:.0f} hype=%{p['hype']*100:.0f} sinir=%{p['rage']*100:.0f}", flush=True)
    print("  chat:", " | ".join(c for c in p["chat"][:6]))
    print("  en yuksek ses:", ", ".join(f"{kick_vod.fmt(t)}({v:.0f}dB)" for t, v in sorted(loud)))
    for t, s in r["text"]:
        print(f"  {kick_vod.fmt(t)}  {s}")
    res.append({**p, "text": r["text"], "loud": r["loud"]})
json.dump({"meta": d["meta"], "peaks": res}, open(out / "inspected.json", "w"), ensure_ascii=False)
