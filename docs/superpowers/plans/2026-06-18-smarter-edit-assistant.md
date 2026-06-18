# Smarter Conversational Edit Assistant — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the single whole-MusicXML-rewrite `/api/v1/fix` Lambda into a conversational Router→Edit pipeline that confirms/explains/clarifies/declines, validates and repairs edited XML once, threads multi-turn context, and stays transparent about using a budget model.

**Architecture:** A cheap Router LLM call (no XML) classifies each request into `edit | transpose | restore | clarify | reject` and writes a conversational reply; only `edit` proceeds to the existing whole-XML Editor LLM call, which is then sanitized, validated, and repaired at most once. Edit logic is extracted from the 868-line `handler.py` into focused, unit-testable modules; the `/fix` route becomes a thin orchestrator returning a uniform `{action, reply, xmlContent?, intent?}` envelope. The frontend branches on `action` and sends recent conversation history.

**Tech Stack:** Python 3.11 AWS Lambda (Docker image, `boto3` + Bedrock `converse`/`invoke_model`), pytest (new, dev-only, Bedrock mocked) for backend pure functions; React 18 + TypeScript + Vite frontend (no test framework — manual + `npm run build`).

**Spec:** `docs/superpowers/specs/2026-06-18-smarter-edit-assistant-design.md`

**Commit policy (user requirement):** Commit after each small step. Each task ends in its own scoped commit; stage ONLY the exact paths named. The branch `SLL-18-...` carries unrelated files — never `git add -A`/`git add .`.

**A note on the module split vs. the spec:** the spec lists `musicxml_validate.py` as "orchestrating the repair retry." To keep `musicxml_validate.py` pure (no LLM, fully unit-testable) and avoid a circular import with the Editor, the **repair loop lives in `edit_executor.py`** (which already owns the Editor LLM calls) and *uses* `validate_musicxml` from `musicxml_validate.py`. This is a cleaner one-way dependency and is the intended reading of the spec.

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `api-lambda/requirements-dev.txt` | Dev-only deps (pytest); not packaged into the image | Create |
| `api-lambda/Dockerfile` | Copy all `*.py` modules into the image (currently only `handler.py`) | Modify |
| `api-lambda/transpose.py` | Deterministic transpose helpers moved out of `handler.py` | Create (move) |
| `api-lambda/musicxml_validate.py` | Pure: `count_notes`, `sanitize_editor_output`, `validate_musicxml` | Create |
| `api-lambda/edit_response.py` | Pure: `build_response` envelope builder | Create |
| `api-lambda/edit_router.py` | `build_router_prompt`, `parse_router_output` (pure) + `run_router` (LLM) | Create |
| `api-lambda/edit_executor.py` | `call_editor_model` (LLM) + `edit_with_repair` (repair loop) | Create |
| `api-lambda/handler.py` | `/api/v1/fix` becomes a thin orchestrator; remove old inline classify/editor code | Modify |
| `api-lambda/tests/test_*.py` | pytest for the pure functions (Bedrock mocked) | Create |
| `web/src/components/chat/ChatInterface.tsx` | Send `history`; branch on `action`; lightweight-model framing copy | Modify |
| `web/src/components/chat/ChatInterface.css` | Style for the framing one-liner | Modify |

**Backend commands run from `eg-solo-app/api-lambda`. Frontend commands from `eg-solo-app/web`.**

---

### Task 1: pytest dev setup + Dockerfile packaging fix

**Files:**
- Create: `api-lambda/requirements-dev.txt`
- Modify: `api-lambda/Dockerfile`
- Create: `api-lambda/tests/__init__.py`
- Create: `api-lambda/pytest.ini`

- [ ] **Step 1: Create `api-lambda/requirements-dev.txt`**

```
-r requirements.txt
pytest==8.3.4
```

