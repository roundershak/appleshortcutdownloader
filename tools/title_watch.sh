#!/bin/bash
# canli-log dalinda basligi bekleyen yeni klipleri bildirir (Claude icin)
D=$(cd "$(dirname "$0")/.." && pwd)/.canli
[ -d "$D" ] || git -C "$(dirname "$0")/.." worktree add -q "$D" origin/canli-log
seen=""
while true; do
  git -C "$D" fetch -q origin canli-log 2>/dev/null && git -C "$D" reset -q --hard origin/canli-log
  for f in "$D"/canli/*.json; do
    [ -e "$f" ] || continue
    case "$(basename $f)" in _*) continue;; esac
    id=$(basename "$f" .json)
    [ -e "$D/canli/$id.title" ] || [ -e "$D/canli/$id.sonuc" ] && continue
    case " $seen " in *" $id "*) continue;; esac
    seen="$seen $id"
    echo "YENI_KLIP $id $(python3 -c "import json,sys;d=json.load(open('$f'));print(d['fallback_title'],'| skor',d['score'])")"
  done
  sleep 15
done
