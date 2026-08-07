# 김봉수 — Facebook 피드 수집기 (Pure Python)

페이스북 프로필 [`bongsoo2`](https://www.facebook.com/bongsoo2)(김봉수)의 **어제(KST) 포스트**를 Playwright로 긁어 Obsidian 월별 노트에 저장하는 일일 자동화 스크립트.

원래 Claude Code 스킬(`~/.claude/skills/김봉수/`)에서 동작하던 파이프라인을 Claude 의존성 없는 순수 Python으로 포팅했다.

---

## 기능 요약

- Playwright(headless Chromium)으로 프로필 페이지를 스크롤하며 포스트 수집
- 시간 링크 hover tooltip 또는 `creation_time` 스크립트 데이터에서 정확한 `HH:MM` 추출
- 어제 날짜(KST)만 필터링, 시간순(오름차순)으로 정렬
- Obsidian 월별 노트에 `#### MMDD HH:MM <요약>` 형식으로 저장
  - 파일 없음 → frontmatter 포함 신규 생성
  - 파일 있음 → `---` 구분선과 함께 append
- **idempotent** — 같은 포스트를 다시 넣지 않는다. fingerprint 기준:
  1순위 post permalink, 2순위 `HH:MM + 본문 앞 40자`
- 종료 코드: 정상 `0`, 치명적 오류 `1`. "어제 글 없음"도 `0`.

---

## 디렉토리 구조

```
김봉수/
├── main.py          # 엔트리포인트
├── config.py        # 경로·상수 (환경변수로 override 가능)
├── session.py       # 세션 확인 / 대화형 재로그인
├── scraper.py       # Playwright 스크래퍼
├── summary.py       # 포스트 본문 → 5단어 한국어 요약 (heuristic)
├── note_writer.py   # Obsidian 월별 노트 writer
├── requirements.txt
└── README.md
```

---

## 초기 설정

### 1. Python 의존성 설치

```bash
cd C:/Code_Local/1_Daily_Code/김봉수
python -m pip install -r requirements.txt
```

### 2. Playwright 브라우저 설치

```bash
python -m playwright install chromium
```

### 3. Facebook 세션 로그인

세션 파일 경로는 기존 Claude 스킬과 동일하다: `C:/Users/DELL/.claude/fb_session.json`. 다른 프로젝트(노정석 등)와 세션을 공유한다.

```bash
python session.py
```

헤드풀 브라우저가 뜨면 Facebook에 로그인한 뒤 터미널에서 Enter를 누른다. 세션이 저장된다.

세션이 만료되면 같은 명령을 다시 실행하면 된다.

---

## 실행

```bash
python main.py
```

기본 동작:
- 대상 날짜: 어제(KST, 실행 시점 기준)
- 저장 위치: `C:/Obsidian/Sync1/03 Sources/3 큐레이션/김봉수_YYMM.md`

특정 날짜로 수동 실행:

```bash
python main.py --date 2026-04-19
python main.py --date 260419
```

---

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|-------|-----|
| `FB_SESSION_FILE` | `C:/Users/DELL/.claude/fb_session.json` | 세션 파일 경로 |
| `OBSIDIAN_VAULT` | `C:/Users/DELL/Obsidian/Sync1` | Obsidian 볼트 루트 |

---

## 노트 포맷

```markdown
---
type: curation
person: 김봉수
month: 2026-04
source: https://www.facebook.com/bongsoo2
tags:
  - 김봉수
  - 큐레이션
  - 조선
---

# 김봉수 2604

---

#### 0419 09:30 VLCC 운임 폭등 신조
<포스트 본문>

---

#### 0419 15:53 LNG 유일 대체연료 전망
<포스트 본문>
```

- 헤더 요약은 heuristic으로 본문 첫 유의미한 줄 앞 5단어를 추출한다. 자동화된 일일 실행에서는 완벽하지 않을 수 있어, 필요 시 사람이 노트에서 다듬으면 된다.
- 파일명은 CLAUDE.md 규칙에 따라 `_` 구분자만 사용.

---

## 자동화 (launchd)

매일 자동 실행: `~/Library/LaunchAgents/com.tealeaf.day.plist` → `plist_day_tmux.sh` → `plist_day.sh` → `1_Daily_Code/김봉수/run.sh` → `python main.py`.

수동 실행: 이 폴더에서 `python main.py`.

---

## 알려진 제약

- `creation_time`이 없고 hover tooltip도 실패하면 시간은 `??:??`로 기록된다(원본 스킬과 동일).
- 프로필이 스크롤 중 Facebook의 rate-limit에 걸릴 경우 수집 건수가 줄어들 수 있다. `MAX_SCROLLS`/`SCROLL_DELAY_MS`를 `config.py`에서 조정.
- 세션 쿠키 만료 시 Playwright는 로그인 월(wall)로 리다이렉트되어 결과가 비어 있을 수 있다. 이 경우 `python session.py` 재실행.
