#!/bin/bash

# 매일 05:10 배치 (Claude 사용 한도 리셋 직후).
#   1) 00:05 plist_day.sh에서 Claude 사용 한도로 미실행된 작업(PENDING) 이어서 재시도
#   2) compile (compile_day) — 데일리 노트 통합
#   3) wiki_update — Wiki 갱신 + #wiki Discord 알림
# plist_day.sh와 동일한 run_with_timeout 패턴. 단, 여기서는 한도 재시도 큐를 다시 쌓지 않는다.

TIMEOUT=1800  # 30분
LOG="/Users/tealeaf/Code_Local/launchd_output.log"
PENDING="/tmp/claude_limit_pending.txt"

TASK_NAMES=()
TASK_RESULTS=()

run_with_timeout() {
    local name="$1"
    shift
    local tasklog="/tmp/morningtask_current.log"
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
    if grep -iqE 'usage limit|limit reached|limit will reset' "$tasklog"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] LIMIT: $name (05:10에도 Claude 한도 — 재시도 불가)" >> "$LOG"
        TASK_RESULTS+=("limit")
    elif [ $exit_code -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] ERROR: $name (실패, exit=$exit_code)" >> "$LOG"
        TASK_RESULTS+=("fail")
    else
        TASK_RESULTS+=("ok")
    fi
    return 0
}

# PENDING에 기록된 작업명 → 실제 실행 스크립트 매핑 (Claude를 쓰는 작업만 대상)
resolve_script() {
    case "$1" in
        nrd)            echo "/Users/tealeaf/Code_Local/1_Daily_Skill/nrd/run.sh" ;;
        tech_yt_script) echo "/Users/tealeaf/Code_Local/1_Daily_Skill/tech_yt_script/run.sh" ;;
        tech_blog)      echo "/Users/tealeaf/Code_Local/1_Daily_Skill/tech_blog/run.sh" ;;
        dart_shiporder) echo "/Users/tealeaf/Code_Local/1_Daily_Skill/dart_shiporder/run.sh" ;;
        ec_transcripts) echo "/Users/tealeaf/Code_Local/1_Daily_Code/ec_transcripts/plist_transcripts.sh" ;;
        *) echo "" ;;
    esac
}

notify_summary() {
    local lines=""
    local nl=$'\n'
    local i
    for i in "${!TASK_NAMES[@]}"; do
        local name="${TASK_NAMES[$i]}"
        local result="${TASK_RESULTS[$i]}"
        case "$result" in
            ok)      lines="${lines}${nl}- ✅ ${name}" ;;
            fail)    lines="${lines}${nl}- ❌ ${name}" ;;
            timeout) lines="${lines}${nl}- ⏰ ${name} (timeout ${TIMEOUT}s)" ;;
            limit)   lines="${lines}${nl}- 🚫 ${name} (Claude 한도)" ;;
        esac
    done
    [ -z "$lines" ] && lines="${nl}- (catch-up 대상 없음, compile/wiki만 수행)"
    local msg="🌅 plist_morning.sh 작업 결과 (05:10)${lines}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] morning 작업 결과 디스코드 전송" >> "$LOG"
    /usr/local/bin/python3 /Users/tealeaf/.claude/skills/log/scripts/log.py discord "$msg" >> "$LOG" 2>&1 || true
}

# 1) 00:05 배치에서 Claude 한도로 미실행된 작업 재시도
if [ -s "$PENDING" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] === morning catch-up 시작 ($(wc -l < "$PENDING" | tr -d ' ')건) ===" >> "$LOG"
    while IFS= read -r task; do
        [ -z "$task" ] && continue
        script="$(resolve_script "$task")"
        if [ -n "$script" ]; then
            run_with_timeout "catchup:$task" "$script"
        else
            echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] catch-up 스크립트 매핑 없음: $task (스킵)" >> "$LOG"
        fi
    done < "$PENDING"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] morning catch-up 대상 없음" >> "$LOG"
fi

# 2) compile_day — 데일리 노트 통합 (catch-up으로 수집분 반영 후)
run_with_timeout "compile" /Users/tealeaf/Code_Local/1_Daily_Skill/compile_day/compile_day.sh

# 3) wiki_update — Wiki 갱신
run_with_timeout "wiki_update" /Users/tealeaf/Code_Local/1_Daily_Skill/wiki_update/run.sh

notify_summary

# 처리 완료 → PENDING 비우기
: > "$PENDING"
