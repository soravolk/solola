import { useState } from "react";

export const FileUpload = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

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

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      // Check if it's an audio file
      if (file.type.startsWith("audio/")) {
        updateFileUploadStatus(file);
      } else {
        alert("Please select an audio file");
      }
    }
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
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        style={{
          display: "flex",
          border: `2px dashed ${isDragOver ? "#ff6b6b" : "#008CBA"}`,
          borderRadius: "8px",
          padding: "1em",
          backgroundColor: isDragOver
            ? "rgba(255, 107, 107, 0.1)"
            : "rgba(0, 140, 186, 0.1)",
          cursor: "pointer",
          height: "40vh",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          transition: "all 0.2s ease",
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
          <p style={{ margin: "0.5em 0" }}>
            {isDragOver
              ? "Drop your audio file here"
              : "Drag & drop your audio file here"}
          </p>
          <p style={{ margin: "0.5em 0" }}>or click to select file</p>
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
