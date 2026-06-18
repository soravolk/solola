# App Orientation (Onboarding) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign Solola's chat empty state into a clean, professional first-touch that says what the app is for and sets expectations, with all detail tucked behind a collapsed "How it works & what to expect" accordion.

**Architecture:** A new self-contained `HowItWorks` React component (owns its own open/closed state, static content) is dropped into the existing empty-state block of `ChatInterface.tsx`. The old three-suggestion-card grid and timing paragraph are removed; YouTube moves to a "coming soon" footer hint and the input placeholder is updated. Frontend-only — no backend, no pipeline, no WebSocket changes.

**Tech Stack:** React 18 + TypeScript, Vite, plain CSS modules per component, `lucide-react` icons. **No test framework exists** in this project (no Vitest, no test files), and adding one is out of scope per the spec — verification is `npm run lint`, `npm run build`, and a manual checklist.

**Spec:** `docs/superpowers/specs/2026-06-16-app-orientation-design.md`

**Commit policy (user requirement):** Commit after each small step. Each task below ends in a commit; do not batch tasks into one commit.

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `web/src/components/chat/HowItWorks.tsx` | The collapsible orientation accordion: trigger + panel (3 steps + 3 expectation lines), owns open/closed state | Create |
| `web/src/components/chat/HowItWorks.css` | Styling + collapse animation + responsive/reduced-motion for the accordion | Create |
| `web/src/components/chat/ChatInterface.tsx` | Wire `HowItWorks` into the empty state; new headline/subtitle copy; remove suggestion cards + timing paragraph; update input placeholder and footer hint | Modify |
| `web/src/components/chat/ChatInterface.css` | Remove now-unused suggestion-card and timing styles (incl. responsive rules) | Modify |

**Working directory for all commands:** `eg-solo-app/web`

---

### Task 1: Create the `HowItWorks` accordion component

**Files:**
- Create: `web/src/components/chat/HowItWorks.tsx`
- Create: `web/src/components/chat/HowItWorks.css`

- [ ] **Step 1: Create `HowItWorks.css`**

Create `web/src/components/chat/HowItWorks.css` with exactly:

```css
.how-it-works {
  width: 100%;
  max-width: 460px;
  margin: 4px auto 32px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  text-align: left;
  overflow: hidden;
}

.how-it-works-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 12px 16px;
  background: transparent;
  border: none;
  color: #cfcfe0;
  font-size: 0.85rem;
  font-family: inherit;
  cursor: pointer;
}

.how-it-works--open .how-it-works-trigger {
  color: #b0abf5;
}

.how-it-works-chevron {
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.how-it-works--open .how-it-works-chevron {
  transform: rotate(180deg);
}

.how-it-works-panel {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.25s ease;
}

.how-it-works--open .how-it-works-panel {
  max-height: 360px;
}

.how-it-works-panel-inner {
  padding: 4px 16px 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.how-it-works-steps {
  display: flex;
  gap: 8px;
  margin: 12px 0;
}

.how-it-works-step {
  flex: 1;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 9px 8px;
  font-size: 0.7rem;
  color: #cfcfe0;
  line-height: 1.35;
}

.how-it-works-step-label {
  display: block;
  color: #b0abf5;
  font-size: 0.62rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  margin-bottom: 4px;
}

.how-it-works-expectations {
  list-style: none;
  margin: 0;
  padding: 0;
  font-size: 0.76rem;
  color: #9a9ab0;
  line-height: 1.6;
}

.how-it-works-expectations li {
  margin-bottom: 3px;
}

@media (prefers-reduced-motion: reduce) {
  .how-it-works-panel,
  .how-it-works-chevron {
    transition: none;
  }
}

@media (max-width: 768px) {
  .how-it-works-steps {
    flex-direction: column;
  }
}
```

- [ ] **Step 2: Create `HowItWorks.tsx`**

