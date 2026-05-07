import { useEffect, useState } from "react";
import { GuitarTabViewer } from "../components/GuitarTabViewer";

export const TestPage: React.FC = () => {
  const [xmlContent, setXmlContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Load the test XML file
    fetch("/test.xml")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load test.xml: ${response.status}`);
        }
        return response.text();
      })
      .then((xml) => {
        console.log("Loaded test.xml, length:", xml.length);
        setXmlContent(xml);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error loading test.xml:", err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div style={{ padding: "20px", textAlign: "center" }}>
        <h2>Loading test file...</h2>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "20px", textAlign: "center", color: "red" }}>
        <h2>Error</h2>
        <p>{error}</p>
        <p>Make sure test.xml exists in the public folder.</p>
      </div>
    );
  }

  if (!xmlContent) {
    return (
      <div style={{ padding: "20px", textAlign: "center" }}>
        <h2>No XML content loaded</h2>
      </div>
    );
  }

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <div
        style={{
          padding: "10px 20px",
          background: "#333",
          color: "white",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1 style={{ margin: 0, fontSize: "1.2rem" }}>🎸 AlphaTab Test Page</h1>
        <a href="/" style={{ color: "#4fc3f7", textDecoration: "none" }}>
          ← Back to App
        </a>
      </div>
      <div style={{ flex: 1, overflow: "hidden" }}>
        <GuitarTabViewer xmlContent={xmlContent} />
      </div>
    </div>
  );
};
