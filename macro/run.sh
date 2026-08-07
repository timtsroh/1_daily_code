#!/bin/bash
set -euo pipefail

# macro 일일 wrapper
# 1) ECOS/UST/FRED 등에서 거시지표(금리·환율·물가·수출·실업률) 수집 → adb1 macro.json 갱신
# 2) macro.json 이 바뀌었으면 adb1 레포에 커밋·푸시 → Vercel 자동 배포
# (수동 전체 재수집: python collectors/build.py --download)

ADB1="C:/Code_Local/GitHub/adb1"
MACRO="$ADB1/macro"
JSON_REL="macro/data/macro.json"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Starting macro collector..."

cd "$MACRO"
python collectors/build.py

# macro.json 변경분만 배포 (Vercel-연동 repo → author 반드시 timtsroh)
if [ -d "$ADB1/.git" ]; then
  cd "$ADB1"
  if ! git diff --quiet -- "$JSON_REL" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] macro.json 변경 감지 → adb1 push"
    git add "$JSON_REL"
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        commit -m "chore(macro): 거시지표 갱신 ($(date '+%Y-%m-%d'))" \
        --author="timtsroh <254851998+timtsroh@users.noreply.github.com>"
    # 다른 대시보드 자동화가 origin 을 앞서가므로 push 전 rebase 로 동기화 (안 하면 non-fast-forward 거부)
    # --autostash: user WIP(uncommitted 변경분)가 있어도 rebase 자동 stash/pop 하여 배치가 안 죽음
    git fetch origin -q
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        pull --rebase --autostash origin main
    git push origin main
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] macro.json 변경 없음 — push 생략"
  fi
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Done."
