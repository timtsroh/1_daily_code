# 노정석 (chester.roh) — Facebook 피드 수집기

Facebook 프로필 `chester.roh`(노정석)의 **어제 날짜(KST)** 포스트를 Playwright로
수집하여 Obsidian 월별 노트로 저장하는 순수 파이썬 파이프라인.

원본은 Claude Code 스킬(`/노정석`)이었으며, Claude/LLM 의존성을 제거하고
`python main.py` 한 방에 끝나도록 포팅한 버전이다.

---

## 파일 구조

```
노정석/
├── main.py            # 엔트리포인트 (일일 파이프라인)
├── fetch_feed.py      # Playwright 스크래핑 (어제 KST 필터)
├── fb_login.py        # Facebook 로그인 세션 저장 (대화형, 최초 1회)
├── note_writer.py     # Obsidian 월별 노트 쓰기/append (idempotent)
├── requirements.txt
└── README.md
```

---

## 실행 방법

### 1) 의존성 설치 (최초 1회)

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

### 2) Facebook 로그인 세션 저장 (최초 1회, 세션 만료 시 재실행)

```bash
python C:/Code_Local/1_Daily_Code/노정석/fb_login.py
```

브라우저가 열리면 Facebook 로그인을 완료한 뒤 터미널에서 Enter.
세션은 **원본 스킬과 동일 경로**에 저장된다:

```
C:/Users/DELL/.claude/fb_session.json
```

이 경로를 그대로 유지하므로, 기존 `/김봉수`, `/노정석` 등 다른 Claude 스킬과
세션을 공유한다.

### 3) 일일 실행

```bash
python C:/Code_Local/1_Daily_Code/노정석/main.py
```

cron/launchd에서 호출할 경우 작업 디렉토리를 프로젝트 폴더로 맞춰준다:

```bash
cd C:/Code_Local/1_Daily_Code/노정석 && python main.py
```

종료 코드:
- `0` — 정상 (어제 포스트 0건이어도 0)
- `1` — 치명적 오류 (세션 없음/만료, Playwright 미설치, 스크랩 예외 등)

---

## 출력

`C:/Obsidian/Sync1/03 Sources/3 큐레이션/노정석_YYMM.md`

- 파일이 없으면 frontmatter + 제목 포함하여 신규 생성
- 파일이 있으면 끝에 `---` 구분선과 함께 append
- `(HH:MM, 본문 첫 줄 40자)` 기준으로 **중복 스킵** — 재실행 시 동일 포스트를 또 쓰지 않음
- 포스트 블록 포맷:

  ```
  #### MM/DD HH:MM <본문 첫 어절 5개 이내 프리뷰>

  <본문 전체>
  ```

> 원본 Claude 스킬은 LLM으로 "5단어 이내 한국어 요약"을 생성해 헤더에 붙였다.
> 본 포팅은 LLM 금지이므로, 본문 첫 줄의 앞 5어절을 컷하여 헤더 프리뷰로 사용한다.
> (URL은 제거, 40자 초과 시 `…` 말줄임)

---

## `fetch_feed.py` 변형 선택 사유

원본 스킬의 `scripts/`에는 6종의 스크립트가 있다:

| 파일 | 용도 | 사용 여부 |
|------|------|----------|
| `fetch_feed.py` | **어제 날짜만 수집** (일일 파이프라인용) | 채택 |
| `fetch_2026.py` | 2026년 전체 백필 (스크롤 120회) | 일회성 백필 — 제외 |
| `fetch_2026_v2.py` | v2, 절대날짜 파싱 + 스크롤 300회 | 일회성 백필 — 제외 |
| `fetch_2026_early.py` | 2026 1~2월 타임라인 필터 URL 방식 | 일회성 백필 — 제외 |
| `fetch_2026_graphql.py` | GraphQL 응답 인터셉트 방식 실험 | 실험용 — 제외 |
| `fetch_2026_intercepted.py` | doc_id로 afterTime/beforeTime 주입 실험 | 실험용 — 제외 |

포팅 요구사항은 **"yesterday(KST) 포스트를 매일 수집"** 이므로 일일 드라이버인
`fetch_feed.py`가 유일한 캐노니컬 소스다.
`fetch_2026*`는 2026-01-01 이후 전체를 긁어오는 백필/실험 스크립트이며 매일 돌릴
목적이 아니다. (스크롤 120~300회, 브라우저에 수분간 머무르며 실험적 네트워크
인터셉트를 수행) 따라서 본 프로젝트에서는 포함하지 않았다.

향후 대량 백필이 필요하면 원본 `C:/Users/DELL/.claude/skills/노정석/scripts/fetch_2026_v2.py`를
직접 실행하면 된다.

---

## 세션 핸들링

- **세션 파일**: `C:/Users/DELL/.claude/fb_session.json` (원본 스킬과 동일 위치)
- **만료 시 신호**: 스크랩 결과가 이상하게 0건이거나 Playwright가 로그인 페이지로
  리다이렉트되는 경우. 이때 `fb_login.py`를 다시 실행해 세션을 갱신한다.
- `fb_login.py`는 **대화형**(headless=False)이므로 launchd/cron에서는 사용 불가.
  사용자가 직접 터미널에서 실행해야 한다.
- `main.py`는 세션 파일이 없으면 즉시 exit 1 하고 안내 메시지를 출력한다.

---

## 보존된 동작 (원본 Claude 프롬프트 대비)

- 시간 표시 우선순위:
  1. 시간 링크가 `comment_id` **없으면** → hover tooltip(`Thursday, March 19, 2026 at 2:27 PM`) 파싱
  2. `comment_id` **있으면** → 포스트 상세 페이지에서 `"creation_time":<epoch>` 스크립트 값 추출
  3. 둘 다 실패 시 → `??:??`
- 어제 이전 포스트를 만나면 스크롤 루프를 조기 종료(효율)
- "See more" / "더 보기" 버튼 자동 클릭으로 본문 전체 확보
- 월별 노트 파일명 `노정석_YYMM.md` (구분기호는 `_` 하나)
- Obsidian 저장 경로는 **태스크 명세에 따라 `3 큐레이션/`** 로 변경
  (원본 스킬은 `3 큐레이션/`에 저장했다.)
- Playwright UA/viewport/세션 경로는 원본 그대로

---

## launchd 연동

매일 자동 실행: `~/Library/LaunchAgents/com.tealeaf.day.plist` → `plist_day_tmux.sh` → `plist_day.sh` → `1_Daily_Code/노정석/run.sh` → `python main.py`.

수동 실행: 이 폴더에서 `python main.py`.
