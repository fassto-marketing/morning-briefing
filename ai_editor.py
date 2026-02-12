import google.generativeai as genai
import datetime
import os 

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

def analyze_for_leadership(all_articles):
    if not GOOGLE_API_KEY:
        return "🚨 API Key 오류", "오류"

    news_text_dump = ""
    for idx, item in enumerate(all_articles, 1):
        news_text_dump += f"기사{idx}: 제목='{item['title']}', 링크='{item['link']}'\n"

    utc_now = datetime.datetime.utcnow()
    kst_now = utc_now + datetime.timedelta(hours=9)
    today = kst_now.strftime("%Y-%m-%d")

    # 프롬프트: 마케팅팀 브리핑 스타일로 극도로 압축 (태그, 줄바꿈 제거)
    prompt = f"""
    당신은 파스토(Fassto)의 최고 전략 책임자(CSO)입니다.
    경영진이 시장 흐름을 30초 만에 파악할 수 있도록, 가장 중요한 뉴스 5개를 '초간결'하게 요약하세요.

    [입력된 뉴스 데이터]
    {news_text_dump}

    [작성 원칙 - 엄격 준수]
    1. 인사말, 맺음말, 불필요한 기호(--- 등)를 절대 쓰지 마세요.
    2. 기사당 요약은 무조건 **'1줄'**로 끝내세요. (팩트와 파스토에 미치는 영향을 한 문장으로 압축)
    3. 해시태그(🏷️)나 [Fact], [Impact] 같은 구분자를 절대 넣지 마세요.
    4. 아래 [출력 템플릿]의 형태를 100% 똑같이 유지하세요.

    [출력 템플릿]
    🔥 *{today} 경영진 모닝 브리핑*

    📰 *오늘의 핵심 뉴스 (Top 5)*
    * <링크주소|기사제목> - (핵심 팩트 및 시사점 1줄 요약)
    * <링크주소|기사제목> - (핵심 팩트 및 시사점 1줄 요약)
    * <링크주소|기사제목> - (핵심 팩트 및 시사점 1줄 요약)
    * <링크주소|기사제목> - (핵심 팩트 및 시사점 1줄 요약)
    * <링크주소|기사제목> - (핵심 팩트 및 시사점 1줄 요약)

    🔭 *경영 시사점 (Executive Insight)*
    * 시장 흐름: (전체적인 시장의 핵심 동향 1줄)
    * 대응 전략: (파스토가 즉시 취해야 할 전사적 포지셔닝/전략 1줄)
    ===SPLIT===
    ⚡ *부서별 Action Item*
    * 💼 Sales: (구체적인 영업/고객방어 지시 1줄)
    * 💻 Tech: (IT/기술 점검 지시 1줄)
    * 👥 HR: (인사/조직/채용 지시 1줄)
    * 💰 Finance: (재무/투자/비용 지시 1줄)
    * 🚛 SCM: (물류운영/단가방어 지시 1줄)
    """

    try:
        model = genai.GenerativeModel("gemini-2.5-flash") 
        response = model.generate_content(prompt, generation_config={"temperature": 0.4}) 
        full_text = response.text.replace("**", "*")
        
        if "===SPLIT===" in full_text:
            parts = full_text.split("===SPLIT===")
            summary_message = parts[0].strip()
            detail_message = parts[1].strip()
            return summary_message, detail_message
        else:
            return full_text, "상세 내용 생성 실패"
        
    except Exception as e:
        return f"🚨 에러: {e}", "에러 발생"
