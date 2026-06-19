"""The Editor: whole-MusicXML rewrite via Bedrock, plus a one-shot repair loop.

call_editor_model returns the RAW model text. edit_with_repair sanitizes,
validates, and (when allowed) repairs once, returning (ok, xml, error).
"""
import json
import time

from botocore.exceptions import ReadTimeoutError

from musicxml_validate import sanitize_editor_output, validate_musicxml

# A single Editor call is capped by the Bedrock client's read timeout (set in
# handler.py). Keep EDITOR_READ_TIMEOUT_S in sync with it. The repair retry only
# runs when a second full call still fits the API Gateway ~30s budget.
EDITOR_READ_TIMEOUT_S = 25
DEFAULT_TIME_BUDGET_S = 28

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
    except ReadTimeoutError:
        # The model is too slow for this document; do NOT spend another full
        # read-timeout on the invoke_model fallback - propagate so the caller
        # can fail gracefully within the gateway budget.
        raise
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


def _renderable(xml: str) -> bool:
    """True if xml is well-formed enough to display: parses, has a closing
    </score-partwise>, and has >=1 note. Passing original_note_count=0 skips the
    soft note-count plausibility band, leaving only the hard structural checks."""
    return bool(xml) and validate_musicxml(xml, 0)[0]


def edit_with_repair(client, model_id: str, current_xml: str, instruction: str,
                     original_note_count: int, allow_repair: bool = True,
                     time_budget_s: float = DEFAULT_TIME_BUDGET_S):
    """Run the Editor, sanitize, validate, and repair once if there is time.

    Returns (ok: bool, xml: str | None, error: str | None). A model timeout or
    error fails gracefully (ok=False) rather than raising, so the caller can
    return a friendly message instead of letting the request hit the gateway
    timeout. The repair retry only runs when a second full call still fits the
    remaining time budget.

    Best-effort: if the output is well-formed and renderable but only trips the
    soft note-count plausibility heuristic, it is returned as a success (matching
    the pre-Router behaviour) rather than discarded - so a real edit surfaces a
    result instead of a dead-end. Only genuinely malformed output is rejected.
    """
    start = time.monotonic()
    try:
        raw = call_editor_model(client, model_id, current_xml, instruction)
    except ReadTimeoutError:
        return False, None, "editor timed out"
    except Exception as e:  # noqa: BLE001
        return False, None, f"editor failed: {e}"

    xml = sanitize_editor_output(raw)
    ok, err = validate_musicxml(xml, original_note_count)
    if ok:
        return True, xml, None

    # Repair only if allowed AND a second full call still fits the time budget.
    budget_left = (time.monotonic() - start) <= (time_budget_s - EDITOR_READ_TIMEOUT_S)
    if allow_repair and budget_left:
        try:
            raw2 = call_editor_model(client, model_id, current_xml, instruction,
                                     prior_error=err)
            xml2 = sanitize_editor_output(raw2)
            ok2, err2 = validate_musicxml(xml2, original_note_count)
            if ok2:
                return True, xml2, None
            # Prefer the repair if it is at least renderable (it had the hint).
            if _renderable(xml2):
                xml, err = xml2, (err2 or err)
        except ReadTimeoutError:
            pass  # out of time - fall through to best-effort with pass #1
        except Exception as e:  # noqa: BLE001
            print(f"Editor repair failed: {e}")

    # Best-effort: a renderable result beats rejecting outright.
    if _renderable(xml):
        return True, xml, None
    return False, None, err