- [ ] **Step 2: Create `api-lambda/pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 3: Create empty `api-lambda/tests/__init__.py`** (empty file, makes `tests` a package).

- [ ] **Step 4: Update the Dockerfile to copy all modules**

In `api-lambda/Dockerfile`, find:
```dockerfile
# Copy handler code
COPY handler.py ${LAMBDA_TASK_ROOT}/
```
Replace with:
```dockerfile
# Copy handler + edit-pipeline modules (tests/ and *-dev files are NOT copied)
COPY *.py ${LAMBDA_TASK_ROOT}/
```
(`COPY *.py` picks up `handler.py` and the new modules but not `tests/`, `requirements-dev.txt`, or shell scripts.)

- [ ] **Step 5: Verify pytest installs and runs (no tests yet)**

Run: `cd api-lambda && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt && python -m pytest -q`
Expected: pytest collects 0 items and exits 0 ("no tests ran"). Deactivate after.
Add `.venv/` to the repo's `.gitignore` if not already ignored (the eg-solo-app `.gitignore` already ignores `node_modules`/`dist`; append a line `api-lambda/.venv/` under a new `# python` section).

- [ ] **Step 6: Commit**

```bash
git add api-lambda/requirements-dev.txt api-lambda/pytest.ini api-lambda/tests/__init__.py api-lambda/Dockerfile .gitignore
git commit -m "chore(api-lambda): add pytest dev setup and copy all modules in Docker image

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Extract `transpose.py` (move, behavior unchanged)

**Files:**
- Create: `api-lambda/transpose.py`
- Modify: `api-lambda/handler.py`
- Create: `api-lambda/tests/test_transpose.py`

- [ ] **Step 1: Create `api-lambda/transpose.py` by moving the existing helpers**

Move these symbols **verbatim** from `handler.py` into a new `api-lambda/transpose.py` (they currently live at handler.py lines ~26–175): the module constants `_STEP_TO_SEMI`, `_SEMI_TO_PITCH`, `_GUITAR_OPEN_MIDI`, and the functions `_pitch_to_midi`, `_midi_to_pitch`, `parse_transpose_semitones`, `transpose_musicxml`. Prepend the file with:
```python
"""Deterministic MusicXML transpose helpers (no LLM)."""
import re
```
Then paste the moved code unchanged. (The functions already use `import re as _re` internally; leave those as-is — they will still work. The top-level `import re` is harmless.)

- [ ] **Step 2: Replace the moved code in `handler.py` with an import**

Delete the moved block from `handler.py` (lines ~22–175, the `# Deterministic transpose helpers` section through the end of `transpose_musicxml`). Add, near the top of `handler.py` after the existing imports (after line 5 `from datetime import ...`):
```python
from transpose import parse_transpose_semitones, transpose_musicxml
```

- [ ] **Step 3: Write a characterization test**

Create `api-lambda/tests/test_transpose.py`:
```python
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
    # E2 fret 0 on string 6 -> F#2, fret 2
    assert "<step>F</step>" in out
    assert "<alter>1</alter>" in out
    assert "<fret>2</fret>" in out
```

- [ ] **Step 4: Run the test**

Run: `cd api-lambda && . .venv/bin/activate && python -m pytest tests/test_transpose.py -q`
Expected: 4 passed.

- [ ] **Step 5: Sanity-check handler still imports**

Run: `cd api-lambda && . .venv/bin/activate && python -c "import handler"`
Expected: no ImportError. (boto3 clients initialize lazily on first call; `import handler` only constructs client objects, which is fine offline. If it errors on network, report it.)

- [ ] **Step 6: Commit**

```bash
git add api-lambda/transpose.py api-lambda/handler.py api-lambda/tests/test_transpose.py
git commit -m "refactor(api-lambda): extract transpose helpers into transpose.py

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `musicxml_validate.py` (pure: count, sanitize, validate)

**Files:**
- Create: `api-lambda/musicxml_validate.py`
- Create: `api-lambda/tests/test_musicxml_validate.py`

- [ ] **Step 1: Create `api-lambda/musicxml_validate.py`**

```python
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
```

- [ ] **Step 2: Create `api-lambda/tests/test_musicxml_validate.py`**

```python
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
    # original had 100 notes, output has 2 -> below 50% floor
    ok, err = validate_musicxml(VALID, original_note_count=100)
    assert not ok and "implausible" in err
