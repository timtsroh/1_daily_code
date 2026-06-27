#!/bin/bash

# 매일 00:05 배치. 각 작업에 타임아웃 적용 (초 단위). 타임아웃·에러 시 해당 작업만 스킵하고 다음 진행.
TIMEOUT=1800  # 30분
LOG="/Users/tealeaf/Code_Local/launchd_output.log"

# Claude 사용 한도(usage limit)로 미실행된 작업명을 기록 → 05:10 morning 배치(plist_morning.sh)에서 재시도.
PENDING="/tmp/claude_limit_pending.txt"
: > "$PENDING"   # 매 실행 시작 시 초기화

# 작업별 결과를 누적하고, log_end 직전에 전체 요약을 디스코드로 전송.
TASK_NAMES=()
TASK_RESULTS=()

# 각 작업의 출력을 임시 로그로 캡처 → 메인 로그에 합치고, Claude 사용 한도 메시지를 감지한다.
run_with_timeout() {
    local name="$1"
    shift
    local tasklog="/tmp/daytask_current.log"   # 작업은 순차 실행이라 단일 파일 재사용 가능
    : > "$tasklog"
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] === $name ===" >> "$LOG"
    /bin/bash "$@" > "$tasklog" 2>&1 &
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
            cat "$tasklog" >> "$LOG"
            TASK_NAMES+=("$name")
            TASK_RESULTS+=("timeout")
            return 0
        fi
    done
    wait "$pid" 2>/dev/null
    local exit_code=$?
    cat "$tasklog" >> "$LOG"
    TASK_NAMES+=("$name")
    # Claude 사용 한도 메시지 감지 → PENDING 기록 후 'limit' 표기 (05:10에 재시도)
    if grep -iqE 'usage limit|limit reached|limit will reset' "$tasklog"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] LIMIT: $name (Claude 사용 한도 → 05:10 재시도 대기)" >> "$LOG"
        echo "$name" >> "$PENDING"
        TASK_RESULTS+=("limit")
    elif [ $exit_code -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] ERROR: $name (실패, exit=$exit_code)" >> "$LOG"
        TASK_RESULTS+=("fail")
    else
        TASK_RESULTS+=("ok")
    fi
    return 0  # 에러여도 다음 작업 진행
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
            limit)   lines="${lines}${nl}- 🚫 ${name} (Claude 한도 → 05:10 재시도)" ;;
        esac
    done
    local msg="📋 plist_day.sh 작업 결과 (00:05)${lines}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 작업 결과 디스코드 전송" >> "$LOG"
    /usr/local/bin/python3 /Users/tealeaf/.claude/skills/log/scripts/log.py discord "$msg" >> "$LOG" 2>&1 || true
}

run_with_timeout "log_start" /Users/tealeaf/Code_Local/1_Daily_Code/log/run.sh start
run_with_timeout "전종현"     /Users/tealeaf/Code_Local/1_Daily_Code/전종현/run.sh
run_with_timeout "김봉수"     /Users/tealeaf/Code_Local/1_Daily_Code/김봉수/run.sh
run_with_timeout "노정석"     /Users/tealeaf/Code_Local/1_Daily_Code/노정석/run.sh
run_with_timeout "nrd"       /Users/tealeaf/Code_Local/1_Daily_Skill/nrd/run.sh
run_with_timeout "최광식"     /Users/tealeaf/Code_Local/1_Daily_Code/최광식/run.sh
run_with_timeout "엄민용"     /Users/tealeaf/Code_Local/1_Daily_Code/엄민용/run.sh
run_with_timeout "tech_yt_listing" /Users/tealeaf/Code_Local/1_Daily_Code/tech_yt_listing/run.sh
run_with_timeout "tech_yt_script"  /Users/tealeaf/Code_Local/1_Daily_Skill/tech_yt_script/run.sh
run_with_timeout "tech_blog"       /Users/tealeaf/Code_Local/1_Daily_Skill/tech_blog/run.sh
run_with_timeout "ec_transcripts"  /Users/tealeaf/Code_Local/1_Daily_Code/ec_transcripts/plist_transcripts.sh
run_with_timeout "todo"      /Users/tealeaf/Code_Local/1_Daily_Code/todo/run.sh
run_with_timeout "dart_shiporder" /Users/tealeaf/Code_Local/1_Daily_Skill/dart_shiporder/run.sh

# 완료 알림 전에 전체 작업 결과를 디스코드에 전송한다.
# (compile_day · wiki_update 는 05:10 plist_morning.sh 로 이동)
notify_summary

run_with_timeout "log_end"   /Users/tealeaf/Code_Local/1_Daily_Code/log/run.sh end
