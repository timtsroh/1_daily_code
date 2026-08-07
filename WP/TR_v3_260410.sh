#!/bin/bash

# 각 스킬에 타임아웃 적용 (초 단위). 타임아웃 시 해당 스킬만 스킵하고 다음 진행.
TIMEOUT=900  # 15분
LOG="C:/Code_Local/launchd_output.log"

run_with_timeout() {
    local name="$1"
    shift
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] === $name ===" >> "$LOG"
    /bin/bash "$@" &
    local pid=$!
    local elapsed=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep 5
        elapsed=$((elapsed + 5))
        if [ $elapsed -ge $TIMEOUT ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] TIMEOUT: $name (${TIMEOUT}s 초과, killing pid=$pid)" >> "$LOG"
            kill -TERM "$pid" 2>/dev/null
            sleep 3
            kill -9 "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null
            return 0
        fi
    done
    wait "$pid" 2>/dev/null
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] ERROR: $name (exit=$exit_code)" >> "$LOG"
    fi
    return 0  # 에러여도 다음 스킬 진행
}

run_with_timeout "log_start" C:/Code_Local/GitHub/launchd/log/run.sh start
run_with_timeout "전종현"     C:/Code_Local/GitHub/launchd/전종현/run.sh
run_with_timeout "김봉수"     C:/Code_Local/GitHub/launchd/김봉수/run.sh
run_with_timeout "nrd"       C:/Code_Local/GitHub/launchd/nrd/run.sh
run_with_timeout "최광식"     C:/Code_Local/GitHub/launchd/최광식/run.sh
run_with_timeout "엄민용"     C:/Code_Local/GitHub/launchd/엄민용/run.sh
run_with_timeout "노정석"     C:/Code_Local/GitHub/launchd/노정석/run.sh
run_with_timeout "daily"     C:/Code_Local/GitHub/launchd/daily/run.sh
run_with_timeout "log_end"   C:/Code_Local/GitHub/launchd/log/run.sh end
