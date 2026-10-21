"""해외 물류·로봇 매체 RSS — 네이버 API 는 국내 기사만 커버해 글로벌 동향(Amazon·Exotec·CEVA 등)이 빠진다."""
import html
import re
import xml.etree.ElementTree as ET

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; FasstoBriefingBot/2.0; +https://www.fassto.com)"}
# (카테고리, 매체명, RSS 2.0 URL) — 2026-10-21 응답 확인. 죽은 피드는 로그만 남기고 건너뛴다
FEEDS = [
    ("AMR·물류로봇", "The Robot Report", "https://www.therobotreport.com/feed/"),
    ("AMR·물류로봇", "Robotics & Automation News", "https://roboticsandautomationnews.com/feed/"),
    ("풀필먼트 경쟁사", "DC Velocity", "https://www.dcvelocity.com/rss/articles"),
    ("풀필먼트 경쟁사", "Supply Chain Dive", "https://www.supplychaindive.com/feeds/news/"),
    ("풀필먼트 경쟁사", "Supply Chain 24/7", "https://www.supplychain247.com/rss"),
    ("AMR·물류로봇", "TechNode", "https://technode.com/feed/"),
]


def fetch_feed(url, limit=15):
    """[{title, link, description, pubDate}] 최신순 limit 건. 실패 시 예외 (호출부가 건너뜀)."""
    r = requests.get(url, headers=UA, timeout=10)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for it in root.iter("item"):
        g = lambda tag: html.unescape((it.findtext(tag) or "").strip())
        desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", g("description"))).strip()
        out.append({"title": g("title"), "link": g("link"), "description": desc[:300], "pubDate": g("pubDate")})
    return out[:limit]
