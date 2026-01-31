// src/utils/collaboration.ts
// WebSocket client service for collaborative assistance

// import { API_BASE } from "../config";

const API_BASE = "http://127.0.0.1:8003";

export type CollaborationRole = "user" | "guide";
export type MessageType =
  | "connected"
  | "frame" // Changed from camera_frame to match backend (legacy, kept for compatibility)
  | "guidance"
  | "voice_message"
  | "user_connected"
  | "guide_connected"
  | "user_disconnected"
  | "guide_disconnected"
  | "webrtc_offer" // WebRTC offer (user -> guide)
  | "webrtc_answer" // WebRTC answer (guide -> user)
  | "webrtc_ice" // WebRTC ICE candidate (both ways)
  | "video_received" // Helper acknowledgment that video track was received
  | "ping"
  | "pong"
  | "error";

export interface CollaborationMessage {
  type: MessageType;
  role?: CollaborationRole;
  session_id?: string;
  image?: string; // data URL for frame messages
  data?: string; // legacy: base64 image for camera_frame
  text?: string; // text guidance (new format)
  message?: string; // legacy: text guidance
  audio?: string; // base64 audio for voice_message
  // WebRTC signaling
  sdp?: RTCSessionDescriptionInit; // SDP for offer/answer
  candidate?: RTCIceCandidateInit; // ICE candidate
  timestamp?: string;
}

export interface SessionInfo {
  session_id: string;
  expires_at: string;
}

export interface SessionStatus {
  session_id: string;
  user_connected: boolean;
  guide_connected: boolean;
  created_at: string;
}

// Shared normalization functions (used by both user and helper)
export const normalizeCode = (code: string): string => {
  if (!code) return "";
  return code.trim().toUpperCase();
};

export const roomFor = (code: string): string => {
  return `askafriend:${normalizeCode(code)}`;
};

class CollaborationService {
  private ws: WebSocket | null = null;
  private sessionId: string | null = null;
  private role: CollaborationRole | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private messageHandlers: Map<
    MessageType,
    ((msg: CollaborationMessage) => void)[]
  > = new Map();
  private socketId: string | null = null;

