# plist_week.sh — Product Requirements Document

매주 1회 자동 실행되는 주간 정리·요약 파이프라인. inbox 정리 + 위클리 노트 생성.

---

## 1. 목적

매일 쌓이는 데일리 노트(`daily_*.md`) · 뉴스 노트(`news_*.md`) · todo 노트(`todo_*.md`)가 `02 Daily/1 inbox/`에 누적되지 않도록 한 주에 한 번 오래된 파일을 `A2 Archive/1 moved/`로 정리하고, 같은 시점에 그 한 주(토~금) 동안 새로 들어온 포스팅·작업을 한 노트(`weekly_YYMMDD.md`)에 임베드 형식으로 모아 둔다.

`plist_day.sh`(매일)가 "어제"를 정리한다면, `plist_week.sh`(매주 토)는 "지난 주 전체"를 회고·아카이브한다.

## 2. 트리거 / 진입점

| 항목 | 값 |
|------|-----|
| 시각 | 매주 토요일 05:00 KST (`Weekday=6`) |
| LaunchAgent | `~/Library/LaunchAgents/com.tealeaf.saturday.plist` |
| 진입 흐름 | launchd → `plist_week.sh` 직접 실행 |
| 위치 | `/Users/tealeaf/Code_Local/1_Daily_Code/plist_week.sh` |

`plist_day.sh`와 달리 tmux wrapper가 없다 — keychain 접근이 필요한 외부 인증(Telegram, Facebook 등)을 호출하지 않으므로 launchd 자식 프로세스에서 직접 실행해도 무방하다.

## 3. 작업 순서 (2개)

각 작업은 두 가지 차원에서 분류된다:
- **분류** (콘텐츠 도메인): 정리 / 통합 및 갱신
- **유형** (실행 방식):
  - **Code** — `1_Daily_Code/<name>/<script>.sh` (로컬 bash 직접 실행)
  - **Skill** — `claude -p "/<skill>"` (Claude 스킬 호출)

| 분류 | # | 작업 | 유형 | 실행방법 | 내용 |
|------|---|------|------|---------|------|
| 정리 | 1 | move | Code | `1_Daily_Code/move/move.sh` | `02 Daily/1 inbox/`의 2일 이상 지난 `daily_*.md`/`news_*.md`/`todo_*.md` → `A2 Archive/1 moved/` 이동 |
| 통합 및 갱신 | 2 | compile_week | Skill | `claude --dangerously-skip-permissions -p "/compile_week"` | 이번 주(토~금) 신규 포스팅·작업 → `02 Daily/2 weekly/weekly_YYMMDD.md` 위클리 노트 생성 |

## 4. 동작 원리

### 4.1 순차 실행
- 두 작업은 **순차적**으로 실행된다 (병렬 X).
- `set -euo pipefail` — move 실패 시 compile_week도 실행되지 않음.

### 4.2 타임아웃 / 실패 격리
- `plist_week.sh`는 `plist_day.sh`와 달리 작업별 wrapper(`run_with_timeout`)가 없다. 작업 수가 적고 외부 인증·세션 충돌 위험이 없어 단순 순차 실행으로 충분하다.
- launchd 자체 프로세스 한도에만 의존.

### 4.3 결과 알림
- 별도 Discord 알림 없음. 결과는 `~/Code_Local/launchd_output.log` + `1_Daily_Code/move/logs/`에 기록된다.
- 향후 필요 시 `notify_summary` 패턴(plist_day.sh)을 가져올 수 있음.

## 5. 작업 상세

### 5.1 move (`move/move.sh`)

`02 Daily/1 inbox/` 안의 일자가 박힌 파일 중 **파일명 YYMMDD 기준 2일 이상 지난** 것을 `A2 Archive/1 moved/`로 이동한다.

| 항목 | 값 |
|------|-----|
| 대상 패턴 | `daily_*.md`, `news_*.md`, `todo_*.md` |
| 일자 추출 | `basename`에서 첫 6자리 숫자 (`grep -oE '[0-9]{6}' | head -1`) |
| 컷오프 | `date -v-2d +%y%m%d` (오늘 -2일, YYMMDD) |
| 비교 | `file_date -lt cutoff` (문자열 정수 비교) |
| 이동 대상 | `$VAULT/A2 Archive/1 moved/` |

**판정 기준이 mtime이 아니라 파일명인 이유**: iCloud 동기화로 mtime이 자주 갱신되어 부정확. 파일명에 박힌 일자(`YYMMDD`)는 노트 생성 시점에 결정되어 변하지 않는다.

**알려진 한계 — todo 월별 파일과의 충돌**:
- `todo_*.md` glob은 신·구 두 가지를 모두 매칭한다:
  - 구: `todo_YYMMDD.md` (예: `todo_260430.md`) — 정상 처리
  - 신: `todo_YYYYMM.md` (예: `todo_202605.md`, 2026-05 누적 노트)
- 후자의 경우 첫 6자리가 `202605`로 추출되어 컷오프(`260503` 등)와 비교 시 `202605 < 260503`이 성립 → **현재 진행 중인 월별 todo 노트가 매주 토요일 archive 폴더로 이동되는 버그**.
- 해결 방안 (보류, 향후 작업): glob에서 `todo_*` 제외하거나, 8자리 prefix(`todo_YYYYMM` ⇄ `todo_YYMMDD`)를 식별해 분기 처리.

### 5.2 compile_week (`/compile_week` 스킬)

매주 토~금 한 주를 단위로 신규 포스팅·신규 작업을 한 노트로 모은다.

