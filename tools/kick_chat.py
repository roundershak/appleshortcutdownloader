"""Kick yayin tekrari (VOD) chat'ini indirir: 5 sn'lik pencereler halinde.

python tools/kick_chat.py <kanal> <vod_index|vod_id> <cikti.jsonl>
"""
from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from curl_cffi import requests as creq

_local = threading.local()


def _sess():
    if not hasattr(_local, "s"):
        _local.s = creq.Session(impersonate="chrome")
    return _local.s


def get(url, tries=5):
    import time
    for i in range(tries):
        try:
            r = _sess().get(url, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 403, 500, 502, 503):
                time.sleep(2 * (i + 1))
                continue
            return None
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def vods(channel: str):
    return get(f"https://kick.com/api/v2/channels/{channel}/videos") or []


def fetch_window(chan_id: int, t: datetime):
    ts = t.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    d = get(f"https://kick.com/api/v2/channels/{chan_id}/messages?start_time={ts}")
    if not d:
        return t, None
    out = []
    for m in d.get("data", {}).get("messages", []):
        out.append({"t": m.get("created_at"), "u": (m.get("sender") or {}).get("username"),
                    "c": m.get("content", ""), "type": m.get("type")})
    return t, out


def main(channel, which, out_path, workers=4):
    vs = vods(channel)
    v = vs[int(which)] if str(which).isdigit() and int(which) < 100 else next(x for x in vs if str(x["id"]) == str(which))
    chan_id = v["channel_id"]
    start = datetime.strptime(v["start_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    dur = v["duration"] / 1000
    times = [start + timedelta(seconds=s) for s in range(0, int(dur) + 5, 5)]
    print(f"{v['session_title']} | {start} | {dur / 3600:.1f} saat | {len(times)} pencere", flush=True)
    missing = 0
    with open(out_path, "w", encoding="utf-8") as f, ThreadPoolExecutor(workers) as ex:
        f.write(json.dumps({"meta": {"vod_id": v["id"], "uuid": v["video"]["uuid"], "title": v["session_title"],
                                     "start": v["start_time"], "duration": dur, "views": v.get("views")}}, ensure_ascii=False) + "\n")
        for i, (t, msgs) in enumerate(ex.map(lambda t: fetch_window(chan_id, t), times)):
            off = (t - start).total_seconds()
            if msgs is None:
                missing += 1
                msgs = []
            f.write(json.dumps({"off": off, "n": len(msgs), "m": msgs}, ensure_ascii=False) + "\n")
            if i % 1000 == 0:
                print(f"  {i}/{len(times)}", flush=True)
    print(f"bitti, eksik pencere: {missing}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
