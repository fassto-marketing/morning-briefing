"""
물류 업계 동향 브리핑 v2 — 수집(네이버) → 후보 선정(Gemini) → 본문 읽기 → 작성(Gemini) → Slack Block Kit
실행: SLACK_CHANNEL_ID 채널로 발송. 테스트는 env SLACK_CHANNEL_ID 를 테스트 채널로 바꿔 실행.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, time as dtime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import ai_editor
import article
import feeds
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
    ("🏛️", "정책·규제", ["이커머스 규제", "유통 규제", "택배 기사", "물류 중대재해"]),
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
    "2027-09-14", "2027-09-15", "2027-09-16", "2027-10-03", "2027-10-04", "2027-10-09", "2027-10-11", "2027-12-25", "2027-12-27",
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


def _title_key(title):
    return "".join(ch for ch in title if ch.isalnum())


def collect(cutoff, sent_links, sent_keys):
    """cutoff(KST, aware) 이후 게재 기사 (네이버 + 해외 RSS). 네이버 API 가 전부 실패하면 예외 — '뉴스 0건' 으로 둔갑시키지 않는다."""
    articles, seen_links, seen_titles = [], set(), set(sent_keys)

    def add(it, label, kw, site=""):
        link = it.get("originallink") or it.get("link")
        title = _clean(it.get("title", ""))
        if not link or not title:
            return False
        key = _title_key(title)
        try:
            pub = parsedate_to_datetime(it["pubDate"])
        except Exception:
            return False
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=KST)
        if pub < cutoff or link in seen_links or key in seen_titles or link in sent_links or it.get("link") in sent_links:
            return False
        seen_links.add(link); seen_titles.add(key)
        articles.append({
            "category": label, "keyword": kw, "title": title, "link": link, "site": site,
            "description": _clean(it.get("description", "")),
            "pubdate": pub.astimezone(KST).strftime("%m/%d"),
        })
        return True

    fails = total = 0
    for _, label, keywords in CATEGORIES:
        for kw in keywords:
            res = naver_search.search_naver_news(kw, display=10)
            total += 1
            if res is None:
                fails += 1
            n = sum(add(it, label, kw) for it in (res or {}).get("items", []))
            print(f"   🔍 [{label}] {kw} → {n}건")
            time.sleep(0.3)
    if fails == total:
        raise RuntimeError(f"네이버 API 전부 실패 ({fails}/{total}) — 키·쿼터 확인")
    for label, name, url in feeds.FEEDS:
        try:
            items = feeds.fetch_feed(url)
        except Exception as e:
            print(f"   ⚠️ RSS 실패 {name}: {str(e)[:80]}")
            continue
        n = sum(add(it, label, name, site=name) for it in items)
        print(f"   🌐 [{label}] {name} → {n}건")
    return articles


def window(now):
    """(cutoff, date_label, range_label) — 직전 평일(=마지막 발송일) 07:00 부터 수집.
    실행 시각 기준 N×24h 로 자르면 Actions 지연 편차(08:10 vs 09:40)만큼 영구 누락 구간이 생긴다. 겹침은 sent_links 가 거른다."""
    today = now.date()
    check = now - timedelta(days=1)
    while _is_offday(check):
        check -= timedelta(days=1)
    last_workday = check.date()
    cutoff = datetime.combine(last_workday, dtime(7, 0), tzinfo=KST)
    gap = [last_workday + timedelta(days=k) for k in range(1, (today - last_workday).days)]
    tag = "주말 포함" if any(d.weekday() >= 5 for d in gap) else "휴일 포함"
    start = last_workday + timedelta(days=1)
    range_label = f" ({start.month}/{start.day}~{today.month}/{today.day} {tag})" if gap else ""
    return cutoff, f"{today} ({WEEKDAY_KO[today.weekday()]})", range_label


def main():
    print("🚀 [물류 업계 동향 브리핑 v2] 시작")
    if not SLACK_CHANNEL_ID or not slack_sender.SLACK_BOT_TOKEN:
        print("❌ SLACK_BOT_TOKEN / SLACK_CHANNEL_ID 없음")
        sys.exit(1)
    print(f"   🤖 슬랙 봇: {slack_sender.bot_identity()} → 채널 {SLACK_CHANNEL_ID}")

    now = datetime.now(KST)
    today = now.date()
    # 휴일 스킵은 본 채널 발송에만 — 테스트 발송(ALLOW_RESEND)은 휴일에도 직전 평일까지의 기사로 나간다
    if not os.environ.get("ALLOW_RESEND") and _is_offday(now):
        print(f"📅 {today} 휴일 — 스킵")
        return

    cutoff, date_label, range_label = window(now)
    print(f"📅 {date_label} · 수집 범위 {cutoff:%m/%d %H:%M} 이후")

    state = _load_state()
    # 지연 도착한 예약 실행 + 수동 실행이 겹쳐도 본 채널엔 하루 1회. 테스트 발송(ALLOW_RESEND)은 예외
    if str(today) in {e["date"] for e in state} and not os.environ.get("ALLOW_RESEND"):
        print("📭 오늘 이미 발송됨 — 스킵")
        return
    sent_links = {e["link"] for e in state}
    sent_keys = {_title_key(e["title"]) for e in state}
    recent_titles = [e["title"] for e in state][-40:]

    articles = collect(cutoff, sent_links, sent_keys)
    print(f"   📊 후보 {len(articles)}건 (중복·기발송 제외)")
    if not articles:
        print("수집된 뉴스가 없습니다.")
        slack_sender.post_alert(SLACK_ALERT_CHANNEL_ID, "📭 *[물류 동향 브리핑]* 오늘 수집된 기사가 0건이라 발송을 건너뜁니다.")
        return

    print("🧠 1차 선정 중...")
    picks = ai_editor.pick_candidates(articles, recent_titles, n=CANDIDATE_N)
    if not picks:
        raise RuntimeError("1차 선정 결과 없음")
    candidates, used = [], set()
    for idx, also in picks:  # 같은 사건의 다른 기사는 extras 로 묶어 출처를 여러 개 단다
        if idx in used:
            continue
        used.add(idx)
        a = articles[idx]
        a["extras"] = [articles[j] for j in also if j not in used and not used.add(j)][:2]
        candidates.append(a)

    print(f"📖 본문 읽는 중 ({len(candidates)}건 + 추가 출처 {sum(len(c['extras']) for c in candidates)}건)...")
    for a in candidates:
        for x in [a] + a["extras"]:
            x["body"], site = article.fetch(x["link"])
            x["site"] = x.get("site") or site or urlparse(x["link"]).hostname or ""  # AI 정리명 > RSS 매체명 > og:site_name > 도메인
        print(f"   {'✅' if a['body'] else '⚠️'} {a['site'] or '-'} | {a['title'][:50]}")

    print("✍️ 브리핑 작성 중...")
    items, daily_insight = ai_editor.write_briefing(candidates, [label for _, label, _ in CATEGORIES], n=TOP_N)
    if not items:
        raise RuntimeError("브리핑 작성 결과 없음")
    rows = []
    for it in items:
        c = candidates[it["idx"]]
        links = [(it["source"] or c["site"], c["link"])] + [(x["site"], x["link"]) for x in c["extras"]]
        rows.append((it, links))
        print(f"   📰 {EMOJI_OF.get(it['category'], '📰')} {it['category']} | {it['headline']} ({' · '.join(s for s, _ in links)}) {c['link']}")
    print(f"   🎯 {daily_insight}")

    text, blocks = slack_sender.build_message(date_label, range_label, rows, EMOJI_OF, daily_insight)
    print("📨 슬랙 전송 중...")
    ts = slack_sender.post_briefing(SLACK_CHANNEL_ID, text, blocks)
    global SENT
    SENT = True
    print(f"✅ 전송 완료 (ts={ts}) — {len(items)}건")

    for it in items:
        c = candidates[it["idx"]]
        state += [{"date": str(today), "title": x["title"], "link": x["link"]} for x in [c] + c["extras"]]
    _save_state(state, today)
    print("🏁 완료")


SENT = False  # 슬랙 발송 뒤에 죽으면 Re-run 금지 (중복 발송)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 실패: {e}")
        advice = "이미 발송은 됐습니다 — *Re-run 금지*, state/sent.json 만 확인" if SENT else "GitHub Actions 에서 Re-run 해주세요"
        slack_sender.post_alert(SLACK_ALERT_CHANNEL_ID, f"⚠️ *[물류 동향 브리핑]* 오늘 실행 실패: `{str(e)[:200]}`\n{advice}.")
        sys.exit(1)
