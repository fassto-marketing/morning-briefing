import naver_search
import slack_sender
import ai_editor
import time
import os
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

# 환경변수 체크
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")

# [업데이트] 경영진용 확장 키워드 세트 (User Customized)
KEYWORDS = [
    "파스토", "풀필먼트", "3PL",      # 자사 및 핵심 업종
    "CJ대한통운", "쿠팡", "알리익스프레스", "테무", # 거대 플랫폼
    "품고", "두핸즈", "아르고", "테크타카", "위킵", # ★직접 경쟁사 (추가됨)
    "이커머스 정책", "유통 규제",  # 대관/법무 이슈
    "물류 로봇", "스마트 물류",    # 기술/Tech 트렌드
    "주 52시간", "중대재해처벌법"   # HR/노무 리스크
]

def clean_html(text):
    return text.replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

def is_recent_news(pubDate_str):
    try:
        article_date = parsedate_to_datetime(pubDate_str)
        now = datetime.now(article_date.tzinfo)
        return (now - article_date) <= timedelta(hours=24)
    except:
        return True

def main():
    print("🚀 [Morning Briefing: 경영진 봇] 시작...")
    
    if not SLACK_BOT_TOKEN:
        print("❌ SLACK_BOT_TOKEN이 없습니다. Secrets 설정을 확인하세요.")
        return

    all_news_list = []
    seen_titles = set() # 중복 기사 제거용

    # 1. 뉴스 수집
    for keyword in KEYWORDS:
        print(f"   🔍 '{keyword}' 동향 파악 중...", end=" ")
        
        # ★ 수정 포인트: 키워드가 많아졌으므로, 각 키워드당 상위 3개만 수집 (총량 조절)
        result = naver_search.search_naver_news(keyword, display=3) 
        
        if result and "items" in result:
            count = 0
            for item in result['items']:
                title_clean = clean_html(item['title'])
                
                # 중복 기사 & 24시간 지난 기사 제외
                if title_clean not in seen_titles and is_recent_news(item['pubDate']):
                    all_news_list.append({
                        'keyword': keyword,
                        'title': title_clean,
                        'link': item['link']
                    })
                    seen_titles.add(title_clean)
                    count += 1
            print(f"-> {count}건")
        else:
            print("-> 없음")
        time.sleep(0.3) # 검색 차단 방지 딜레이

    if not all_news_list:
        print("수집된 뉴스가 없습니다.")
        return

    print(f"🧠 총 {len(all_news_list)}개의 뉴스를 경영진 관점(CSO)으로 분석 중...")
    
    # AI에게 분석 요청 (요약본, 상세본 2개로 나눠 받음)
    summary_msg, detail_msg = ai_editor.analyze_for_leadership(all_news_list)

    print("📨 경영진 브리핑 전송 중...")
    slack_sender.send_leadership_briefing(summary_msg, detail_msg)
    
    print("🏁 브리핑 완료!")

if __name__ == "__main__":
    main()
