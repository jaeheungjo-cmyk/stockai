import os
import json
import requests
import feedparser
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

CHANNELS = [
    {"name": "소수몽키", "feed": "https://www.youtube.com/feeds/videos.xml?user=sosumonkey"},
    {"name": "수페TV", "feed": "https://www.youtube.com/feeds/videos.xml?channel_id=UC4Z..."},
    {"name": "박종훈의 지식한방", "feed": "https://www.youtube.com/feeds/videos.xml?user=kpunch"},
    {"name": "전인구경제연구소", "feed": "https://www.youtube.com/feeds/videos.xml?user=moneydo"},
    {"name": "경제명탐정", "feed": "https://www.youtube.com/feeds/videos.xml?channel_id=경제명탐정"},
]

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_sheet():
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(os.environ["YOUTUBE_SHEET_ID"]).sheet1

def analyze_with_gemini(title, link, summary):
    api_key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

    prompt = f"""
다음 유튜브 영상을 투자 관점에서 한국어로 분석해줘.

제목: {title}
링크: {link}
설명: {summary}

아래 형식으로만 답변:
한줄요약:
분석전문내용:
시장전망:
태그:
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def parse_result(text):
    result = {
        "한줄요약": "",
        "분석전문내용": "",
        "시장전망": "",
        "태그": ""
    }

    current = None
    for line in text.splitlines():
        line = line.strip()
        for key in result:
            if line.startswith(key + ":"):
                current = key
                result[key] = line.replace(key + ":", "").strip()
                break
        else:
            if current and line:
                result[current] += " " + line

    return result

def existing_links(sheet):
    values = sheet.get_all_values()
    return {row[3] for row in values[1:] if len(row) > 3}

def main():
    sheet = get_sheet()
    saved_links = existing_links(sheet)

    added = 0

    for channel in CHANNELS:
        feed = feedparser.parse(channel["feed"])

        for entry in feed.entries[:3]:
            title = entry.title
            link = entry.link
            published = entry.get("published", datetime.now().strftime("%Y-%m-%d"))
            summary = entry.get("summary", "")

            if link in saved_links:
                continue

            analysis_text = analyze_with_gemini(title, link, summary)
            parsed = parse_result(analysis_text)

            row = [
                channel["name"],
                title,
                published[:10],
                link,
                parsed["한줄요약"],
                parsed["분석전문내용"],
                parsed["시장전망"],
                parsed["태그"],
                ""
            ]

            sheet.append_row(row, value_input_option="USER_ENTERED")
            added += 1

    print(f"Added {added} new YouTube rows.")

if __name__ == "__main__":
    main()
