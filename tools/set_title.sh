#!/bin/bash
# kullanim: tools/set_title.sh <id> "<baslik>" [oyun|irl]   (ATLA = paylasma)
D=$(cd "$(dirname "$0")/.." && pwd)/.canli
cd "$D" && git fetch -q origin canli-log && git reset -q --hard origin/canli-log
printf '%s\n' "$2" > "canli/$1.title"
[ -n "$3" ] && printf '%s\n' "$3" > "canli/$1.tur"
git add canli/ && git commit -qm "baslik $1" && for i in 1 2 3 4; do git push -q origin HEAD:canli-log 2>/dev/null && echo "gonderildi: $1 -> $2 ${3:+[$3]}" && exit 0; git pull -q --rebase origin canli-log; done
