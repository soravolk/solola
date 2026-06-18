# Solola — Smarter Conversational Edit Assistant Design

**Date:** 2026-06-18
**Status:** Approved for planning
**Scope:** A near-term "make the AI feel smarter" pass on the existing `/api/v1/fix` edit flow. This is an interim step toward — but explicitly NOT — the full structured edit-engine rewrite (deferred; see *Roadmap context*).

---

## Problem

After a transcription is produced, the chat box becomes an edit channel. Today any non-transpose, non-restore request is sent to a single budget LLM (`openai.gpt-oss-20b` via Bedrock) that **rewrites the entire MusicXML document**
([api-lambda/handler.py](../../../api-lambda/handler.py), `/api/v1/fix`). This causes three felt problems:

- **It doesn't converse.** On success the backend returns only XML; the frontend shows canned text ("Updated the transcription: …"). The assistant never confirms what it understood, never explains what changed, never asks when a request is ambiguous.
- **It mishandles out-of-scope requests.** Anything the classifier labels `fix` goes to the rewrite call, which will attempt — and often mangle — requests it can't actually fulfil, instead of declining helpfully.
- **It can return broken output.** The whole-document rewrite sometimes emits malformed or truncated MusicXML; the frontend sanitizes some cases but broken results still surface.

We are intentionally **keeping the budget model** (cost-conscious) and instead making the experience feel smarter through the response/prompt/validation layers, while being transparent with users that a lightweight model powers edits.

## Goals

- **Conversational responses:** the assistant confirms what it understood, explains the change in plain language, and asks a clarifying question when the request is ambiguous.
- **Graceful scope handling:** unclear or unsupported requests get a helpful reply (what it *can* do) instead of a mangled score.
- **Validation + auto-repair:** edited MusicXML is validated; if broken, repaired once, and otherwise declined cleanly — never returning garbage to the client.
- **Multi-turn clarification:** the assistant can ask a question and apply the edit on the user's follow-up.
- **Transparency:** users are told, subtly, that edits use a lightweight model so expectations are calibrated.

## Non-goals (explicitly out of scope)

- Replacing the whole-XML rewrite with a structured intent→operation engine (the deferred robust-engine piece — see roadmap). The fragile rewrite stays underneath; this pass raises the *felt* quality, not the absolute reliability ceiling.
- Upgrading the model off `gpt-oss-20b`.
- Adding brand-new deterministic edit operations beyond today's transpose. (The Editor LLM may already attempt articulations/rhythm via rewrite; we gate, validate, and narrate — we do not build new deterministic ops here.)
- Moving `/fix` to async/WebSocket (kept synchronous; noted as a future option if latency demands it).
- Changes to the transcription/generation pipeline.

## Roadmap context

Part of the Solola LLM-UX roadmap. Sequencing was revised this session: this "smarter assistant" pass comes first as a low-risk win; the structured edit-engine rewrite is deferred to a later piece (it can reuse the Router defined here as its front door).

- **⓪ App orientation** — DONE.
- **★ Smarter conversational edit assistant** ← *this spec*
- **① Robust structured edit engine** — deferred (intent→operation→apply→validate; deterministic application).
- **② In-context discoverability & graceful failure** — depends on the above.
- **③ Pre-transcription parameters (tempo)** — independent.
- **④ Export & playback** — independent.

---

## Architecture (Approach B: Router + Edit)

`/api/v1/fix` becomes a small pipeline. The deterministic transpose/restore fast-paths are preserved.

```
request { currentXml, instruction, history[] }
        │
        ▼
 ┌──────────────┐   transpose ──► transpose_musicxml() ───────────┐
 │   ROUTER     │   restore   ──► signal client restore ──────────┤
 │  (LLM call,  │   clarify   ──► reply only (no XML) ────────────┤
 │   NO XML)    │   reject    ──► reply only (no XML) ────────────┤
 │              │   edit ─────► EDITOR (LLM, XML) ─► VALIDATE ─────┤
 └──────────────┘                          ▲           │ invalid   │
                                            └─ repair×1 ┘           │
                                                                    ▼
                          response { action, reply, xmlContent? }
```