  /**
   * Create a new collaboration session
   */
  async createSession(): Promise<SessionInfo> {
    try {
      const response = await fetch(`${API_BASE}/collaboration/create-session`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Failed to create session: ${response.status}`);
      }
      const data: SessionInfo = await response.json();
      this.sessionId = normalizeCode(data.session_id);
      return { ...data, session_id: this.sessionId };
    } catch (error) {
      console.error("[Collaboration] Error creating session:", error);
      throw error;
    }
  }

  /**
   * Get session status
   */
  async getSessionStatus(sessionId: string): Promise<SessionStatus> {
    try {
      // Normalize session ID
      const normalizedId = normalizeCode(sessionId);

      // Validate format
      if (!this.validateSessionId(normalizedId)) {
        throw new Error(
          `Invalid session code format. Must be 8 alphanumeric characters. Got: "${sessionId}"`,
        );
      }

      console.log(
        `[Collaboration] 📊 Checking status for session: "${sessionId}" → normalized: "${normalizedId}"`,
      );
      const url = `${API_BASE}/collaboration/session/${encodeURIComponent(normalizedId)}/status`;
      console.log(`[Collaboration] Requesting: ${url}`);

      const response = await fetch(url);
      if (!response.ok) {
        const errorText = await response.text();
        let errorMessage = `Failed to get session status: ${response.status}`;
        try {
          const errorData = JSON.parse(errorText);
          errorMessage = errorData.detail || errorMessage;
        } catch {
          errorMessage = errorText || errorMessage;
        }
        console.error(
          `[Collaboration] ❌ Status check failed: ${errorMessage}`,
        );
        throw new Error(errorMessage);
      }
      const status = await response.json();
      console.log(
        `[Collaboration] ✅ Status: user=${status.user_connected}, guide=${status.guide_connected}`,
      );
      return status;
    } catch (error) {
      console.error("[Collaboration] Error getting session status:", error);
      throw error;
    }
  }

  /**
   * Validate session ID format: exactly 8 alphanumeric characters
   */
  private validateSessionId(sessionId: string): boolean {
    const normalized = normalizeCode(sessionId);
    return normalized.length === 8 && /^[A-Z0-9]+$/.test(normalized);
  }

  /**
   * Connect to a collaboration session
   */
  connect(sessionId: string, role: CollaborationRole): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.disconnect();
      }

      // Normalize session ID
      const normalizedId = normalizeCode(sessionId);

      // Validate format
      if (!this.validateSessionId(normalizedId)) {
        const error = new Error(
          `Invalid session code format. Must be 8 alphanumeric characters. Got: "${sessionId}"`,
        );
        console.error(`[Collaboration] ${error.message}`);
        reject(error);
        return;
      }

      this.sessionId = normalizedId;
      this.role = role;

      // Construct WebSocket URL
      const wsProtocol = API_BASE.startsWith("https") ? "wss" : "ws";
      const wsBase = API_BASE.replace(/^https?/, wsProtocol);
      const wsUrl = `${wsBase}/collaboration/ws/${normalizedId}/${role}`;
      const room = roomFor(normalizedId);

      console.log(`[Collaboration] 🔌 Connecting to ${wsUrl}`);
      console.log(
        `[Collaboration] Session ID: "${sessionId}" → normalized: "${normalizedId}"`,
      );
      console.log(`[Collaboration] Room: ${room}`);

      try {
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          this.socketId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
          console.log(
            `[Collaboration] ✅ Socket connected (socket_id: ${this.socketId})`,
          );
          console.log(
            `[Collaboration] ✅ Connected as ${role} to session "${normalizedId}"`,
          );
          console.log(`[Collaboration] ✅ Joined room: ${room}`);
          this.reconnectAttempts = 0;
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: CollaborationMessage = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error("[Collaboration] Error parsing message:", error);
          }
        };

        this.ws.onerror = (error) => {
          console.error(
            `[Collaboration] ❌ WebSocket error (socket_id: ${this.socketId}):`,
            error,
          );
          reject(error);
        };

        this.ws.onclose = (event) => {
          console.log(
            `[Collaboration] 🔌 Socket disconnected (socket_id: ${this.socketId}, code: ${event.code}, reason: ${event.reason})`,
          );
          this.ws = null;
          this.socketId = null;

          // Attempt reconnection if not intentional
          if (
            event.code !== 1000 &&
            this.reconnectAttempts < this.maxReconnectAttempts
          ) {
            this.reconnectAttempts++;
            console.log(
              `[Collaboration] 🔄 Reconnecting (attempt ${this.reconnectAttempts})...`,
            );
            setTimeout(() => {
              if (this.sessionId && this.role) {
                this.connect(this.sessionId, this.role).catch(console.error);
              }
            }, 2000 * this.reconnectAttempts);
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Disconnect from session
   */
  disconnect(): void {
    if (this.ws) {
      try {
        console.log(
          `[Collaboration] 🔌 Disconnecting (socket_id: ${this.socketId})`,
        );
        this.ws.send(JSON.stringify({ type: "disconnect" }));
        this.ws.close(1000, "User disconnected");
      } catch (error) {
        console.error("[Collaboration] Error disconnecting:", error);
      }
      this.ws = null;
      this.socketId = null;
    }
    this.sessionId = null;
    this.role = null;
  }

  /**
   * Send camera frame (user only)
   * Accepts either base64 string or full data URL
   */
  sendCameraFrame(base64Image: string): void {
    if (
      this.role !== "user" ||
      !this.ws ||
      this.ws.readyState !== WebSocket.OPEN
    ) {
      console.warn("[FRAME] ⚠️ Cannot send frame:", {
        role: this.role,
        wsReady: this.ws?.readyState === WebSocket.OPEN,
      });
      return;
    }

    try {
      // Ensure we have the full data URL format
      let imageData = base64Image;
      if (!imageData.startsWith("data:image")) {
        imageData = `data:image/jpeg;base64,${imageData}`;
      }

      // Normalize session code
      const code = normalizeCode(this.sessionId || "");
      const room = roomFor(code);
      const ts = Date.now();

      this.ws.send(
        JSON.stringify({
          type: "frame",
          image: imageData,
          session_id: code,
          timestamp: new Date().toISOString(),
        }),
      );

      // Log frame send (throttled to once per second)
      const frameCount = ((this as any).frameSendCount =
        ((this as any).frameSendCount || 0) + 1);
      if (frameCount % 8 === 0) {
        // ~8 FPS, so log once per second
        console.log(
          `[FRAME] 📤 Sent ${frameCount} frames (room: ${room}, bytes: ${imageData.length})`,
        );
      }
    } catch (error) {
      console.error("[FRAME] ❌ Error sending camera frame:", error);
    }
  }

  /**
   * Send guidance message (guide only)
   */
  sendGuidance(message: string): void {
    if (
      this.role !== "guide" ||
      !this.ws ||
      this.ws.readyState !== WebSocket.OPEN
    ) {
      return;
    }

    try {
      this.ws.send(
        JSON.stringify({
          type: "guidance",
          text: message,
          timestamp: new Date().toISOString(),
        }),
      );
    } catch (error) {
      console.error("Error sending guidance:", error);
    }
  }

  /**
   * Send voice message (guide only)
   */
  sendVoiceMessage(base64Audio: string): void {
    if (
      this.role !== "guide" ||
      !this.ws ||
      this.ws.readyState !== WebSocket.OPEN
    ) {
      return;
    }

    try {
      this.ws.send(
        JSON.stringify({
          type: "voice_message",
          audio: base64Audio,
          timestamp: new Date().toISOString(),
        }),
      );
    } catch (error) {
      console.error("Error sending voice message:", error);
    }
  }

  /**
   * Send WebRTC offer (user only)
   */
  sendWebRTCOffer(sdp: RTCSessionDescriptionInit): void {
    if (
      this.role !== "user" ||
      !this.ws ||
      this.ws.readyState !== WebSocket.OPEN
    ) {
      console.error(
        "[Collaboration] Cannot send WebRTC offer: not connected as user",
      );
      return;
    }

    try {
      const code = normalizeCode(this.sessionId || "");
      const room = roomFor(code);
      console.log(`[Collaboration] 📤 Sending WebRTC offer (room: ${room})`);
      this.ws.send(
        JSON.stringify({
          type: "webrtc_offer",
          sdp: sdp,
          session_id: code,
          timestamp: new Date().toISOString(),
        }),
      );
    } catch (error) {
      console.error("[Collaboration] Error sending WebRTC offer:", error);
    }
  }

  /**
   * Send WebRTC answer (guide only)
   */
  sendWebRTCAnswer(sdp: RTCSessionDescriptionInit): void {
    if (
      this.role !== "guide" ||
      !this.ws ||
      this.ws.readyState !== WebSocket.OPEN
    ) {
      console.error(
        "[Collaboration] Cannot send WebRTC answer: not connected as guide",
      );
      return;
    }

    try {
      const code = normalizeCode(this.sessionId || "");
      const room = roomFor(code);
      console.log(`[Collaboration] 📤 Sending WebRTC answer (room: ${room})`);
      this.ws.send(
        JSON.stringify({
          type: "webrtc_answer",
          sdp: sdp,
          session_id: code,
          timestamp: new Date().toISOString(),
        }),
      );
    } catch (error) {
      console.error("[Collaboration] Error sending WebRTC answer:", error);
    }
  }

  /**
   * Send WebRTC ICE candidate (both roles)
   */
  sendWebRTCICE(candidate: RTCIceCandidateInit): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    try {
      const code = normalizeCode(this.sessionId || "");
      const room = roomFor(code);
      console.log(
        `[Collaboration] 📤 Sending WebRTC ICE candidate (room: ${room})`,
      );
      this.ws.send(
        JSON.stringify({
          type: "webrtc_ice",
          candidate: candidate,
          session_id: code,
          timestamp: new Date().toISOString(),
        }),
      );
    } catch (error) {
      console.error(
        "[Collaboration] Error sending WebRTC ICE candidate:",
        error,
      );
    }
  }

  /**
   * Register message handler
   */
  onMessage(
    type: MessageType,
    handler: (msg: CollaborationMessage) => void,
  ): () => void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, []);
    }
    this.messageHandlers.get(type)!.push(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.messageHandlers.get(type);
      if (handlers) {
        const index = handlers.indexOf(handler);
        if (index > -1) {
          handlers.splice(index, 1);
        }
      }
    };
  }

  /**
   * Handle incoming messages
   */
  private handleMessage(message: CollaborationMessage): void {
    const rawType = (message as any).type as string;
    console.log(
      `[Collaboration] 📨 Received message type: "${rawType}"`,
      message,
    );

    // Map legacy message types to new format
    // Check raw type string to handle legacy "camera_frame" type
    let msgType: MessageType = message.type;

    if (rawType === "camera_frame") {
      msgType = "frame";
      // Normalize data to image field
      if (message.data && !message.image) {
        (message as any).image = message.data;
      }
    }

    // Special handling for guidance messages
    if (rawType === "guidance") {
      console.log(`[Collaboration] 📢 Processing guidance message:`, {
        text: message.text,
        message: message.message,
        fullMessage: message,
      });
    }

    // Call handlers for the mapped type
    const handlers = this.messageHandlers.get(msgType);
    if (handlers) {
      console.log(
        `[Collaboration] ✅ Found ${handlers.length} handler(s) for type "${msgType}"`,
      );
      handlers.forEach((handler, index) => {
        try {
          console.log(
            `[Collaboration] 🔄 Calling handler ${index + 1} for "${msgType}"`,
          );
          handler(message);
        } catch (error) {
          console.error(
            `[Collaboration] ❌ Error in message handler for ${msgType}:`,
            error,
          );
        }
      });
    } else {
      console.warn(
        `[Collaboration] ⚠️ No handlers registered for message type "${msgType}"`,
      );
      console.warn(
        `[Collaboration] ⚠️ Available handlers:`,
        Array.from(this.messageHandlers.keys()),
      );
    }

    // Also call handlers for legacy type if different
    if (msgType !== message.type && message.type in this.messageHandlers) {
      const legacyHandlers = this.messageHandlers.get(
        message.type as MessageType,
      );
      if (legacyHandlers) {
        legacyHandlers.forEach((handler) => {
          try {
            handler(message);
          } catch (error) {
            console.error(
              `Error in legacy message handler for ${message.type}:`,
              error,
            );
          }
        });
      }
    }
  }

  /**
   * Get current connection state
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Get current session ID
   */
  getSessionId(): string | null {
    return this.sessionId;
  }

  /**
   * Get current role
   */
  getRole(): CollaborationRole | null {
    return this.role;
  }

  /**
   * Send generic message (for video_received acknowledgment)
   */
  sendMessage(type: string, data: any): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    try {
      this.ws.send(
        JSON.stringify({
          type,
          ...data,
          session_id: this.sessionId,
          timestamp: new Date().toISOString(),
        }),
      );
    } catch (error) {
      console.error(`[Collaboration] Error sending ${type}:`, error);
    }
  }
}

// Export singleton instance
export const collaborationService = new CollaborationService();
