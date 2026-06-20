import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from edit_response import build_response

def test_edit_includes_xml():
    b = build_response("edit", "Done!", xml_content="<xml/>")
    assert b == {"action": "edit", "reply": "Done!", "xmlContent": "<xml/>"}

def test_transpose_includes_xml():
    b = build_response("transpose", "Up 2.", xml_content="<xml/>")
    assert b["action"] == "transpose" and b["xmlContent"] == "<xml/>"

def test_restore_sets_intent():
    b = build_response("restore", "Restored.")
    assert b["intent"] == "restore_original"
    assert "xmlContent" not in b

def test_clarify_has_no_xml_or_intent():
    b = build_response("clarify", "Which note?")
    assert b == {"action": "clarify", "reply": "Which note?"}

def test_reject_has_no_xml():
    b = build_response("reject", "Can't do that.")
    assert b == {"action": "reject", "reply": "Can't do that."}

def test_invalid_action_raises():
    with pytest.raises(ValueError):
        build_response("nonsense", "x")
