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
            # 128 is ample for {intent, short reply, semitones}; keeping it low
            # shrinks the Router's slice of the ~30s gateway budget so the Editor
            # pass that follows has room (restoring f8da25f's single-pass headroom).
            inferenceConfig={"temperature": 0, "maxTokens": 128},
        )
        text = response["output"]["message"]["content"][0]["text"]
        return parse_router_output(text)
    except Exception as e:  # noqa: BLE001 - router must never hard-fail the request
        print(f"Router call failed, defaulting to edit: {e}")
        return {"intent": "edit", "reply": "", "semitones": None}
