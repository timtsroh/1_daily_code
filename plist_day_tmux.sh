#!/bin/bash
# launchd 래퍼 — day.sh를 사용자의 기존 tmux 세션에 send-keys로 실행한다.
#
# 배경: launchd 자식 프로세스는 macOS Keychain 접근이 불가하고,
# tmux new-session -d도 wake 직후 새 shell을 fork하므로 같은 문제가 발생한다.
# 기존 활성 세션의 새 window에 send-keys로 명령하면, sleep 전부터
# 인증된 shell 환경을 그대로 사용하므로 keychain 접근이 가능하다.

set -uo pipefail

LOG="/Users/tealeaf/Code_Local/launchd_output.log"
ERR="/Users/tealeaf/Code_Local/launchd_error.log"
TMUX_BIN="/opt/homebrew/bin/tmux"
TMUX_SOCKET="/tmp/tmux-501/default"
DAY_SH="/Users/tealeaf/Code_Local/1_Daily_Code/plist_day.sh"
TARGET_SESSION="0"
WINDOW_NAME="day_$(date +%s)"
SENTINEL="/tmp/${WINDOW_NAME}.done"
WAIT_MAX=5400    # 90분 (개별 스킬 timeout 5분 × 13작업 = 최대 65분 + 여유)

ts() { date '+%Y-%m-%d %H:%M:%S KST'; }

if [ ! -x "$TMUX_BIN" ]; then
    echo "[$(ts)] FATAL: tmux 바이너리 없음 ($TMUX_BIN)" >> "$ERR"
    exit 1
fi

if [ ! -S "$TMUX_SOCKET" ]; then
    echo "[$(ts)] FATAL: tmux socket 없음 ($TMUX_SOCKET) — 사용자 tmux 서버가 떠있지 않음" >> "$ERR"
    exit 1
fi

# 기존 세션 존재 확인
if ! "$TMUX_BIN" -S "$TMUX_SOCKET" has-session -t "$TARGET_SESSION" 2>/dev/null; then
    echo "[$(ts)] FATAL: tmux 세션 '$TARGET_SESSION' 없음" >> "$ERR"
    exit 1
fi

echo "[$(ts)] day_tmux: 기존 세션에 새 window 생성 ($WINDOW_NAME)" >> "$LOG"

# 기존 세션에 새 window를 만들고 send-keys로 명령 전송
"$TMUX_BIN" -S "$TMUX_SOCKET" new-window -t "${TARGET_SESSION}:" -n "$WINDOW_NAME"
"$TMUX_BIN" -S "$TMUX_SOCKET" send-keys -t "${TARGET_SESSION}:${WINDOW_NAME}" \
    "/bin/bash $DAY_SH >> $LOG 2>> $ERR; touch $SENTINEL" Enter

# day.sh 종료까지 polling 대기
elapsed=0
while [ ! -f "$SENTINEL" ]; do
    sleep 10
    elapsed=$((elapsed + 10))
    if [ $elapsed -ge $WAIT_MAX ]; then
        echo "[$(ts)] FATAL: day.sh ${WAIT_MAX}s 초과, kill ($WINDOW_NAME)" >> "$ERR"
        "$TMUX_BIN" -S "$TMUX_SOCKET" kill-window -t "${TARGET_SESSION}:${WINDOW_NAME}" 2>/dev/null
        exit 1
    fi
done

rm -f "$SENTINEL"
# 완료 후 window 정리
"$TMUX_BIN" -S "$TMUX_SOCKET" kill-window -t "${TARGET_SESSION}:${WINDOW_NAME}" 2>/dev/null
echo "[$(ts)] day_tmux: 완료 ($WINDOW_NAME, ${elapsed}s)" >> "$LOG"
exit 0