Create `web/src/components/chat/HowItWorks.tsx` with exactly:

```tsx
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import "./HowItWorks.css";

const STEPS = [
  { num: "1", label: "UPLOAD", body: "An electric guitar solo (audio file)" },
  { num: "2", label: "WAIT", body: "~7–8× the clip length" },
  { num: "3", label: "REFINE", body: "Edit & play the tab" },
] as const;

const EXPECTATIONS = [
  "⏱ A 25s clip ≈ 3 min · a 2 min clip ≈ 16 min",
  "🎸 Built for single-instrument electric guitar solos",
  "⚠️ Beta — AI output isn't perfect; you can fix it in chat",
] as const;

interface HowItWorksProps {
  /** Start expanded — primarily for manual review/testing. */
  defaultOpen?: boolean;
}

export const HowItWorks: React.FC<HowItWorksProps> = ({
  defaultOpen = false,
}) => {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = "how-it-works-panel";

  return (
    <div className={`how-it-works${open ? " how-it-works--open" : ""}`}>
      <button
        type="button"
        className="how-it-works-trigger"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
      >
        <span>How it works &amp; what to expect</span>
        <ChevronDown size={16} className="how-it-works-chevron" />
      </button>
      <div
        id={panelId}
        className="how-it-works-panel"
        role="region"
        aria-label="How it works and what to expect"
      >
        <div className="how-it-works-panel-inner">
          <div className="how-it-works-steps">
            {STEPS.map((s) => (
              <div key={s.num} className="how-it-works-step">
                <span className="how-it-works-step-label">
                  {s.num} · {s.label}
                </span>
                {s.body}
              </div>
            ))}
          </div>
          <ul className="how-it-works-expectations">
            {EXPECTATIONS.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};
```

- [ ] **Step 3: Verify it type-checks and lints**