```

- [ ] **Step 3: Run the tests**

Run: `cd api-lambda && . .venv/bin/activate && python -m pytest tests/test_musicxml_validate.py -q`
Expected: 7 passed.

- [ ] **Step 4: Commit**

```bash
git add api-lambda/musicxml_validate.py api-lambda/tests/test_musicxml_validate.py
git commit -m "feat(api-lambda): add pure MusicXML sanitize + validation helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `edit_response.py` (pure envelope builder)

**Files:**
- Create: `api-lambda/edit_response.py`
- Create: `api-lambda/tests/test_edit_response.py`

- [ ] **Step 1: Create `api-lambda/edit_response.py`**

```python
"""Builds the uniform /api/v1/fix response body."""

VALID_ACTIONS = {"edit", "transpose", "restore", "clarify", "reject"}


def build_response(action: str, reply: str, xml_content: str = None,
                   intent: str = None) -> dict:
    """Assemble the response body.

    - action: one of VALID_ACTIONS.
    - reply: always present, conversational.
    - xml_content: included only for edit/transpose.
    - intent: included only for restore (preserves client restore behaviour).
    """
    if action not in VALID_ACTIONS:
        raise ValueError(f"invalid action: {action}")
    body = {"action": action, "reply": reply}
    if action in ("edit", "transpose"):
        body["xmlContent"] = xml_content
    if action == "restore":
        body["intent"] = intent or "restore_original"
    return body
```

- [ ] **Step 2: Create `api-lambda/tests/test_edit_response.py`**

```python
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
```

- [ ] **Step 3: Run the tests**

Run: `cd api-lambda && . .venv/bin/activate && python -m pytest tests/test_edit_response.py -q`
Expected: 6 passed.

- [ ] **Step 4: Commit**

```bash
git add api-lambda/edit_response.py api-lambda/tests/test_edit_response.py
git commit -m "feat(api-lambda): add uniform edit response envelope builder

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `edit_router.py` (prompt + parse + run)

**Files:**
- Create: `api-lambda/edit_router.py`
- Create: `api-lambda/tests/test_edit_router.py`

- [ ] **Step 1: Create `api-lambda/edit_router.py`**

```python
"""The Router: classify an edit request + write a conversational reply.

The Router prompt contains NO MusicXML — only the recent conversation and the
new instruction — so it is cheap, fast, and token-safe. Returns a small dict
{intent, reply, semitones}. On any parse failure we fall back to intent="edit"
(the historical safe default).
"""
import json
import re

VALID_INTENTS = {"edit", "transpose", "restore", "clarify", "reject"}

SCOPE_BLOCK = (
    "SUPPORTED capabilities (what you can do):\n"
    "- edit: change a note's pitch / fret / string; change a note's duration or "
    "rhythm; add or remove guitar articulations (bend, slide, hammer-on, "
    "pull-off, vibrato, palm-mute).\n"
    "- transpose: shift every note up or down by N semitones.\n"
    "- restore: revert the score to the original transcription.\n\n"
    "NOT supported (must be rejected): generating new music, changing the "
    "instrument or tuning wholesale, adding backing tracks, editing the audio, "
    "lyrics, or wholesale re-composition.\n"
)

SYSTEM_PROMPT = (
    "You are Solola's guitar-tab edit assistant. You run on a small, "
    "lightweight model, so keep replies short and only attempt supported edits.\n\n"
    + SCOPE_BLOCK +
    "\nClassify the user's latest request into EXACTLY one intent:\n"
    "  edit      - a supported change to specific notes/rhythm/articulation\n"
    "  transpose - shift all notes by semitones (also set \"semitones\": signed int)\n"
    "  restore   - revert to the original transcription\n"
    "  clarify   - a supported edit, but too vague to act on (ask ONE question)\n"
    "  reject    - not supported; briefly say what you CAN do instead\n\n"
    "Write a short, friendly \"reply\" to show the user: for edit/transpose, "
    "confirm what you understood; for clarify, ask the question; for reject, "
    "explain the limit and suggest supported alternatives.\n\n"
    "Respond with ONLY a single JSON object, no prose, no markdown:\n"
    '{\"intent\": \"<one intent>\", \"reply\": \"<message>\", \"semitones\": <signed int or null>}'
)