### Components

Each is a focused unit with one responsibility.

**1. Router** — *LLM call #1, no XML in the prompt.*
- Input: recent conversation `history` (text only) + the new `instruction` + a flag for whether a transcription currently exists.
- Output (small structured result): `intent ∈ {edit, transpose, restore, clarify, reject}`, a conversational `reply` string, and `semitones` (signed int) when `intent=transpose`.
- Replaces and extends the current `_classify_intent` + `_classify_transpose_semitones`. Because it sees history but no XML, it is cheap, fast, token-safe, and can resolve follow-ups to its own clarifying questions.
- The router prompt embeds the **scope list** (below) so in/out-of-scope decisions have a single source of truth.
- Output format: a single small strict JSON object (no XML is present in the Router path, so JSON is safe and robust to parse). Parsing falls back to `intent=edit` on any parse failure (preserves today's safe default).

**2. Deterministic fast-paths** — transpose (existing `transpose_musicxml`) and restore (client-side swap, already implemented). Unchanged logic, but each now carries a conversational `reply` (from the Router for transpose; templated for restore).

**3. Editor** — *LLM call #2, with XML.* Runs ONLY for `intent=edit`. Essentially today's whole-XML rewrite call (same system prompt with guitar tuning rules), returning edited MusicXML. Followed immediately by Validation.

**4. Validator + repair** — see *Validation & auto-repair*.

**5. Response builder** — assembles the uniform response envelope.

### Response contract

`/api/v1/fix` always returns this shape:

```json
{
  "action": "edit | transpose | restore | clarify | reject",
  "reply": "always present — the assistant's conversational message",
  "xmlContent": "present ONLY for edit and transpose",
  "intent": "restore_original (present ONLY for restore; preserves current client behavior)"
}
```

Frontend behavior by `action`:
- `edit` / `transpose`: show `reply` as the assistant bubble; swap the score with `xmlContent`.
- `restore`: existing client-side restore behavior (swap to `originalXmlRef`), show `reply`.
- `clarify` / `reject`: show `reply` only; no score change; stay ready for the next message.

---

## Validation & auto-repair

Applied to Editor output before it can reach the client:

1. **Sanitize** — reuse existing fixes: `A#`/`Ab` → `<step>` + `<alter>`, grace-note structure repair, strip `<?GP…?>`, strip reasoning/thinking blocks, extract from `<?xml`/`<score-partwise>` to `</score-partwise>`.
2. **Validate** — parse with `xml.etree.ElementTree` (well-formed?); confirm structural sanity: contains a `<score-partwise>`…`</score-partwise>`, has ≥1 `<note>`, is not truncated, and the note count has not changed implausibly versus the input (guards against the model dropping large sections). The exact "implausible" threshold: reject if the new note count is < 50% or > 200% of the original (a heuristic, documented as tunable).
3. **Repair ×1** — if invalid, retry the Editor once with the validation error appended ("your previous output was invalid because X; return the complete corrected MusicXML"). Subject to the time guard below.
4. **Decline gracefully** — if still invalid, NEVER return broken XML. Downgrade to `action=reject` with a reply like "I couldn't apply that cleanly — try rephrasing or being more specific."

### 30-second budget constraint

API Gateway caps the synchronous request at 30s, and the pipeline may run Router + Editor + one repair. Router is tiny (~1–2s). Decision:
- Keep `/fix` **synchronous**.
- Allow **at most one** repair retry.
- Add a **server-side time guard**: track elapsed time; skip the repair retry if insufficient budget remains (fall back to the graceful decline) so we never hit the gateway timeout.
- Future option (out of scope): move `/fix` to the async WebSocket pattern already used by transcription if Editor latency proves too tight.

---

## Scope definition (Router gating)

Single source of truth, embedded in the Router prompt and here:

- **In scope → `edit`:** change a note's pitch / fret / string; change a note's duration or rhythm; add or remove guitar articulations (bend, slide, hammer-on / pull-off, vibrato, palm-mute).
- **In scope → fast-path:** transpose up/down N semitones; restore/undo to the original transcription.
- **Ambiguous but in scope → `clarify`:** a supported edit type missing a target or value (e.g. "fix the wrong note" → ask which measure/note and the intended value).
- **Out of scope → `reject` + guidance:** generating new music, changing instrument or tuning wholesale, adding backing tracks, editing the audio, lyrics, structural re-composition — anything not expressible as an edit to the existing notation. The reply explains what the assistant *can* do.

---

## Frontend changes

In [web/src/components/chat/ChatInterface.tsx](../../../web/src/components/chat/ChatInterface.tsx):

- **Multi-turn context:** `handleAiFix` sends `{ currentXml, instruction, history }`, where `history` is the last ~6 message texts (role + content, NO XML) so the Router can resolve follow-ups to its clarifying questions.
- **Uniform response handling:** branch on `action` per the contract above. The hard-coded client-side `isRestoreIntent` shortcut may remain as an instant path, but its reply text should match the new conversational tone; the Router's `restore` is the fallback. (Implementation note: keep one source of restore truth — prefer routing through the response contract; the client shortcut is an optimization, not a second behavior.)
- **Transparency framing:** a subtle, persistent one-liner in the edit area, e.g. *"Edits use a lightweight AI model — keep requests specific."* Shown once/subtly (not per message). `reject` replies may also mention the lightweight model tastefully.

---

## File structure

**Backend** — extract edit logic out of the 868-line `handler.py` into focused modules in `api-lambda/`, each independently testable:

| File | Responsibility |
|------|----------------|
| `api-lambda/edit_router.py` | Build Router prompt (incl. scope list), call Bedrock, parse the structured result; safe `edit` fallback on parse failure. |
| `api-lambda/edit_executor.py` | Build Editor prompt, call Bedrock, run sanitize fixes. |
| `api-lambda/musicxml_validate.py` | Validate well-formedness + structural sanity (note-count heuristic); orchestrate the single repair retry. |
| `api-lambda/transpose.py` | The existing deterministic transpose helpers, moved out of `handler.py`. |
| `api-lambda/edit_response.py` | Build the uniform response envelope. |
| `api-lambda/handler.py` | `/api/v1/fix` route becomes a thin orchestrator: rate-limit → size-check → Router → dispatch → (Editor → validate/repair) → response builder. Other routes unchanged. |

**Frontend** — changes confined to `ChatInterface.tsx` (handler + response branching + framing copy); no new components required.

---

## Error handling

- Existing IP rate-limiting and size limits (`MAX_XML_SIZE`, `MAX_INSTRUCTION_SIZE`) stay, applied before the Router.
- Router call failure → fall back to `intent=edit` (today's safe default) OR, if no XML edit is sensible, a generic graceful `reject` reply. Never 500 to the user for a routing hiccup.
- Editor failure / Bedrock error → `action=reject` with a "try again in a moment" reply (preserving the existing 429/503 friendly messaging).
- Validation failure after repair → graceful `reject` (never broken XML).
- All paths stay within the 30s gateway budget via the time guard.

## Testing

No test framework exists in the project today (the `lambda/test_*.py` files are unrelated POC leftovers). For this work we add a **minimal pytest** suite targeting the pure, bug-prone functions, with a mocked Bedrock client (no network):

- `musicxml_validate`: valid XML passes; malformed/truncated XML fails; note-count heuristic triggers on implausible counts; repair-orchestration returns the graceful decline when repair still fails.
- `edit_router` parsing: well-formed router JSON parses to the right `intent`/`reply`/`semitones`; malformed router output falls back to `intent=edit`.
- `edit_response`: builds the correct envelope per action (xmlContent present/absent as specified).

Setup: add `pytest` as a dev dependency for `api-lambda` (e.g. a `requirements-dev.txt`); tests run locally, not packaged into the Lambda image. Bedrock is mocked so tests are offline and deterministic.

Frontend verification (no framework): `npm run build` passes, plus a manual checklist — conversational replies appear; a clarifying question round-trips (ask → follow-up → edit applied); an out-of-scope request is declined with guidance; a deliberately tough edit that breaks XML results in a graceful decline rather than a broken score; the lightweight-model framing is visible.
