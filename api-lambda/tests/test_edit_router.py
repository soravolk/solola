import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from edit_router import build_router_prompt, parse_router_output, run_router

def test_prompt_includes_instruction_and_history():
    p = build_router_prompt(
        [{"role": "assistant", "content": "Which note?"},
         {"role": "user", "content": "the third one"}],
        "the third one", has_transcription=True)
    assert "Latest request" in p
    assert "Which note?" in p
    assert "the third one" in p

def test_prompt_flags_missing_transcription():
    p = build_router_prompt([], "transpose up", has_transcription=False)
    assert "No transcription" in p

def test_parse_edit():
    out = parse_router_output('{"intent": "edit", "reply": "Sure.", "semitones": null}')
    assert out == {"intent": "edit", "reply": "Sure.", "semitones": None}

def test_parse_transpose_with_semitones():
    out = parse_router_output('{"intent":"transpose","reply":"Up 2.","semitones":2}')
    assert out["intent"] == "transpose" and out["semitones"] == 2

def test_parse_with_surrounding_prose():
    out = parse_router_output('Here you go: {"intent":"reject","reply":"No","semitones":null} done')
    assert out["intent"] == "reject"

def test_parse_invalid_intent_falls_back_to_edit():
    out = parse_router_output('{"intent":"frobnicate","reply":"x"}')
    assert out["intent"] == "edit"

def test_parse_garbage_falls_back():
    out = parse_router_output("not json at all")
    assert out == {"intent": "edit", "reply": "", "semitones": None}

class _FakeClient:
    def __init__(self, text): self._text = text
    def converse(self, **kw):
        return {"output": {"message": {"content": [{"text": self._text}]}}}

class _BoomClient:
    def converse(self, **kw):
        raise RuntimeError("bedrock down")

def test_run_router_parses_response():
    out = run_router(_FakeClient('{"intent":"clarify","reply":"Which?","semitones":null}'),
                     "m", [], "fix it", True)
    assert out["intent"] == "clarify" and out["reply"] == "Which?"

def test_run_router_falls_back_on_error():
    out = run_router(_BoomClient(), "m", [], "fix it", True)
    assert out["intent"] == "edit"
