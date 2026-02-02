import { useEffect, useRef, useState } from "react";
import type { AlphaTabApi as AlphaTabApiType } from "@coderline/alphatab";

interface GuitarTabViewerProps {
  xmlContent: string;
}

export const GuitarTabViewer: React.FC<GuitarTabViewerProps> = ({
  xmlContent,
}) => {
  const alphaTabRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<AlphaTabApiType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!alphaTabRef.current || !xmlContent) return;

    let cleanup: (() => void) | undefined;

    const initAlphaTab = async () => {
      try {
        const { AlphaTabApi, Settings } = await import("@coderline/alphatab");

        if (!alphaTabRef.current) return;

        // Destroy previous instance if exists
        if (apiRef.current) {
          apiRef.current.destroy();
          apiRef.current = null;
        }

        const settings = new Settings();
        settings.core.fontDirectory = "/font/";
        settings.core.engine = "html5";
        settings.core.logLevel = 1; // Enable debug logging
        settings.player.enablePlayer = false; // Disable player for now to simplify

        const api = new AlphaTabApi(alphaTabRef.current, settings);
        apiRef.current = api;

        // Add error handler
        api.error.on((e) => {
          console.error("AlphaTab error:", e);
          setError(
            `Failed to render guitar tab: ${e.message || "Unknown error"}`,
          );
          setIsLoading(false);
        });

        api.renderStarted.on(() => {
          console.log("AlphaTab rendering started");
          setIsLoading(true);
        });

        api.renderFinished.on(() => {
          console.log("✓ AlphaTab rendering finished");
          setIsLoading(false);
        });

        // Convert XML string to ArrayBuffer and load it
        const encoder = new TextEncoder();
        const data = encoder.encode(xmlContent);

        console.log("Loading MusicXML content into AlphaTab...");
        console.log("XML preview:", xmlContent.substring(0, 500));

        // Use the load method with the raw data
        api.load(data.buffer as ArrayBuffer);

        cleanup = () => {
          if (apiRef.current) {
            apiRef.current.destroy();
            apiRef.current = null;
          }
        };
      } catch (err) {
        console.error("Failed to initialize AlphaTab:", err);
        setError("Failed to load guitar tab viewer");
        setIsLoading(false);
      }
    };

    initAlphaTab();

    return () => {
      cleanup?.();
    };
  }, [xmlContent]);

  return (
    <div
      style={{
        width: "100%",
        backgroundColor: "#fff",
        borderRadius: "8px",
        padding: "1em",
        boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
      }}
    >
      <h2 style={{ color: "#333", marginTop: 0 }}>Guitar Tab</h2>
      {error && (
        <div
          style={{
            padding: "1em",
            backgroundColor: "#ffebee",
            color: "#c62828",
            borderRadius: "4px",
            marginBottom: "1em",
          }}
        >
          {error}
        </div>
      )}
      {isLoading && !error && (
        <div
          style={{
            padding: "1em",
            color: "#666",
            textAlign: "center",
          }}
        >
          Loading guitar tab...
        </div>
      )}
      <div
        ref={alphaTabRef}
        style={{
          minHeight: "400px",
          width: "100%",
        }}
      />
    </div>
  );
};
