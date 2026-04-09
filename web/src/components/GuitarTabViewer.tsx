import { useRef, useState, useEffect, useCallback } from "react";
import {
  Play,
  Pause,
  Square,
  Printer,
  Code2,
  Music4,
  ZoomIn,
  ZoomOut,
  Columns2,
  FileText,
  ChevronUp,
  ChevronDown,
  Loader2,
  Download,
} from "lucide-react";
import { useAlphaTab } from "../hooks/useAlphaTab";
import "./GuitarTabViewer.css";

interface GuitarTabViewerProps {
  xmlContent: string;
  /** Start collapsed inside a chat bubble */
  defaultCollapsed?: boolean;
}

export const GuitarTabViewer: React.FC<GuitarTabViewerProps> = ({
  xmlContent,
  defaultCollapsed = false,
}) => {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const mainRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);

  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const [showXml, setShowXml] = useState(false);

  const [state, actions] = useAlphaTab({ xmlContent, mainRef, viewportRef });

  // Keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      )
        return;

      if (e.code === "Space" && state.playerReady) {
        e.preventDefault();
        actions.playPause();
      }
      if (e.code === "Escape" && state.isPlaying) {
        actions.stop();
      }
    },
    [state.playerReady, state.isPlaying, actions],
  );

  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    el.addEventListener("keydown", handleKeyDown as EventListener);
    return () =>
      el.removeEventListener("keydown", handleKeyDown as EventListener);
  }, [handleKeyDown]);

  const handleDownloadXml = () => {
    const blob = new Blob([xmlContent], { type: "application/xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${state.songTitle || "transcription"}.musicxml`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (collapsed) {
    return (
      <button className="at-collapsed-card" onClick={() => setCollapsed(false)}>
        <Music4 size={20} />
        <div className="at-collapsed-info">
          <span className="at-collapsed-title">
            {state.songTitle || "Guitar Transcription"}
          </span>
          <span className="at-collapsed-sub">Click to expand tab viewer</span>
        </div>
        <ChevronDown size={16} className="at-collapsed-chevron" />
      </button>
    );
  }

  return (
    <div className="at-wrap" ref={wrapperRef} tabIndex={0}>
      {/* ── Floating Toolbar ── */}
      <div className="at-toolbar">
        <div className="at-toolbar-group">
          <button
            className="at-icon-btn"
            onClick={actions.stop}
            disabled={!state.playerReady}
            title="Stop"
          >
            <Square size={16} />
          </button>
          <button
            className={`at-icon-btn at-play-btn ${state.isPlaying ? "playing" : ""}`}
            onClick={actions.playPause}
            disabled={!state.playerReady}
            title={state.isPlaying ? "Pause (Space)" : "Play (Space)"}
          >
            {state.isPlaying ? <Pause size={16} /> : <Play size={16} />}
          </button>

          {!state.playerReady && (
            <span className="at-toolbar-loading">
              <Loader2 size={14} className="at-spin" />
              {state.loadingProgress}%
            </span>
          )}

          <span className="at-toolbar-time">
            {state.currentTime} / {state.endTime}
          </span>
        </div>

        <div className="at-toolbar-song">
          <span className="at-toolbar-title">{state.songTitle}</span>
          {state.songArtist && (
            <span className="at-toolbar-artist">{state.songArtist}</span>
          )}
        </div>

        <div className="at-toolbar-group">
          <button
            className="at-icon-btn"
            onClick={() => actions.setZoom(Math.max(25, state.zoom - 25))}
            title="Zoom out"
          >
            <ZoomOut size={16} />
          </button>
          <span className="at-toolbar-zoom-label">{state.zoom}%</span>
          <button
            className="at-icon-btn"
            onClick={() => actions.setZoom(Math.min(200, state.zoom + 25))}
            title="Zoom in"
          >
            <ZoomIn size={16} />
          </button>

          <div className="at-toolbar-divider" />

          <button
            className={`at-icon-btn ${state.layout === "horizontal" ? "active" : ""}`}
            onClick={() =>
              actions.setLayout(state.layout === "page" ? "horizontal" : "page")
            }
            title={`Layout: ${state.layout}`}
          >
            {state.layout === "page" ? (
              <FileText size={16} />
            ) : (
              <Columns2 size={16} />
            )}
          </button>

          <button
            className={`at-icon-btn ${showXml ? "active" : ""}`}
            onClick={() => setShowXml(!showXml)}
            title={showXml ? "Show tab" : "Show XML source"}
          >
            <Code2 size={16} />
          </button>

          <button
            className="at-icon-btn"
            onClick={handleDownloadXml}
            title="Download MusicXML"
          >
            <Download size={16} />
          </button>

          <button className="at-icon-btn" onClick={actions.print} title="Print">
            <Printer size={16} />
          </button>

          <div className="at-toolbar-divider" />

          <button
            className="at-icon-btn"
            onClick={() => setCollapsed(true)}
            title="Collapse"
          >
            <ChevronUp size={16} />
          </button>
        </div>
      </div>

      {/* ── Loading Overlay ── */}
      {state.isLoading && (
        <div className="at-overlay">
          <div className="at-overlay-content">
            <Loader2 size={24} className="at-spin" />
            <span>Loading music sheet...</span>
          </div>
        </div>
      )}

      {/* ── Render Error ── */}
      {state.renderError && !state.isLoading && (
        <div className="at-overlay">
          <div className="at-overlay-content" style={{ color: '#ff6b6b' }}>
            <span>⚠ {state.renderError}</span>
          </div>
        </div>
      )}

      {/* ── Content ── */}
      <div className="at-content">
        {!showXml ? (
          <div className="at-viewport" ref={viewportRef}>
            <div className="at-main" ref={mainRef}></div>
          </div>
        ) : (
          <div className="at-xml-view">
            <pre>{xmlContent}</pre>
          </div>
        )}
      </div>
    </div>
  );
};
