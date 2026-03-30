import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Guitar, Upload, Link, Sparkles } from "lucide-react";
import type { ChatMessage } from "../../types/chat";
import { ChatMessageBubble } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { useWebSocket } from "../../hooks/useWebSocket";
import "./ChatInterface.css";

const generateId = () =>
  `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

/** Strip reasoning/thinking blocks and extract only MusicXML from AI response */
function sanitizeXml(raw: string): string {
  // Remove <reasoning>, <think>, <thinking>, <scratchpad> blocks
  let cleaned = raw.replace(
    /<(reasoning|think|thinking|scratchpad)\b[^>]*>[\s\S]*?<\/\1>/gi,
    "",
  );
  // Extract from <?xml or <score-partwise to </score-partwise>
  const xmlMatch = cleaned.match(
    /(<\?xml\b[\s\S]*<\/score-partwise>)|(<score-partwise\b[\s\S]*<\/score-partwise>)/,
  );
  return xmlMatch ? xmlMatch[0].trim() : cleaned.trim();
}

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "Hi! I'm Solola, your AI guitar transcription assistant. Upload an audio file or paste a YouTube link, and I'll transcribe it into guitar tablature for you.",
  timestamp: new Date(),
};

const SUGGESTION_CARDS = [
  {
    icon: Upload,
    title: "Upload Audio",
    description: "Drop a guitar recording to transcribe",
  },
  {
    icon: Link,
    title: "YouTube Link",
    description: "Paste a link to transcribe (coming soon)",
  },
  {
    icon: Sparkles,
    title: "AI Transcription",
    description: "Get notation + tablature automatically",
  },
];

export const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [isProcessing, setIsProcessing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentAssistantMsgId = useRef<string | null>(null);
  const latestXmlRef = useRef<string | null>(null);

  // userId
  const userId = useMemo(() => {
    let id = sessionStorage.getItem("userId");
    if (!id) {
      id = `user-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      sessionStorage.setItem("userId", id);
    }
    return id;
  }, []);

  // WebSocket
  const wsUrl =
    import.meta.env.VITE_WEBSOCKET_URL ||
    "wss://vz9wg4syuh.execute-api.us-east-1.amazonaws.com/prod";
  const { isConnected, lastMessage: wsMessage } = useWebSocket(wsUrl, userId);

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Helper to update the current assistant message
  const updateAssistantMessage = useCallback(
    (updates: Partial<ChatMessage>) => {
      const id = currentAssistantMsgId.current;
      if (!id) return;
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, ...updates } : m)),
      );
    },
    [],
  );

  // Fetch XML result
  const fetchXmlContent = useCallback(
    async (url: string) => {
      try {
        const res = await fetch(url);
        const xml = sanitizeXml(await res.text());
        latestXmlRef.current = xml;
        updateAssistantMessage({
          content:
            "Here's your guitar transcription! You can play it back, zoom, and switch layouts.",
          status: "complete",
          progress: 100,
          xmlContent: xml,
        });
        setIsProcessing(false);
      } catch {
        updateAssistantMessage({
          content: "Failed to load the transcription result.",
          status: "error",
          statusText: "Could not fetch transcription XML.",
        });
        setIsProcessing(false);
      }
    },
    [updateAssistantMessage],
  );

  // Handle WebSocket messages
  useEffect(() => {
    if (!wsMessage) return;

    switch (wsMessage.type) {
      case "generation_progress":
      case "transcription_progress":
        updateAssistantMessage({
          status: "processing",
          progress: wsMessage.data?.progress || 0,
          statusText: wsMessage.data?.message || "Processing...",
        });
        break;

      case "generation_complete":
        updateAssistantMessage({
          content: "Generation complete!",
          status: "complete",
          progress: 100,
        });
        setIsProcessing(false);
        break;

      case "transcription_complete":
        if (wsMessage.data?.xmlUrl) {
          updateAssistantMessage({
            status: "processing",
            progress: 95,
            statusText: "Loading transcription...",
          });
          void fetchXmlContent(wsMessage.data.xmlUrl);
        } else {
          updateAssistantMessage({
            content: "Transcription complete!",
            status: "complete",
            progress: 100,
          });
          setIsProcessing(false);
        }
        break;

      case "generation_error":
      case "error":
        updateAssistantMessage({
          content: "An error occurred during processing.",
          status: "error",
          statusText:
            wsMessage.data?.error || wsMessage.message || "Unknown error",
        });
        setIsProcessing(false);
        break;
    }
  }, [wsMessage, updateAssistantMessage, fetchXmlContent]);

  // Upload file to S3 & trigger generation
  const handleUploadAndGenerate = useCallback(
    async (file: File) => {
      try {
        // 1. Get presigned URL
        const apiUrl =
          import.meta.env.VITE_API_URL ||
          "https://kc3itnsdm0.execute-api.us-east-1.amazonaws.com/api/v1/audio";

        const res = await fetch(apiUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_type: "local",
            source: { filename: file.name, content_type: file.type },
          }),
        });

        if (!res.ok)
          throw new Error(`Upload URL request failed: ${res.status}`);

        const { upload_url, id } = (await res.json()) as {
          upload_url: string;
          id: string;
        };

        // 2. Upload to S3
        updateAssistantMessage({
          status: "processing",
          progress: 15,
          statusText: "Uploading audio file...",
        });

        const uploadRes = await fetch(upload_url, {
          method: "PUT",
          headers: { "Content-Type": file.type },
          body: file,
        });

        if (!uploadRes.ok) throw new Error("S3 upload failed");

        // 3. Trigger generation
        updateAssistantMessage({
          status: "processing",
          progress: 30,
          statusText: "Starting transcription...",
        });

        const generateUrl =
          "https://kc3itnsdm0.execute-api.us-east-1.amazonaws.com/api/v1/generate";

        const genRes = await fetch(generateUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            file_id: id,
            filename: file.name,
            user_id: userId,
          }),
        });

        if (!genRes.ok) {
          const errData = await genRes.json();
          throw new Error(
            errData.error || `Generation failed: ${genRes.status}`,
          );
        }

        updateAssistantMessage({
          status: "processing",
          progress: 35,
          statusText: "Transcription in progress — this may take a minute...",
        });
      } catch (err: any) {
        updateAssistantMessage({
          content: "Sorry, something went wrong.",
          status: "error",
          statusText: err?.message || "Upload or generation failed.",
        });
        setIsProcessing(false);
      }
    },
    [userId, updateAssistantMessage],
  );

  // AI-powered MusicXML fix via Bedrock
  const handleAiFix = useCallback(
    async (instruction: string) => {
      if (!latestXmlRef.current) return;

      try {
        updateAssistantMessage({
          status: "processing",
          progress: 30,
          statusText: "Sending fix request to AI...",
        });

        const fixUrl =
          import.meta.env.VITE_FIX_API_URL ||
          "https://kc3itnsdm0.execute-api.us-east-1.amazonaws.com/api/v1/fix";

        const res = await fetch(fixUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            currentXml: latestXmlRef.current,
            instruction,
          }),
        });

        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.error || `Fix request failed: ${res.status}`);
        }

        updateAssistantMessage({
          status: "processing",
          progress: 80,
          statusText: "Applying changes...",
        });

        const data = await res.json();
        const fixedXml = sanitizeXml(data.xmlContent);

        // Update the latest XML reference
        latestXmlRef.current = fixedXml;

        updateAssistantMessage({
          content: `Updated the transcription: "${instruction}"`,
          status: "complete",
          progress: 100,
          xmlContent: fixedXml,
        });
        setIsProcessing(false);
      } catch (err: any) {
        updateAssistantMessage({
          content: "Sorry, the AI couldn't apply that fix.",
          status: "error",
          statusText: err?.message || "Fix request failed.",
        });
        setIsProcessing(false);
      }
    },
    [updateAssistantMessage],
  );

  // Handle user sending a message
  const handleSend = useCallback(
    (text: string, file?: File) => {
      // Add user message
      const userMsg: ChatMessage = {
        id: generateId(),
        role: "user",
        content: text || (file ? `Transcribe ${file.name}` : ""),
        timestamp: new Date(),
        file,
      };
      setMessages((prev) => [...prev, userMsg]);

      // Create assistant reply
      const assistantId = generateId();
      currentAssistantMsgId.current = assistantId;

      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        status: "thinking",
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsProcessing(true);

      if (file) {
        // File upload flow
        void handleUploadAndGenerate(file);
      } else if (text.includes("youtube.com") || text.includes("youtu.be")) {
        // YouTube link — placeholder for future implementation
        updateAssistantMessage({
          content:
            "YouTube link processing is coming soon! For now, please upload an audio file directly.",
          status: "complete",
        });
        setIsProcessing(false);
      } else if (latestXmlRef.current) {
        // There's a previous transcription — use AI to fix/edit it
        void handleAiFix(text);
      } else {
        // Text-only message
        updateAssistantMessage({
          content:
            "Please upload an audio file or provide a YouTube link so I can transcribe it into guitar tabs.",
          status: "complete",
        });
        setIsProcessing(false);
      }
    },
    [handleUploadAndGenerate, handleAiFix, updateAssistantMessage],
  );

  const hasUserMessages = messages.some((m) => m.role === "user");

  return (
    <div className="chat-interface">
      {/* Header */}
      <header className="chat-header">
        <div className="chat-header-left">
          <div className="chat-header-logo">
            <Guitar size={22} />
          </div>
          <div>
            <h1 className="chat-header-title">Solola</h1>
            <span className="chat-header-subtitle">
              AI Guitar Transcription
            </span>
          </div>
        </div>
        <div className="chat-header-right">
          <div
            className={`chat-connection-dot ${isConnected ? "connected" : ""}`}
          />
          <span className="chat-connection-label">
            {isConnected ? "Connected" : "Connecting..."}
          </span>
        </div>
      </header>

      {/* Messages */}
      <div className="chat-messages">
        <div className="chat-messages-inner">
          {!hasUserMessages && (
            <div className="chat-empty-state">
              <div className="chat-empty-logo">
                <Guitar size={40} />
              </div>
              <h2 className="chat-empty-title">
                What would you like to transcribe?
              </h2>
              <p className="chat-empty-subtitle">
                Upload a guitar recording and I'll generate notation and
                tablature for you.
              </p>
              <div className="chat-suggestion-cards">
                {SUGGESTION_CARDS.map((card) => (
                  <div key={card.title} className="chat-suggestion-card">
                    <card.icon size={20} className="chat-suggestion-icon" />
                    <div>
                      <div className="chat-suggestion-title">{card.title}</div>
                      <div className="chat-suggestion-desc">
                        {card.description}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {hasUserMessages &&
            messages.map((msg) => (
              <ChatMessageBubble key={msg.id} message={msg} />
            ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="chat-input-wrapper">
        <ChatInput
          onSend={handleSend}
          disabled={isProcessing}
          placeholder={
            isProcessing
              ? "Processing your request..."
              : "Upload an audio file or paste a YouTube link..."
          }
        />
        <p className="chat-disclaimer">
          Solola uses AI to transcribe guitar audio. Results may vary based on
          audio quality.
        </p>
      </div>
    </div>
  );
};
