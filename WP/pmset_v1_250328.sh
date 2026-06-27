#!/bin/bash

# 오늘 밤 23:59 예약 - 오늘 최초로 깨어서 아래 Tomorrow 변환을 실행
sudo pmset schedule wakeorpoweron "$(date +%m/%d/%Y) 23:59:00"

# 내일 날짜 - 영구 반복됨
TOMORROW=$(date -v+1d +%m/%d/%Y)

# 내일 아침/저녁/밤 예약
sudo pmset schedule wakeorpoweron "$TOMORROW 05:59:00" # tealeaf.light.plist에서 6am에 Light.sh 실행 명령
sudo pmset schedule wakeorpoweron "$TOMORROW 23:59:00" # 다음날 깨어나서 Tomorrow를 재설정하기 위한 wakeup 예약

# 1200초 (20분) 후 자동 잠자기
sleep 1200
osascript -e 'tell application "System Events" to sleep'


# 실행어 /Users/tealeaf/Local/Light/pmset.sh
