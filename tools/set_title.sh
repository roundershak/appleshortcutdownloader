#!/bin/bash
# kullanim: tools/set_title.sh <id> "<baslik>"   (ATLA = paylasma)
D=$(cd "$(dirname "$0")/.." && pwd)/.canli
cd "$D" && git fetch -q origin canli-log && git reset -q --hard origin/canli-log
printf '%s\n' "$2" > "canli/$1.title"
git add "canli/$1.title" && git commit -qm "baslik $1" && for i in 1 2 3; do git push -q origin HEAD:canli-log && echo "gonderildi: $1 -> $2" && exit 0; git pull -q --rebase origin canli-log; done
