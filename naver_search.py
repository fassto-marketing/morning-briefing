import requests
import os

CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")


def search_naver_news(keyword, display=10):
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ 네이버 API 키가 없습니다. Secrets 설정을 확인하세요.")
        return None

    # sort=date: 최신순 — 관련도순(sim)은 오래된 기사가 상위로 와서
    # 24시간 필터에 다 걸러지는 날이 생김 (news-bot v4에서 검증된 설정)
    try:
        response = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            headers={"X-Naver-Client-Id": CLIENT_ID, "X-Naver-Client-Secret": CLIENT_SECRET},
            params={"query": keyword, "display": display, "sort": "date"},
            timeout=10,
        )
        if response.status_code != 200:
            print(f"   ⚠️ 네이버 API {response.status_code}: {response.text[:120]}")
            return None
        return response.json()
    except Exception as e:
        print(f"API Error: {e}")
        return None
