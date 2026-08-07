# 엄민용 (Standalone Python Port)

신한투자증권 리서치본부 제약/바이오 텔레그램 채널 **`t.me/bio_shinhan`** 에서
`bbs2.shinhansec.com` 으로 연결된 PDF 리서치 리포트를 자동 수집·정리한다.

Claude Code 스킬 `/엄민용` 을 순수 Python 으로 이식한 독립 실행 프로젝트다.

## 목적

- last_run.log 기준으로 증분 수집 (최초 실행 시 최근 30일).
- bbs2 PDF 를 다운로드해 규칙적 파일명으로 Google Drive Inbox 에 저장.
- 포스트 원문(markdown 장식 제거)을 Obsidian 월별 피드 노트에 시간순으로 append.
- LLM 요약은 하지 않는다. 원문 그대로, dedup 만 수행.

## 파일명 규칙

```
기업분석: 기업명_YYMMDD_신한_제목_p페이지수.pdf
산업분석: 산업명_YYMMDD_신한_제목_p페이지수.pdf
```

- **기업명/산업명**: `『...』` 제목에서 추출.
  - `(358570.KQ)` 같은 티커 괄호가 있으면 → 기업분석, 괄호 앞단어가 기업명.
  - 티커가 없고 선두 단어가 `SECTOR_KEYWORDS` 목록에 포함되면 → 산업분석.
  - 둘 다 아니면 **모호 케이스로 스킵** (다운로드·노트 모두 패스).
- **제목**: 『』 내부의 ` - ` 뒤쪽.
- **날짜**: 포스트 `datetime` (KST) → `YYMMDD`.
- **페이지수**: PDF 바이너리에서 `/Type /Page` 오브젝트 수 카운트. 실패 시 `p?`.
- **금지 문자** (`\ / : * ? " < > |`) 는 공백으로 치환.
- 중복 방지: 저장 폴더에서 `{부분파일명}*.pdf` glob 으로 확인. 일치 파일 있으면 다운로드 스킵.

예시:
```
셀트리온_260416_신한_좋아질 일만 남았다_p9.pdf
알지노믹스_260421_신한_AACR 2026 플랫폼 바이오텍으로 레벨업_p7.pdf
```

## 경로

| 항목 | 경로 |
|------|------|
| PDF 저장 | `C:/Users/DELL/Library/CloudStorage/GoogleDrive-taeseungg@gmail.com/My Drive/02 주식/02 자료/0 Inbox` |
| 피드 노트 | `C:/Obsidian/Sync1/03 Sources/3 큐레이션/엄민용_YYMM.md` |
| last_run 로그 | `C:/Users/DELL/.claude/skills/엄민용/last_run.log` |
| Telegram 세션 | `C:/Users/DELL/.claude/tg_session.session` (다른 텔레그램 스킬과 공유) |

> **세션 파일 공유**: `C:/Users/DELL/.claude/tg_session.session` 는 `전종현` 등
> 다른 Telethon 기반 스킬이 함께 사용한다. 삭제·이동 금지. 만료 시 재인증은
> 기존 스킬의 `reauth.py` 와 동일 절차로 진행하면 된다.

## 피드 노트 포맷

월별 파일 `엄민용_YYMM.md` 에 엔트리 단위로 append.

```markdown
## 0416 셀트리온 (068270,KS) - 좋아질 일만 남았다
기업분석부 이호철, 엄민용 ☎️ 02-3772-2669
▶️ 신한생각: 단기 이슈 해소 후 고마진 신제품 기반 성장 지속 전망
26년 1분기 연결 기준 매출 ...
→ 저장: 셀트리온_260416_신한_좋아질 일만 남았다_p9.pdf
```

- 헤더(`## MMDD ...`) 가 이미 파일에 있으면 해당 포스트는 스킵 (dedup).
- 포스트는 시간순(오래된 것부터)으로 append.
- 본문은 Telegram `**bold**` 마크업만 스트립하고 나머지 원문은 그대로 보존.

## 실행

```bash
# 의존성 설치
python -m pip install -r requirements.txt

# 실행
python main.py
```

- 인자 없이 실행. 수집 범위는 `last_run.log` 에서 자동 결정.
- 종료 코드: `0` (성공, 신규 0건 포함) / `1` (하나라도 에러 발생).
- 에러 발생 시 **last_run.log 를 갱신하지 않는다** → 다음 실행 시 재시도 보장.

## last_run 관리

```
last_run: 2026-04-22
```

- 읽기: `C:/Users/DELL/.claude/skills/엄민용/last_run.log` 1줄 `last_run: YYYY-MM-DD` 포맷.
- 조회 시작일: 로그의 날짜 **−1일** (오류 재시도 누락 방지). 파일이 없으면 오늘 −30일.
- 쓰기: 모든 포스트가 오류 없이 처리된 후에만 오늘(KST) 날짜로 덮어쓴다.

## 분류 휴리스틱 상세

1. Telegram 메시지 텍스트에서 `**...**` 볼드 마크업 제거.
2. `『...』` 정규식으로 제목 블록 추출. 없으면 스킵.
3. 제목 내부에 `(숫자 5~6자리 [., ] KQ/KS/..)` 형태의 **티커 괄호**가 있는가?
   - **있다** → 기업분석. 괄호 이전 = 기업명, `-` 이후 = 제목.
   - **없다** → 산업분석 후보. `-` 로 쪼갠 head 가 `SECTOR_KEYWORDS` 에 속하면 산업분석.
4. 위 조건 모두 실패 시 → **스킵**. 안전하게 사람 검토 대상으로 남긴다.

`SECTOR_KEYWORDS`: `바이오`, `제약`, `헬스케어`, `바이오헬스케어`, `바이오시밀러`,
`제약바이오`, `바이오/제약`, `제약/바이오`, `CDMO`, `신약`.

새로운 섹터 표기가 등장해 자동 스킵되면 `main.py` 의 `SECTOR_KEYWORDS` 에 추가한다.

## 외부 의존

- `telethon` 1.36+ — 채널 메시지 수집. Python 3.8+ 필요.
- 표준 라이브러리: `urllib.request`, `ssl`, `re`, `glob`, `asyncio` 등.
- PDF 다운로드 시 `bbs2.shinhansec.com` TLS 체인 간헐적 오류 대비로
  SSL 검증을 비활성화한다 (기존 스킬의 `curl -sL` 과 동일 동작).
