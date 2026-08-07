#!/bin/bash
# launchd 래퍼 — plist_morning.sh를 사용자의 기존 tmux 세션에 send-keys로 실행한다.
# (plist_day_tmux.sh와 동일 패턴. keychain 접근을 위해 기존 인증된 tmux 세션 사용.)

set -uo pipefail

LOG="C:/Code_Local/launchd_output.log"
ERR="C:/Code_Local/launchd_error.log"
TMUX_BIN="/opt/homebrew/bin/tmux"
TMUX_SOCKET="/tmp/tmux-501/default"
MORNING_SH="C:/Code_Local/1_Daily_Code/plist_morning.sh"
TARGET_SESSION="0"
WINDOW_NAME="morning_$(date +%s)"
SENTINEL="/tmp/${WINDOW_NAME}.done"
WAIT_MAX=9000    # 150분 (catch-up 최대 5작업 + compile + wiki, 각 30분 timeout 여유)

ts() { date '+%Y-%m-%d %H:%M:%S KST'; }

if [ ! -x "$TMUX_BIN" ]; then
    echo "[$(ts)] FATAL: tmux 바이너리 없음 ($TMUX_BIN)" >> "$ERR"
    exit 1
fi

if [ ! -S "$TMUX_SOCKET" ]; then
    echo "[$(ts)] FATAL: tmux socket 없음 ($TMUX_SOCKET) — 사용자 tmux 서버가 떠있지 않음" >> "$ERR"
    exit 1
fi

if ! "$TMUX_BIN" -S "$TMUX_SOCKET" has-session -t "$TARGET_SESSION" 2>/dev/null; then
    echo "[$(ts)] FATAL: tmux 세션 '$TARGET_SESSION' 없음" >> "$ERR"
    exit 1
fi

echo "[$(ts)] morning_tmux: 기존 세션에 새 window 생성 ($WINDOW_NAME)" >> "$LOG"

"$TMUX_BIN" -S "$TMUX_SOCKET" new-window -t "${TARGET_SESSION}:" -n "$WINDOW_NAME"
"$TMUX_BIN" -S "$TMUX_SOCKET" send-keys -t "${TARGET_SESSION}:${WINDOW_NAME}" \
    "/bin/bash $MORNING_SH >> $LOG 2>> $ERR; touch $SENTINEL" Enter

elapsed=0
while [ ! -f "$SENTINEL" ]; do
    sleep 10
    elapsed=$((elapsed + 10))
    if [ $elapsed -ge $WAIT_MAX ]; then
        echo "[$(ts)] FATAL: plist_morning.sh ${WAIT_MAX}s 초과, kill ($WINDOW_NAME)" >> "$ERR"
        "$TMUX_BIN" -S "$TMUX_SOCKET" kill-window -t "${TARGET_SESSION}:${WINDOW_NAME}" 2>/dev/null
        exit 1
    fi
done

rm -f "$SENTINEL"
"$TMUX_BIN" -S "$TMUX_SOCKET" kill-window -t "${TARGET_SESSION}:${WINDOW_NAME}" 2>/dev/null
echo "[$(ts)] morning_tmux: 완료 ($WINDOW_NAME, ${elapsed}s)" >> "$LOG"
exit 0
