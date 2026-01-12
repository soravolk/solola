import { useState } from "react";

interface GetUploadURLResponse {
  upload_url: string;
  id: string;
}

export const FileUpload = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [uploadedFileId, setUploadedFileId] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);

  const updateFileUploadStatus = (file: File | null) => {
    if (file) {
      setSelectedFile(file);
      setUploadedFileId(null); // Reset uploaded state when new file selected
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    updateFileUploadStatus(file);
  };

  const handleUpload = async () => {
    if (!selectedFile)
      throw new Error("No file is found, please select a file");

    setIsUploading(true);

    try {
      // Step 1: Request presigned URL from backend
      const requestData = {
        source_type: "local",
        source: {
          filename: selectedFile.name,
          content_type: selectedFile.type,
        },
      };

      const apiUrl =
        import.meta.env.VITE_API_URL ||
        "https://kc3itnsdm0.execute-api.us-east-1.amazonaws.com/api/v1/audio";

      console.log("API URL:", apiUrl);
      console.log("Request data:", requestData);

      const response = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestData),
      });

      console.log("Response status:", response.status);
      console.log(
        "Response headers:",
        Object.fromEntries(response.headers.entries())
      );

      const responseText = await response.text();
      console.log("Response body:", responseText);

      if (!response.ok)
        throw new Error(`Failed to get presigned URL: ${response.status}`);

      const result = JSON.parse(responseText) as GetUploadURLResponse;
      const { upload_url, id } = result;

      // Step 2: Upload file directly to S3
      const uploadRes = await fetch(upload_url, {
        method: "PUT",
        headers: { "Content-Type": selectedFile.type },
        body: selectedFile,
      });

      if (!uploadRes.ok) throw new Error("S3 upload failed");

      // Store the uploaded file ID
      setUploadedFileId(id);
      alert(`File uploaded successfully! ID: ${id}`);
    } catch {
      alert("Upload failed. Please try again.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleGenerate = async () => {
    if (!uploadedFileId) return;

    setIsGenerating(true);

    try {
      // TODO: Call your generate API endpoint
      console.log("Generating tabs for file ID:", uploadedFileId);

      // Example API call (adjust based on your backend):
      // const response = await fetch(`${apiUrl}/generate`, {
      //   method: "POST",
      //   headers: { "Content-Type": "application/json" },
      //   body: JSON.stringify({ audio_id: uploadedFileId }),
      // });

      alert(`Starting tab generation for file ID: ${uploadedFileId}`);

      // TODO: Handle the response and show results
    } catch (error) {
      alert("Generation failed. Please try again.");
      console.error("Generation error:", error);
    } finally {
      setIsGenerating(false);
    }
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
        {!uploadedFileId && (
          <div style={{ display: "flex", flexDirection: "column" }}>
            <p style={{ margin: "0.5em 0" }}>
              {isDragOver
                ? "Drop your audio file here"
                : "Drag & drop your audio file here"}
            </p>
            <p style={{ margin: "0.5em 0" }}>or click to select file</p>
          </div>
        )}
        {selectedFile && !uploadedFileId && (
          <div style={{ marginTop: "1em" }}>
            <p style={{ margin: "0.5em 0" }}>Selected: {selectedFile.name}</p>
            <button
              onClick={(e) => {
                e.stopPropagation();
                void handleUpload();
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
        {uploadedFileId && (
          <div style={{ marginTop: "1em", textAlign: "center" }}>
            <p style={{ margin: "0.5em 0", color: "#4CAF50" }}>
              ✓ Upload successful!
            </p>
            <p style={{ margin: "0.5em 0", fontSize: "0.9em", color: "#666" }}>
              File: {selectedFile?.name}
            </p>
            <button
              onClick={(e) => {
                e.stopPropagation();
                void handleGenerate();
              }}
              disabled={isGenerating}
              style={{
                padding: "0.75em 1.5em",
                backgroundColor: isGenerating ? "#666" : "#4CAF50",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: isGenerating ? "not-allowed" : "pointer",
                fontSize: "1em",
                fontWeight: "bold",
                marginTop: "0.5em",
              }}
            >
              {isGenerating ? "Generating..." : "Generate Guitar Tabs"}
            </button>
          </div>
        )}
      </div>
    </section>
  );
};
