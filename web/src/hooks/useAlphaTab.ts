import { useEffect, useRef, useState, useCallback } from "react";
import type { AlphaTabApi as AlphaTabApiType } from "@coderline/alphatab";

export interface AlphaTabState {
  isLoading: boolean;
  renderError: string | null;
  playerReady: boolean;
  isPlaying: boolean;
  songTitle: string;
  songArtist: string;
  currentTime: string;
  endTime: string;
  loadingProgress: number;
  zoom: number;
  layout: "page" | "horizontal";
}

export interface AlphaTabActions {
  playPause: () => void;
  stop: () => void;
  setZoom: (zoom: number) => void;
  setLayout: (layout: "page" | "horizontal") => void;
  print: () => void;
}

interface UseAlphaTabOptions {
  xmlContent: string;
  mainRef: React.RefObject<HTMLDivElement | null>;
  viewportRef: React.RefObject<HTMLDivElement | null>;
}

const formatDuration = (milliseconds: number) => {
  let seconds = milliseconds / 1000;
  const minutes = (seconds / 60) | 0;
  seconds = (seconds - minutes * 60) | 0;
  return (
    String(minutes).padStart(2, "0") + ":" + String(seconds).padStart(2, "0")
  );
};

export const useAlphaTab = ({
  xmlContent,
  mainRef,
  viewportRef,
}: UseAlphaTabOptions): [AlphaTabState, AlphaTabActions] => {
  const apiRef = useRef<AlphaTabApiType | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [playerReady, setPlayerReady] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [songTitle, setSongTitle] = useState("");
  const [songArtist, setSongArtist] = useState("");
  const [currentTime, setCurrentTime] = useState("00:00");
  const [endTime, setEndTime] = useState("00:00");
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [zoom, setZoomState] = useState(80);
  const [layout, setLayoutState] = useState<"page" | "horizontal">("page");

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
        settings.player.soundFont = "/soundfont/sonivox.sf3";
        settings.player.scrollElement = viewportRef.current;
        settings.display.layoutMode = LayoutMode.Page;
        settings.display.scale = 0.8;
        // Shrink tab number font (default 13px) and grace font (default 11px)
        settings.display.resources.tablatureFont.size = 12;
        settings.display.resources.graceFont.size = 9;

        const api = new AlphaTabApi(mainRef.current, settings);
        apiRef.current = api;

        api.renderStarted.on(() => {
          setIsLoading(true);
          setRenderError(null);
        });
        api.renderFinished.on(() => setIsLoading(false));

        api.scoreLoaded.on((score) => {
          setSongTitle(score.title || "Guitar Tab");
          setSongArtist(score.artist || "");
          for (const track of score.tracks) {
            for (const staff of track.staves) {
              staff.showStandardNotation = true;
              staff.showTablature = true;
            }
          }
        });

        api.soundFontLoad.on((e) => {
          setLoadingProgress(Math.floor((e.loaded / e.total) * 100));
        });

        api.playerReady.on(() => setPlayerReady(true));
        api.playerStateChanged.on((e) => setIsPlaying(e.state === 1));
        api.playerPositionChanged.on((e) => {
          setCurrentTime(formatDuration(e.currentTime));
          setEndTime(formatDuration(e.endTime));
        });
        api.error.on((e) => {
          console.error("AlphaTab error:", e);
          setIsLoading(false);
          setRenderError(
            typeof e === "object" && e?.message
              ? e.message
              : "Failed to render music sheet",
          );
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
    return () => cleanup?.();
  }, [xmlContent, mainRef, viewportRef]);

  const playPause = useCallback(() => {
    if (apiRef.current && playerReady) apiRef.current.playPause();
  }, [playerReady]);

  const stop = useCallback(() => {
    if (apiRef.current && playerReady) apiRef.current.stop();
  }, [playerReady]);

  const setZoom = useCallback((newZoom: number) => {
    setZoomState(newZoom);
    if (apiRef.current) {
      apiRef.current.settings.display.scale = newZoom / 100;
      apiRef.current.updateSettings();
      apiRef.current.render();
    }
  }, []);

  const setLayout = useCallback(async (newLayout: "page" | "horizontal") => {
    setLayoutState(newLayout);
    if (apiRef.current) {
      const alphaTab = await import("@coderline/alphatab");
      apiRef.current.settings.display.layoutMode =
        newLayout === "horizontal"
          ? alphaTab.LayoutMode.Horizontal
          : alphaTab.LayoutMode.Page;
      apiRef.current.updateSettings();
      apiRef.current.render();
    }
  }, []);

  const print = useCallback(() => {
    if (apiRef.current) apiRef.current.print();
  }, []);

  const state: AlphaTabState = {
    isLoading,
    renderError,
    playerReady,
    isPlaying,
    songTitle,
    songArtist,
    currentTime,
    endTime,
    loadingProgress,
    zoom,
    layout,
  };

  const actions: AlphaTabActions = {
    playPause,
    stop,
    setZoom,
    setLayout,
    print,
  };

  return [state, actions];
};
