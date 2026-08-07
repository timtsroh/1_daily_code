#!/bin/bash

# 각 스킬에 타임아웃 적용 (초 단위). 타임아웃 시 해당 스킬만 스킵하고 다음 진행.
TIMEOUT=1800  # 30분
LOG="C:/Code_Local/launchd_output.log"

# 작업별 결과를 누적하고, log_end 직전에 전체 요약을 디스코드로 전송.
TASK_NAMES=()
TASK_RESULTS=()

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
            TASK_NAMES+=("$name")
            TASK_RESULTS+=("timeout")
            return 0
        fi
    done
    wait "$pid" 2>/dev/null
    local exit_code=$?
    TASK_NAMES+=("$name")
    if [ $exit_code -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] ERROR: $name (실패, exit=$exit_code)" >> "$LOG"
        TASK_RESULTS+=("fail")
    else
        TASK_RESULTS+=("ok")
    fi
    return 0  # 에러여도 다음 스킬 진행
}

# log_end 호출 직전에 전체 작업 결과를 디스코드로 전송한다.
# log_start/log_end 자체는 보고 대상에서 제외.
notify_summary() {
    local lines=""
    local nl=$'\n'
    local i
    for i in "${!TASK_NAMES[@]}"; do
        local name="${TASK_NAMES[$i]}"
        local result="${TASK_RESULTS[$i]}"
        case "$name" in log_start|log_end) continue ;; esac
        case "$result" in
            ok)      lines="${lines}${nl}- ✅ ${name}" ;;
            fail)    lines="${lines}${nl}- ❌ ${name}" ;;
            timeout) lines="${lines}${nl}- ⏰ ${name} (timeout ${TIMEOUT}s)" ;;
        esac
    done
    local msg="📋 plist_day.sh 작업 결과${lines}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 작업 결과 디스코드 전송" >> "$LOG"
    python C:/Users/DELL/.claude/skills/log/scripts/log.py discord "$msg" >> "$LOG" 2>&1 || true
}

run_with_timeout "log_start" C:/Code_Local/1_Daily_Code/log/run.sh start
run_with_timeout "전종현"     C:/Code_Local/1_Daily_Code/전종현/run.sh
run_with_timeout "김봉수"     C:/Code_Local/1_Daily_Code/김봉수/run.sh
run_with_timeout "노정석"     C:/Code_Local/1_Daily_Code/노정석/run.sh
run_with_timeout "nrd"       C:/Code_Local/1_Daily_Skill/nrd/run.sh
run_with_timeout "최광식"     C:/Code_Local/1_Daily_Code/최광식/run.sh
run_with_timeout "엄민용"     C:/Code_Local/1_Daily_Code/엄민용/run.sh
run_with_timeout "tech_yt_listing" C:/Code_Local/1_Daily_Code/tech_yt_listing/run.sh
run_with_timeout "tech_yt_script"  C:/Code_Local/1_Daily_Skill/tech_yt_script/run.sh
run_with_timeout "tech_blog"       C:/Code_Local/1_Daily_Skill/tech_blog/run.sh
run_with_timeout "todo"      C:/Code_Local/1_Daily_Code/todo/run.sh
run_with_timeout "compile"   C:/Code_Local/1_Daily_Skill/compile_day/compile_day.sh
run_with_timeout "wiki_update" C:/Code_Local/1_Daily_Skill/wiki_update/run.sh

# 완료 알림 전에 전체 작업 결과를 디스코드에 전송한다.
notify_summary

run_with_timeout "log_end"   C:/Code_Local/1_Daily_Code/log/run.sh end
