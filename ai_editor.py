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
        news_text_dump += f"기사{idx}: 제목='{item['title']}', 링크='{item['link']}'\n"

    # 2. 한국 시간 계산
    utc_now = datetime.datetime.utcnow()
    kst_now = utc_now + datetime.timedelta(hours=9)
    today = kst_now.strftime("%Y-%m-%d")
    weekday = kst_now.strftime("%A")

    # 3. 팩트 중심 초정밀 프롬프트
    prompt = f"""
    당신은 파스토(Fassto)의 'Daily Intelligence Officer'입니다.
    제공된 뉴스 중 가장 중요한 5개를 엄선하여 뉴스레터 스타일로 요약하세요.

    [입력된 뉴스 데이터]
    {news_text_dump}

    [작성 원칙 - 엄격 준수]
    1. 인사말("안녕하세요" 등), 맺음말, 설명하는 문장을 절대 출력하지 마세요.
    2. "---" 같은 불필요한 구분선이나 의미 없는 기호(*)를 절대 쓰지 마세요.
    3. 주관적 의견을 배제하고 객관적 팩트 위주로 간결하게(개조식) 요약하세요.
    4. 슬랙 하이퍼링크 포맷인 `<링크주소|기사제목>` 형식을 반드시 지키세요.
    5. 아래 제공된 [출력 템플릿]의 형태를 100% 똑같이 유지하고 내용만 채워서 바로 출력하세요.

    [출력 템플릿] (이 형태 그대로 출력할 것)
    🏛️ *{today} 모닝 브리핑 ({weekday})*

    📊 *Market Watch*

    1. <링크주소|기사제목>
    > 핵심 팩트 1~2줄 요약
    > 🏷️ #태그1 #태그2 #태그3

    2. <링크주소|기사제목>
    > 핵심 팩트 1~2줄 요약
    > 🏷️ #태그1 #태그2 #태그3

    3. <링크주소|기사제목>
    > 핵심 팩트 1~2줄 요약
    > 🏷️ #태그1 #태그2 #태그3

    4. <링크주소|기사제목>
    > 핵심 팩트 1~2줄 요약
    > 🏷️ #태그1 #태그2 #태그3

    5. <링크주소|기사제목>
    > 핵심 팩트 1~2줄 요약
    > 🏷️ #태그1 #태그2 #태그3

    🔭 *Executive Summary*
    * 위 뉴스들을 관통하는 시장의 핵심 흐름을 3줄 이내로 통찰력 있게 요약
    ===SPLIT===
    ⚡ *부서별 Action Item*
    * 💼 *Sales:* 경쟁사 동향에 따른 영업 포인트
    * 💻 *Tech:* 기술 트렌드/보안 이슈 점검
    * 👥 *HR:* 채용/조직문화 리스크
    * 💰 *Finance:* 투자/비용 이슈
    * 🚛 *SCM:* 운영/물류 현장 이슈
    """

    try:
        # temperature를 0.3으로 낮춰서 포맷을 엄격하게 지키게 함
        model = genai.GenerativeModel("gemini-2.5-flash") 
        response = model.generate_content(prompt, generation_config={"temperature": 0.3}) 
        full_text = response.text.replace("**", "*")
        
        # AI가 혹시라도 ---를 넣었을 경우 강제 삭제
        full_text = full_text.replace("---", "").strip()
        
        if "===SPLIT===" in full_text:
            parts = full_text.split("===SPLIT===")
            summary_message = parts[0].strip()
            detail_message = parts[1].strip()
            
            # 맨 앞/뒤에 붙은 불필요한 기호(*) 강제 제거
            if summary_message.startswith("*"): summary_message = summary_message[1:].strip()
            if detail_message.startswith("*"): detail_message = detail_message[1:].strip()
            
            return summary_message, detail_message
        else:
            return full_text, "상세 내용 생성 실패"
        
    except Exception as e:
        return f"🚨 에러: {e}", "에러 발생"
