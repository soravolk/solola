import { useEffect, useRef, useState } from "react";
import type { AlphaTabApi as AlphaTabApiType } from "@coderline/alphatab";
import "./GuitarTabViewer.css";

interface GuitarTabViewerProps {
  xmlContent: string;
}

export const GuitarTabViewer: React.FC<GuitarTabViewerProps> = ({
  xmlContent,
}) => {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const mainRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<AlphaTabApiType | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [playerReady, setPlayerReady] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [songTitle, setSongTitle] = useState("");
  const [songArtist, setSongArtist] = useState("");
  const [currentTime, setCurrentTime] = useState("00:00");
  const [endTime, setEndTime] = useState("00:00");
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [zoom, setZoom] = useState(100);
  const [layout, setLayout] = useState<"page" | "horizontal">("page");
  const [showXml, setShowXml] = useState(false);

  const formatDuration = (milliseconds: number) => {
    let seconds = milliseconds / 1000;
    const minutes = (seconds / 60) | 0;
    seconds = (seconds - minutes * 60) | 0;
    return (
      String(minutes).padStart(2, "0") + ":" + String(seconds).padStart(2, "0")
    );
  };

  useEffect(() => {
    if (!mainRef.current || !xmlContent || !viewportRef.current) return;

    let cleanup: (() => void) | undefined;

    const initAlphaTab = async () => {
      try {
        const alphaTab = await import("@coderline/alphatab");
        const { AlphaTabApi, Settings, LayoutMode } = alphaTab;

        if (!mainRef.current || !viewportRef.current) return;

        if (apiRef.current) {
          apiRef.current.destroy();
          apiRef.current = null;
        }

        const settings = new Settings();
        settings.core.fontDirectory = "/font/";
        settings.core.engine = "html5";
        settings.core.logLevel = 1;

        settings.player.enablePlayer = true;
        settings.player.enableCursor = true;
        settings.player.enableUserInteraction = true;
        settings.player.soundFont = "/soundfont/sonivox.sf2";
        settings.player.scrollElement = viewportRef.current;

        settings.display.layoutMode = LayoutMode.Page;

        const api = new AlphaTabApi(mainRef.current, settings);
        apiRef.current = api;

        api.renderStarted.on(() => {
          setIsLoading(true);
        });

        api.renderFinished.on(() => {
          setIsLoading(false);
        });

        api.scoreLoaded.on((score) => {
          setSongTitle(score.title || "Guitar Tab");
          setSongArtist(score.artist || "");

          // Enable both standard notation and tablature for all staves
          for (const track of score.tracks) {
            for (const staff of track.staves) {
              staff.showStandardNotation = true;
              staff.showTablature = true;
            }
          }
        });

        api.soundFontLoad.on((e) => {
          const percentage = Math.floor((e.loaded / e.total) * 100);
          console.log(`Soundfont loading: ${percentage}%`);
          setLoadingProgress(percentage);
        });

        api.playerReady.on(() => {
          console.log("✓ Player is ready!");
          setPlayerReady(true);
        });

        api.playerStateChanged.on((e) => {
          console.log("Player state:", e.state);
          setIsPlaying(e.state === 1);
        });

        api.playerPositionChanged.on((e) => {
          setCurrentTime(formatDuration(e.currentTime));
          setEndTime(formatDuration(e.endTime));
        });

        api.error.on((e) => {
          console.error("AlphaTab error:", e);
        });

        const encoder = new TextEncoder();
        const data = encoder.encode(xmlContent);
        api.load(data.buffer as ArrayBuffer);

        cleanup = () => {
          if (apiRef.current) {
            apiRef.current.destroy();
            apiRef.current = null;
          }
        };
      } catch (err) {
        console.error("Failed to initialize AlphaTab:", err);
        setIsLoading(false);
      }
    };

    initAlphaTab();

    return () => {
      cleanup?.();
    };
  }, [xmlContent]);

  const playPause = () => {
    if (apiRef.current && playerReady) {
      apiRef.current.playPause();
    }
  };

  const stop = () => {
    if (apiRef.current && playerReady) {
      apiRef.current.stop();
    }
  };

  const handleZoomChange = async (newZoom: number) => {
    setZoom(newZoom);
    if (apiRef.current) {
      apiRef.current.settings.display.scale = newZoom / 100;
      apiRef.current.updateSettings();
      apiRef.current.render();
    }
  };

  const handleLayoutChange = async (newLayout: "page" | "horizontal") => {
    setLayout(newLayout);
    if (apiRef.current) {
      const alphaTab = await import("@coderline/alphatab");
      apiRef.current.settings.display.layoutMode =
        newLayout === "horizontal"
          ? alphaTab.LayoutMode.Horizontal
          : alphaTab.LayoutMode.Page;
      apiRef.current.updateSettings();
      apiRef.current.render();
    }
  };

  const handlePrint = () => {
    if (apiRef.current) {
      apiRef.current.print();
    }
  };

  return (
    <div className="at-wrap" ref={wrapperRef}>
      {isLoading && (
        <div className="at-overlay">
          <div className="at-overlay-content">Loading music sheet...</div>
        </div>
      )}

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

      <div className="at-controls">
        <div className="at-controls-left">
          <button
            className={
              "at-btn at-player-stop" + (!playerReady ? " disabled" : "")
            }
            onClick={stop}
            disabled={!playerReady}
            title="Stop"
          >
            ⏹
          </button>
          <button
            className={
              "at-btn at-player-play-pause" + (!playerReady ? " disabled" : "")
            }
            onClick={playPause}
            disabled={!playerReady}
            title={isPlaying ? "Pause" : "Play"}
          >
            {isPlaying ? "⏸" : "▶"}
          </button>

          {!playerReady && (
            <span className="at-player-progress">{loadingProgress}%</span>
          )}

          <div className="at-song-info">
            <span className="at-song-title">{songTitle}</span>
            {songArtist && (
              <span className="at-song-artist"> - {songArtist}</span>
            )}
          </div>

          <div className="at-song-position">
            {currentTime} / {endTime}
          </div>
        </div>

        <div className="at-controls-right">
          <button
            className={"at-btn" + (!showXml ? " active" : "")}
            onClick={() => setShowXml(false)}
            title="Tab View"
          >
            Tab
          </button>
          <button
            className={"at-btn" + (showXml ? " active" : "")}
            onClick={() => setShowXml(true)}
            title="XML Source"
          >
            XML
          </button>

          <button className="at-btn" onClick={handlePrint} title="Print">
            Print
          </button>

          <div className="at-zoom">
            <select
              value={zoom}
              onChange={(e) => handleZoomChange(parseInt(e.target.value))}
            >
              <option value="25">25%</option>
              <option value="50">50%</option>
              <option value="75">75%</option>
              <option value="90">90%</option>
              <option value="100">100%</option>
              <option value="110">110%</option>
              <option value="125">125%</option>
              <option value="150">150%</option>
              <option value="200">200%</option>
            </select>
          </div>

          <div className="at-layout">
            <select
              value={layout}
              onChange={(e) =>
                handleLayoutChange(e.target.value as "page" | "horizontal")
              }
            >
              <option value="page">Page</option>
              <option value="horizontal">Horizontal</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );
};
