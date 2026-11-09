#!/bin/zsh
# 맥북 로컬 실행 — 평일 08:00 fassto-office blog-pipeline/scheduler.js 가 호출 (수동: ./run_local.sh).
# AI 편집은 claude 헤드리스(구독 토큰 CLAUDE_CODE_OAUTH_TOKEN 은 scheduler 가 env 로 넘김). 수집·발송·state 는 GitHub 판과 같은 main.py.
# .env 미설정·발송 전 실패면 GitHub Actions(Gemini)로 대체 실행. 같은 날 2회 발송은 main.py 의 하루 1회 가드(state)가 막는다.
cd "${0:A:h}" || exit 1
GH=/opt/homebrew/bin/gh
export PYTHONWARNINGS=ignore  # 시스템 python 3.9·LibreSSL 경고가 로그를 덮지 않게

alert() {  # main.py 바깥 단계 장애만 — main.py 실패는 main.py 가 직접 알린다
  [ -n "$SLACK_ALERT_CHANNEL_ID" ] && [ -n "$SLACK_BOT_TOKEN" ] || return 0
  curl -s -m 15 -X POST https://slack.com/api/chat.postMessage \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN" -H "Content-Type: application/json; charset=utf-8" \
    -d "{\"channel\":\"$SLACK_ALERT_CHANNEL_ID\",\"text\":\"⚠️ *[물류 동향 브리핑]* $1\"}" >/dev/null
}
fallback() {
  echo "↪️ GitHub Actions 대체 실행 — $1"
  "$GH" workflow run daily_briefing.yml -R fassto-marketing/morning-briefing && return 0
  alert "$1 + GitHub 대체 실행 트리거도 실패 — 수동 확인 필요"
  return 1
}
pull() {  # 작업 중 파일은 autostash, state 충돌은 맥북 쪽 우선. 그래도 실패하면 리베이스를 되돌려 브랜치가 반쯤 멈춘 채 남지 않게
  git pull -q --rebase --autostash -X theirs origin main || { git rebase --abort 2>/dev/null; return 1; }
}

set -a; [ -f .env ] && . ./.env; set +a
if [ -z "$NAVER_CLIENT_ID" ] || [ -z "$NAVER_CLIENT_SECRET" ]; then
  fallback ".env 에 네이버 키 없음(맥북 로컬 미설정)"
  exit $?
fi

pull || echo "⚠️ git pull 실패 — 로컬 state 로 진행"
.venv/bin/python -u main.py
rc=$?
if [ $rc -eq 0 ]; then
  git add state/sent.json
  git diff --cached --quiet -- state/sent.json && exit 0  # 휴일·이미 발송·기사 0건 스킵
  git commit -qm "state: $(date +%F) 발송 기록 (맥북)" -- state/sent.json  # 경로 지정 — 다른 staged 파일이 딸려 가지 않게
  for i in 1 2 3; do  # GitHub 백업 실행이 오늘 발송을 알아야 중복 발송을 안 한다
    git push -q origin HEAD:main 2>/dev/null && exit 0
    pull && git push -q origin HEAD:main && exit 0
    sleep 30
  done
  alert "발송은 됐지만 state 푸시 실패 — GitHub 백업 실행이 중복 발송할 수 있으니 ~/morning-briefing 에서 git push 필요"
  exit 2
fi
[ $rc -ne 3 ] && fallback "맥북 실행 실패(exit $rc)"  # 3 = 발송 후 실패 → 대체 실행하면 중복 발송
exit $rc