def build_router_prompt(history: list, instruction: str,
                        has_transcription: bool) -> str:
    """Render the user-turn text for the Router (history + new instruction)."""
    lines = []
    if not has_transcription:
        lines.append("(No transcription exists yet.)")
    if history:
        lines.append("Recent conversation:")
        for msg in history[-6:]:
            role = msg.get("role", "user")
            content = (msg.get("content") or "").strip()
            if content:
                lines.append(f"{role}: {content}")
        lines.append("")
    lines.append(f"Latest request: \"{instruction}\"")
    return "\n".join(lines)


def parse_router_output(text: str) -> dict:
    """Parse the Router's JSON. Falls back to a safe edit intent on failure."""
    fallback = {"intent": "edit", "reply": "", "semitones": None}
    if not text:
        return fallback
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return fallback
    try:
        data = json.loads(m.group(0))
    except (ValueError, TypeError):
        return fallback

    intent = data.get("intent")
    if intent not in VALID_INTENTS:
        intent = "edit"

    reply = data.get("reply")
    if not isinstance(reply, str):
        reply = ""

    semitones = data.get("semitones")
    if not isinstance(semitones, int) or isinstance(semitones, bool):
        semitones = None

    return {"intent": intent, "reply": reply, "semitones": semitones}


def run_router(client, model_id: str, history: list, instruction: str,
               has_transcription: bool) -> dict:
    """Call Bedrock and return parse_router_output(...). Safe fallback on error."""
    user_text = build_router_prompt(history, instruction, has_transcription)
    try:
        response = client.converse(
            modelId=model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            inferenceConfig={"temperature": 0, "maxTokens": 256},
        )
        text = response["output"]["message"]["content"][0]["text"]
        return parse_router_output(text)
    except Exception as e:  # noqa: BLE001 - router must never hard-fail the request
        print(f"Router call failed, defaulting to edit: {e}")
        return {"intent": "edit", "reply": "", "semitones": None}
```

- [ ] **Step 2: Create `api-lambda/tests/test_edit_router.py`**

```python
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
```

- [ ] **Step 3: Run the tests**

Run: `cd api-lambda && . .venv/bin/activate && python -m pytest tests/test_edit_router.py -q`
Expected: 9 passed.

- [ ] **Step 4: Commit**

```bash
git add api-lambda/edit_router.py api-lambda/tests/test_edit_router.py
git commit -m "feat(api-lambda): add Router (classify + conversational reply)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: `edit_executor.py` (Editor call + repair loop)

**Files:**
- Create: `api-lambda/edit_executor.py`
- Create: `api-lambda/tests/test_edit_executor.py`

- [ ] **Step 1: Create `api-lambda/edit_executor.py`**

