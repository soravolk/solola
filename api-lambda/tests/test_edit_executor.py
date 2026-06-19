import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from botocore.exceptions import ReadTimeoutError

from edit_executor import call_editor_model, edit_with_repair

VALID = (
    '<?xml version="1.0"?><score-partwise><part><measure>'
    '<note><pitch><step>E</step><octave>2</octave></pitch><duration>4</duration></note>'
    '</measure></part></score-partwise>'
)
BROKEN = "<score-partwise><part>oops"

class _ConverseClient:
    """Returns queued texts on successive converse() calls."""
    def __init__(self, texts): self._texts = list(texts); self.calls = 0
    def converse(self, **kw):
        t = self._texts[min(self.calls, len(self._texts) - 1)]
        self.calls += 1
        return {"output": {"message": {"content": [{"text": t}]}}}

def test_call_editor_returns_text():
    out = call_editor_model(_ConverseClient([VALID]), "m", VALID, "change it")
    assert "<score-partwise>" in out

def test_edit_ok_first_try():
    client = _ConverseClient([VALID])
    ok, xml, err = edit_with_repair(client, "m", VALID, "x", original_note_count=1)
    assert ok and xml.endswith("</score-partwise>") and err is None
    assert client.calls == 1

def test_edit_repairs_then_succeeds():
    client = _ConverseClient([BROKEN, VALID])
    ok, xml, err = edit_with_repair(client, "m", VALID, "x", original_note_count=1)
    assert ok and client.calls == 2

def test_edit_gives_up_after_repair():
    client = _ConverseClient([BROKEN, BROKEN])
    ok, xml, err = edit_with_repair(client, "m", VALID, "x", original_note_count=1)
    assert not ok and xml is None and err

def test_edit_no_repair_when_disallowed():
    client = _ConverseClient([BROKEN, VALID])
    ok, xml, err = edit_with_repair(client, "m", VALID, "x",
                                    original_note_count=1, allow_repair=False)
    assert not ok and client.calls == 1


def test_edit_best_effort_returns_renderable_despite_soft_failure():
    # Well-formed/renderable output that only trips the note-count plausibility
    # heuristic (original had 100 notes) is returned, not discarded - pre-rewrite
    # parity so a real edit surfaces a result instead of a dead-end.
    client = _ConverseClient([VALID])  # VALID is well-formed, 1 note
    ok, xml, err = edit_with_repair(client, "m", VALID, "x",
                                    original_note_count=100, allow_repair=False)
    assert ok and xml and err is None

def test_edit_rejects_malformed_even_without_repair():
    client = _ConverseClient([BROKEN])
    ok, xml, err = edit_with_repair(client, "m", VALID, "x",
                                    original_note_count=1, allow_repair=False)
    assert not ok and xml is None and err


class _TimeoutClient:
    """converse() always times out; invoke_model must never be reached."""
    def converse(self, **kw):
        raise ReadTimeoutError(endpoint_url="test")
    def invoke_model(self, **kw):
        raise AssertionError("invoke_model must not run after a read timeout")

def test_edit_with_repair_handles_timeout_gracefully():
    ok, xml, err = edit_with_repair(_TimeoutClient(), "m", VALID, "x",
                                    original_note_count=1)
    assert not ok and xml is None and "timed out" in err
