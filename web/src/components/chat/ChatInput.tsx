import { useState, useRef, useCallback } from "react";
import { Paperclip, Send, Music, X } from "lucide-react";
import "./ChatInput.css";

interface ChatInputProps {
  onSend: (text: string, file?: File) => void;
  disabled?: boolean;
  placeholder?: string;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  disabled = false,
  placeholder = "Upload an audio file or paste a YouTube link...",
}) => {
  const [text, setText] = useState("");
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed && !attachedFile) return;

    onSend(trimmed, attachedFile || undefined);
    setText("");
    setAttachedFile(null);

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [text, attachedFile, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && file.type.startsWith("audio/")) {
      setAttachedFile(file);
    }
    // Reset input so the same file can be re-selected
    e.target.value = "";
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("audio/")) {
      setAttachedFile(file);
    }
  };

  const handleTextareaInput = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 150) + "px";
    }
  };

  return (
    <div
      className={`chat-input-container ${isDragOver ? "drag-over" : ""}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Attached file preview */}
      {attachedFile && (
        <div className="chat-input-file-preview">
          <div className="file-preview-info">
            <Music size={16} className="file-preview-icon" />
            <span className="file-preview-name">{attachedFile.name}</span>
            <span className="file-preview-size">
              ({(attachedFile.size / (1024 * 1024)).toFixed(1)} MB)
            </span>
          </div>
          <button
            className="file-preview-remove"
            onClick={() => setAttachedFile(null)}
            title="Remove file"
          >
            <X size={14} />
          </button>
        </div>
      )}

      <div className="chat-input-row">
        {/* File attach button */}
        <button
          className="chat-input-attach"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          title="Attach audio file"
        >
          <Paperclip size={20} />
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*"
          style={{ display: "none" }}
          onChange={handleFileSelect}
        />

        {/* Text input */}
        <textarea
          ref={textareaRef}
          className="chat-input-textarea"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onInput={handleTextareaInput}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
        />

        {/* Send button */}
        <button
          className={`chat-input-send ${
            text.trim() || attachedFile ? "active" : ""
          }`}
          onClick={handleSend}
          disabled={disabled || (!text.trim() && !attachedFile)}
          title="Send"
        >
          <Send size={20} />
        </button>
      </div>

      {isDragOver && (
        <div className="chat-input-drop-overlay">
          <span>Drop audio file here</span>
        </div>
      )}
    </div>
  );
};
