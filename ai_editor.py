"""
ai_editor.py — Gemini 2-pass 큐레이션
  1) pick_candidates : 제목·요약만 보고 후보 N건 선정 (카테고리 다양성, 최근 발송분 제외)
  2) write_briefing  : 후보 본문을 읽고 최종 5건 작성 (불릿 2개 + 파스토 시사점) → JSON
news-bot(ai_editor.py)의 모델 폴백·JSON 파서를 그대로 가져왔다.
"""
import json
import os
import time

from google import genai

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None

# 2.0/1.5 flash 는 2026-10-01 퇴역(404). 2.5-flash 는 무료 티어에서 429/503 반복 — 구글 권장 후속을 1순위로
MODELS = ["gemini-3.8-flash", "gemini-2.5-flash"]
MAX_RETRIES_PER_MODEL = 2
RETRY_DELAY = 30


def _call_gemini(prompt):
    for model_name in MODELS:
        for attempt in range(MAX_RETRIES_PER_MODEL):
            try:
                print(f"   🤖 {model_name} 호출 (시도 {attempt + 1}/{MAX_RETRIES_PER_MODEL})...")
                config = {"temperature": 0.4, "response_mime_type": "application/json"}
                if model_name.startswith("gemini-2.5"):
                    config["thinking_config"] = {"thinking_budget": 4096}
                res = client.models.generate_content(model=model_name, contents=prompt, config=config)
                return res.text
            except Exception as e:
                err = str(e)
                retryable = any(k in err for k in ["503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded"])
                if retryable and attempt < MAX_RETRIES_PER_MODEL - 1:
                    print(f"   ⏳ {model_name} 일시 오류 — {RETRY_DELAY}초 후 재시도")
                    time.sleep(RETRY_DELAY)
                elif retryable or "404" in err or "NOT_FOUND" in err:
                    print(f"   ⚠️ {model_name} 실패({err[:80]}) — 다음 모델로 폴백")
                    break
                else:
                    raise
    raise RuntimeError(f"모든 모델 실패: {', '.join(MODELS)}")


def _parse_json(raw):
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0] if "```" in text else text
    return json.loads(text.strip())


def pick_candidates(articles, recent_titles, n=8):
    """후보 index 목록 반환 (articles 의 0-based index)."""
    if not client:
        raise RuntimeError("GOOGLE_API_KEY 없음")
    lines = []
    for i, a in enumerate(articles):
        lines.append(f"{i}. [{a['category']}] {a['title']} ({a['pubdate']})\n   요약: {a['description'][:150]}")
    recent = "\n".join(f"- {t}" for t in recent_titles) or "- 없음"
    prompt = f"""당신은 파스토(FASSTO, AI 스마트 풀필먼트·물류대행 기업)의 산업 동향 리서처입니다.
아래 뉴스 후보 중 오늘 사내에 공유할 가치가 큰 기사 {n}건을 고르세요.

[선정 기준]
- 파스토 사업(풀필먼트·3PL·물류센터 자동화·WMS/IT·이커머스 물류)과 직접 관련된 업계 동향 우선.
- 서로 다른 사건이어야 하며, 같은 사건을 다룬 기사는 1건만 고른다 (가장 상세한 기사).
- 카테고리가 고르게 섞이도록 한다. 같은 카테고리에서 3건 이상 고르지 않는다.
- '파스토'가 직접 언급된 기사가 있으면 반드시 포함한다.
- 제외: 주가·증권 리포트, 단순 인사·부고, 행사 안내, 광고성 보도자료, 기사와 무관한 키워드 매칭.
- 아래 [최근 발송된 제목]과 같은 사건은 제외한다.

[최근 발송된 제목]
{recent}

[뉴스 후보]
{chr(10).join(lines)}

[출력 — JSON만]
{{"picks": [번호, 번호, ...]}}
"""
    data = _parse_json(_call_gemini(prompt))
    picks = [int(i) for i in data.get("picks", []) if str(i).lstrip("-").isdigit()]
    return [i for i in dict.fromkeys(picks) if 0 <= i < len(articles)][:n]


