# plist_day.sh — Product Requirements Document

매일 1회 자동 실행되는 일일 데이터 수집·정리 파이프라인의 메인 오케스트레이터.

---

## 1. 목적

여러 외부 소스(텔레그램·페이스북·네이버 금융·YouTube·VC 블로그 등)에서 어제(KST) 자료를 일괄 수집하고, 결과를 Obsidian 데일리 노트(`daily_YYMMDD.md`)로 통합한다. 사용자는 매일 아침 기상 시점에 "어제 무슨 일이 있었는지" 한 노트에서 확인할 수 있다.

## 2. 트리거 / 진입점

| 항목 | 값 |
|------|-----|
| 시각 | 매일 05:00 KST |
| LaunchAgent | `~/Library/LaunchAgents/com.tealeaf.day.plist` |
| 진입 흐름 | launchd → `plist_day_tmux.sh` (tmux 경유, keychain 접근용) → `plist_day.sh` |
| 위치 | `/Users/tealeaf/Code_Local/1_Daily_Code/plist_day.sh` |

`plist_day_tmux.sh`가 별도 wrapper인 이유: launchd 자식 프로세스는 macOS Keychain 접근이 불가하므로, 이미 인증된 사용자 tmux 세션 `0`의 새 window로 send-keys 한다. plist_day.sh는 그 안에서 실행된다.

## 3. 작업 순서 (14개)

각 작업은 두 가지 차원에서 분류된다:
- **분류** (콘텐츠 도메인): 시스템 / 정보 수집 (SNS/SNS) / 투자 리포트 / Tech·미디어 / 개인 관리 / 통합 및 갱신
- **유형** (실행 방식):
  - **Code** — `1_Daily_Code/<name>/run.sh` (로컬 Python/bash 직접 실행, Claude CLI 호출 없음)
  - **Skill** — `1_Daily_Skill/<name>/run.sh` (`claude -p "/<skill>"`로 Claude 스킬 호출)

| 분류 | # | 작업 | 유형 | 실행방법 | 내용 |
|------|---|------|------|---------|------|
| 시스템 | 1 | log_start | Code | `1_Daily_Code/log/run.sh start` | Google Sheets + Discord 시작 로그 |
| 정보 수집 (SNS/SNS) | 2 | 전종현 | Code | `1_Daily_Code/전종현/run.sh` | 텔레그램 채널(@chunjonghyun) 피드 수집 (Telethon) |
| 정보 수집 (SNS/SNS) | 3 | 김봉수 | Code | `1_Daily_Code/김봉수/run.sh` | 페이스북 프로필(bongsoo2) 피드 수집 (Playwright) |
| 정보 수집 (SNS/SNS) | 4 | 노정석 | Code | `1_Daily_Code/노정석/run.sh` | 페이스북 프로필(chester.roh) 피드 수집 (Playwright) |
| 투자 리포트 | 5 | nrd | Skill | `1_Daily_Skill/nrd/run.sh` → `/nrd` | 네이버 금융 산업분석 리포트 다운로드 + Obsidian 노트 |
| 투자 리포트 | 6 | 최광식 | Code | `1_Daily_Code/최광식/run.sh` | 다올증권 텔레그램(t.me/HI_GS) PDF 리포트 수집 → Drive |
| 투자 리포트 | 7 | 엄민용 | Code | `1_Daily_Code/엄민용/run.sh` | 신한투자 텔레그램(t.me/bio_shinhan) PDF 리포트 수집 → Drive |
| Tech/미디어 | 8 | tech_yt_listing | Code | `1_Daily_Code/tech_yt_listing/run.sh` | YouTube 채널 신규 영상 → Google Sheets `yt2` 시트 |
| Tech/미디어 | 9 | tech_yt_script | Skill | `1_Daily_Skill/tech_yt_script/run.sh` → `/tech_yt_script` | yt2 미처리 영상 → `/yt` 스킬로 자막 추출 → Obsidian 노트 |
| Tech/미디어 | 10 | tech_blog | Skill | `1_Daily_Skill/tech_blog/run.sh` → `/tech_blog` | VC/Tech 블로그 신규 글 → 한국어 3불릿 요약 + 전문 번역 |
| 개인 관리 | 11 | todo | Code | `1_Daily_Code/todo/run.sh` | 텔레그램 @atomtodo → `/tmp/todo_feed.json` + `02 Daily/1 inbox/todo_YYYYMM.md` (월별 누적) |
| 통합 및 갱신 | 12 | compile | Skill | `1_Daily_Skill/compile_day/compile_day.sh` → `/compile_day` | #1~11 결과를 `daily_YYMMDD.md`로 통합 임베드 |
| 통합 및 갱신 | 13 | wiki_update | Skill | `1_Daily_Skill/wiki_update/run.sh` → `/wiki_update` | 신규 Raw Sources → `A1 Wiki/` 갱신 + #wiki Discord 알림 |
| 시스템 | 14 | log_end | Code | `1_Daily_Code/log/run.sh end` | 작업 결과 요약 → #routine Discord + Google Sheets 종료 로그 |

