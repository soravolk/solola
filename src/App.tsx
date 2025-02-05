import reactLogo from "./assets/react.svg";
import "./App.css";

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
        <img
          src={reactLogo}
          className="logo"
          alt="React logo"
          style={{
            height: "60px",
            marginRight: "20px",
            padding: "0.5em",
            filter: "invert(1)", // invert colors for good contrast on dark background
          }}
        />
        <h1 style={{ margin: 0, color: "#fff" }}>EG Solo App</h1>
      </div>
    </header>
  );
};

// Content component: displays three parts for the audio upload process
const Content = () => {
  return (
    <main
      style={{
        flex: 1,
        padding: "20px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
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
        {/* Part 2: Drop zone for the audio file */}
        <section style={{ width: "60%" }}>
          <div
            style={{
              display: "flex",
              border: "2px dashed #008CBA",
              borderRadius: "8px",
              padding: "1em",
              backgroundColor: "rgba(0, 140, 186, 0.1)",
              cursor: "pointer",
              height: "40vh",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div style={{ display: "flex", flexDirection: "column" }}>
              <p style={{ margin: "0.5em 0" }}>
                Drag & drop your audio file here
              </p>
              <p style={{ margin: "0.5em 0" }}>or click to select file</p>
            </div>
          </div>
        </section>
      </div>
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
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: "100vh",
        width: "100%",
        background: "linear-gradient(135deg, #000428, #004e92)", // dark blue gradient background
        color: "#fff",
      }}
    >
      <Header />
      <Content />
      <Footer />
    </div>
  );
}

export default App;
