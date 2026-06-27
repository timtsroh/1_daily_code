#!/bin/bash
# launchd 래퍼 — plist_transcripts.sh를 사용자의 기존 tmux 세션에 send-keys로 실행한다.
#
# day.sh와 동일한 패턴. launchd 자식은 macOS Keychain·git push 자격 접근 불가하므로
# 사용자가 띄워둔 tmux 세션의 새 window에서 실행한다.
set -uo pipefail

LOG="/Users/tealeaf/Code_Local/launchd_output.log"
ERR="/Users/tealeaf/Code_Local/launchd_error.log"
TMUX_BIN="/opt/homebrew/bin/tmux"
TMUX_SOCKET="/tmp/tmux-501/default"
SCRIPT="/Users/tealeaf/Code_Local/1_Daily_Code/ec_transcripts/plist_transcripts.sh"
TARGET_SESSION="0"
WINDOW_NAME="ec_transcripts_$(date +%s)"
SENTINEL="/tmp/${WINDOW_NAME}.done"
WAIT_MAX=3600    # 60분 (transcripts.py 짧음 + /ec 6종목 처리 여유)

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

echo "[$(ts)] ec_transcripts_tmux: 기존 세션에 새 window 생성 ($WINDOW_NAME)" >> "$LOG"

"$TMUX_BIN" -S "$TMUX_SOCKET" new-window -t "${TARGET_SESSION}:" -n "$WINDOW_NAME"
"$TMUX_BIN" -S "$TMUX_SOCKET" send-keys -t "${TARGET_SESSION}:${WINDOW_NAME}" \
    "/bin/bash $SCRIPT >> $LOG 2>> $ERR; touch $SENTINEL" Enter

elapsed=0
while [ ! -f "$SENTINEL" ]; do
    sleep 10
    elapsed=$((elapsed + 10))
    if [ $elapsed -ge $WAIT_MAX ]; then
        echo "[$(ts)] FATAL: ec_transcripts.sh ${WAIT_MAX}s 초과, kill ($WINDOW_NAME)" >> "$ERR"
        "$TMUX_BIN" -S "$TMUX_SOCKET" kill-window -t "${TARGET_SESSION}:${WINDOW_NAME}" 2>/dev/null
        exit 1
    fi
done

rm -f "$SENTINEL"
"$TMUX_BIN" -S "$TMUX_SOCKET" kill-window -t "${TARGET_SESSION}:${WINDOW_NAME}" 2>/dev/null
echo "[$(ts)] ec_transcripts_tmux: 완료 ($WINDOW_NAME, ${elapsed}s)" >> "$LOG"
exit 0
