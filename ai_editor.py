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

    # 프롬프트: 보고서체(음슴체/명사형 종결) 완벽 강제
    prompt = f"""
    당신은 파스토(Fassto)의 최고 전략 책임자(CSO)입니다.
    경영진이 시장 흐름을 30초 만에 파악할 수 있도록, 가장 중요한 뉴스 5개를 요약하세요.

    [입력된 뉴스 데이터]
    {news_text_dump}

    [작성 원칙 - 🚨엄격 준수🚨]
    1. **말투 강제:** 모든 문장의 끝은 반드시 '~함', '~됨', '~전망', '~요망', '~할 것', '~필요' 등 **짧은 명사형(보고서체/개조식)**으로 끝내세요. ("~합니다", "~하십시오", "~해야 합니다" 절대 사용 금지)
    2. 기사당 요약은 **딱 1문장(50자 내외)**으로, '팩트+파스토의 리스크/기회'만 극도로 압축하세요.
    3. 아래 [출력 템플릿]의 기호와 띄어쓰기를 100% 똑같이 유지하세요.

    [출력 템플릿]
    🔥 *{today} 모닝 브리핑*

    📰 *오늘의 핵심 뉴스 (Top 5)*
    * <링크주소|기사제목> - (핵심 팩트 및 시사점 1줄 요약. 명사형 종결)
    * <링크주소|기사제목> - (핵심 팩트 및 시사점 1줄 요약. 명사형 종결)
    * <링크주소|기사제목> - (핵심 팩트 및 시사점 1줄 요약. 명사형 종결)
    * <링크주소|기사제목> - (핵심 팩트 및 시사점 1줄 요약. 명사형 종결)
    * <링크주소|기사제목> - (핵심 팩트 및 시사점 1줄 요약. 명사형 종결)

    🔭 *경영 시사점 (Executive Insight)*
    * *시장 흐름:* (핵심 동향 1줄. 명사형 종결)
    * *대응 전략:* (파스토의 취해야 할 포지셔닝 1줄. 명사형 종결)
    ===SPLIT===
    ⚡ *부서별 Action Item*
    * 💼 *Sales:* (영업/고객방어 지시 1줄. '~할 것' 또는 '~요망'으로 종결)
    * 💻 *Tech:* (IT/기술 점검 지시 1줄. '~할 것' 또는 '~요망'으로 종결)
    * 👥 *HR:* (인사/조직 지시 1줄. '~할 것' 또는 '~요망'으로 종결)
    * 💰 *Finance:* (재무/투자 지시 1줄. '~할 것' 또는 '~요망'으로 종결)
    * 🚛 *SCM:* (물류운영/단가방어 지시 1줄. '~할 것' 또는 '~요망'으로 종결)
    """

    try:
        model = genai.GenerativeModel("gemini-2.5-flash") 
        response = model.generate_content(prompt, generation_config={"temperature": 0.3}) 
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
