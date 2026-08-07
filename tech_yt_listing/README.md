# tech_yt_listing

Google Sheets `yt1` 시트에 등록된 YouTube 채널에서 최근 영상을 수집하여, 2분(120초) 이하 Shorts/클립을 제외한 본편만 `yt2` 시트에 기록하는 pure-Python 파이프라인.

기존 `/tech_yt_listing` Claude Code 스킬을 Claude 없이 단독 실행 가능하도록 포팅한 버전.

---

## 목적

- 여러 YouTube 채널(VC / Tech / Media 등)의 RSS 피드를 주기적으로 스캔
- Shorts·짧은 클립을 걸러내고 본편 영상만 모아 Google Sheets에 누적
- launchd / cron / 수동 실행 어느 쪽도 지원

---

## 요구 사항

- Python 3.9+
- macOS / Linux
- GCP 서비스 계정 JSON 키 (Sheets API 권한)

```bash
pip install -r requirements.txt
```

`requirements.txt`:
- `gspread` — Google Sheets 읽기/쓰기
- `google-auth` — 서비스 계정 인증
- `yt-dlp` — 영상 duration 조회 (Shorts 판별)
- `certifi` — macOS SSL 인증서 번들

---

## 사용법

```bash
# 1) 인자 없음 → 이번 주 월요일~오늘 (KST)
python main.py

# 2) YYMMDD 단일 → 해당 날짜 ~ 오늘
python main.py 260406

# 3) 날짜 범위 (하이픈 또는 공백 구분)
python main.py 260406-260411
python main.py 260406 260411
```

Exit code:
- `0` — 정상 (개별 채널 에러가 있더라도 파이프라인 완주 시)
- `1` — 복구 불가 오류 (인자 파싱 실패, Sheets 인증 실패, 최종 insert 실패 등)

---

## Google Sheet 구조

**Sheet ID**: `1jhIf2aTKP5uYl-imT9nRCnLiZ_q1dV94FeVRfXWfGLE`

### `yt1` — 채널 목록

| 열 | 내용 | 예시 |
|---|---|---|
| A | Category | VC, Tech, Media |
| B | Source | 20VC, No Priors |
| C | URL | `https://www.youtube.com/@20VC/videos` |

C열 값이 `https://www.youtube.com/` 으로 시작하는 행만 대상.

### `yt2` — 수집 결과 (2행부터 최신순 삽입)

| 열 | 내용 | 예시 |
|---|---|---|
| A | Today (기록일) | `2026-04-20` |
| B | Source | `20VC` |
| C | Title | `OpenAI Buys TBPN...` |
| D | URL | `https://youtu.be/cUngseNueP8` |
| E | Posted (업로드일) | `2026-04-19` |
| F | Length | `1:32:20` |
| G | Script | (빈칸) |

---

## 인증 경로

- **GCP 서비스 계정 키**: `C:/Code_Local/gcp-oauth.keys2.json`
  (CLAUDE.md의 전역 설정과 동일; `tech_yt_listing/config.py`의 `KEY_FILE` 상수에서 변경 가능)
- 스코프: `https://www.googleapis.com/auth/spreadsheets`

해당 서비스 계정 이메일이 위 Sheet에 **편집자** 권한으로 공유되어 있어야 한다.

---

## Shorts 판별 방식

RSS 피드(`https://www.youtube.com/feeds/videos.xml?channel_id=...`)에는 영상 길이 정보가 포함되지 않는다. 따라서 본 프로젝트는 **yt-dlp**로 각 영상의 메타데이터를 조회해 `duration`(초)을 얻고, 120초 이하면 Shorts/클립으로 간주하여 제외한다.

장점: YouTube Data API 키·쿼터 불필요.
단점: 영상 1건당 수 초의 네트워크 요청이 발생.

대안(현재 미채용):
- YouTube Data API v3 `videos.list` — API 키 발급 + 일일 쿼터 관리 필요
- oEmbed — duration 필드 없음

