import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]

def get_client():
    service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES
    )
    return gspread.authorize(credentials)

def append_youtube_test_row(client):
    sheet_id = os.environ["YOUTUBE_SHEET_ID"]
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.sheet1

    row = [
        "TEST_CHANNEL",
        "자동화 테스트 제목",
        datetime.now().strftime("%Y-%m-%d"),
        "https://youtube.com/test",
        "자동화 테스트 한줄요약",
        "자동화 테스트 분석전문내용",
        "자동화 테스트 시장전망",
        "TEST",
        ""
    ]

    worksheet.append_row(row, value_input_option="USER_ENTERED")

def append_earnings_test_row(client):
    sheet_id = os.environ["EARNINGS_SHEET_ID"]
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.sheet1

    row = [
        "TEST",
        "2026-Q2",
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        "세그먼트1",
        0,
        0,
        "세그먼트2",
        0,
        0,
        "세그먼트3",
        0,
        0,
        "테스트",
        "핵심포인트1 테스트",
        "핵심포인트2 테스트",
        "핵심포인트3 테스트",
        "리스크1 테스트",
        "리스크2 테스트",
        "종합평가 테스트",
        "중립",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "경영진발언요약 테스트",
        "경쟁환경변화 테스트",
        "규제리스크 테스트",
        "M&A파트너십 테스트",
        "제품업데이트 테스트",
        "거시경제영향 테스트",
        "애널리스트반응 테스트",
        "주가반응 테스트",
        "전분기개선점 테스트",
        "전분기악화점 테스트",
        "투자자주목포인트 테스트"
    ]

    worksheet.append_row(row, value_input_option="USER_ENTERED")

def main():
    client = get_client()
    append_youtube_test_row(client)
    append_earnings_test_row(client)
    print("Google Sheets test rows added successfully.")

if __name__ == "__main__":
    main()
