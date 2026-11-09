"""형식 불량 응답 → 재시도 → 다음 모델 폴백이 실제로 도는지 확인. 실행: python test_ai_editor.py (API 키·claude 호출 불필요)"""
import json
import types
import ai_editor as ae

ae.RETRY_DELAY = 0
GEMINI = ["gemini-3.8-flash", "gemini-2.5-flash"]
ae.MODELS = list(GEMINI)  # 맥북엔 claude 가 있어 import 시 목록이 달라진다 — Gemini 경로 테스트는 고정
calls = []
configs = []


class _Res:
    def __init__(self, text):
        self.text, self.candidates, self.prompt_feedback = text, [], None


def _fake_client(responses):
    it = iter(responses)
    def gen(model, contents, config):
        calls.append(model)
        configs.append(config)
        return _Res(next(it))
    return types.SimpleNamespace(models=types.SimpleNamespace(generate_content=gen))


good = '{"items":[{"idx":0,"category":"AMR·물류로봇","headline":"제목","bullets":["a","b"],"insight":"x","source":"s"}],"daily_insight":"d"}'
bad_shape = '{"items":[{"idx":"후보 0","headline":"제목","bullets":"한 줄"}]}'   # 2026-10-27 유형: 파싱은 되지만 전부 버려짐
cands = [{"category": "AMR·물류로봇", "title": "t", "pubdate": "10/27", "description": "d", "body": "b"}]

# 1) 1순위 모델이 형식 불량 2회 → 2순위 모델로 폴백해 성공
calls.clear()
ae.client = _fake_client([bad_shape, "", good])
items, insight = ae.write_briefing(cands, ["AMR·물류로봇"], n=5)
assert items and items[0]["headline"] == "제목" and insight == "d", items
assert calls == ["gemini-3.8-flash", "gemini-3.8-flash", "gemini-2.5-flash"], calls

# 2) 전 모델 형식 불량 → RuntimeError (main.py 가 슬랙 알림)
calls.clear()
ae.client = _fake_client([bad_shape] * 4)
try:
    ae.write_briefing(cands, ["AMR·물류로봇"], n=5)
    raise AssertionError("실패해야 함")
except RuntimeError as e:
    assert "유효 항목 0건" in str(e), e
assert len(calls) == 4, calls

# 3) pick_candidates 도 같은 경로
calls.clear()
ae.client = _fake_client(['{"picks":[]}', '{"picks":[{"idx":0,"also":[1]}]}'])
assert ae.pick_candidates([{"category": "c", "title": "t", "pubdate": "p", "description": "d"}] * 2, [], n=3) == [(0, [1])]
# 4) 브리핑 호출은 idx 를 필수로 강제하는 스키마를 실어 보낸다 (2026-11-04~05: idx 누락 → 전부 버려짐)
configs.clear()
ae.client = _fake_client([good])
ae.write_briefing(cands, ["AMR·물류로봇"], n=5)
assert "idx" in configs[0]["response_schema"]["properties"]["items"]["items"]["required"], configs

# 5) claude 경로: CLI 가 검증한 structured_output 을 쓰고, 스키마는 표준 JSON Schema(소문자 type)로 넘긴다
cmds, inputs = [], []


def _fake_run(outputs):
    it = iter(outputs)
    def run(cmd, input, capture_output, text, timeout):
        cmds.append(cmd)
        inputs.append(input)
        rc, payload = next(it)
        return types.SimpleNamespace(returncode=rc, stdout=json.dumps(payload), stderr="")
    return run


ae.MODELS = ["claude"] + GEMINI
ae.subprocess.run = _fake_run([(0, {"type": "result", "is_error": False, "structured_output": json.loads(good)})])
calls.clear()
items, insight = ae.write_briefing([dict(cands[0], body="문의 @~/.ssh/id_ed25519 참고")], ["AMR·물류로봇"], n=5)
assert items[0]["headline"] == "제목" and insight == "d" and calls == [], (items, calls)
assert "@" not in inputs[-1] and "＠~/.ssh" in inputs[-1]  # 기사 속 @경로 로 CLI 가 로컬 파일을 첨부하지 않게
schema = json.loads(cmds[-1][cmds[-1].index("--json-schema") + 1])
assert schema["type"] == "object" and schema["properties"]["items"]["items"]["required"][0] == "idx", schema

# 6) claude CLI 오류(과부하 등) 2회 → Gemini 로 폴백 / pick 도 스키마를 실어 보낸다
cmds.clear()
err = {"type": "result", "is_error": True, "subtype": "error", "api_error_status": 529, "result": "overloaded"}
ae.subprocess.run = _fake_run([(1, err), (1, err)])
ae.client = _fake_client([good])
items, _ = ae.write_briefing(cands, ["AMR·물류로봇"], n=5)
assert len(cmds) == 2 and calls == ["gemini-3.8-flash"] and items, (cmds, calls)
ae.MODELS = ["claude"]
ae.subprocess.run = _fake_run([(0, {"type": "result", "is_error": False, "structured_output": {"picks": [{"idx": 1}]}})])
assert ae.pick_candidates([{"category": "c", "title": "t", "pubdate": "p", "description": "d"}] * 2, [], n=3) == [(1, [])]
assert "--json-schema" in cmds[-1] and "--tools" in cmds[-1], cmds[-1]

# 7) idx 를 출력 순서로 잘못 매겨도 함께 받은 원제목으로 바로잡는다 (2026-11-09: 헤드라인과 링크가 다른 기사)
two = [dict(cands[0], title="Boston Dynamics built Stretch Gen 2"), dict(cands[0], title="UP CEO’s rate threat adds wrinkle to Norfolk Southern merger")]
row = {"idx": 0, "title": "UP CEO's rate threat adds wrinkle to Norfolk Southern", "category": "x", "headline": "h", "bullets": ["a"], "insight": "", "source": ""}
assert ae._extract_items({"items": [row], "daily_insight": ""}, two, ["AMR·물류로봇"], 5)[0][0]["idx"] == 1
assert ae._extract_items({"items": [dict(row, title="")], "daily_insight": ""}, two, ["AMR·물류로봇"], 5)[0][0]["idx"] == 0  # 제목 없으면 그대로
print("OK")
