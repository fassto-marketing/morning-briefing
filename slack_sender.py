import requests
import os

# GitHub Secrets에서 가져올 키
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID") # 경영진 브리핑 채널 ID

def send_leadership_briefing(summary_text, detail_text):
    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL_ID:
        print("❌ 슬랙 설정(토큰 또는 채널ID)이 누락되었습니다.")
        return

    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
    url = "https://slack.com/api/chat.postMessage"

    # 1. 메인 브리핑 전송 (전체 요약 & 시사점)
    # 경영진이 가장 먼저 보게 될 깔끔한 요약본입니다.
    payload_main = {
        "channel": SLACK_CHANNEL_ID,
        "text": summary_text,
        "unfurl_links": False # 링크 미리보기 끄기 (깔끔함 유지)
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload_main)
        res_json = res.json()
        
        if res_json.get("ok"):
            ts = res_json.get("ts") # 방금 보낸 메시지의 ID (타임스탬프) 확보
            print("✅ 메인 경영 브리핑 전송 완료")
            
            # 2. 스레드(댓글) 전송 (부서별 상세 가이드)
            # 관심 있는 리더들만 클릭해서 볼 수 있도록 댓글로 답니다.
            if detail_text:
                payload_thread = {
                    "channel": SLACK_CHANNEL_ID,
                    "text": detail_text,
                    "thread_ts": ts # 메인 메시지의 댓글로 달림
                }
                requests.post(url, headers=headers, json=payload_thread)
                print("✅ 상세 가이드(스레드) 전송 완료")
            
        else:
            print(f"❌ 전송 실패: {res.text}")

    except Exception as e:
        print(f"❌ 에러: {e}")
