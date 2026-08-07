# 전종현 — Telegram 채널 자동 수집 (pure Python)

텔레그램 채널 `chunjonghyun`(전종현)의 **어제(KST) 날짜** 메시지를 수집하여
Obsidian 월별 노트에 시간순으로 병합 저장한다. Claude CLI 의존성 없는 순수
Python 스탠드얼론 프로젝트.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `main.py` | 엔트리포인트. 수집 → 저장 → 요약 출력 |
| `fetch_feed.py` | Telethon으로 어제자 메시지 수집, entity → 마크다운 변환 |
| `write_note.py` | Obsidian 월별 노트 생성/병합 (중복 제거) |
| `reauth.py` | Telethon 세션 재인증 (최초 1회 전화번호 인증) |
| `requirements.txt` | 의존성 (`telethon`) |

## 설치

```bash
cd C:/Code_Local/1_Daily_Code/전종현
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 실행

```bash
python main.py
```

인자 없음. 어제 날짜(KST = UTC+9)는 자동 계산.

### 출력 예시

```
[INFO] 날짜(KST): 2026-04-19
[INFO] 수집 메시지: 7건
[UPDATED] C:/Obsidian/Sync1/03 Sources/3 큐레이션/전종현_2604.md
[INFO] 추가: 7건, 중복 건너뜀: 0건
[PREVIEW]
  08:12  …
  ...
```

- exit 0: 정상 (수집 0건 포함)
- exit 1: 하드 에러 (Telethon 인증 실패, 네트워크, 파일 쓰기 실패 등)

## 입출력

| 항목 | 값 |
|------|-----|
| 수집 채널 | `chunjonghyun` (https://t.me/chunjonghyun) |
| 수집 범위 | 어제 00:00~23:59 KST (최근 200건에서 필터) |
| 세션 파일 | `C:/Users/DELL/.claude/tg_session.session` (변경 금지 — 기존 경로 유지) |
| 노트 경로 | `C:/Obsidian/Sync1/03 Sources/3 큐레이션/전종현_YYMM.md` |

## 인증

세션 파일이 없거나 만료되면 `main.py` 실행 시 에러가 난다. 다음 명령으로
재인증:

```bash
python reauth.py
```

전화번호·Telegram 인증 코드·(설정된 경우) 2FA 비밀번호를 순차 입력.

## launchd

매일 자동 실행: `~/Library/LaunchAgents/com.tealeaf.day.plist` → `plist_day_tmux.sh` → `plist_day.sh` → `1_Daily_Code/전종현/run.sh` → `python main.py`.

수동 실행: 이 폴더에서 `python main.py`.

## 동작 세부

- **메시지 순서**: 수집 시 오름차순(오래된 것부터) 정렬 후 저장.
- **중복 제거**: 수집 단계에서 `msg.text[:30]` 중복 제거. 저장 단계에서는
  노트 내 동일 `#### HH:MM` 헤더 존재 시 건너뜀.
- **마크다운 변환**: `MessageEntityTextUrl` / `Url` / `Bold` / `Italic` /
  `Underline`(→ bold) / `Code` / `Pre` 엔티티를 마크다운으로 변환.
- **Forwarded 처리**: 원본 채널명·URL을 조회해 `> Forwarded from [채널명](URL)`
  인용 블록으로 표시.
- **프론트매터**: 신규 파일 생성 시 `tags: [전종현, 텔레그램, 산업분석]`,
  `date: YYYY-MM`, `source: https://t.me/chunjonghyun`.
- **날짜 섹션 정렬**: 새 날짜 섹션은 기존 노트 내 날짜순(오름차순)에 맞춰 삽입.

## 원본 스킬과의 차이

- Claude CLI 호출 제거 — 오케스트레이션이 모두 Python으로 내재화.
- 저장 경로가 기존 스킬의 `3 큐레이션/`에서 `3 큐레이션/`로 이동 (CLAUDE.md의
  피드 노트 경로 규약에 맞춤).
- 항목 헤더에 LLM 요약이 붙던 `#### HH:MM 핵심내용 요약`은 `#### HH:MM`
  으로 간소화 (LLM 없이 동작하기 위함). 요약은 사후에 수동/별도 프로세스로
  추가 가능.
