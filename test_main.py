"""main.py 발송 단계 — 슬랙 응답 유실이면 발송으로 기록(대체·백업 실행 중복 발송 방지), 연결 자체 실패면 예외(→ exit 1 → 대체 실행).
실행: python test_main.py (네트워크·실제 state 파일 사용 안 함)"""
import json
import os
import tempfile
from datetime import datetime
from email.utils import format_datetime

os.environ.update(SLACK_CHANNEL_ID="C_TEST", SLACK_ALERT_CHANNEL_ID="C_ALERT", SLACK_BOT_TOKEN="x")
os.environ.pop("ALLOW_RESEND", None)
import main
import requests
from main import ai_editor, article, feeds, naver_search, slack_sender

main.STATE_PATH = os.path.join(tempfile.mkdtemp(), "sent.json")
main._is_offday = lambda d: False
main.time.sleep = lambda s: None
feeds.FEEDS = []
item = {"title": "기사", "link": "https://e.x/1", "description": "d", "pubDate": format_datetime(datetime.now(main.KST))}
naver_search.search_naver_news = lambda kw, display=10: {"items": [item]}
ai_editor.pick_candidates = lambda arts, recent, n: [(0, [])]
article.fetch = lambda url: ("본문", "매체")
ai_editor.write_briefing = lambda c, cats, n: ([{"idx": 0, "category": "파스토", "headline": "h", "bullets": ["b"], "insight": "", "source": "s"}], "i")
slack_sender.bot_identity = lambda: "bot"
alerts = []
slack_sender.post_alert = lambda ch, text: alerts.append(text)


def raising(exc):
    def f(*a, **k):
        raise exc
    return f


# 1) 응답 유실(ReadTimeout) → 발송으로 기록 + 확인 요청 알림, 예외 없이 끝남(exit 0 → run_local.sh 가 state 푸시)
slack_sender.post_briefing = raising(requests.ReadTimeout("read timed out"))
main.main()
assert json.load(open(main.STATE_PATH))[0]["link"] == "https://e.x/1" and main.SENT and "응답" in alerts[-1], alerts

# 2) 연결 거절·DNS 실패 → 요청이 안 나감 → 예외, 기록 없음 (대체 실행해도 중복 아님)
os.remove(main.STATE_PATH)
for exc in (requests.ConnectionError("Caused by NewConnectionError: refused"), requests.ConnectionError("Caused by NameResolutionError")):
    main.SENT = False
    slack_sender.post_briefing = raising(exc)
    try:
        main.main()
        raise AssertionError("예외여야 함")
    except requests.ConnectionError:
        pass
    assert not os.path.exists(main.STATE_PATH) and not main.SENT
print("OK")