def write_briefing(candidates, categories, n=5):
    """candidates: dict(list) with body/site. 반환: [{idx, category, headline, bullets, insight, source}]"""
    blocks = []
    for i, a in enumerate(candidates):
        body = a.get("body") or f"(본문 수집 실패 — 요약만 사용) {a['description']}"
        blocks.append(f"### 후보 {i} [{a['category']}] {a['title']}\n매체: {a.get('site') or '불명'} / 게재일: {a['pubdate']}\n본문: {body}")
    cat_list = " / ".join(categories)
    prompt = f"""당신은 파스토(FASSTO)의 산업 동향 브리핑 에디터입니다. 파스토는 AI 스마트 풀필먼트(물류대행) 기업으로,
자체 WMS와 자동화 물류센터를 운영하며 이커머스 셀러·제조사 물류를 대행합니다.
아래 후보 기사를 읽고 전사 공유용 '물류 업계 동향 브리핑' 핵심 뉴스 {n}건을 작성하세요.

[절대 규칙]
1. 팩트 그라운딩: 본문에 명시된 사실·수치·고유명사만 쓴다. 본문에 없는 수치·추정·일반론을 지어내지 않는다.
2. 같은 사건은 1건만. 서로 다른 카테고리가 섞이도록 고른다. 후보가 {n}건 미만이면 있는 만큼만 쓴다.
3. 브랜드 표기는 '파스토'만 사용한다.
4. 문체: 사내 보고용 존댓말 서술체("~합니다", "~입니다"). 이모지·과장·감탄 금지.

[항목 형식]
- category: 다음 중 하나 그대로: {cat_list}
- headline: 기사 핵심을 담은 제목, 40자 이내, 마침표 없음. 예) "카덱스, 기존 WMS를 유지한 채 WES로 오토스토어를 연동한 사례"
- bullets: 정확히 2개. 각각 한 문장(100자 이내)으로 본문의 핵심 팩트를 수치·고유명사와 함께 쓴다.
  예) "미국 워런 캣은 520㎡ 공간에 오토스토어 R5 20대와 빈 2만 852개를 구축해 하루 피킹 3,648라인을 처리합니다."
- insight: '파스토 시사점' 1~2문장(140자 이내). 이 뉴스가 파스토에 주는 기회·리스크·참고 모델을 구체적으로 쓴다.
  예) "'WMS는 유지하고 WES만 붙이는' 구조는 파스토 WMS에 다양한 설비를 연동할 때 참고 모델이 됩니다."
- source: 매체명(한글 또는 영문 고유명). 본문의 매체 정보로 판단하고 모르면 빈 문자열.

[후보 기사]
{chr(10).join(blocks)}

[출력 — JSON만]
{{"items": [{{"idx": 후보번호, "category": "", "headline": "", "bullets": ["", ""], "insight": "", "source": ""}}]}}
"""
    data = _parse_json(_call_gemini(prompt))
    items = []
    for it in data.get("items", []):
        try:
            idx = int(it["idx"])
            if not (0 <= idx < len(candidates)):
                continue
            bullets = [str(b).strip() for b in it.get("bullets", []) if str(b).strip()][:2]
            if not it.get("headline") or not bullets:
                continue
            items.append({
                "idx": idx,
                "category": str(it.get("category", "")).strip(),
                "headline": str(it["headline"]).strip().rstrip("."),
                "bullets": bullets,
                "insight": str(it.get("insight", "")).strip(),
                "source": str(it.get("source", "")).strip(),
            })
        except (KeyError, ValueError, TypeError):
            continue
    seen = set()
    return [i for i in items if not (i["idx"] in seen or seen.add(i["idx"]))][:n]
