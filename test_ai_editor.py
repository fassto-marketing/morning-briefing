"""형식 불량 응답 → 재시도 → 다음 모델 폴백이 실제로 도는지 확인. 실행: python test_ai_editor.py (API 키 불필요)"""
import types
import ai_editor as ae

ae.RETRY_DELAY = 0
calls = []


class _Res:
    def __init__(self, text):
        self.text, self.candidates, self.prompt_feedback = text, [], None


def _fake_client(responses):
    it = iter(responses)
    def gen(model, contents, config):
        calls.append(model)
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
print("OK")
