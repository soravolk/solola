"""Deterministic MusicXML transpose helpers (no LLM)."""
import re

# Chromatic semitone within an octave for each step
_STEP_TO_SEMI = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

# Prefer sharps when converting back
_SEMI_TO_PITCH = {
    0: ('C', 0), 1: ('C', 1),  2: ('D', 0), 3: ('D', 1),  4: ('E', 0),
    5: ('F', 0), 6: ('F', 1),  7: ('G', 0), 8: ('G', 1),  9: ('A', 0),
    10: ('A', 1), 11: ('B', 0),
}

# Guitar standard tuning: string number -> open-string MIDI note
_GUITAR_OPEN_MIDI = {1: 64, 2: 59, 3: 55, 4: 50, 5: 45, 6: 40}


def _pitch_to_midi(step: str, alter: int, octave: int) -> int:
    return (octave + 1) * 12 + _STEP_TO_SEMI[step] + alter


def _midi_to_pitch(midi: int):
    octave = (midi // 12) - 1
    step, alter = _SEMI_TO_PITCH[midi % 12]
    return step, alter, octave


def parse_transpose_semitones(instruction: str):
    """
    Detect a transpose instruction and return the semitone count as an int
    (positive = up, negative = down).  Returns None if not a transpose request.
    """
    import re as _re
    text = instruction.lower()

    transpose_keywords = [
        'transpose', 'transpos', 'half-step', 'half step', 'semitone',
        'raise', 'lower', 'shift up', 'shift down', 'move up', 'move down',
        'pitch up', 'pitch down', 'key up', 'key down',
    ]
    if not any(k in text for k in transpose_keywords):
        return None

    num_match = _re.search(r'\b(\d+)\b', text)
    n = int(num_match.group(1)) if num_match else 1

    down_keywords = ['down', 'lower', 'flat', 'decrease', 'minus', '-']
    if any(k in text for k in down_keywords):
        return -n
    return n


def transpose_musicxml(xml_string: str, semitones: int) -> str:
    """Transpose every pitch (and guitar fret) in *xml_string* by *semitones*."""
    import re as _re

    def _transpose_pitch_block(pitch_xml: str) -> str:
        step_m   = _re.search(r'<step>([A-G])</step>', pitch_xml)
        alter_m  = _re.search(r'<alter>([-\d.]+)</alter>', pitch_xml)
        octave_m = _re.search(r'<octave>(\d+)</octave>', pitch_xml)
        if not step_m or not octave_m:
            return pitch_xml

        step   = step_m.group(1)
        alter  = int(round(float(alter_m.group(1)))) if alter_m else 0
        octave = int(octave_m.group(1))

        new_midi                    = _pitch_to_midi(step, alter, octave) + semitones
        new_step, new_alter, new_oct = _midi_to_pitch(new_midi)

        result = _re.sub(r'<step>[A-G]</step>',
                         f'<step>{new_step}</step>', pitch_xml)
        result = _re.sub(r'<octave>\d+</octave>',
                         f'<octave>{new_oct}</octave>', result)

        if new_alter != 0:
            alter_tag = f'<alter>{new_alter}</alter>'
            if alter_m:
                result = _re.sub(r'<alter>[-\d.]+</alter>', alter_tag, result)
            else:
                result = _re.sub(r'(</step>)', r'\1' + alter_tag, result, count=1)
        else:
            result = _re.sub(r'\s*<alter>[-\d.]+</alter>', '', result)

        return result

    def _transpose_note(note_xml: str) -> str:
        # 1. Update <pitch> block
        new_note = _re.sub(
            r'<pitch>.*?</pitch>',
            lambda m: _transpose_pitch_block(m.group(0)),
            note_xml, flags=_re.DOTALL,
        )

        # 2. Update <fret> (guitar tab notation)
        string_m = _re.search(r'<string>(\d+)</string>', new_note)
        fret_m   = _re.search(r'<fret>(\d+)</fret>',    new_note)
        if not (string_m and fret_m):
            return new_note

        string_num = int(string_m.group(1))

        # Extract new pitch MIDI from the already-updated <pitch> block
        pitch_m = _re.search(r'<pitch>(.*?)</pitch>', new_note, _re.DOTALL)
        if not pitch_m:
            return new_note
        step_m2   = _re.search(r'<step>([A-G])</step>',    pitch_m.group(1))
        alter_m2  = _re.search(r'<alter>([-\d.]+)</alter>', pitch_m.group(1))
        octave_m2 = _re.search(r'<octave>(\d+)</octave>',  pitch_m.group(1))
        if not (step_m2 and octave_m2):
            return new_note

        new_step2  = step_m2.group(1)
        new_alter2 = int(round(float(alter_m2.group(1)))) if alter_m2 else 0
        new_oct2   = int(octave_m2.group(1))
        new_midi   = _pitch_to_midi(new_step2, new_alter2, new_oct2)

        # Try same string first
        new_fret = new_midi - _GUITAR_OPEN_MIDI.get(string_num, 0)
        new_string = string_num

        if new_fret < 0:
            # Move to a higher-pitched (lower-numbered) string
            for s in range(string_num - 1, 0, -1):
                candidate = new_midi - _GUITAR_OPEN_MIDI[s]
                if 0 <= candidate <= 24:
                    new_fret, new_string = candidate, s
                    break
            else:
                new_fret = 0  # can't represent on standard guitar – clamp

        elif new_fret > 24:
            # Move to a lower-pitched (higher-numbered) string
            for s in range(string_num + 1, 7):
                candidate = new_midi - _GUITAR_OPEN_MIDI[s]
                if 0 <= candidate <= 24:
                    new_fret, new_string = candidate, s
                    break

        if new_string != string_num:
            new_note = _re.sub(r'<string>\d+</string>',
                               f'<string>{new_string}</string>',
                               new_note, count=1)
        new_note = _re.sub(r'<fret>\d+</fret>',
                           f'<fret>{max(0, new_fret)}</fret>',
                           new_note, count=1)
        return new_note

    return _re.sub(
        r'<note>.*?</note>',
        lambda m: _transpose_note(m.group(0)),
        xml_string, flags=_re.DOTALL,
    )
