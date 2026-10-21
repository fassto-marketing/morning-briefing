# 물류 업계 동향 브리핑 봇 (v2)

매일 아침(평일 08:00 KST) 네이버 뉴스에서 물류 업계 동향을 수집·선별해 Slack `#info_news`에
**카테고리 | 제목 → 핵심 팩트 2줄 → 💡 파스토 시사점 → 🔗 출처** 포맷(Block Kit)으로 핵심 뉴스 5건을 발송합니다.

## 1. 배경 — 기존 봇 2개와의 관계

| | morning-briefing v1 (이 레포, 2026-02) | news-bot (`#고객마케팅`) | **v2 (이 레포)** |
|---|---|---|---|
| 대상·채널 | 경영진 | 마케팅팀 + 블로그 소재 | 전사 `#info_news` |
| 입력 | 기사 **제목+링크만** | 제목+요약 200자 | 1차 선정 후 **본문 2,500자** + 매체명 |
| 모델 | gemini-2.5-flash, 텍스트 템플릿 | gemini 2.5→2.0 폴백 (2.0 퇴역으로 10월부터 AI 단계 실패) | gemini-3.8-flash → 2.5 폴백, **JSON 출력** |
| 출력 | mrkdwn 텍스트 (Top5 + 부서별 액션) | mrkdwn 텍스트 + 블로그 초안 | **Block Kit** (코드가 포맷 고정, AI는 내용만) |
| 중복 방지 | 없음 | 블로그 제목만 | 14일 발송 링크·제목 `state/sent.json` |
| 상태 | 4월부터 60일 비활성으로 스케줄 꺼짐 | 운영 중 | 매일 state 커밋 → 비활성화 재발 방지 |

news-bot(블로그 소재·아이디어 뱅크 연계)은 그대로 두고, 이 레포는 **전사용 업계 동향 브리핑**만 맡습니다.

## 2. 파이프라인

```
08:00 KST — 맥북 스케줄러(fassto-office blog-pipeline/scheduler.js)가 `gh workflow run` 으로 정시에 트리거
            (백업: GitHub cron 08:40 KST, 30분~2시간 지연 가능 — 이미 보낸 날은 하루 1회 가드가 스킵)
 │  휴일 스킵 · 주말/연휴만큼 수집 범위 확장 (월요일 = 72h, 연휴 뒤엔 연휴 기간 포함)
 ├─ ① 수집      naver_search.py  6개 카테고리 × 28 키워드 × 최신 10건 (국내)
 │              feeds.py         해외 매체 RSS 6개 × 최신 15건 (The Robot Report·DC Velocity·Supply Chain Dive 등)
 │              → 링크·제목·기발송 중복 제거, 직전 평일 07:00 이후 게재분만
 ├─ ② 1차 선정  ai_editor.pick_candidates  제목·요약으로 후보 8건 (카테고리 고루, 같은 사건은 1건 + 추가 출처 ≤2, 파스토 언급 필수 포함)
 ├─ ③ 본문 읽기 article.fetch   기사 본문 2,500자 + og:site_name(매체명). 추가 출처도 읽음. 실패 시 요약으로 대체
 ├─ ④ 작성      ai_editor.write_briefing  핵심 5건: headline / 불릿 2개 / 파스토 시사점 / 출처 + 오늘의 한 줄 인사이트 (JSON)
 ├─ ⑤ 발송      slack_sender.py  chat.postMessage — header · context · rich_text(list/quote/link) · 🎯 한 줄 인사이트
 └─ ⑥ 기록      state/sent.json (14일 보관) → 워크플로우가 커밋
```

팩트 그라운딩: 불릿은 **본문에 있는 수치·고유명사만** 쓰도록 프롬프트에서 강제하고, 본문 수집에 실패한 기사는 요약만 근거로 씁니다.

## 3. 메시지 포맷

```
📦 물류 업계 동향 브리핑                      ← header
2026-10-12 (월) · 핵심 뉴스 5건 (10/9~10/12 주말 포함)   ← context
──────────
🧠 물류 IT·AI | 카덱스, 기존 WMS를 유지한 채 WES로 오토스토어를 연동한 사례
 • 미국 워런 캣은 520㎡ 공간에 오토스토어 R5 20대와 … 하루 피킹 3,648라인을 처리합니다.
 • 카덱스 WES 'FulfillX'가 기존 WMS와 오토스토어 사이의 실행 계층을 맡아 …
 ┃ 💡 파스토 시사점: 'WMS는 유지하고 WES만 붙이는' 구조는 … 참고 모델이 됩니다.
 🔗 로봇신문 · TechNode          ← 같은 사건을 다룬 기사가 여럿이면 출처를 나란히
──────────
(× 5건)
 ┃ 🎯 오늘의 한 줄 인사이트: 로봇 하드웨어는 빠르게 범용화되고 … 소프트웨어에서 나옵니다.
```

## 4. 카테고리 · 키워드

`main.py`의 `CATEGORIES` 한 곳에서 관리합니다. (이모지, 라벨, 네이버 검색 키워드)

