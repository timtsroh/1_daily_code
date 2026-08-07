#!/bin/bash
set -euo pipefail

# policy_dates 주간 wrapper (매주 토요일 05:00, plist_week.sh)
# 1) Fed FOMC + BOK 금통위 스크래핑 + Jackson Hole 상수 → adb1 ec_cal/data/policy_dates.json 갱신
# 2) JSON 변경 시 adb1 push (author=timtsroh) → Vercel 자동 재배포
# 수동 실행: bash C:/Code_Local/1_Daily_Code/policy_dates/run.sh

ADB1="C:/Code_Local/GitHub/adb1"
EC_CAL="$ADB1/ec_cal"
JSON_REL="ec_cal/data/policy_dates.json"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Starting policy_dates collector..."

cd "$EC_CAL"
python -m collectors.policy_dates

# policy_dates.json 변경분만 배포 (Vercel-연동 repo → author 반드시 timtsroh)
if [ -d "$ADB1/.git" ]; then
  cd "$ADB1"
  if ! git diff --quiet -- "$JSON_REL" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] policy_dates.json 변경 감지 → adb1 push"
    git add "$JSON_REL"
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        commit -m "chore(policy_dates): FOMC·BOK·Jackson Hole 일정 갱신 ($(date '+%Y-%m-%d'))" \
        --author="timtsroh <254851998+timtsroh@users.noreply.github.com>"
    git fetch origin -q
    git -c user.name=timtsroh -c user.email=254851998+timtsroh@users.noreply.github.com \
        pull --rebase --autostash origin main
    git push origin main
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] policy_dates.json 변경 없음 — push 생략"
  fi
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Done."
