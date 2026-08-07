#!/bin/bash

# 오늘 밤 23:59 예약 - 오늘 최초로 깨어서 아래 Tomorrow 변환을 실행
pmset schedule wakeorpoweron "$(date +%m/%d/%Y) 23:59:00"

# 내일 날짜 - 영구 반복됨
TOMORROW=$(date -v+1d +%m/%d/%Y)

# 내일 아침/저녁/밤 예약
pmset schedule wakeorpoweron "$TOMORROW 23:59:00" # 다음날 깨어나서 Tomorrow를 재설정하기 위한 wakeup 예약



# 터미널에서 실행 = sudo bash C:/Code_Local/GitHub/launchd/pmset.sh