## 4. 동작 원리

### 4.1 순차 실행
- 모든 작업은 위 순서대로 **순차적**으로 실행된다 (병렬 X).
- 사유: 일부 작업이 같은 외부 세션 파일 공유 (Telethon `~/.claude/tg_session`, Playwright `~/.claude/fb_session.json`). 동시 호출 시 세션 충돌 위험.

### 4.2 작업별 타임아웃
- 함수 `run_with_timeout()`이 각 작업을 30분(`TIMEOUT=1800`) 한도로 감싼다.
- 한도 초과 또는 비정상 종료 시: 해당 작업만 SKIP, 다음 작업 정상 진행.
- 결과는 배열 `TASK_NAMES[]` / `TASK_RESULTS[]`에 누적 (값: `ok` / `fail` / `timeout`).

### 4.3 외부 wrapper 타임아웃
- `plist_day_tmux.sh`의 `WAIT_MAX=5400` (90분)으로 전체 실행을 polling 대기. 초과 시 tmux window 강제 kill.

### 4.4 결과 알림
- `log_end` 직전에 `notify_summary()`가 모든 작업의 ✅/❌/⏰ 결과를 `📋 plist_day.sh 작업 결과` 메시지로 #routine Discord에 일괄 전송.
- log_start / log_end 자체는 요약에서 제외.

## 5. 의존성 흐름

```
[1] log_start                    실행 시작 기록
     │
[2-7] 피드/리포트 수집           → 02 Daily/1 inbox/, 03 Sources/3 큐레이션/, Drive 0 Inbox
     ├─ 전종현 (텔레그램)
     ├─ 김봉수 (페이스북)
     ├─ 노정석 (페이스북)
     ├─ nrd (네이버 금융)
     ├─ 최광식 (텔레그램 PDF)
     └─ 엄민용 (텔레그램 PDF)
     │
[8-10] 테크 콘텐츠 수집
     ├─ tech_yt_listing → yt2 시트
     ├─ tech_yt_script  → 03 Sources/5 Youtube/
     └─ tech_blog       → 03 Sources/6 Tech Blog/
     │
[11] todo (@atomtodo)            → 02 Daily/1 inbox/todo_YYYYMM.md (월별 누적, 일별 `# YYYY-MM-DD` 섹션)
     │
[12] compile (compile_day)       → 02 Daily/1 inbox/daily_YYMMDD.md
     │   #1~11 결과를 ![[note#heading]] 형태로 임베드 통합
     │
[13] wiki_update                 → A1 Wiki/ 페이지 갱신 (entities/concepts)
     │   #1~12에서 생긴 Raw Sources만 대상
     │
