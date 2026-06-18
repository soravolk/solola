# Solola — App Orientation (Onboarding) Design

**Date:** 2026-06-16
**Status:** Approved for planning
**Scope:** Piece ⓪ of a larger LLM-UX roadmap (see *Roadmap context* below)

---

## Problem

New users of Solola's chat interface don't reliably understand **what the app
is for** or **what to expect** from it. The current empty state
([web/src/components/chat/ChatInterface.tsx](../../../web/src/components/chat/ChatInterface.tsx))
shows a welcome line, a generic "What would you like to transcribe?" prompt, a
timing note, and three suggestion cards (Upload / YouTube / AI Transcription).
It neither frames the input scope (it's built specifically for **electric
guitar solos**) nor sets expectations about the long processing time and
imperfect, beta-quality output — so the wait and the errors feel broken rather
than expected.

The constraint that shapes this design: the result must feel like a **clean,
professional AI dialogue tool**. Piling on instructional text makes it less
attractive, so orientation must be present but **progressively disclosed** —
minimal by default, full detail one click away.

## Goals

- Communicate, on first touch, **what Solola does** and **what input it expects**
  (single-instrument electric guitar solos, audio file).
- **Set expectations** clearly: the ~7–8× processing time and the beta /
  imperfect-but-fixable nature of AI output.
- Keep the default view **minimal and professional**; no walls of text.
- Mark **YouTube import as "coming soon."**

## Non-goals (explicitly out of scope for piece ⓪)

- In-context discoverability of *edit* capabilities (suggestion chips tied to a
  rendered score, graceful out-of-scope rejection) — that is **piece ②**.
- Any change to the transcription pipeline, the `/fix` edit engine, or the
  WebSocket/progress flow.
- A "Try a sample" pre-loaded demo. Considered and deferred (needs a bundled
  sample audio + finished MusicXML asset); revisit later if desired.
- A persistent in-session "How it works" affordance. By explicit decision the
  orientation lives **only** in the empty state; once a transcription starts it
  is not re-accessible. (Header stays clean: logo + connection status only.)
- Introducing a test framework (none exists today — see *Testing*).

## Roadmap context

This is the first of five planned pieces, each with its own spec → plan →
implementation cycle:

- **⓪ App orientation** ← *this spec*
- **① Robust edit engine** — replace full-MusicXML LLM rewrites with an
  intent→structured-operation layer (reliability + clean out-of-scope detection).
- **② In-context discoverability & graceful failure** — depends on ①.
- **③ Pre-transcription parameters** — let users supply tempo (and possibly
  tuning/key) before generation to improve accuracy. Independent.
- **④ Export & playback** — PDF/Guitar Pro/MIDI export, loop/slow-down. Independent.

---

## Design overview

Chosen direction: **Collapsible "How it works"** (Option C from brainstorming).

The empty state is redesigned around a single confident headline and a
**collapsed accordion**. By default the user sees almost nothing beyond the
value proposition and the input bar. Clicking the accordion reveals the full
orientation: a 3-step flow and three expectation lines. The existing
three-suggestion-card block is removed; the YouTube "coming soon" signal moves
to a quiet footer hint.

### Default (collapsed) — what users see on arrival

```
        🎸  (logo)
   Transcribe your guitar solo
   AI turns an electric guitar solo into editable notation & tab.

   ┌─────────────────────────────────────────┐
   │ How it works & what to expect        ⌄  │
   └─────────────────────────────────────────┘

   ┌─────────────────────────────────────────┐
   │ ＋  Upload an audio file to transcribe…  │
   └─────────────────────────────────────────┘
   🔗 YouTube import — coming soon · Beta · AI results may vary
```

### Expanded (after click)

```
   ┌─────────────────────────────────────────┐
   │ How it works & what to expect        ⌃  │
   ├─────────────────────────────────────────┤
   │ ┌─1·UPLOAD──┐ ┌─2·WAIT────┐ ┌─3·REFINE─┐ │
   │ │ An elec.  │ │ ~7–8× the │ │ Edit &   │ │
   │ │ guitar    │ │ clip      │ │ play the │ │
   │ │ solo      │ │ length    │ │ tab      │ │
   │ └───────────┘ └───────────┘ └──────────┘ │
   │ ⏱ A 25s clip ≈ 3 min · a 2 min clip ≈ 16 min
   │ 🎸 Built for single-instrument electric guitar solos
   │ ⚠️ Beta — AI output isn't perfect; you can fix it in chat
   └─────────────────────────────────────────┘
```

---

## Exact content (copy)

