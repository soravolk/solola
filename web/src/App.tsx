import "./App.css";
import { useState } from "react";
import { FileUpload } from "./components/fileUpload";
import { GuitarTabViewer } from "./components/GuitarTabViewer";

// Header component: displays the logos and the main title
const Header: React.FC = () => {
  return (
    <header
      style={{
        width: "100%",
        backgroundColor: "#001f3f", // dark blue header background
        borderBottom: "1px solid #003366",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "start",
          padding: "20px",
        }}
      >
        <h1 style={{ margin: 0, color: "#fff" }}>Solola</h1>
      </div>
    </header>
  );
};

// Content component: displays three parts for the audio upload process
const Content = () => {
  const [xmlContent, setXmlContent] = useState<string | null>(null);

  return (
    <main
      style={{
        flex: 1,
        padding: "20px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        gap: "20px",
      }}
    >
      {!xmlContent ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            width: "80%",
            backgroundColor: "rgba(255, 255, 255, 0.1)",
            borderRadius: "12px",
            padding: "2em",
            boxShadow: "0 4px 12px rgba(0, 0, 0, 0.3)",
            textAlign: "center",
          }}
        >
          {/* Part 1: Instruction for uploading audio */}
          <section style={{ marginBottom: "1em" }}>
            <p style={{ fontSize: "18px", margin: 0 }}>
              Please enter youtube link or upload your audio file.
            </p>
          </section>
          {/* Part 2: Search box for YouTube link */}
          <section style={{ width: "100%" }}>
            <input
              type="text"
              placeholder="Enter YouTube link"
              style={{
                width: "50%",
                padding: "0.6em",
                borderRadius: "4px",
                border: "1px solid #ccc",
                fontSize: "16px",
              }}
            />
          </section>
          <span style={{ padding: "0.5em" }}>or</span>
          {/* Part 3: Drop zone for the audio file */}
          <FileUpload onXmlReady={setXmlContent} />
        </div>
      ) : (
        <div style={{ width: "90%", height: "100%" }}>
          <GuitarTabViewer xmlContent={xmlContent} />
        </div>
      )}
    </main>
  );
};

// Footer component: displays additional information or links
const Footer: React.FC = () => {
  return (
    <footer
      style={{
        width: "100%",
        backgroundColor: "#001f3f",
        padding: "10px 20px",
        borderTop: "1px solid #003366",
        textAlign: "center",
        color: "#fff",
      }}
    >
      <p style={{ marginBottom: "8px" }}>Developed by</p>
      <p style={{ fontSize: "0.8em", opacity: 0.8, margin: 0 }}>
        © 2025 MCT Lab. All rights reserved.
      </p>
    </footer>
  );
};

function App() {
  const [testMode, setTestMode] = useState(false);
  const [testXml, setTestXml] = useState<string | null>(null);

  const loadTestXml = async () => {
    try {
      const response = await fetch("/test.xml");
      const xml = await response.text();
      setTestXml(xml);
      setTestMode(true);
    } catch (err) {
      console.error("Failed to load test.xml:", err);
    }
  };

  if (testMode && testXml) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          height: "100vh",
          width: "100%",
          background: "linear-gradient(135deg, #000428, #004e92)",
          color: "#fff",
        }}
      >
        <header
          style={{
            width: "100%",
            backgroundColor: "#001f3f",
            borderBottom: "1px solid #003366",
            padding: "10px 20px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <h1 style={{ margin: 0, fontSize: "1.2rem" }}>
            🎸 AlphaTab Test Page
          </h1>
          <button
            onClick={() => setTestMode(false)}
            style={{
              padding: "8px 16px",
              background: "#4fc3f7",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
              fontWeight: "bold",
            }}
          >
            ← Back to App
          </button>
        </header>
        <div style={{ flex: 1, overflow: "hidden" }}>
          <GuitarTabViewer xmlContent={testXml} />
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: "100vh",
        width: "100%",
        background: "linear-gradient(135deg, #000428, #004e92)",
        color: "#fff",
      }}
    >
      <Header />
      <Content />
      <Footer />
      {/* Test Mode Button */}
      <button
        onClick={loadTestXml}
        style={{
          position: "fixed",
          bottom: "20px",
          right: "20px",
          padding: "10px 20px",
          background: "#ff9800",
          color: "#000",
          border: "none",
          borderRadius: "8px",
          cursor: "pointer",
          fontWeight: "bold",
          boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
        }}
      >
        🧪 Test Tab Viewer
      </button>
    </div>
  );
}

export default App;
