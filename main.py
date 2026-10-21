"""
물류 업계 동향 브리핑 v2 — 수집(네이버) → 후보 선정(Gemini) → 본문 읽기 → 작성(Gemini) → Slack Block Kit
실행: SLACK_CHANNEL_ID 채널로 발송. 테스트는 env SLACK_CHANNEL_ID 를 테스트 채널로 바꿔 실행.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import ai_editor
import article
import naver_search
import slack_sender

KST = ZoneInfo("Asia/Seoul")
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")        # 본 발송 채널 (ID 또는 #채널명)
SLACK_ALERT_CHANNEL_ID = os.environ.get("SLACK_ALERT_CHANNEL_ID")  # 장애 알림(선택) — 전사 채널에 오류를 띄우지 않기 위해 분리
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "sent.json")
STATE_KEEP_DAYS = 14
TOP_N = 5
CANDIDATE_N = 8

# (이모지, 카테고리, 네이버 검색 키워드) — 카테고리 라벨은 슬랙 제목 "🏭 풀필먼트 경쟁사 | …" 에 그대로 노출
CATEGORIES = [
    ("🏭", "풀필먼트 경쟁사", ["풀필먼트", "3PL 물류", "품고 풀필먼트", "두핸즈", "위킵", "테크타카", "CJ대한통운 풀필먼트", "쿠팡 물류센터"]),
    ("🤖", "AMR·물류로봇", ["물류 로봇", "AMR 물류", "물류 자동화", "피킹 로봇", "휴머노이드 물류"]),
    ("🧠", "물류 IT·AI", ["WMS", "물류 AI", "스마트 물류", "오토스토어", "물류 디지털 전환"]),
    ("🛒", "이커머스·플랫폼", ["이커머스 물류", "알리익스프레스 물류", "테무 물류", "네이버 도착보장", "쿠팡 로켓배송"]),
    ("📜", "정책·규제", ["이커머스 규제", "유통 규제", "택배 기사", "물류 중대재해"]),
    ("🏢", "파스토", ["파스토"]),
]
EMOJI_OF = {label: emoji for emoji, label, _ in CATEGORIES}

# 한국 공휴일 (대체·임시공휴일 포함, 2026~2027) — news-bot main.py 와 동일 목록. 신규 지정 시 양쪽 함께 갱신.
KR_HOLIDAYS = {
    "2026-01-01", "2026-02-16", "2026-02-17", "2026-02-18", "2026-03-01", "2026-03-02", "2026-05-05",
    "2026-05-24", "2026-05-25", "2026-06-03", "2026-06-06", "2026-08-15", "2026-08-17",
    "2026-09-24", "2026-09-25", "2026-09-26", "2026-10-03", "2026-10-05", "2026-10-09", "2026-12-25",
    "2027-01-01", "2027-02-06", "2027-02-07", "2027-02-08", "2027-02-09", "2027-03-01",
    "2027-05-05", "2027-05-13", "2027-06-06", "2027-06-07", "2027-08-15", "2027-08-16",
    "2027-09-14", "2027-09-15", "2027-09-16", "2027-10-03", "2027-10-04", "2027-10-09", "2027-10-11", "2027-12-25",
}
WEEKDAY_KO = "월화수목금토일"


def _is_offday(d):
    return d.weekday() >= 5 or d.strftime("%Y-%m-%d") in KR_HOLIDAYS


def _clean(text):
    return (text.replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
            .replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&apos;", "'"))


def _load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _save_state(entries, today):
    cutoff = (today - timedelta(days=STATE_KEEP_DAYS)).strftime("%Y-%m-%d")
    entries = [e for e in entries if e.get("date", "") >= cutoff]
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)


def collect(lookback_hours, sent_links):
    now = datetime.now(KST)
    articles, seen_links, seen_titles = [], set(), set()
    for _, label, keywords in CATEGORIES:
        for kw in keywords:
            res = naver_search.search_naver_news(kw, display=10)
            n = 0
            for it in (res or {}).get("items", []):
                link = it.get("originallink") or it["link"]
                title = _clean(it["title"])
                key = "".join(ch for ch in title if ch.isalnum())
                try:
                    pub = parsedate_to_datetime(it["pubDate"])
                except Exception:
                    continue
                if (now - pub) > timedelta(hours=lookback_hours):
                    continue
                if link in seen_links or key in seen_titles or link in sent_links or it["link"] in sent_links:
                    continue
                seen_links.add(link); seen_titles.add(key)
                articles.append({
                    "category": label, "keyword": kw, "title": title, "link": link,
                    "description": _clean(it.get("description", "")),
                    "pubdate": pub.astimezone(KST).strftime("%m/%d"),
                })
                n += 1
            print(f"   🔍 [{label}] {kw} → {n}건")
            time.sleep(0.3)
    return articles


def main():
    print("🚀 [물류 업계 동향 브리핑 v2] 시작")
    if not SLACK_CHANNEL_ID or not slack_sender.SLACK_BOT_TOKEN:
        print("❌ SLACK_BOT_TOKEN / SLACK_CHANNEL_ID 없음")
        sys.exit(1)
    print(f"   🤖 슬랙 봇: {slack_sender.bot_identity()} → 채널 {SLACK_CHANNEL_ID}")

    now = datetime.now(KST)
    today = now.date()
    if now.strftime("%Y-%m-%d") in KR_HOLIDAYS or now.weekday() >= 5:
        print(f"📅 {today} 휴일 — 스킵")
        return

    # 어제부터 거슬러 올라가며 주말·공휴일만큼 수집 범위 확장 (월요일 = 72h)
    lookback_hours, check = 24, now - timedelta(days=1)
    while _is_offday(check):
        lookback_hours += 24
        check -= timedelta(days=1)
    start = today - timedelta(hours=lookback_hours)
    range_label = f" ({start.month}/{start.day}~{today.month}/{today.day} 주말·휴일 포함)" if lookback_hours > 24 else ""
    date_label = f"{today} ({WEEKDAY_KO[today.weekday()]})"
    print(f"📅 {date_label} · 수집 범위 최근 {lookback_hours}시간")

    state = _load_state()
    sent_links = {e["link"] for e in state}
    recent_titles = [e["title"] for e in state][-40:]

    articles = collect(lookback_hours, sent_links)
    print(f"   📊 후보 {len(articles)}건 (중복·기발송 제외)")
    if not articles:
        print("수집된 뉴스가 없습니다.")
        return

    print("🧠 1차 선정 중...")
    picks = ai_editor.pick_candidates(articles, recent_titles, n=CANDIDATE_N)
    if not picks:
        raise RuntimeError("1차 선정 결과 없음")
    candidates = [articles[i] for i in picks]

    print(f"📖 본문 읽는 중 ({len(candidates)}건)...")
    for a in candidates:
        a["body"], a["site"] = article.fetch(a["link"])
        print(f"   {'✅' if a['body'] else '⚠️'} {a['site'] or '-'} | {a['title'][:50]}")

    print("✍️ 브리핑 작성 중...")
    items = ai_editor.write_briefing(candidates, [label for _, label, _ in CATEGORIES], n=TOP_N)
    if not items:
        raise RuntimeError("브리핑 작성 결과 없음")
    for it in items:  # 매체명: AI가 정리한 이름 우선(og:site_name 은 "(주) 서울경제티브이" 식 법인명이 섞임), 없으면 메타
        it["source"] = it["source"] or candidates[it["idx"]].get("site") or urlparse(candidates[it["idx"]]["link"]).hostname or ""
        print(f"   📰 {EMOJI_OF.get(it['category'], '📰')} {it['category']} | {it['headline']} ({it['source'] or '출처 불명'}) {candidates[it['idx']]['link']}")

    text, blocks = slack_sender.build_message(date_label, range_label, [(it, candidates[it["idx"]]["link"]) for it in items], EMOJI_OF)
    print("📨 슬랙 전송 중...")
    ts = slack_sender.post_briefing(SLACK_CHANNEL_ID, text, blocks)
    print(f"✅ 전송 완료 (ts={ts}) — {len(items)}건")

    state += [{"date": str(today), "title": candidates[it["idx"]]["title"], "link": candidates[it["idx"]]["link"]} for it in items]
    _save_state(state, today)
    print("🏁 완료")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 실패: {e}")
        slack_sender.post_alert(SLACK_ALERT_CHANNEL_ID, f"⚠️ *[물류 동향 브리핑]* 오늘 발송 실패: `{str(e)[:200]}`\nGitHub Actions 에서 Re-run 해주세요.")
        sys.exit(1)
