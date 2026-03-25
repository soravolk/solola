export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  /** Attached audio file (user messages) */
  file?: File;
  /** Processing state for assistant messages */
  status?: "thinking" | "processing" | "complete" | "error";
  /** Progress percentage (0-100) */
  progress?: number;
  /** Status text shown during processing */
  statusText?: string;
  /** MusicXML content to render in the tab viewer */
  xmlContent?: string;
  /** Uploaded file ID from server */
  fileId?: string;
}

export type LayoutMode = "page" | "horizontal";
