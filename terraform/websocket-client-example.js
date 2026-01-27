/**
 * WebSocket Client for EG Solo
 *
 * This client connects directly to API Gateway WebSocket endpoint.
 * No CloudFront involved - direct connection for real-time communication.
 */

class EGSoloWebSocketClient {
  constructor(websocketUrl) {
    this.url = websocketUrl;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
  }

  /**
   * Connect to WebSocket API
   */
  connect() {
    return new Promise((resolve, reject) => {
      console.log(`Connecting to WebSocket: ${this.url}`);

      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log("✅ WebSocket connected");
        this.reconnectAttempts = 0;
        resolve();
      };

      this.ws.onerror = (error) => {
        console.error("❌ WebSocket error:", error);
        reject(error);
      };

      this.ws.onmessage = (event) => {
        console.log("📩 Message received:", event.data);
        try {
          const data = JSON.parse(event.data);
          this.handleMessage(data);
        } catch (e) {
          console.log("Raw message:", event.data);
        }
      };

      this.ws.onclose = (event) => {
        console.log("🔌 WebSocket closed:", event.code, event.reason);
        this.handleReconnect();
      };
    });
  }

  /**
   * Send a message to the WebSocket server
   */
  sendMessage(action, data = {}) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({
        action,
        ...data,
      });
      console.log("📤 Sending message:", message);
      this.ws.send(message);
    } else {
      console.error(
        "❌ WebSocket is not connected. State:",
        this.ws?.readyState,
      );
    }
  }

  /**
   * Handle incoming messages
   */
  handleMessage(data) {
    console.log("Processing message:", data);

    // Add your custom message handling logic here
    switch (data.type) {
      case "transcription_progress":
        console.log(`Progress: ${data.progress}%`);
        break;
      case "transcription_complete":
        console.log("Transcription complete:", data.result);
        break;
      case "error":
        console.error("Server error:", data.message);
        break;
      default:
        console.log("Unknown message type:", data);
    }
  }

  /**
   * Handle reconnection
   */
  handleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * this.reconnectAttempts;
      console.log(
        `🔄 Reconnecting in ${delay}ms... (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`,
      );

      setTimeout(() => {
        this.connect().catch((err) => {
          console.error("Reconnection failed:", err);
        });
      }, delay);
    } else {
      console.error("❌ Max reconnection attempts reached. Giving up.");
    }
  }

  /**
   * Disconnect from WebSocket
   */
  disconnect() {
    if (this.ws) {
      console.log("Disconnecting WebSocket...");
      this.reconnectAttempts = this.maxReconnectAttempts; // Prevent auto-reconnect
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Check if connected
   */
  isConnected() {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// Usage Example
// ============================================================================

// Get WebSocket URL from Terraform output
const WEBSOCKET_URL =
  "wss://your-api-id.execute-api.us-east-1.amazonaws.com/prod";

// Create client
const wsClient = new EGSoloWebSocketClient(WEBSOCKET_URL);

// Connect
wsClient
  .connect()
  .then(() => {
    console.log("Connected! Ready to send messages.");

    // Example: Send a message
    wsClient.sendMessage("ping", { timestamp: Date.now() });

    // Example: Request transcription status
    wsClient.sendMessage("getStatus", { jobId: "123456" });
  })
  .catch((err) => {
    console.error("Failed to connect:", err);
  });

// Disconnect when page unloads
window.addEventListener("beforeunload", () => {
  wsClient.disconnect();
});

// Export for module usage
if (typeof module !== "undefined" && module.exports) {
  module.exports = EGSoloWebSocketClient;
}