Run (from `eg-solo-app/web`): `npm run lint && npx tsc -b`
Expected: no errors. (The component isn't imported yet, so `npm run build` would tree-shake it; `tsc -b` confirms types, `lint` confirms style.)

- [ ] **Step 4: Commit**

```bash
git add web/src/components/chat/HowItWorks.tsx web/src/components/chat/HowItWorks.css
git commit -m "feat(chat): add HowItWorks orientation accordion component

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Wire `HowItWorks` into the empty state and update copy

**Files:**
- Modify: `web/src/components/chat/ChatInterface.tsx`

- [ ] **Step 1: Add the `HowItWorks` import**

In `web/src/components/chat/ChatInterface.tsx`, find (line ~5):

```tsx
import { ChatInput } from "./ChatInput";
```

Add immediately below it:

```tsx
import { HowItWorks } from "./HowItWorks";
```

- [ ] **Step 2: Replace the empty-state block**

Find the empty-state JSX (currently lines ~603–643):

```tsx
          {!hasUserMessages && (
            <div className="chat-empty-state">
              <div className="chat-empty-logo">
                <Guitar size={40} />
              </div>
              <h2 className="chat-empty-title">
                What would you like to transcribe?
              </h2>
              <p className="chat-empty-subtitle">
                Upload a guitar recording and I'll generate notation and
                tablature for you.
              </p>
              <p className="chat-empty-timing">
                ⏱ Transcription takes roughly 7–8× the audio length (e.g. a
                25s clip ≈ 3 min, a 2 min clip ≈ 16 min).
              </p>
              <div className="chat-suggestion-cards">
                {SUGGESTION_CARDS.map((card) => (
                  <div
                    key={card.title}
                    className={`chat-suggestion-card${
                      card.comingSoon ? " chat-suggestion-card--coming-soon" : ""
                    }`}
                  >
                    <card.icon size={20} className="chat-suggestion-icon" />
                    <div style={{ flex: 1 }}>
                      <div className="chat-suggestion-title">
                        {card.title}
                        {card.comingSoon && (
                          <span className="chat-suggestion-coming-soon">Coming Soon</span>
                        )}
                      </div>
                      <div className="chat-suggestion-desc">
                        {card.description}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
```

Replace the entire block above with:

```tsx
          {!hasUserMessages && (
            <div className="chat-empty-state">
              <div className="chat-empty-logo">
                <Guitar size={40} />
              </div>
              <h2 className="chat-empty-title">Transcribe your guitar solo</h2>
              <p className="chat-empty-subtitle">
                AI turns an electric guitar solo into editable notation &amp;
                tab.
              </p>
              <HowItWorks />
            </div>
          )}
```

- [ ] **Step 3: Verify the empty state renders correctly**

Run (from `eg-solo-app/web`): `npm run dev`, open the printed localhost URL.
Expected (before sending any message):
- Headline reads "Transcribe your guitar solo".
- Subtitle reads "AI turns an electric guitar solo into editable notation & tab."
- A **collapsed** "How it works & what to expect" row is visible.
- The old three suggestion cards are gone.
- Clicking the row expands to show 3 steps (UPLOAD / WAIT / REFINE) and 3 expectation lines; clicking again collapses it.

(There will be a temporary lint/TS warning about unused `SUGGESTION_CARDS` and icon imports — that is cleaned up in Task 4. Do not fix it here.)

- [ ] **Step 4: Commit**

```bash
git add web/src/components/chat/ChatInterface.tsx
git commit -m "feat(chat): use HowItWorks accordion in empty state, update copy

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Update input placeholder and footer hint

**Files:**
- Modify: `web/src/components/chat/ChatInterface.tsx`

- [ ] **Step 1: Update the idle input placeholder**

Find (lines ~668–672):

```tsx
          placeholder={
            isProcessing
              ? "Processing your request..."
              : "Upload an audio file or paste a YouTube link..."
          }
```

Replace with:

```tsx
          placeholder={
            isProcessing
              ? "Processing your request..."
              : "Upload an audio file to transcribe…"
          }
```

- [ ] **Step 2: Replace the disclaimer with the footer hint**

Find (lines ~674–677):

```tsx
        <p className="chat-disclaimer">
          Solola uses AI to transcribe guitar audio. Results may vary based on
          audio quality.
        </p>
```

Replace with:

```tsx
        <p className="chat-disclaimer">
          🔗 YouTube import — coming soon · Beta · AI results may vary
        </p>
```

- [ ] **Step 3: Verify**

Run (from `eg-solo-app/web`): `npm run dev` (or refresh the running dev server).
Expected:
- The input box placeholder reads "Upload an audio file to transcribe…".
- The footer line below the input reads "🔗 YouTube import — coming soon · Beta · AI results may vary".

- [ ] **Step 4: Commit**

```bash
git add web/src/components/chat/ChatInterface.tsx
git commit -m "feat(chat): update input placeholder and footer to mark YouTube coming soon

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Remove now-unused code and styles

**Files:**
- Modify: `web/src/components/chat/ChatInterface.tsx`
- Modify: `web/src/components/chat/ChatInterface.css`

- [ ] **Step 1: Remove the `SUGGESTION_CARDS` constant**

In `ChatInterface.tsx`, find and delete the entire `SUGGESTION_CARDS` array (currently lines ~75–92):

```tsx
const SUGGESTION_CARDS = [
  {
    icon: Upload,
    title: "Upload Audio",
    description: "Drop a guitar recording to transcribe",
  },
  {
    icon: Link,
    title: "YouTube Link",
    description: "Paste a link to transcribe",
    comingSoon: true,
  },
  {
    icon: Sparkles,
    title: "AI Transcription",
    description: "Get notation + tablature automatically",
  },
];
```

- [ ] **Step 2: Drop the now-unused icon imports**

Find (line ~2):

```tsx
import { Guitar, Upload, Link, Sparkles } from "lucide-react";
```

Replace with:

```tsx
import { Guitar } from "lucide-react";
```

(`Upload`, `Link`, and `Sparkles` were only used by the deleted `SUGGESTION_CARDS`. `Guitar` is still used in the header and empty-state logo.)

- [ ] **Step 3: Remove unused CSS rules**

In `ChatInterface.css`:

(a) Delete the `.chat-empty-timing` rule (currently lines ~186–192):

```css
.chat-empty-timing {
  margin: 0 0 32px;
  font-size: 0.82rem;
  color: #999;
  max-width: 420px;
  line-height: 1.5;
}
```

(b) Delete the entire suggestion-card block (currently lines ~194–265): every rule from `.chat-suggestion-cards {` through the end of `.chat-suggestion-desc { ... }` inclusive. That is these selectors:
`.chat-suggestion-cards`, `.chat-suggestion-card`, `.chat-suggestion-card:hover`, `.chat-suggestion-card--coming-soon`, `.chat-suggestion-card--coming-soon:hover`, `.chat-suggestion-coming-soon`, `.chat-suggestion-icon`, `.chat-suggestion-title`, `.chat-suggestion-desc`.

(c) In the `@media (max-width: 768px)` block, delete the two suggestion rules (currently lines ~322–330):

```css
  .chat-suggestion-cards {
    flex-direction: column;
    align-items: center;
  }

  .chat-suggestion-card {
    width: 100%;
    max-width: 280px;
  }
```

Leave `.chat-empty-title` (the responsive `font-size: 1.25rem` rule) intact.

- [ ] **Step 4: Verify lint, types, and build all pass clean**

Run (from `eg-solo-app/web`): `npm run lint && npm run build`
Expected: no errors and no unused-variable warnings (the `SUGGESTION_CARDS`/icon warnings from Task 2 are now gone). `npm run build` (which runs `tsc -b && vite build`) completes successfully.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/chat/ChatInterface.tsx web/src/components/chat/ChatInterface.css
git commit -m "refactor(chat): remove unused suggestion cards and timing styles

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Final manual verification pass

**Files:** none (verification only)

- [ ] **Step 1: Run the full manual checklist**

Run (from `eg-solo-app/web`): `npm run dev` and open the localhost URL. Confirm every item:

- [ ] Empty state shows: logo, "Transcribe your guitar solo", the subtitle, a **collapsed** accordion, the input bar, and the footer hint with "YouTube import — coming soon".
- [ ] The old three suggestion cards are no longer present.
- [ ] Clicking the accordion reveals exactly the 3 steps (UPLOAD / WAIT / REFINE) and the 3 expectation lines; clicking again collapses it; the chevron rotates.
- [ ] Keyboard: Tab to the accordion trigger, press Enter/Space — it toggles, and `aria-expanded` flips (inspect in devtools).
- [ ] Resize the window narrow (<768px): the step row stacks vertically without horizontal overflow.
- [ ] Upload an audio file (or otherwise send a first message): the empty state + accordion disappear and the conversation view behaves exactly as before.
- [ ] With OS "reduce motion" enabled, expanding the accordion does not animate.

- [ ] **Step 2: Commit (if any verification-driven fix was needed)**

If Step 1 surfaced a defect, fix it, re-run the checklist, then:

```bash
git add web/src/components/chat/
git commit -m "fix(chat): address onboarding verification findings

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

If no fix was needed, no commit — the feature is complete.

---

## Notes for the implementer

- **Only touch the four files listed.** This branch has unrelated pre-existing staged/modified files (`ChatInterface.tsx` was already staged before this work, plus untracked lambda/terraform files). When committing, add **only the specific paths named in each step** so unrelated changes are never swept into your commits.
- The `WELCOME_MESSAGE` constant (top of `ChatInterface.tsx`) is intentionally left unchanged — it only appears once the message list shows.
- The YouTube `handleSend` branch is intentionally left functional; we stop advertising YouTube but do not disable the code path.
