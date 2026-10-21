"""기사 본문·매체명 추출 — 제목·요약(≤200자)만으로는 수치가 빈약해 본문을 직접 읽는다."""
import re
import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; FasstoBriefingBot/2.0; +https://www.fassto.com)"}
# 국내 언론사·포털에서 흔한 본문 컨테이너 (앞에서부터 첫 매치 사용)
BODY_SELECTORS = [
    "#dic_area", "#articleBody", "#article-view-content-div", "#articeBody",
    "[itemprop=articleBody]", ".article_body", "#news_body_area", "#CmAdContent",
    ".news_body", "#article_body", ".article-body", "article",
]


def fetch(url, max_chars=2500):
    """(본문 텍스트, 매체명) — 실패하면 ("", ""). 호출부는 요약문으로 대체한다."""
    try:
        r = requests.get(url, headers=UA, timeout=10)
        r.raise_for_status()
        if not r.encoding or r.encoding.lower() == "iso-8859-1":  # charset 헤더 없는 EUC-KR 사이트
            r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"   ⚠️ 본문 수집 실패 ({url[:60]}): {e}")
        return "", ""

    for t in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "figure"]):
        t.decompose()
    for t in soup.select('[hidden], [aria-hidden="true"], [style*="display:none"], [style*="display: none"]'):
        t.decompose()  # 숨긴 텍스트(프롬프트 주입·광고)는 근거에서 제외

    node = None
    for sel in BODY_SELECTORS:
        node = soup.select_one(sel)
        if node:
            break
    if node:
        text = node.get_text(" ", strip=True)
    else:
        text = " ".join(p.get_text(" ", strip=True) for p in soup.find_all("p"))
    text = re.sub(r"\s+", " ", text).strip()[:max_chars]

    site = soup.find("meta", attrs={"property": "og:site_name"})
    site_name = site["content"].strip()[:40] if site and site.get("content") else ""
    return text, site_name