관련 상수: `tech_yt_listing/config.py::MIN_DURATION` (기본 120초).

---

## 중복 제거 (Idempotent)

실행 시 yt2 D열의 기존 URL을 전부 읽어 `video_id` 집합을 만든 뒤, 같은 ID면 삽입하지 않는다. 동일 배치 내 중복도 in-memory 세트로 방지. 따라서 같은 날짜 범위를 여러 번 실행해도 중복 행이 쌓이지 않는다.

---

## 실행 흐름

```
1. 인자 → (start_date, end_date) 결정
2. yt1 로딩 → 채널 목록
3. yt2 로딩 → 기존 video_id 집합
4. 각 채널:
     a. @handle URL → channel_id(UC...) 추출 (HTML 스크랩)
     b. RSS XML 파싱 → 날짜 범위 필터링
     c. 중복 ID 스킵
     d. yt-dlp로 duration 조회 → 120초 이하 스킵
     e. 통과 영상 수집
5. 최신순 정렬 후 yt2 2행에 일괄 insert_rows
6. 요약 테이블 출력
```

---

## 요약 출력 포맷

```
=== 결과 요약 ===
  20VC: RSS 4건, 추가 3건, Shorts제외 1건, 중복 0건
  No Priors: RSS 2건, 추가 2건, Shorts제외 0건, 중복 0건
  ...
  합계: RSS 12건, 추가 9건, Shorts제외 2건, 중복 1건
```

개별 채널에서 HTTP 500 등 에러가 나면 해당 라인에 `(ERROR: ...)` 가 붙고, 파이프라인은 계속 진행된다.

---

## cron / launchd 예시

### cron (매일 오전 7시 KST)

```cron
0 7 * * * cd C:/Code_Local/tech_yt_listing && python main.py >> logs/run.log 2>&1
```

### launchd run.sh 예시

```bash
#!/bin/bash
set -euo pipefail
cd C:/Code_Local/tech_yt_listing
LOG_DIR="$(dirname "$0")/logs"
mkdir -p "$LOG_DIR"
TS="$(date '+%Y-%m-%d %H:%M:%S KST')"
echo "[$TS] tech_yt_listing start"
python main.py
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] tech_yt_listing done"
```

기존 `~/Code_Local/GitHub/launchd/tech_yt_listing/run.sh` 를 위와 같이 갈아끼우면 Claude CLI 의존성 없이 돌릴 수 있다.

---

## 파일 구조

```
tech_yt_listing/
├── main.py                 # 엔트리 포인트
├── requirements.txt
├── README.md
├── .gitignore
└── tech_yt_listing/        # 패키지
    ├── __init__.py
    ├── config.py           # Sheet ID, KEY_FILE, MIN_DURATION 등
    ├── dates.py            # YYMMDD 파서 & 범위 해석
    ├── rss.py              # channel_id 추출 + RSS 파서
    ├── duration.py         # yt-dlp 기반 duration 조회
    ├── sheets.py           # gspread 래퍼 (yt1 읽기 / yt2 읽기·쓰기)
    ├── scan.py             # 채널 단위 스캔 로직
    └── report.py           # 요약 테이블 출력
```

---

## 원본 스킬과의 차이

| 항목 | Claude 스킬 (`/tech_yt_listing`) | 본 프로젝트 |
|---|---|---|
| 실행 주체 | Claude CLI + 프롬프트 + 단일 스크립트 | pure Python CLI |
| 날짜 인자 해석 | Claude가 해석 후 스크립트 호출 | `main.py`에서 직접 해석 |
| 모듈화 | 단일 `scan_channels.py` | 패키지(`config/dates/rss/duration/sheets/scan/report`) |
| 동작/결과 | 동일 (동일 Sheet, 동일 필터, 동일 요약 포맷) | 동일 |

---

## 라이선스 / 개인 사용

개인 자동화 스크립트. 별도 라이선스 없음.
