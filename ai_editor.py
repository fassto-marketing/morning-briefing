import google.generativeai as genai
import datetime
import os 

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

def analyze_for_leadership(all_articles):
    if not GOOGLE_API_KEY:
        return "🚨 API Key 오류", "오류"

    # 1. 뉴스 데이터 정리
    news_text_dump = ""
    for idx, item in enumerate(all_articles, 1):
        news_text_dump += f"{idx}. [{item['keyword']}] {item['title']} (링크:{item['link']})\n"

    # 2. 한국 시간(KST) 계산 (서버 시간 이슈 해결)
    utc_now = datetime.datetime.utcnow()
    kst_now = utc_now + datetime.timedelta(hours=9)
    today = kst_now.strftime("%Y년 %m월 %d일")
    weekday = kst_now.strftime("%A") # 요일 표시

    # 3. 경영진 브리핑 전용 프롬프트
    prompt = f"""
    당신은 파스토(Fassto)의 **'최고 전략 책임자(CSO)'**입니다.
    경영진(C-Level)과 각 부서 리더들이 매일 아침 봐야 할 **'일일 비즈니스 인텔리전스 리포트'**를 작성하세요.

    [오늘의 뉴스 데이터]
    {news_text_dump}

    ------------------------------------------------------------------
    **[작성 원칙]**
    1. **거시적 관점:** 단순 사실 나열이 아니라, 이 뉴스가 '물류/이커머스 업계'에 미칠 파장을 해석하세요.
    2. **경영자 언어:** "했습니다/입니다" 대신 **"~것으로 판단됨", "~요망", "~검토 필요"** 등 간결하고 힘 있는 어조를 사용하세요.
    3. **명확한 분리:** 전체 요약과 부서별 지침을 구분선으로 완벽히 쪼개주세요.

    ------------------------------------------------------------------
    **[출력 파트 1: 경영진 브리핑 (메인 메시지용)]**
    - 제목: 🏛️ *{today} Fassto Daily Leadership Brief* ({weekday})
    - **🚨 Market Watch (업계 주요 동향):** 가장 파급력이 큰 이슈 3가지를 선정하여 1줄 요약(링크 포함).
    - **🔭 Executive Summary (경영 시사점):** 위 뉴스들이 우리 회사(파스토)의 사업 방향성(성장, 리스크 관리)에 주는 핵심 시사점 1문단.

    ------------------------------------------------------------------
    **===SPLIT===** (위 구분자를 꼭 넣어주세요. 여기서부터는 댓글로 달릴 내용입니다.)
    ------------------------------------------------------------------

    **[출력 파트 2: 부서별 대응 가이드 (상세 스레드용)]**
    각 리더들이 오늘 챙겨야 할 액션 아이템을 지시하세요. (관련 이슈가 없으면 생략 가능)

    * **💼 Sales & Biz (영업/사업):** 경쟁사 동향 대응 논리, 신규 영업 포인트.
    * **💻 Tech & Product (IT/개발):** 기술 트렌드 적용 검토, 시스템 안정성 관련 이슈.
    * **👥 HR & Culture (인사/조직):** 채용 시장 변화, 조직 문화, 노무 리스크.
    * **💰 Finance & Risk (재무/리스크):** 비용 절감 요인, 투자 시장 동향, 규제 리스크.
    * **🚛 SCM & Operation (운영/물류):** 현장 운영 이슈, 배송 대란 대비, 파트너사 관리.

    """

    try:
        model = genai.GenerativeModel("gemini-2.5-flash") 
        response = model.generate_content(prompt, generation_config={"temperature": 0.7})
        full_text = response.text.replace("**", "*")
        
        # ===SPLIT=== 기준으로 메인 메시지와 댓글(스레드) 메시지를 나눔
        if "===SPLIT===" in full_text:
            parts = full_text.split("===SPLIT===")
            summary_message = parts[0].strip() # 메인 채팅방에 갈 내용
            detail_message = parts[1].strip()  # 댓글(스레드)에 달릴 내용
            return summary_message, detail_message
        else:
            return full_text, "상세 내용 생성 실패"
        
    except Exception as e:
        return f"🚨 에러: {e}", "에러 발생"