| 카테고리 | 키워드 |
|---|---|
| 🏭 풀필먼트 경쟁사 | 풀필먼트, 3PL 물류, 품고, 두핸즈, 위킵, 테크타카, CJ대한통운 풀필먼트, 쿠팡 물류센터 |
| 🤖 AMR·물류로봇 | 물류 로봇, AMR 물류, 물류 자동화, 피킹 로봇, 휴머노이드 물류 |
| 🧠 물류 IT·AI | WMS, 물류 AI, 스마트 물류, 오토스토어, 물류 디지털 전환 |
| 🛒 이커머스·플랫폼 | 이커머스 물류, 알리익스프레스 물류, 테무 물류, 네이버 도착보장, 쿠팡 로켓배송 |
| 🏛️ 정책·규제 | 이커머스 규제, 유통 규제, 택배 기사, 물류 중대재해 |
| 🏢 파스토 | 파스토 |

해외 RSS(`feeds.py`의 `FEEDS`): The Robot Report·Robotics & Automation News → AMR·물류로봇, DC Velocity·Supply Chain Dive·Supply Chain 24/7 → 풀필먼트 경쟁사, TechNode → AMR·물류로봇. 키 없이 동작하며, 죽은 피드는 로그만 남기고 건너뜁니다.

## 5. 운영

**Secrets** (Settings → Secrets and variables → Actions)

| 이름 | 값 |
|---|---|
| `GOOGLE_API_KEY` | Gemini API 키 (news-bot과 동일 키 사용 가능) |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 네이버 검색 API |
| `SLACK_BOT_TOKEN` | 봇 토큰 (xoxb-). 봇이 발송 채널에 **초대되어 있어야** 합니다 |
| `SLACK_CHANNEL_ID` | 본 발송 채널 — `#info_news` 또는 채널 ID |
| `SLACK_ALERT_CHANNEL_ID` | (선택) 장애 알림 채널. 전사 채널에 오류를 띄우지 않도록 테스트방 권장 |

**테스트 발송**: Actions → *Daily Logistics Briefing* → Run workflow → `channel`에 테스트 채널 ID 입력
(예: `G01J39A4T2P` 홍철없는홍철방). 테스트 발송은 `state/sent.json`에 기록하지 않습니다.

```bash
gh workflow run daily_briefing.yml -R fassto-marketing/morning-briefing -f channel=G01J39A4T2P
```

**본 채널(#info_news) 전환 체크리스트**
1. `#info_news`에서 `/invite @햄기자블로그봇` (현재 미참여 — not_in_channel)
2. Secret `SLACK_CHANNEL_ID` 값을 `#info_news`(또는 채널 ID)로 변경 — 지금은 테스트방 `G01J39A4T2P`로 매일 발송 중
3. 같은 채널에 기존 브리핑을 올리던 쪽을 중단 (하루 2건 중복 방지) — 기존 메시지 하단 "다음을 사용하여 보냄 @Claude" 로 보아 claude.ai 예약 작업(루틴)입니다

**장애**: `main.py`가 알림 채널에 사유를 올리고 exit 1 → Actions에서 *Re-run*. 설치·크래시 단계 실패는 워크플로우가 별도로 알립니다.

**정시 발송**: 상시 가동 맥북의 스케줄러가 평일 08:00 KST 에 `gh workflow run daily_briefing.yml` 로 트리거합니다(workflow_dispatch 는 즉시 시작).
GitHub cron(08:40 KST)은 맥북이 꺼진 날의 백업이며, 같은 날 두 번 돌아도 `state/sent.json` 의 오늘 날짜 가드가 두 번째를 스킵합니다.

**로컬 실행**
```bash
pip install -r requirements.txt
GOOGLE_API_KEY=… NAVER_CLIENT_ID=… NAVER_CLIENT_SECRET=… SLACK_BOT_TOKEN=… SLACK_CHANNEL_ID=G01J39A4T2P python main.py
```

## 6. 의도적으로 뺀 것

- 메시지 상단 날짜 선택 드롭다운 — 상호작용 백엔드(서버)가 필요해 제외. 과거 브리핑은 채널 스크롤로 확인
- 스레드 상세·부서별 액션 아이템(v1) — 전사 공유용에는 과함
- 블로그 초안·아이디어 뱅크 연계 — news-bot 담당
- 공휴일 목록은 하드코딩(2026~2027, news-bot과 동일) — 매년 1월 갱신 필요
- 휴일 스킵은 본 채널 발송에만 적용 — 테스트 채널 발송은 휴일에도 직전 평일 이후 기사로 발송
- 중복 방지 3중: 같은 실행 안 링크·제목 키 / 14일 발송 기록의 링크·제목 키(추가 출처 포함) / AI 1차 선정에 최근 발송 제목 40개 전달
- 하루 1회 가드: `state/sent.json`에 오늘 날짜가 있으면 본 채널 발송 스킵(지연 도착한 예약 + 수동 실행 겹침 대비). 테스트 채널 발송은 예외
