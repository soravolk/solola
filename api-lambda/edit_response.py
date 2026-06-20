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