```python
"""The Editor: whole-MusicXML rewrite via Bedrock, plus a one-shot repair loop.

call_editor_model returns the RAW model text. edit_with_repair sanitizes,
validates, and (when allowed) repairs once, returning (ok, xml, error).
"""
import json

from musicxml_validate import sanitize_editor_output, validate_musicxml

SYSTEM_PROMPT = (
    "You are a MusicXML editing assistant for guitar transcriptions. "
    "The user will give you a MusicXML document and a change request. "
    "Apply the requested changes accurately and return ONLY the complete "
    "corrected MusicXML document. No explanation, no markdown fences, "
    "no extra text - just the raw XML starting with <?xml.\n\n"
    "IMPORTANT: Guitar standard tuning open string pitches (fret 0):\n"
    "  String 1 (high E) = E4\n  String 2 = B3\n  String 3 = G3\n"
    "  String 4 = D3\n  String 5 = A2\n  String 6 (low E) = E2\n\n"
    "Each fret raises the pitch by one semitone. The chromatic scale is: "
    "C, C#/Db, D, D#/Eb, E, F, F#/Gb, G, G#/Ab, A, A#/Bb, B. "
    "The octave increments after B (i.e., B4 -> C5).\n\n"
    "When changing <string> or <fret>, you MUST recalculate and update "
    "the <pitch> element (<step>, <alter>, <octave>) to match. "
    "Use <alter>-1</alter> for flats and <alter>1</alter> for sharps."
)


def _build_user_prompt(current_xml: str, instruction: str,
                       prior_error: str = None) -> str:
    base = (
        f"Here is the current MusicXML:\n\n{current_xml}\n\n"
        f"Please make this change: {instruction}"
    )
    if prior_error:
        base += (
            f"\n\nYour previous attempt was invalid because: {prior_error}. "
            "Return the COMPLETE corrected MusicXML document."
        )
    return base


def _extract_converse_text(response: dict) -> str:
    msg = response.get("output", {}).get("message", {})
    for item in msg.get("content", []):
        if isinstance(item, dict) and "text" in item:
            return item["text"]
        if isinstance(item, str):
            return item
    return ""


def call_editor_model(client, model_id: str, current_xml: str,
                      instruction: str, prior_error: str = None) -> str:
    """Call Bedrock (converse, with invoke_model fallback). Returns raw text."""
    user_prompt = _build_user_prompt(current_xml, instruction, prior_error)
    try:
        response = client.converse(
            modelId=model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            inferenceConfig={"temperature": 0, "maxTokens": 8192},
        )
        text = _extract_converse_text(response)
        if text:
            return text
    except Exception as e:  # noqa: BLE001
        print(f"Editor converse failed, trying invoke_model: {e}")

    # Fallback: invoke_model (OpenAI-compatible body).
    body = json.dumps({
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 8192,
        "temperature": 0,
    })
    response = client.invoke_model(
        modelId=model_id, contentType="application/json",
        accept="application/json", body=body,
    )
    payload = json.loads(response["body"].read())
    if "choices" in payload:
        return payload["choices"][0]["message"]["content"]
    if "content" in payload:
        c = payload["content"]
        return c[0].get("text", str(c[0])) if isinstance(c, list) else str(c)
    if "completion" in payload:
        return payload["completion"]
    return ""


def edit_with_repair(client, model_id: str, current_xml: str, instruction: str,
                     original_note_count: int, allow_repair: bool = True):
    """Run the Editor, sanitize, validate, and repair once if allowed.

    Returns (ok: bool, xml: str | None, error: str | None).
    """
    raw = call_editor_model(client, model_id, current_xml, instruction)
    xml = sanitize_editor_output(raw)
    ok, err = validate_musicxml(xml, original_note_count)
    if ok:
        return True, xml, None

    if not allow_repair:
        return False, None, err

    raw2 = call_editor_model(client, model_id, current_xml, instruction,
                             prior_error=err)
    xml2 = sanitize_editor_output(raw2)
    ok2, err2 = validate_musicxml(xml2, original_note_count)
    if ok2:
        return True, xml2, None
    return False, None, err2 or err
```

- [ ] **Step 2: Create `api-lambda/tests/test_edit_executor.py`**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
```

- [ ] **Step 3: Run the tests**

Run: `cd api-lambda && . .venv/bin/activate && python -m pytest tests/test_edit_executor.py -q`
Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add api-lambda/edit_executor.py api-lambda/tests/test_edit_executor.py
git commit -m "feat(api-lambda): add Editor call with one-shot validate+repair loop

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Rewrite the `/api/v1/fix` route as a thin orchestrator

**Files:**
- Modify: `api-lambda/handler.py`

- [ ] **Step 1: Add module imports + a time budget constant**

In `handler.py`, below the existing `from transpose import ...` line added in Task 2, add:
```python
from edit_router import run_router
from edit_executor import edit_with_repair
from edit_response import build_response
from musicxml_validate import count_notes

