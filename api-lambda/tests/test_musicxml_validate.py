import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from musicxml_validate import count_notes, sanitize_editor_output, validate_musicxml

VALID = (
    '<?xml version="1.0"?><score-partwise><part><measure>'
    '<note><pitch><step>E</step><octave>2</octave></pitch>'
    '<duration>4</duration></note>'
    '<note><pitch><step>G</step><octave>3</octave></pitch>'
    '<duration>4</duration></note>'
    '</measure></part></score-partwise>'
)

def test_count_notes():
    assert count_notes(VALID) == 2
    assert count_notes("") == 0

def test_sanitize_strips_fences_and_reasoning():
    raw = "```xml\n<think>blah</think>" + VALID + "\ntrailing junk```"
    out = sanitize_editor_output(raw)
    assert out.startswith("<?xml")
    assert out.endswith("</score-partwise>")
    assert "think" not in out

def test_sanitize_normalises_sharp():
    raw = "<score-partwise><part><measure><note><pitch><step>A#</step><octave>4</octave></pitch><duration>4</duration></note></measure></part></score-partwise>"
    out = sanitize_editor_output(raw)
    assert "<step>A</step><alter>1</alter>" in out

def test_validate_ok():
    ok, err = validate_musicxml(VALID, original_note_count=2)
    assert ok and err == ""

def test_validate_rejects_malformed():
    ok, err = validate_musicxml("<score-partwise><part></score-partwise>", 2)
    assert not ok

def test_validate_rejects_missing_close():
    ok, err = validate_musicxml("<score-partwise><part>", 2)
    assert not ok and "score-partwise" in err

def test_validate_rejects_implausible_note_count():
    ok, err = validate_musicxml(VALID, original_note_count=100)
    assert not ok and "implausible" in err
