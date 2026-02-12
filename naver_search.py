import requests
import os

# GitHub Secrets에서 가져올 키
CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

def search_naver_news(keyword, display=5):
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ 네이버 API 키가 없습니다.")
        return None

    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET
    }
    # 정확도(sim) 순으로 정렬하여 관련성 높은 뉴스 수집
    params = {"query": keyword, "display": display, "sort": "sim"}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return None
        return response.json()
    except Exception as e:
        print(f"API Error: {e}")
        return None