# Leave this much of the 30s gateway budget for the repair retry; skip repair
# if less remains. The Lambda context's remaining time is the source of truth.
REPAIR_MIN_BUDGET_MS = 12000
```
Also delete the now-unused `_classify_intent` and `_classify_transpose_semitones` functions (handler.py lines ~180–237) — the Router replaces them.

- [ ] **Step 2: Replace the entire body of the `/api/v1/fix` route**

Find the block starting at `if http_method == 'POST' and request_path == '/api/v1/fix':` (line ~559) and ending just before the final `# No route matched - return 404` comment (line ~860). Replace that whole `if` block with:

```python
    # Route: POST /api/v1/fix - conversational Router -> Edit pipeline
    if http_method == 'POST' and request_path == '/api/v1/fix':
        print(">>> Matched /api/v1/fix route")
        try:
            body = json.loads(event.get('body', '{}'))
            current_xml = body.get('currentXml', '')
            instruction = body.get('instruction', '')
            history = body.get('history', []) or []

            source_ip = event.get('requestContext', {}).get('http', {}).get('sourceIp', 'unknown')

            if not instruction:
                return {'statusCode': 400, 'headers': headers,
                        'body': json.dumps({'error': 'Missing instruction'})}

            rate_check = check_rate_limit(source_ip)
            if not rate_check['allowed']:
                return {'statusCode': 429, 'headers': headers,
                        'body': json.dumps({'error': rate_check['error']})}

            MAX_XML_SIZE = 500_000
            MAX_INSTRUCTION_SIZE = 1000
            if len(current_xml) > MAX_XML_SIZE:
                return {'statusCode': 413, 'headers': headers,
                        'body': json.dumps({'error': f'XML too large (max {MAX_XML_SIZE} bytes)'})}
            if len(instruction) > MAX_INSTRUCTION_SIZE:
                return {'statusCode': 413, 'headers': headers,
                        'body': json.dumps({'error': f'Instruction too long (max {MAX_INSTRUCTION_SIZE} chars)'})}

            has_transcription = bool(current_xml)
            original_note_count = count_notes(current_xml)

            # --- Router (no XML; cheap) ---
            routed = run_router(bedrock_client, BEDROCK_MODEL_ID, history,
                                instruction, has_transcription)
            intent = routed['intent']
            reply = routed['reply']
            print(f"Router intent={intent} ip={source_ip} instr={instruction[:80]!r}")

            # --- clarify / reject: reply only, no XML ---
            if intent in ('clarify', 'reject'):
                if not reply:
                    reply = ("Could you be more specific about which note or change you want?"
                             if intent == 'clarify'
                             else "I can change notes, rhythm, articulations, transpose, or restore the original - but not that.")
                return {'statusCode': 200, 'headers': headers,
                        'body': json.dumps(build_response(intent, reply))}

            # --- restore: signal client-side swap ---
            if intent == 'restore':
                return {'statusCode': 200, 'headers': headers,
                        'body': json.dumps(build_response('restore', reply or "Restored the original transcription."))}

            # Everything below needs a current transcription.
            if not has_transcription:
                return {'statusCode': 200, 'headers': headers,
                        'body': json.dumps(build_response('reject',
                            "Please generate a transcription first, then I can edit it."))}

            # --- transpose: deterministic ---
            if intent == 'transpose':
                semitones = routed['semitones']
                if semitones is None:
                    semitones = parse_transpose_semitones(instruction)
                if semitones is None:
                    return {'statusCode': 200, 'headers': headers,
                            'body': json.dumps(build_response('clarify',
                                "How many semitones should I transpose, and up or down?"))}
                transposed = transpose_musicxml(current_xml, semitones)
                direction = 'up' if semitones > 0 else 'down'
                msg = reply or f"Transposed {direction} {abs(semitones)} semitone(s)."
                return {'statusCode': 200, 'headers': headers,
                        'body': json.dumps(build_response('transpose', msg, xml_content=transposed))}

            # --- edit: Editor + validate/repair (time-guarded) ---
            remaining_ms = context.get_remaining_time_in_millis() if context else 30000
            allow_repair = remaining_ms > REPAIR_MIN_BUDGET_MS
            ok, fixed_xml, err = edit_with_repair(
                bedrock_client, BEDROCK_MODEL_ID, current_xml, instruction,
                original_note_count, allow_repair=allow_repair)
            if ok:
                msg = reply or "Done - updated the transcription."
                return {'statusCode': 200, 'headers': headers,
                        'body': json.dumps(build_response('edit', msg, xml_content=fixed_xml))}
            print(f"Edit failed validation: {err}")
            return {'statusCode': 200, 'headers': headers,
                    'body': json.dumps(build_response('reject',
                        "I couldn't apply that cleanly - try rephrasing or being more specific."))}

        except Exception as e:
            print(f"Error in /api/v1/fix: {str(e)}")
            return {'statusCode': 500, 'headers': headers,
                    'body': json.dumps({'error': f'Edit failed: {str(e)}'})}
```