**Headline:** `Transcribe your guitar solo`
**Subtitle:** `AI turns an electric guitar solo into editable notation & tab.`
**Accordion trigger label:** `How it works & what to expect`

**Three steps:**

| Step | Label | Body |
|------|-------|------|
| 1 | `UPLOAD` | `An electric guitar solo (audio file)` |
| 2 | `WAIT` | `~7–8× the clip length` |
| 3 | `REFINE` | `Edit & play the tab` |

**Three expectation lines:**

- `⏱ A 25s clip ≈ 3 min · a 2 min clip ≈ 16 min`
- `🎸 Built for single-instrument electric guitar solos`
- `⚠️ Beta — AI output isn't perfect; you can fix it in chat`

**Input placeholder (idle):** `Upload an audio file to transcribe…`
(drops the "or paste a YouTube link" wording now that YouTube is "coming soon")

**Footer hint:** `🔗 YouTube import — coming soon · Beta · AI results may vary`
(replaces the current `chat-disclaimer` copy)

---

## Components and files affected

All changes are confined to the web frontend; no backend changes.

1. **New component: `HowItWorks` accordion**
   - New file: `web/src/components/chat/HowItWorks.tsx` (+ `HowItWorks.css`).
   - Self-contained: owns its open/closed state (`useState<boolean>`, default
     `false`). Renders the trigger row + collapsible panel (3 steps + 3
     expectation lines). Content is static; no props required (or an optional
     `defaultOpen` prop for testing).
   - **What it does:** show/hide the orientation panel.
     **How you use it:** drop `<HowItWorks />` into the empty state.
     **Depends on:** nothing beyond React + its CSS.

2. **`ChatInterface.tsx` — empty-state block** (currently lines ~603–643)
   - Replace headline/subtitle copy with the new wording.
   - Remove the `SUGGESTION_CARDS` array and its rendered card grid.
   - Remove the standalone `chat-empty-timing` paragraph (its content is
     absorbed into the accordion's expectation lines).
   - Insert `<HowItWorks />` between the subtitle and the message list.

3. **`ChatInterface.tsx` — input + footer**
   - Update idle placeholder to `Upload an audio file to transcribe…`
     (the "Processing your request…" busy placeholder is unchanged).
   - Replace the `chat-disclaimer` text with the footer hint copy.

4. **`WELCOME_MESSAGE`** (lines ~67–73): left as-is — it only appears once the
   message list is shown, which is consistent with the empty state being the
   first-touch surface. (Optional: trim it for tone; not required.)

5. **`.gitignore`**: add `.superpowers/` (brainstorming companion artifacts).

### Interaction / state

- Accordion is **collapsed by default**; click (or Enter/Space on the trigger)
  toggles. Implement the trigger as a `<button>` with `aria-expanded` and
  `aria-controls` pointing at the panel for accessibility.
- Panel expand/collapse uses a CSS transition (max-height or grid-rows) to feel
  smooth; no layout jank in the centered empty state.
- The whole empty state (including the accordion) unmounts once
  `hasUserMessages` becomes true — unchanged from today's behavior. No
  persistence of the open/closed state across sessions.

### Edge cases

- **Very narrow viewports:** the 3-step row should wrap or shrink gracefully
  (stack vertically below a small breakpoint) so steps stay readable on mobile.
- **YouTube link still pasted:** the existing `handleSend` YouTube branch is
  left functional and untouched; the UI simply stops advertising it. (Disabling
  the handler is out of scope.)
- **Reduced motion:** respect `prefers-reduced-motion` by skipping the
  expand/collapse transition.

---

## Testing

The web app currently has **no test framework** (no Vitest, no test files, no
test script). Adding one is out of scope for this small, presentational change.
Verification is therefore:

1. **Type + lint + build pass:** `npm run lint` and `npm run build` (which runs
   `tsc -b`) succeed with no new errors.
2. **Manual verification checklist** (run `npm run dev`):
   - Empty state shows the new headline, subtitle, a **collapsed** accordion,
     the input bar, and the footer hint with "YouTube import — coming soon."
   - The old three suggestion cards are gone.
   - Clicking the accordion reveals exactly the 3 steps and 3 expectation lines;
     clicking again collapses it.
   - Keyboard: the trigger is focusable and toggles on Enter/Space;
     `aria-expanded` flips.
   - Sending a first message (uploading a file) hides the empty state and
     accordion as before.
   - Narrow-width: the step row wraps/stacks without overflow.

If the user later wants automated coverage, a follow-up can introduce Vitest +
React Testing Library and a `HowItWorks` render/toggle test — noted, not
required here.
