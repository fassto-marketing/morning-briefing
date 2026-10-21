"""Slack Block Kit 렌더링 — 포맷은 코드가 고정하고 AI는 내용(JSON)만 채운다."""
import os
import requests

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")


def _api(method, payload):
    return requests.post(
        f"https://slack.com/api/{method}",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json"},
        json=payload, timeout=15,
    ).json()


def bot_identity():
    r = _api("auth.test", {})
    return r.get("user") if r.get("ok") else f"auth.test 실패: {r.get('error')}"


def _item_block(emoji, item, links):
    """links: [(매체명, url), ...] — 같은 사건의 여러 출처를 ' · ' 로 잇는다"""
    elements = [
        {"type": "rich_text_section", "elements": [
            {"type": "text", "text": f"{emoji} {item['category']} | {item['headline']}", "style": {"bold": True}},
        ]},
        {"type": "rich_text_list", "style": "bullet", "elements": [
            {"type": "rich_text_section", "elements": [{"type": "text", "text": b}]} for b in item["bullets"]
        ]},
    ]
    if item.get("insight"):
        elements.append({"type": "rich_text_quote", "elements": [
            {"type": "text", "text": "💡 파스토 시사점: ", "style": {"bold": True}},
            {"type": "text", "text": item["insight"], "style": {"bold": True}},
        ]})
    link_els = [{"type": "text", "text": "🔗 "}]
    for i, (name, url) in enumerate(links):
        if i:
            link_els.append({"type": "text", "text": " · "})
        link_els.append({"type": "link", "url": url, "text": name or "기사 보기"})
    elements.append({"type": "rich_text_section", "elements": link_els})
    return {"type": "rich_text", "elements": elements}


def build_message(date_label, range_label, items, emoji_of, daily_insight=""):
    """items: [(item, links)] — 반환 (text, blocks)"""
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "📦 물류 업계 동향 브리핑", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"_{date_label} · 핵심 뉴스 {len(items)}건{range_label}_"}]},
        {"type": "divider"},
    ]
    for item, links in items:
        blocks.append(_item_block(emoji_of.get(item["category"], "📰"), item, links))
        blocks.append({"type": "divider"})
    if daily_insight:
        blocks.append({"type": "rich_text", "elements": [{"type": "rich_text_quote", "elements": [
            {"type": "text", "text": "🎯 오늘의 한 줄 인사이트: ", "style": {"bold": True}},
            {"type": "text", "text": daily_insight},
        ]}]})
    text = f"📦 물류 업계 동향 브리핑 {date_label} — " + " / ".join(i["headline"] for i, _ in items)
    return text, blocks


def post_briefing(channel, text, blocks):
    r = _api("chat.postMessage", {"channel": channel, "text": text, "blocks": blocks, "unfurl_links": False, "unfurl_media": False})
    if not r.get("ok"):
        raise RuntimeError(f"슬랙 전송 실패: {r.get('error')} {r.get('response_metadata', '')}")
    return r.get("ts")


def post_alert(channel, text):
    if not channel:
        return
    r = _api("chat.postMessage", {"channel": channel, "text": text, "unfurl_links": False})
    if not r.get("ok"):
        print(f"   ⚠️ 알림 전송 실패: {r.get('error')}")