- [ ] **Step 3: Verify handler imports and no dead references remain**

Run: `cd api-lambda && . .venv/bin/activate && python -c "import handler" && python -m pytest -q`
Expected: import succeeds; all backend tests pass (transpose, validate, response, router, executor — ~31 tests).
Also grep to confirm the old helpers are gone:
Run: `grep -n "_classify_intent\|_classify_transpose_semitones" handler.py`
Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add api-lambda/handler.py
git commit -m "feat(api-lambda): rewrite /fix as conversational Router->Edit pipeline

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Frontend — send history, branch on action, framing copy

**Files:**
- Modify: `web/src/components/chat/ChatInterface.tsx`
- Modify: `web/src/components/chat/ChatInterface.css`

- [ ] **Step 1: Send conversation history and handle the new response contract in `handleAiFix`**

In `ChatInterface.tsx`, replace the body of the `handleAiFix` callback (currently lines ~418–498) so it sends `history` and branches on `action`. Replace from `const handleAiFix = useCallback(` through its closing `, [updateAssistantMessage]);` with:

```tsx
  // Conversational edit via Router->Edit pipeline
  const handleAiFix = useCallback(
    async (instruction: string) => {
      if (!latestXmlRef.current) return;

      try {
        updateAssistantMessage({
          status: "processing",
          progress: 30,
          statusText: "Thinking…",
        });

        const fixUrl =
          import.meta.env.VITE_FIX_API_URL ||
          "https://kc3itnsdm0.execute-api.us-east-1.amazonaws.com/api/v1/fix";

        // Last ~6 prior messages as plain text (no XML) for multi-turn context.
        const history = messages
          .slice(-6)
          .map((m) => ({ role: m.role, content: m.content }))
          .filter((m) => m.content);

        const res = await fetch(fixUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            currentXml: latestXmlRef.current,
            instruction,
            history,
          }),
        });

        if (!res.ok) {
          if (res.status === 503 || res.status === 429) {
            throw new Error(
              "The AI service is temporarily busy. Please try again in a moment.",
            );
          }
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.error || `Request failed: ${res.status}`);
        }

        const data = await res.json();
        const action: string = data.action;
        const reply: string =
          data.reply || "Updated the transcription.";

        // restore: swap to the stored original client-side
        if (action === "restore" && originalXmlRef.current) {
          latestXmlRef.current = originalXmlRef.current;
          updateAssistantMessage({
            content: reply,
            status: "complete",
            progress: 100,
            xmlContent: originalXmlRef.current,
          });
          setIsProcessing(false);
          return;
        }

        // clarify / reject: conversational reply only, no score change
        if (action === "clarify" || action === "reject") {
          updateAssistantMessage({
            content: reply,
            status: "complete",
            progress: 100,
          });
          setIsProcessing(false);
          return;
        }

        // edit / transpose: apply the new score
        if (data.xmlContent) {
          const fixedXml = sanitizeXml(data.xmlContent);
          latestXmlRef.current = fixedXml;
          updateAssistantMessage({
            content: reply,
            status: "complete",
            progress: 100,
            xmlContent: fixedXml,
          });
        } else {
          updateAssistantMessage({
            content: reply,
            status: "complete",
            progress: 100,
          });
        }
        setIsProcessing(false);
      } catch (err: any) {
        updateAssistantMessage({
          content: "Sorry, the AI couldn't handle that request.",
          status: "error",
          statusText: err?.message || "Edit request failed.",
        });
        setIsProcessing(false);
      }
    },
    [messages, updateAssistantMessage],
  );
```

