"""Pure MusicXML sanitize + validation helpers (no LLM, no network)."""
import re
import xml.etree.ElementTree as ET

# Bounds for the note-count sanity heuristic (tunable).
MIN_NOTE_RATIO = 0.5
MAX_NOTE_RATIO = 2.0


def count_notes(xml_string: str) -> int:
    """Count <note> elements via a tolerant regex (handles <note> and <note ...>)."""
    if not xml_string:
        return 0
    return len(re.findall(r"<note[\s>]", xml_string))


def sanitize_editor_output(raw: str) -> str:
    """Clean a raw model response down to a bare MusicXML document.

    Mirrors the cleanup the old inline /fix path performed: strip markdown
    fences and reasoning blocks, extract the XML span, normalise sharp/flat
    steps, drop <?GP ...?> instructions, and repair grace-note structure.
    """
    if raw is None:
        return ""
    text = raw

    # Strip markdown fences.
    text = re.sub(r"```(?:xml|musicxml)?\s*\n?", "", text)
    text = text.replace("```", "").strip()

    # Remove reasoning/thinking/scratchpad blocks.
    for tag in ("reasoning", "think", "thinking", "scratchpad"):
        text = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", text, flags=re.DOTALL)
    text = text.strip()

    # Extract from <?xml or <score-partwise onward.
    m = re.search(r"(<\?xml\b.*)", text, flags=re.DOTALL)
    if not m:
        m = re.search(r"(<score-partwise\b.*)", text, flags=re.DOTALL)
    if m:
        text = m.group(1).strip()
        end = re.search(r"(</score-partwise>)", text)
        if end:
            text = text[: end.end()]

    # Normalise <step>A#</step> / <step>Ab</step>.
    text = re.sub(r"<step>([A-G])#</step>", r"<step>\1</step><alter>1</alter>", text)
    text = re.sub(r"<step>([A-G])b</step>", r"<step>\1</step><alter>-1</alter>", text)

    # Drop Guitar Pro processing instructions that break AlphaTab.
    text = re.sub(r"<\?GP\b.*?\?>", "", text, flags=re.DOTALL)

    # Repair grace notes: <grace/> must be first child, no <duration>, no slides.
    def _fix_grace(note_match):
        inner = note_match.group(1)
        if not re.search(r"<grace\s*/?>", inner):
            return note_match.group(0)
        fixed = re.sub(r"<grace\s*/?>", "", inner, count=1)
        fixed = re.sub(r"<duration>[^<]*</duration>", "", fixed, count=1)
        fixed = re.sub(r"<slide\b[^/]*/>", "", fixed)
        return f"<note><grace />{fixed}</note>"

    text = re.sub(r"<note>(.*?)</note>", _fix_grace, text, flags=re.DOTALL)
    return text.strip()


def validate_musicxml(xml_string: str, original_note_count: int) -> tuple[bool, str]:
    """Return (is_valid, error_message). error_message is '' when valid."""
    if not xml_string or "</score-partwise>" not in xml_string:
        return False, "missing closing </score-partwise>"

    # Strip a DOCTYPE so ElementTree's parser never tries to fetch a DTD.
    parseable = re.sub(r"<!DOCTYPE[^>]*>", "", xml_string, flags=re.DOTALL)
    try:
        ET.fromstring(parseable)
    except ET.ParseError as e:
        return False, f"not well-formed XML: {e}"

    new_count = count_notes(xml_string)
    if new_count < 1:
        return False, "no notes found"

    if original_note_count > 0:
        low = original_note_count * MIN_NOTE_RATIO
        high = original_note_count * MAX_NOTE_RATIO
        if new_count < low or new_count > high:
            return False, (
                f"note count {new_count} is implausible vs original "
                f"{original_note_count}"
            )

    return True, ""