[14] log_end                     실행 종료 + 결과 요약 Discord
```

**불변 제약**:
- compile(#12)는 모든 수집 작업 이후 실행 — todo 노트가 `# 3. todo` 섹션에 임베드 가능해야 함
- wiki_update(#13)는 compile 이후 — wiki 페이지가 데일리 노트의 임베드를 참조
- log_end(#14)는 반드시 마지막 — 다른 작업 결과를 요약해야 함

## 6. 유형 결정 기준 (Code vs Skill)

신규 작업 추가 시 유형 결정:

| 조건 | 유형 | 폴더 |
|------|------|------|
| Python/bash 스크립트 직접 실행, LLM 추론 불필요 | Code | `~/Code_Local/1_Daily_Code/<name>/` |
| `claude -p "/<skill>"` 호출, LLM 추론 필요 | Skill | `~/Code_Local/1_Daily_Skill/<name>/` |

분류(콘텐츠 도메인)는 별개 차원이며 §3 표 참조.

## 7. 새 작업 추가 절차

1. 분류(콘텐츠 도메인) + 유형(Code/Skill) 결정.
2. `<폴더>/run.sh` 생성 (`chmod +x`).
3. `<폴더>/logs/` 디렉토리 생성.
4. `plist_day.sh`에 `run_with_timeout "<name>" <절대경로>/run.sh` 라인 추가 (의존성 흐름에 맞는 위치, log_end 위).
5. Claude 스킬이면 `~/.claude/skills/<skill>/SKILL.md` 작성.
6. plist 자체는 변경 불요 (reload 필요 없음).
7. `~/.claude/routine.md`와 본 PRD 갱신.

## 8. 알림 채널

| Discord 채널 | 메시지 | 발신 시점 |
|------|------|----------|
| `#routine` | 🟡 plist_day.sh 작업 시작 — {시각} | log_start |
| `#routine` | 📋 plist_day.sh 작업 결과 + ✅/❌/⏰ 목록 | notify_summary (log_end 직전) |
| `#routine` | ✅ plist_day.sh 작업 완료 — {시각} | log_end |
| `#routine` | ⚠️ plist_day.sh 일부 작업 실패 — {시각} + 상세 | log skill (실패 발생 시) |
| `#wiki` | wiki_update 결과 (갱신 페이지 + 핵심 인사이트) | wiki_update 작업 내부에서 직접 발송 |

## 9. 로그 위치

| 종류 | 경로 |
|------|------|
| 전체 stdout | `~/Code_Local/launchd_output.log` |
| 전체 stderr | `~/Code_Local/launchd_error.log` |
| 작업별 (Code) | `~/Code_Local/1_Daily_Code/<name>/logs/` |
| 작업별 (Skill) | `~/Code_Local/1_Daily_Skill/<name>/logs/` |

## 10. 실패 모드 / 복구

### 10.1 단일 작업 실패
- 다른 작업 진행에 영향 없음 (timeout 격리).
- 데일리 노트(#12)는 실패한 작업을 `no update`로 표기.

### 10.2 백필 (수집 누락 복구)

특정 날짜 데이터가 누락된 경우:

| 작업 | 백필 방법 |
|------|----------|
| 김봉수 | `python3 main.py --date YYYY-MM-DD` (네이티브 지원) |
| todo | `bash run.sh YYMMDD` (네이티브 지원) |
| 최광식, 엄민용 | `last_run.log`를 누락 시작일 -1로 설정 → `run.sh` 실행 → `last_run` 자동 오늘로 갱신 |
| 전종현, 노정석 | main.py가 `datetime.now()` hardcoded. 단, `fetch_yesterday(target)` / `fetch_yesterday_posts(date)` 함수는 date 인자 받으므로 `python3 -c`로 직접 호출 |
| nrd, tech_yt_*, tech_blog | Claude 스킬, 수동 실행 시 `claude -p "/<skill>"` 호출 |

### 10.3 plist_day.sh 자체 실패
- 90분 외부 wrapper timeout 시 `plist_day_tmux.sh`가 tmux window kill.
- log_end가 실행되지 못하면 #routine 종료 알림 누락 → 사용자 인지 가능.

## 11. 외부 의존성

| 의존 | 용도 |
|------|------|
| Telegram API (Telethon) | 전종현, 최광식, 엄민용, todo |
| Facebook (Playwright) | 김봉수, 노정석 |
| 네이버 금융 (HTTP) | nrd |
| Google Sheets API | tech_yt_listing, tech_yt_script, log |
| Google Drive (로컬 마운트) | 최광식, 엄민용 (PDF 저장) |
| YouTube Transcript API | tech_yt_script (`/yt` 스킬 내부) |
| Discord Webhook | log, wiki_update 알림 |
| Claude Code CLI | nrd, tech_yt_script, tech_blog, compile, wiki_update |

## 12. 변경 이력 (최근)

- **2026-05-05** — `1_Daily/` → `1_Daily_Code/` 리팩토링 후 6개 run.sh 내부 hardcoded 경로 갱신 누락으로 5/4·5/5 5am 실행 시 6개 작업 실패. sed 일괄 치환으로 수정.
- **2026-05-05** — `/digest_day` → `/compile_day`, `/digest_week` → `/compile_week` 스킬명 변경. plist_day.sh 작업 #12 이름도 `digest` → `compile`로 동기화. PRD.md → PRD_day.md로 rename, PRD_week.md 신설.
- **2026-05-04** — todo를 `digest_day` 0단계 → `plist_day.sh` 독립 작업(#11)으로 격상. 책임 분리 (digest_day는 통합만, todo 수집은 plist_day.sh가 직접).
- **2026-05-03** — `~/Code_Local/GitHub/launchd/` 폴더의 모든 컨텐츠를 `1_Daily_Code/`로 이동. 분류별 폴더 구조 정착 (`1_Daily_Code/` = 로컬 코드, `1_Daily_Skill/` = Claude 스킬 wrapper). GitHub 레포 `launchd` → `1_daily_code`로 rename.
- **2026-04-25** — Light.sh, TR.sh 등 레거시 스크립트 정리.

## 관련 문서

- `~/.claude/routine.md` — 운영 레퍼런스 (작업 표 + 의존성 흐름)
- `~/.claude/CLAUDE.md` — 프로젝트 글로벌 컨벤션 (디렉토리 매핑, 숫자 표기 등)
- `1_Daily_Code/CLAUDE.md` — 폴더 구조 + 새 작업 추가 절차 + plist reload 명령