Note: this adds `messages` to the dependency array (needed for `history`). The existing `restore_original` intent branch from the old code is gone — restore is now handled via `action === "restore"`.

- [ ] **Step 2: Add the lightweight-model framing line under the input**

In `ChatInterface.tsx`, find the disclaimer paragraph (added in the onboarding work):
```tsx
        <p className="chat-disclaimer">
          🔗 YouTube import — coming soon · Beta · AI results may vary
        </p>
```
Replace with:
```tsx
        <p className="chat-disclaimer">
          🔗 YouTube import — coming soon · Beta · AI results may vary
        </p>
        {hasUserMessages && latestXmlRef.current && (
          <p className="chat-model-note">
            Edits use a lightweight AI model — keep requests specific.
          </p>
        )}
```

- [ ] **Step 3: Add the `.chat-model-note` style**

In `ChatInterface.css`, directly after the `.chat-disclaimer { ... }` rule, add:
```css
.chat-model-note {
  text-align: center;
  font-size: 0.7rem;
  color: #555;
  margin: 2px 0 0;
}
```

- [ ] **Step 4: Verify the build and lint pass**

Run: `cd web && npm run build`
Expected: `tsc -b && vite build` succeeds with no errors.
Run: `npx eslint src/components/chat/ChatInterface.tsx`
Expected: no NEW errors beyond the project's pre-existing `no-unsafe-*`/`no-explicit-any` baseline in this file (the `any` in the `catch` matches existing style).

- [ ] **Step 5: Commit**

```bash
git add web/src/components/chat/ChatInterface.tsx web/src/components/chat/ChatInterface.css
git commit -m "feat(chat): conversational edit responses, multi-turn history, model note

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `cd api-lambda && . .venv/bin/activate && python -m pytest -q`
Expected: all tests pass (transpose 4 + validate 7 + response 6 + router 9 + executor 5 ≈ 31).

- [ ] **Step 2: Confirm the frontend builds**

Run: `cd web && npm run build`
Expected: success.

- [ ] **Step 3: Manual checklist (requires deployed Lambda or local Bedrock access — note any items you cannot exercise)**

Against a running transcription in the chat UI:
- [ ] A clear edit ("change the 3rd note in measure 2 to a D") returns a conversational confirmation and updates the score.
- [ ] A transpose ("transpose up 2 semitones") confirms and updates the score.
- [ ] An ambiguous request ("fix the wrong note") returns a clarifying question; a follow-up answering it then performs the edit (multi-turn).
- [ ] An out-of-scope request ("add a drum track") is declined with a helpful explanation, score unchanged.
- [ ] A "restore the original" request swaps back to the original transcription.
- [ ] The "Edits use a lightweight AI model" note is visible once a transcription exists.

- [ ] **Step 4: Commit (only if a verification fix was needed)**

If Step 3 surfaced a defect, fix it in the relevant file, re-run Steps 1–2, then commit with a `fix(...)` message scoped to the changed file. If nothing needed fixing, no commit — the feature is complete.

---

## Notes for the implementer

- Only touch the files named per task. The branch carries unrelated pre-existing files; stage exact paths only.
- `import handler` constructs boto3 client objects but makes no network calls — it works offline. If it raises on missing AWS creds/region, set `AWS_REGION=us-east-1` for the check.
- The Editor's `SYSTEM_PROMPT` in `edit_executor.py` is the existing `/fix` system prompt moved verbatim (guitar tuning rules). The Router's prompt is new and contains NO XML.
- Restore is handled two ways that must stay consistent: the existing client-side `isRestoreIntent` shortcut (instant, in `handleSend`) and the backend Router's `restore` action. Both swap to `originalXmlRef`; keep their reply wording friendly and aligned.
