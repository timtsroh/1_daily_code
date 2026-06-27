# 일일 자동화 — 로컬 코드 + plist 오케스트레이터

매일/매주 자동 실행되는 피드 수집 파이프라인. Mac mini는 `sleep 0`(잠자기 비활성, 항상 켜짐)이라 별도 wake 없이 `~/Library/LaunchAgents/com.tealeaf.{day,morning,saturday}.plist`가 이 폴더의 `plist_*.sh`를 실행한다. Claude 스킬 wrapper는 별도 `~/Code_Local/1_Daily_Skill/`에 분리되어 있다.

스케줄: **day=매일 00:05**, **morning=매일 05:10**(Claude 한도 리셋 직후 — catch-up + compile + wiki), **saturday=매주 토 05:00**.

이 폴더는 `github.com/timtsroh/1_daily_code` 레포로 관리된다.

## 폴더 구조

```
1_Daily_Code/
├── plist_day_tmux.sh      # com.tealeaf.day.plist(00:05) 진입점 — tmux 경유 (keychain 접근용)
├── plist_day.sh           # 일일 오케스트레이터 (각 작업의 run.sh 순차 호출 + Claude 한도 감지 → PENDING)
├── plist_morning_tmux.sh  # com.tealeaf.morning.plist(05:10) 진입점 — tmux 경유
├── plist_morning.sh       # 05:10 오케스트레이터 (PENDING catch-up + compile_day + wiki_update)
├── plist_week.sh          # com.tealeaf.saturday.plist 진입점 (move + /compile_week)
├── WP/                    # 옛 버전 백업 (TR_v{N}_{YYMMDD}.sh)
│
├── 전종현/                # main.py (Telethon)
├── 김봉수/                # main.py (Playwright)
├── 노정석/                # main.py (Playwright)
├── 최광식/                # main.py (Telethon)
├── 엄민용/                # main.py (Telethon)
├── todo/                  # fetch_feed.py + write_note.py + extract_meta.py
├── tech_yt_listing/       # main.py (Google Sheets yt2 시트 갱신)
├── log/run.sh             # → ~/.claude/skills/log/scripts/log.py
└── move/move.sh           # 02 Daily/1 inbox/ 2일 이상 경과 노트 → A2 Archive/1 moved/ (주간)

~/Code_Local/1_Daily_Skill/   # Claude 스킬 wrapper (claude -p "/<skill>")
├── nrd/run.sh
├── tech_yt_script/run.sh
├── tech_blog/run.sh
├── compile_day/compile_day.sh
├── wiki_update/run.sh
└── dart_shiporder/run.sh   # claude -p "/dart_shiporder <이번달>" — DART 수주공시 → 구글시트 수주2
```

## launchd plist 위치

| plist | 위치 | 타입 |
|-------|------|------|
| `com.tealeaf.pmset` | `/Library/LaunchDaemons/` | Daemon (root) — sudo pmset 필요 |
| `com.tealeaf.day` | `~/Library/LaunchAgents/` | Agent — 매일 **00:05** `plist_day_tmux.sh` 실행 |
| `com.tealeaf.morning` | `~/Library/LaunchAgents/` | Agent — 매일 **05:10** `plist_morning_tmux.sh` 실행 (catch-up + compile + wiki) |
| `com.tealeaf.saturday` | `~/Library/LaunchAgents/` | Agent — 매주 토 05:00 `plist_week.sh` 실행 |
| ~~`com.tealeaf.ec_transcripts`~~ | `~/Library/LaunchAgents/*.disabled` | 비활성 — 구 17:00 ec, `plist_day.sh` #11로 통합 |

## plist 수정 시 반영 절차

plist를 수정한 후에는 반드시 reload해야 반영된다:

```bash
# LaunchAgent (day / saturday)
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.tealeaf.day.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.tealeaf.day.plist

# LaunchDaemon (pmset) — sudo 필요
sudo launchctl bootout system /Library/LaunchDaemons/com.tealeaf.pmset.plist
sudo launchctl bootstrap system /Library/LaunchDaemons/com.tealeaf.pmset.plist
```

## 스크립트 컨벤션

- **버전 백업**: 현재 파일 수정 전 `파일명_v{N}_{YYMM 또는 YYMMDD}.sh`로 복사
- **run.sh 패턴**: `set -euo pipefail`, 타임스탬프 로그, Claude CLI(스킬) 또는 Python(로컬) 호출
- **실행 순서**: `plist_day.sh` 내 순서가 곧 의존성 순서 — `log_end`는 반드시 마지막
- **로그 확인**:
  - 전체 stdout: `~/Code_Local/launchd_output.log`
  - 전체 stderr: `~/Code_Local/launchd_error.log`
  - 작업별: `1_Daily_Code/<name>/logs/` 또는 `~/Code_Local/1_Daily_Skill/<name>/logs/`

## 새 작업 추가 시

먼저 분류 결정:
- 로컬 Python/bash 직접 실행 → `1_Daily_Code/<name>/`
- Claude 스킬 호출(`claude -p "/<skill>"`) → `1_Daily_Skill/<name>/`

이후 단계:
1. `<폴더>/run.sh` 생성 (`chmod +x`)
2. `<폴더>/logs/` 디렉토리 생성
3. `plist_day.sh`에 `run_with_timeout "<name>" <절대경로>/run.sh` 라인 추가 (`log_end` 위)
4. Claude 스킬이면 `~/.claude/skills/<skill>/SKILL.md` 작성
