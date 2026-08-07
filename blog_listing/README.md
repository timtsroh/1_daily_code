# blog_listing

Google Sheet `blog` 시트에 등록된 소스에서 지정 기간 내 신규 글을 수집하여, blog 시트의 `Destination` 컬럼 값에 따라 `article` 또는 `deals` 시트 2행에 insert 한다 (최근 글이 위).

## 사용법

```bash
# 어제 하루 (plist_day.sh 데일리 실행 기본값)
bash run.sh

# 특정 날짜 하루
bash run.sh 2026-07-15

# 범위
bash run.sh 2026-07-01 2026-07-15
bash run.sh --since 2026-07-01 --until 2026-07-15

# 특정 월 전체 (backfill)
bash run.sh --month 2026-06
```

## 소스별 수집 방식

| Source | Format | Destination | 방식 |
|---|---|---|---|
| Jamin Ball, Apoorv, Sarah Tavel, Elad Gil, ALAD, Dwarkesh | Substack | article | `/api/v1/archive?limit=30&offset=N` JSON, offset paging |
| Sequoia (Perspective / Spotlight) | Sequoia / Sequoia Spotlight | article / deals | `/stories/?_story-category=<slug>` HTML 로 URL 집합 확보 + WP REST API 로 발행일 조회 후 교집합 |
| Stratechery | Stratechery | article | `/feed/` RSS `<pubDate>` |
| BVP News / Atlas | BVP News / BVP Atlas | deals / article | HTML `<article data-date="YYYY-MM-DD">` 파싱 |
| Bill Evans | Bill Evans | article | URL 경로 `/benedictevans/YYYY/M/D/slug` 에서 date 파싱 |
| SemiAnalysis | SemiAnalysis | article | Substack API (`newsletter.semianalysis.com/api/v1/archive`) |

## article / deals 시트 스키마 (동일)

| 열 | 의미 |
|---|---|
| A Today | 이 스크립트가 실행된 날짜 (오늘) |
| B Format | 소스 타입 (Substack / Sequoia / Stratechery / BVP News / BVP Atlas / Bill Evans / SemiAnalysis) |
| C Writer | 저자/필자 |
| D Posted | 원글 발행일 |
| E URL | 원글 URL (Substack 은 `/api/v1/p/<slug>` 형식으로 저장) |
| F Title | 원글 제목 |

## Dedup

article + deals 두 시트의 E열(URL) 집합을 통합하여 이미 어느 시트에라도 존재하면 스킵. 같은 배치 안에서 여러 소스가 같은 URL 을 뱉는 경우도 방지.

## 정렬 규칙

이번 배치 안의 신규 글을 Posted 내림차순 정렬한 뒤 2행에 한 번에 insert. 결과: 헤더 바로 밑이 이번 배치 중 가장 최신 글.

## 인증

`C:/Code_Local/gcp-oauth.keys2.json` (Google Sheets API 서비스 키).

## plist_day.sh 통합

`plist_day.sh` 에서 `tech_blog` 스킬 직전에 실행됨. `tech_blog` 는 어제 신규 글을 Obsidian 노트로 요약/번역하는데, 그 전에 article/deals 시트에 목록을 먼저 축적한다.
