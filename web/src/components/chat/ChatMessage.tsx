import { useState } from "react";
import {
  Music,
  AlertTriangle,
  Download,
  Copy,
  Check,
  Loader2,
  Guitar,
  User,
} from "lucide-react";
import type { ChatMessage as ChatMessageType } from "../../types/chat";
import { GuitarTabViewer } from "../GuitarTabViewer";
import "./ChatMessage.css";

interface ChatMessageProps {
  message: ChatMessageType;
  /** True when this message holds the most recent XML — only this one mounts AlphaTab */
  isLatestXml?: boolean;
}

export const ChatMessageBubble: React.FC<ChatMessageProps> = ({ message, isLatestXml = false }) => {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const [copied, setCopied] = useState(false);

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const handleCopyXml = async () => {
    if (!message.xmlContent) return;
    await navigator.clipboard.writeText(message.xmlContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadXml = () => {
    if (!message.xmlContent) return;
    const blob = new Blob([message.xmlContent], { type: "application/xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "transcription.musicxml";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isSystem) {
    return (
      <div className="chat-message-row system">
        <div className="chat-bubble system-bubble">
          <p>{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`chat-message-row ${isUser ? "user" : "assistant"}`}>
      {!isUser && (
        <div className="chat-avatar assistant-avatar">
          <Guitar size={18} />
        </div>
      )}

      <div
        className={`chat-bubble ${isUser ? "user-bubble" : "assistant-bubble"}`}
      >
        {/* File attachment badge */}
        {isUser && message.file && (
          <div className="chat-file-badge">
            <Music size={16} className="file-icon" />
            <span className="file-name">{message.file.name}</span>
            <span className="file-size">
              {(message.file.size / (1024 * 1024)).toFixed(1)} MB
            </span>
          </div>
        )}

        {/* Text content */}
        {message.content && <p className="chat-text">{message.content}</p>}

        {/* Thinking indicator */}
        {!isUser && message.status === "thinking" && (
          <div className="chat-thinking">
            <div className="thinking-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}

        {/* Progress bar */}
        {!isUser && message.status === "processing" && (
          <div className="chat-progress">
            <div className="chat-progress-header">
              <Loader2 size={14} className="chat-progress-spinner" />
              <span className="chat-progress-text">
                {message.statusText || "Processing..."}
              </span>
            </div>
            <div className="chat-progress-bar">
              <div
                className="chat-progress-fill"
                style={{ width: `${message.progress || 0}%` }}
              />
            </div>
            <div className="chat-progress-percentage">
              {message.progress || 0}%
            </div>
          </div>
        )}

        {/* Guitar Tab Viewer embedded in assistant message */}
        {!isUser && message.xmlContent && message.status === "complete" && (
          <>
            <div className="chat-tab-actions">
              <button
                className="chat-tab-action-btn"
                onClick={handleDownloadXml}
                title="Download MusicXML"
              >
                <Download size={14} />
                <span>Download</span>
              </button>
              <button
                className="chat-tab-action-btn"
                onClick={handleCopyXml}
                title="Copy MusicXML"
              >
                {copied ? <Check size={14} /> : <Copy size={14} />}
                <span>{copied ? "Copied!" : "Copy XML"}</span>
              </button>
            </div>
            {isLatestXml ? (
              <div className="chat-tab-viewer">
                <GuitarTabViewer xmlContent={message.xmlContent} />
              </div>
            ) : (
              <div className="chat-tab-viewer-collapsed">
                <Music size={16} />
                <span>Transcription (see latest below)</span>
              </div>
            )}
          </>
        )}

        {/* Error state */}
        {!isUser && message.status === "error" && (
          <div className="chat-error">
            <AlertTriangle size={16} />
            <span>{message.statusText || "Something went wrong."}</span>
          </div>
        )}

        {/* Timestamp */}
        <div className="chat-timestamp">{formatTime(message.timestamp)}</div>
      </div>

      {isUser && (
        <div className="chat-avatar user-avatar">
          <User size={18} />
        </div>
      )}
    </div>
  );
};
