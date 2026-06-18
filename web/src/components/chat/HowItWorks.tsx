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
        aria-hidden={!open}
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
