import os
import re
import json
import requests
import feedparser
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

CHANNELS = [
    {"name": "소수몽키", "handle": "sosumonkey"},
    {"name": "수페TV", "handle": "supe-tv"},
    {"name": "박종훈의 지식한방", "handle": "kpunch"},
    {"name": "전인구경제연구소", "handle": "moneydo"},
    {"name": "경제명탐정", "handle": "경제명탐정"},
]

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_sheet():
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(os.environ["YOUTUBE_SHEET_ID"]).sheet1


def get_channel_id(handle):
    url = f"https://www.youtube.com/@{handle}"
    headers = {"User-Agent": "Mozilla/5.0"}
    html = requests.get(url, headers=headers, timeout=20).text

    match = re.search(r'"channelId":"(UC[^"]+)"', html)
    if match:
        return match.group(1)

    match = re.search(r'"externalId":"(UC[^"]+)"', html)
    if match:
        return match.group(1)

    raise ValueError(f"채널 ID를 찾지 못했습니다: @{handle}")


def analyze_with_gemini(title, link, summary):
    api_key = os.environ["GEMINI_API_KEY"]
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/gemini-1.5-flash:generateContent?key={api_key}"
    )

    prompt = f"""
다음 유튜브 영상을 투자 관점에서 한국어로 분석해줘.

제목: {title}
링크: {link}
설명: {summary}

반드시 아래 형식으로만 답변해줘.

한줄요약:
분석전문내용:
시장전망:
태그:
"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    response = requests.post(url, json=payload, timeout=40)
    response.raise_for_status()

    return response.json()["candidates"][0]["content"]["parts"][0]["text"]


def parse_result(text):
    result = {
        "한줄요약": "",
        "분석전문내용": "",
        "시장전망": "",
        "태그": "",
    }

    current = None

    for line in text.splitlines():
        line = line.strip()

        matched = False
        for key in result:
            if line.startswith(key + ":"):
                current = key
                result[key] = line.replace(key + ":", "", 1).strip()
                matched = True
                break

        if not matched and current and line:
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
        try:
            channel_id = get_channel_id(channel["handle"])
            feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            feed = feedparser.parse(feed_url)

            print(f'{channel["name"]}: {len(feed.entries)} videos found')

            for entry in feed.entries[:3]:
                title = entry.title
                link = entry.link
                published = entry.get("published", datetime.now().strftime("%Y-%m-%d"))
                summary = entry.get("summary", "")

                if link in saved_links:
                    print(f"skip duplicate: {title}")
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
                    "",
                ]

                sheet.append_row(row, value_input_option="USER_ENTERED")
                saved_links.add(link)
                added += 1

        except Exception as e:
            print(f'ERROR - {channel["name"]}: {e}')
            continue

    print(f"Added {added} new YouTube rows.")


if __name__ == "__main__":
    main()
