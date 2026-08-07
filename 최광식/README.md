# 최광식 — Pure-Python 포팅

다올증권 최광식 텔레그램 채널(`t.me/HI_GS`)의 최근 포스트에서 `bit.ly` 링크로
연결된 PDF 리서치 리포트를 자동으로 다운로드하고, 규약대로 파일명을 붙여
Google Drive Inbox 폴더에 저장한다.

Claude/LLM 없이 순수 Python으로 동작한다 (Claude 스킬의 1~5단계에 해당).
피드 노트 / 리포트 요약 노트 작성은 여전히 Claude 스킬이 담당한다.

---

## 파일 구성

| 파일 | 역할 |
|------|------|
| `main.py` | 엔트리포인트. `python main.py` 로 실행. |
| `config.py` | 세션 파일 경로, API ID/HASH, Drive 경로, 상수. |
| `telegram_client.py` | Telethon으로 채널 크롤링, bit.ly URL 추출. |
| `post_parser.py` | 해시태그/제목/분류(기업·산업) 파싱. |
| `pdf_downloader.py` | bit.ly resolve + PDF 다운로드 + 페이지 수 추출. |
| `requirements.txt` | 의존성 목록. |

---

## 실행

```bash
cd C:/Code_Local/1_Daily_Code/최광식
python main.py
```

인자 없음. 수집 기간은 `last_run.log` 기준 자동 산출.

### 종료 코드

- `0` — 정상 종료 (신규 0건 포함).
- `1` — 치명적 오류 (세션 미인증, Drive 폴더 부재, Telegram fetch 실패 등).
  이 경우 `last_run.log`는 갱신되지 않으므로 다음 실행 시 동일 구간을 재시도한다.

---

## Telegram 세션

`전종현` 스킬과 **동일한 세션 파일을 재사용**한다.

```
C:/Users/DELL/.claude/tg_session.session
```

인증이 만료되면 Telethon이 `RuntimeError` 를 던지므로, 복구는 전종현 스킬의
`reauth.py`(`C:/Users/DELL/.claude/skills/전종현/scripts/reauth.py`)로 진행한다.

API 키는 `config.py` 상단에 하드코딩되어 있으며 전종현 스크립트의 값과 같다.

---

## Google Drive Inbox

```
C:/Users/DELL/Library/CloudStorage/GoogleDrive-taeseungg@gmail.com/My Drive/02 주식/02 자료/0 Inbox
```

Drive가 로컬에 마운트되어 있지 않으면 `main.py` 는 즉시 종료한다.

---

## last_run.log

스킬이 사용하는 로그 파일을 그대로 공유한다.

```
C:/Users/DELL/.claude/skills/최광식/last_run.log
```

형식:

```
last_run: YYYY-MM-DD
```

- 파일이 없으면 최근 30일을 조회 범위로 삼는다.
- 파일이 있으면 `last_run - 1일` 을 조회 시작일로 사용한다 (이전 실행 중단 대비).
- `main.py` 가 치명적 오류 없이 끝나면 오늘 날짜(`KST`)로 갱신한다.

---

## 파일명 규칙

```
# 기업분석
기업명_YYMMDD_다올_제목_p페이지수.pdf
예) 대한조선_260111_다올_귀하다, 미들급 K-조선 챔피언_p20.pdf

# 산업분석
산업명_YYMMDD_다올_제목_p페이지수.pdf
예) 조선_260104_다올_깡통아 태평양을 건너라_p68.pdf
```

| 필드 | 추출 방법 |
|------|-----------|
| 기업명/산업명 | `post_parser.py` 참조 (아래) |
| YYMMDD | 포스트 datetime (KST) |
| 다올 | 고정 |
| 제목 | 「」 또는 『』 안의 텍스트. 없으면 본문 앞 30자. |
| p페이지수 | pypdf → 실패 시 `/Type /Page` 바이너리 카운트. 둘 다 실패 시 `p?` |

HTML 엔티티(`&#33;` 등)는 디코딩 후 사용. 파일명 금지 문자
(`\ / : * ? " < > |` + 제어문자)는 공백으로 치환.

---

## 기업분석 vs 산업분석 분류

LLM을 쓰지 않고 아래 휴리스틱으로 결정한다.

1. 포스트 텍스트에서 **첫 번째 `#해시태그`** 를 찾는다.
   - 있음 + 섹터성 해시태그(`#조선`, `#방산`, `#기계` 등 `post_parser._SECTOR_HASHTAGS`)
     → **산업분석**. entity = 해시태그값.
   - 있음 + 섹터 목록에 없음 → **기업분석**. entity = 해시태그값.
2. 해시태그가 없으면 포스트 첫 줄들에서 `:` 앞 명칭을 산업명 후보로 추출.
   - 추출 성공 → **산업분석**. entity = 콜론 앞 명칭.
   - 추출 실패 → **skip** (경고 로그를 남기고 해당 URL은 처리하지 않음).

즉, LLM 판단이 필요한 모호한 케이스는 **추측하지 않고 건너뛴다**. 스킵된 건은
`[SKIP unparseable]` 로 stdout에 남으므로 사후 수동 처리 가능.

---

## 중복 방지

다운로드 전 Inbox 폴더에서 `{기업명/산업명}_{YYMMDD}_다올_{제목}*.pdf` glob을
확인하여 이미 존재하면 네트워크 요청 없이 스킵한다.

---

## 로그 예시

```
[config] today(KST)=2026-04-21 start_date=2026-04-20
[config] inbox=C:/Users/DELL/Library/CloudStorage/...
[FETCH] https://bit.ly/DOS818  → category=산업분석 entity='조선' title='신조선가 3주 연속 상승...'
[OK] 조선_260419_다올_신조선가 3주 연속 상승...p15.pdf  (pages=15 ctype=application/pdf)
[SKIP dup] 대한조선_260111_다올_귀하다, 미들급 K-조선 챔피언*.pdf (이미 존재) msg=6234
────────────────────────────────────────────────────────────
posts_scanned        : 5
urls_scanned         : 5
downloaded           : 1
skipped_duplicate    : 3
skipped_not_pdf      : 1
skipped_http_error   : 0
skipped_unparseable  : 0
```

---

## 의존성 설치

```bash
pip3 install -r requirements.txt
```

- `telethon` — Telegram MTProto 클라이언트.
- `httpx` — bit.ly 리다이렉트 follow + PDF 스트리밍.
- `pypdf` — PDF 페이지 수 추출(메인). 실패 시 정규식 폴백이 있으므로 필수는 아니지만 정확도를 위해 권장.
