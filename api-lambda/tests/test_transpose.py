import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from transpose import parse_transpose_semitones, transpose_musicxml

SIMPLE_NOTE = (
    '<score-partwise><part><measure><note>'
    '<pitch><step>E</step><octave>2</octave></pitch>'
    '<duration>4</duration><type>quarter</type>'
    '<notations><technical><string>6</string><fret>0</fret></technical></notations>'
    '</note></measure></part></score-partwise>'
)

def test_parse_transpose_up():
    assert parse_transpose_semitones("transpose up 2 semitones") == 2

def test_parse_transpose_down():
    assert parse_transpose_semitones("move down 3") == -3

def test_parse_transpose_none():
    assert parse_transpose_semitones("change the third note to a G") is None

def test_transpose_raises_pitch_and_fret():
    out = transpose_musicxml(SIMPLE_NOTE, 2)
    assert "<step>F</step>" in out
    assert "<alter>1</alter>" in out
    assert "<fret>2</fret>" in out
