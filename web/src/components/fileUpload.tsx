import { useState } from "react";

export const FileUpload = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);

  const updateFileUploadStatus = (file: File | null) => {
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    updateFileUploadStatus(file);
  };

  const handleUpload = () => {
    setIsUploading(true);
  };

  return (
    <section style={{ width: "60%" }}>
      <div
        onClick={() => {
          const fileInput = document.getElementById("fileInput");
          if (fileInput) {
            fileInput.click();
          }
        }}
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
          flexDirection: "column",
        }}
      >
        <input
          id="fileInput"
          type="file"
          accept="audio/*"
          style={{ display: "none" }}
          onChange={handleFileSelect}
        />
        <div style={{ display: "flex", flexDirection: "column" }}>
          <p style={{ margin: "0.5em 0" }}>Click to select file</p>
        </div>
        {selectedFile && (
          <div style={{ marginTop: "1em" }}>
            <p style={{ margin: "0.5em 0" }}>Selected: {selectedFile.name}</p>
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleUpload();
              }}
              disabled={isUploading}
              style={{
                padding: "0.5em 1em",
                backgroundColor: isUploading ? "#666" : "#008CBA",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: isUploading ? "not-allowed" : "pointer",
              }}
            >
              {isUploading ? "Uploading..." : "Upload File"}
            </button>
          </div>
        )}
      </div>
    </section>
  );
};