| 항목 | 값 |
|------|-----|
| 인자 | 없음 → 이번 주 금요일 / `YYMMDD` → 그 금요일이 속한 주 |
| 주 범위 | 토요일 = 금요일 - 6일 |
| 출력 경로 | `/Users/tealeaf/Obsidian/Sync1/02 Daily/2 weekly/weekly_YYMMDD.md` (금요일 일자) |

**섹션 구조** (compile_week 스킬 내 `templates/weekly_note.md` 고정):

```
# 1. 신규 포스팅
  ## 1) Tech Blog       — 03 Sources/6 Tech Blog/ 파일명 YYMMDD prefix가 주 범위
  ## 2) Youtube         — 03 Sources/5 Youtube/ 파일명 YYMMDD prefix(업로드일)가 주 범위
  ## 3) Earnings Call   — 03 Sources/4 Earnings Call/ frontmatter `date`가 주 범위

# 2. 신규 작업
  ## 1) Youtube         — `영상수집일`이 주 범위 AND 업로드일은 범위 밖
  ## 2) Earnings Call   — `note_created`가 주 범위 AND `date`는 범위 밖
```

**임베드 규칙**: 각 섹션은 `[[note]]` + `![[note#heading]]` 형태로 원본을 참조. heading 패턴은 스킬의 `CLAUDE.md` 참조.

## 6. 의존성 흐름

```
[1] move                         02 Daily/1 inbox/ → A2 Archive/1 moved/
     │                           (compile_week가 archive된 파일을 참조하지 않으므로 순서는 무관, 다만 inbox 정리 후 실행하면 깔끔)
     │
[2] compile_week                 02 Daily/2 weekly/weekly_YYMMDD.md
     │   • Tech Blog 신규
     │   • Youtube 신규/작업
     │   • Earnings Call 신규/작업
```

**불변 제약 없음** — 두 작업은 서로 독립적이며 실패가 다른 작업에 영향을 주지 않는다 (단, `set -euo pipefail`로 인해 move 실패 시 compile_week 미실행). 향후 격리 강화 시 `plist_day.sh`의 `run_with_timeout` 패턴 도입 검토.

## 7. 새 작업 추가 절차

1. 분류 + 유형 결정 (Code or Skill).
2. Code: `<폴더>/<script>.sh`, Skill: `~/.claude/skills/<skill>/SKILL.md` 작성.
3. `plist_week.sh`에 호출 라인 추가 (현재 두 작업 사이 또는 끝에).
4. plist 파일은 변경 불요 (reload 필요 없음).
5. 본 PRD 갱신.

## 8. 알림 채널

| 채널 | 메시지 | 발신 시점 |
|------|------|----------|
| (없음) | — | 현재 Discord 알림 없음 |

향후 plist_day.sh 패턴(`#routine` 시작/종료 알림 + 결과 요약)을 가져올 수 있음.

## 9. 로그 위치

| 종류 | 경로 |
|------|------|
| 전체 stdout | `~/Code_Local/launchd_output.log` |
| 전체 stderr | `~/Code_Local/launchd_error.log` |
| move 작업 | `~/Code_Local/1_Daily_Code/move/logs/` (디렉토리는 `mkdir -p`로 보장됨) |
| compile_week 작업 | Claude CLI 자체 로그 (별도 디렉토리 없음) |

## 10. 실패 모드 / 복구

### 10.1 단일 작업 실패
- `set -euo pipefail` 때문에 move 실패 시 compile_week도 실행되지 않는다 (현재 정책).
- 의도적으로 격리하려면 `set +e` 도입 또는 `run_with_timeout` 패턴 적용 필요.

### 10.2 백필 (수동 실행)

| 작업 | 백필 방법 |
|------|----------|
| move | `bash 1_Daily_Code/move/move.sh` (멱등 — 이미 옮겨진 파일은 무시) |
| compile_week | `claude -p "/compile_week"` (이번 주) 또는 `claude -p "/compile_week 260425"` (특정 금요일) |

### 10.3 plist_week.sh 자체 실패
- launchd `Weekday=6` 트리거 미발화 시 다음 토요일까지 누락 (수동 실행으로 복구).

## 11. 외부 의존성

| 의존 | 용도 |
|------|------|
| Obsidian Vault (`~/Obsidian/Sync1/`) | move (inbox/moved 폴더), compile_week (소스·출력 노트) |
| Claude Code CLI | compile_week 스킬 호출 |
| (외부 API 없음) | Telegram/Facebook 인증 불요 → tmux wrapper 불필요 |

## 12. 변경 이력 (최근)

- **2026-05-05** — `/digest_week` → `/compile_week` 스킬명 변경. PRD_week.md 신설. plist_week.sh 주석 갱신.
- **2026-05-03** — `~/Code_Local/GitHub/launchd/` → `1_Daily_Code/`로 이전. plist_week.sh 경로 갱신.
- **2026-04-25** — Light.sh, TR.sh 등 레거시 스크립트 정리 (move.sh 패턴 정착).

## 관련 문서

- `PRD_day.md` — 일일 오케스트레이터 (plist_day.sh) 명세
- `~/.claude/routine.md` — 운영 레퍼런스 (작업 표 + 의존성 흐름)
- `~/.claude/skills/compile_week/SKILL.md` — compile_week 스킬 정의 (섹션 구조·헤딩 패턴)
- `~/.claude/skills/compile_week/CLAUDE.md` — compile_week 작성 가이드라인
- `1_Daily_Code/CLAUDE.md` — 폴더 구조 + 새 작업 추가 절차 + plist reload 명령
