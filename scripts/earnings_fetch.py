"""
earnings_fetch.py
──────────────────
1. data/sp500_latest.json 에서 "관심필요" 종목(연속 3회 이상 순위 상승) 추출
2. 각 종목에 대해 Gemini API(Google Search grounding)를 호출해
   최근 4개 분기 실적을 50개 컬럼 스키마로 구조화
3. Google Apps Script 웹훅으로 POST → 기존 구글 시트에 자동 반영

필요 환경변수:
  GEMINI_API_KEY
  SHEETS_WEBHOOK_URL
  SHEETS_WEBHOOK_TOKEN
"""

import json
import os
import time
import requests
from pathlib import Path

# ── 설정 ──────────────────────────────────────────────────────────
DATA_FILE = Path("data/sp500_latest.json")
MAX_TICKERS = 15          # 관심필요 전체 처리 (안전상한)
QUARTERS_BACK = 4         # 최근 N개 분기 (1년치)
GEMINI_MODEL = "gemini-2.0-flash"

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
WEBHOOK_URL = os.environ["SHEETS_WEBHOOK_URL"]
WEBHOOK_TOKEN = os.environ["SHEETS_WEBHOOK_TOKEN"]

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

# 웹페이지 50개 컬럼 스키마 (Apps Script COLUMN_ORDER와 완전히 동일해야 함)
COLUMN_ORDER = [
    "ticker", "quarter", "revenue", "operating_income", "net_income", "eps",
    "gross_margin", "operating_margin", "net_margin", "revenue_yoy",
    "fcf", "capex", "buyback",
    "seg1_name", "seg1_revenue", "seg1_growth",
    "seg2_name", "seg2_revenue", "seg2_growth",
    "seg3_name", "seg3_revenue", "seg3_growth",
    "beat_estimate",
    "highlight1", "highlight2", "highlight3",
    "risk1", "risk2",
    "ai_summary", "sentiment",
    "ai_arr", "cloud_growth", "user_growth",
    "guidance_low", "guidance_high", "guidance_eps",
    "dividend", "cash", "debt",
    "ceo_quote", "competitive", "regulatory", "ma", "product_update", "macro",
    "analyst", "stock_reaction", "qoq_improved", "qoq_worsened", "investor_focus",
]
# ──────────────────────────────────────────────────────────────────


def load_watch_list() -> list[dict]:
    """data/sp500_latest.json 에서 관심필요(rising_stocks) 종목 추출"""
    if not DATA_FILE.exists():
        print("⚠ data/sp500_latest.json 없음 — 먼저 S&P500 파이프라인을 실행하세요")
        return []
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    rising = data.get("rising_stocks", [])
    print(f"관심필요 종목 {len(rising)}개 발견")
    return rising[:MAX_TICKERS]


def build_prompt(ticker: str, name: str) -> str:
    """Gemini에게 보낼 프롬프트. Google Search grounding으로 실시간 데이터 검색 유도."""
    cols_desc = ", ".join(COLUMN_ORDER)
    return f"""당신은 미국 주식 애널리스트입니다. {name}({ticker}) 의 최근 {QUARTERS_BACK}개 분기
실적 발표(10-Q, 10-K, 어닝콜, 공식 IR 자료, 신뢰할 수 있는 금융 뉴스)를 웹 검색으로 찾아
아래 JSON 스키마에 맞춰 분기별로 정리해주세요.

반드시 아래 형식의 JSON 배열만 출력하세요. 다른 설명, 마크다운, 코드블록 표시 없이 순수 JSON 배열만 출력합니다.

각 분기 객체는 다음 50개 키를 모두 포함해야 합니다 (값이 없으면 null):
{cols_desc}

규칙:
- ticker는 "{ticker}" 로 고정
- quarter는 "2025-Q3" 같은 형식
- revenue, net_income, fcf, capex, buyback, cash, debt, ai_arr, guidance_low, guidance_high 단위는 백만 달러(M$) 숫자
- eps, dividend, guidance_eps는 달러 숫자 (예: 1.25)
- gross_margin, operating_margin, net_margin, revenue_yoy, seg*_growth, cloud_growth, user_growth는 퍼센트 숫자 (예: 12.5)
- beat_estimate는 true 또는 false
- sentiment는 "positive", "negative", "neutral" 중 하나
- highlight1~3, risk1~2, ai_summary, ceo_quote, competitive, regulatory, ma, product_update, macro, analyst, stock_reaction, qoq_improved, qoq_worsened, investor_focus는 한국어로 간결하게 작성
- 정확한 실적 발표 데이터를 찾을 수 없는 분기는 배열에서 제외하세요 (추측 금지)
- 최대 {QUARTERS_BACK}개 분기까지만 포함
"""


def call_gemini_with_search(prompt: str) -> list[dict]:
    """Gemini API를 Google Search grounding 도구와 함께 호출"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8000,
        },
    }
    resp = requests.post(GEMINI_URL, json=payload, timeout=90)

    if resp.status_code == 429:
        print("  ⚠ Rate limit (429) — 60초 대기 후 재시도")
        time.sleep(60)
        resp = requests.post(GEMINI_URL, json=payload, timeout=90)

    resp.raise_for_status()
    result = resp.json()

    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        print(f"  ⚠ Gemini 응답 파싱 실패: {e}")
        print(f"  원본 응답: {json.dumps(result)[:500]}")
        return []

    # 코드블록 표시 제거
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            parsed = [parsed]
        return parsed
    except json.JSONDecodeError as e:
        print(f"  ⚠ JSON 파싱 실패: {e}")
        print(f"  원본 텍스트(앞 300자): {text[:300]}")
        return []


def send_to_sheets(rows: list[dict]) -> dict:
    """Apps Script 웹훅으로 전송"""
    payload = {"token": WEBHOOK_TOKEN, "rows": rows}
    resp = requests.post(WEBHOOK_URL, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    watch_list = load_watch_list()
    if not watch_list:
        print("관심필요 종목이 없습니다. 종료합니다.")
        return

    all_rows = []
    success_tickers = []
    failed_tickers = []

    for stock in watch_list:
        ticker = stock.get("symbol", "")
        name = stock.get("name", ticker)
        print(f"\n📊 {ticker} ({name}) 실적 분석 시작...")

        try:
            prompt = build_prompt(ticker, name)
            rows = call_gemini_with_search(prompt)

            if not rows:
                print(f"  ⚠ {ticker}: 데이터 없음, 스킵")
                failed_tickers.append(ticker)
                continue

            # ticker 필드 강제 보정 (Gemini가 다르게 쓸 경우 대비)
            for r in rows:
                r["ticker"] = ticker

            print(f"  ✓ {ticker}: {len(rows)}개 분기 데이터 수집")
            all_rows.extend(rows)
            success_tickers.append(ticker)

        except Exception as e:
            print(f"  ✗ {ticker} 처리 중 오류: {e}")
            failed_tickers.append(ticker)

        # API 호출 간격 (rate limit 방지)
        time.sleep(8)

    if not all_rows:
        print("\n수집된 데이터가 없습니다. 종료합니다.")
        return

    print(f"\n총 {len(all_rows)}개 분기 데이터를 시트로 전송 중...")
    result = send_to_sheets(all_rows)
    print(f"전송 결과: {result}")

    print(f"\n✅ 완료")
    print(f"  성공: {success_tickers}")
    if failed_tickers:
        print(f"  실패: {failed_tickers}")


if __name__ == "__main__":
    main()
