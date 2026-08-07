#!python
"""반복 자동화 작업 목록을 Google Sheet "work" 시트에 기록.

소스: ~/.claude/CLAUDE.md / ~/.claude/routine.md / launchd plist / plist_day.sh / crontab
작업/스킬/cron이 추가·변경될 때마다 ROWS를 갱신하고 다시 실행하면 됨.
"""
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = "1l3rbFwu05_Ti6H62_Eo4wnuxkum14VUwKK3xBHP0IN0"
KEYFILE = "C:/Code_Local/gcp-oauth.keys2.json"
TAB = "Work"

HEADER = ["작업명", "작업내용", "관련 코드 / 스킬", "작업시간(KST)", "빈도", "트리거"]

ROWS = [
    # --- 매일 00:05  com.tealeaf.day.plist → plist_day_tmux.sh → plist_day.sh (각 30분 timeout, 순차) ---
    ["log_start", "실행 시작 로그 (Google Sheets Launchd 시트 + #routine Discord)",
     "1_Daily_Code/log/run.sh start → skills/log/scripts/log.py start", "매일 00:05 (1번째)", "매일", "launchd: com.tealeaf.day.plist"],
    ["전종현", "텔레그램 채널(chunjonghyun) 어제 메시지 수집 → Obsidian 월별 노트",
     "1_Daily_Code/전종현/main.py (Telethon)", "매일 00:05 (순차)", "매일", "launchd: com.tealeaf.day.plist"],
    ["김봉수", "페이스북 프로필(bongsoo2) 어제 포스트 수집 → Obsidian 월별 노트",
     "1_Daily_Code/김봉수/main.py (Playwright)", "매일 00:05 (순차)", "매일", "launchd: com.tealeaf.day.plist"],
    ["노정석", "페이스북 프로필(chester.roh) 어제 포스트 수집 → Obsidian 월별 노트",
     "1_Daily_Code/노정석/main.py (Playwright)", "매일 00:05 (순차)", "매일", "launchd: com.tealeaf.day.plist"],
    ["nrd", "네이버 금융 산업분석 리포트(조선·반도체·에너지) 전날분 다운로드 → PDF + Obsidian 요약",
     "1_Daily_Skill/nrd/run.sh → claude -p \"/nrd\"", "매일 00:05 (순차)", "매일", "launchd: com.tealeaf.day.plist"],
    ["최광식", "다올증권 텔레그램(HI_GS) PDF 리서치 리포트 수집 → Google Drive + Obsidian",
     "1_Daily_Code/최광식/main.py (Telethon)", "매일 00:05 (순차)", "매일", "launchd: com.tealeaf.day.plist"],
    ["엄민용", "신한투자 텔레그램(bio_shinhan) PDF 리서치 리포트 수집 → Google Drive + Obsidian",
     "1_Daily_Code/엄민용/main.py (Telethon)", "매일 00:05 (순차)", "매일", "launchd: com.tealeaf.day.plist"],
    ["tech_yt_listing", "yt1 채널 최근 영상 수집 → 2분 이하 제외 본편만 Google Sheets yt2 시트 기록",
     "1_Daily_Code/tech_yt_listing/main.py", "매일 00:05 (순차)", "매일", "launchd: com.tealeaf.day.plist"],
    ["tech_yt_script", "yt2 시트 미처리 영상 → /yt 적용해 Obsidian 노트 생성, H열 'v' 표기",
     "1_Daily_Skill/tech_yt_script/run.sh → claude -p \"/tech_yt_script\"", "매일 00:05 (순차)", "매일", "launchd: com.tealeaf.day.plist"],
    ["tech_blog", "blog 시트 소스에서 어제 신규 글 → 한국어 3불릿 요약 + 전문 번역 노트",
     "1_Daily_Skill/tech_blog/run.sh → claude -p \"/tech_blog\"", "매일 00:05 (순차)", "매일", "Task Scheduler: Bill_plist_day"],
    ["news", "CNBC·FT·NYT·WSJ Tech 섹션 RSS + Google News fallback 수집 → adb1/news/data/news.json 재빌드 → commit·push (Vercel 재배포, adb1.vercel.app/#news 갱신)",
     "1_Daily_Code/news/run.sh → python -m news.collectors.build", "매일 00:05 (순차)", "매일", "Task Scheduler: Bill_plist_day"],
    ["report", "네이버 금융 nrd 시트(섹터·기업) 각 최근 5건 리포트 수집 → adb1/report/data/reports.json 재빌드 → commit·push (Vercel 재배포, adb1.vercel.app/#report 갱신)",
     "1_Daily_Code/report/run.sh → 2_Dash python -m report.collectors.build", "매일 00:05 (순차)", "매일", "Task Scheduler: Bill_plist_day"],
    ["ec_transcripts", "실적발표 트랜스크립트 URL 수집 → earnings.json/EC시트 갱신 → adb1 repo push(Vercel 재배포) → 신규분 /ec 노트 생성 (구 17:00 → 00:05 통합)",
     "1_Daily_Code/ec_transcripts/plist_transcripts.sh → collectors.transcripts + claude -p \"/ec\"", "매일 00:05 (순차)", "매일", "launchd: com.tealeaf.day.plist"],
    ["todo", "텔레그램 @atomtodo 어제 메시지 → Obsidian 0 inbox/todo_YYYYMM.md 월별 누적",
     "1_Daily_Code/todo/run.sh (fetch_feed.py + write_note.py)", "매일 00:05 (순차)", "매일", "launchd: com.tealeaf.day.plist"],
    ["dart_shiporder", "DART 단일판매·공급계약(수주) 공시 → 구글시트 '수주2' 이번 달 upsert",
     "1_Daily_Skill/dart_shiporder/run.sh → claude -p \"/dart_shiporder\"", "매일 00:05 (순차)", "매일", "launchd: com.tealeaf.day.plist"],
    ["log_end", "실행 종료 로그 + 작업별 ✅/❌/⏰/🚫 요약 #routine Discord 전송",
     "1_Daily_Code/log/run.sh end → skills/log/scripts/log.py end", "매일 00:05 (마지막)", "매일", "launchd: com.tealeaf.day.plist"],

    # --- 매일 05:10  com.tealeaf.morning.plist → plist_morning_tmux.sh → plist_morning.sh (Claude 한도 리셋 직후) ---
    ["catch-up (한도 재시도)", "00:05 배치에서 Claude 사용 한도로 미실행된 작업(/tmp/claude_limit_pending.txt)을 한도 리셋 후 이어서 재실행 (nrd·tech_yt_script·tech_blog·dart_shiporder·ec_transcripts)",
     "1_Daily_Code/plist_morning.sh (resolve_script)", "매일 05:10 (0번째)", "매일 (한도 시에만)", "launchd: com.tealeaf.morning.plist"],
    ["compile (compile_day)", "당일 수집 결과(catch-up 포함)를 데일리 노트(daily_YYMMDD.md)로 통합 (00:05→05:10 이동)",
     "1_Daily_Skill/compile_day/compile_day.sh → claude -p \"/compile_day\"", "매일 05:10 (1번째)", "매일", "launchd: com.tealeaf.morning.plist"],
    ["wiki_update", "신규 Raw Sources → A1 Wiki/ 페이지 갱신 → #wiki Discord 알림 (00:05→05:10 이동)",
     "1_Daily_Skill/wiki_update/run.sh → claude -p \"/wiki_update\"", "매일 05:10 (2번째)", "매일", "launchd: com.tealeaf.morning.plist"],

    # --- 매주 토 05:00  com.tealeaf.saturday.plist → plist_week.sh ---
    ["move (inbox 정리)", "0 inbox/에서 파일명 날짜 기준 2일 이상 지난 daily_*/news_*/todo_* → 8 moved/ 이동",
     "1_Daily_Code/move/move.sh", "매주 토 05:00 (1번째)", "매주 토", "launchd: com.tealeaf.saturday.plist"],
    ["compile_week", "이번 주(토~금) 신규 포스팅·작업 → 위클리 노트(weekly_YYMMDD.md) 생성",
     "plist_week.sh → claude -p \"/compile_week\"", "매주 토 05:00 (2번째)", "매주 토", "launchd: com.tealeaf.saturday.plist"],

    # --- crontab (현재 비활성: 대상 스크립트 경로 부재) ---
    ["Run_Log (비활성)", "crontab 등록되어 있으나 C:/Users/DELL/Run/Run_Log.py 가 존재하지 않아 실제 동작 안 함",
     "crontab: python C:/Users/DELL/Run/Run_Log.py", "매주 토 18:17", "매주 토 (비활성)", "crontab"],
]


def main():
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(KEYFILE, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)

    try:
        ws = sh.worksheet(TAB)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=TAB, rows=max(50, len(ROWS) + 10), cols=len(HEADER))

    ws.update([HEADER] + ROWS, "A1")
    ws.format("A1:F1", {"textFormat": {"bold": True},
                        "backgroundColor": {"red": 0.85, "green": 0.9, "blue": 1.0}})
    ws.freeze(rows=1)
    print(f"OK: '{TAB}' 시트에 {len(ROWS)}개 작업 기록 완료")


if __name__ == "__main__":
    main()
