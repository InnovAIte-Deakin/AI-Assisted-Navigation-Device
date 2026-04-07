// app/ask-a-friend-web.tsx
// Web-specific "Ask a Friend" user interface
// Uses getUserMedia for camera and speechSynthesis for TTS

import { useEffect, useState, useRef, useCallback, Fragment } from "react";
import {
  View,
  Text,
  Pressable,
  StyleSheet,
  ActivityIndicator,
  Alert,
  ScrollView,
  Platform,
} from "react-native";
import { router, usePathname, useSegments } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import {
  collaborationService,
  SessionInfo,
  normalizeCode,
  roomFor,
} from "@/src/utils/collaboration";
import {
  initWebCamera,
  createWebFrameCaptureHandler,
  WebCameraCapture,
} from "@/src/utils/webCameraCapture";
import {
  speakWeb,
  stopWebSpeech,
  isWebTTSAvailable,
  isWebSpeaking,
} from "@/src/utils/webTTS";

export default function AskAFriendWebScreen() {
  const pathname = usePathname();
  const segments = useSegments();
  const isNavigatingAwayRef = useRef(false);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [guideConnected, setGuideConnected] = useState(false);
  const [helperName, setHelperName] = useState<string | null>(null);
  const [guidanceMessage, setGuidanceMessage] = useState<string>("");
  const [isSpeakingGuidance, setIsSpeakingGuidance] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isDisconnectingRef = useRef(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [cameraPermission, setCameraPermission] = useState<
    "granted" | "denied" | "prompt"
  >("prompt");
  const [microphonePermission, setMicrophonePermission] = useState<
    "granted" | "denied" | "prompt"
  >("prompt");
  const [isMuted, setIsMuted] = useState(false);
  const [hasAudioTrack, setHasAudioTrack] = useState(false);

  const cameraRef = useRef<WebCameraCapture | null>(null);
  const frameCaptureCleanupRef = useRef<(() => void) | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null); // For receiving helper's audio
  const streamRef = useRef<MediaStream | null>(null);
  const [showVideoElement, setShowVideoElement] = useState(false);
  const [cameraStreamReady, setCameraStreamReady] = useState(false);

  // WebRTC peer connection
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const iceCandidatesRef = useRef<RTCIceCandidate[]>([]);
  const [webrtcConnected, setWebrtcConnected] = useState(false);
  const [helperReceivedVideo, setHelperReceivedVideo] = useState(false);
  const [helperReceivedAudio, setHelperReceivedAudio] = useState(false);
  const iceCandidateCountRef = useRef(0);
  const receivedIceCountRef = useRef(0);
  const localAudioTrackRef = useRef<MediaStreamTrack | null>(null);

  // Fallback frame streaming mode
  const [useFallbackMode, setUseFallbackMode] = useState(false);
  const fallbackTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const frameStreamIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const framesSentCountRef = useRef(0);
  const frameStatsIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Check if on web and prevent redirects
  useEffect(() => {
    if (Platform.OS !== "web") {
      Alert.alert("Error", "This screen is only available on web browsers.");
      router.replace("/");
      return;
    }

    // If user has navigated away (e.g., via footer/tab press), do not force-return.
    if (pathname && pathname !== "/ask-a-friend-web") {
      isNavigatingAwayRef.current = true;
      return;
    }

    // CRITICAL: Prevent Expo Router's anchor redirect and splash screen redirect
    // Check if pathname changed away from ask-a-friend-web
    if (
      pathname &&
      pathname !== "/ask-a-friend-web" &&
      !isNavigatingAwayRef.current
    ) {
      console.log(
        "[AskAFriend] Detected redirect attempt, preventing:",
        pathname,
      );
      // Force navigation back to ask-a-friend-web immediately
      // Use replace to prevent back button issues
      router.replace("/ask-a-friend-web");
    }

    // Also check window.location as a fallback (for web)
    if (
      typeof window !== "undefined" &&
      window.location.pathname !== "/ask-a-friend-web"
    ) {
      window.history.replaceState(null, "", "/ask-a-friend-web");
    }
  }, [pathname, router]);

  // Monitor segments to catch redirects to tabs/home
  useEffect(() => {
    if (Platform.OS === "web") {
      // Only enforce while we are on the Ask page.
      if (pathname !== "/ask-a-friend-web") return;

      // If segments indicate we're being redirected to tabs/home, prevent it
      if (segments.length > 0) {
        const isRedirectingToTabs =
          segments.includes("(tabs)") || segments.includes("home");
        const isOnAskAFriendWeb =
          pathname === "/ask-a-friend-web" ||
          segments[0] === "ask-a-friend-web";

        if (isRedirectingToTabs && !isOnAskAFriendWeb) {
          console.log(
            "[AskAFriend] Preventing redirect to tabs/home, segments:",
            segments,
          );
          router.replace("/ask-a-friend-web");
        }
      }
    }
  }, [segments, pathname, router]);

  // Create session on mount
  useEffect(() => {
    console.log("[AskAFriend] 🚀 Component mounted, creating session...");
    createSession();
    return () => {
      cleanup();
    };
  }, []);

  // Set up message handlers
  useEffect(() => {
    const unsubscribeConnected = collaborationService.onMessage(
      "connected",
      (msg) => {
        console.log("[AskAFriend] ✅ Connected to session:", msg);
        setIsConnected(true);
        setIsConnecting(false);
        setError(null);

        // Check if guide is already connected (from connection message)
        if ((msg as any).guide_connected) {
          console.log("[AskAFriend] ✅ Guide already connected");
          setGuideConnected(true);
        }
      },
    );

    const unsubscribeGuideConnected = collaborationService.onMessage(
      "guide_connected",
      (msg) => {
        console.log("[AskAFriend] ✅ Guide connected:", msg);
        const helperNameFromMsg = (msg as any).helper_name || null;
        setGuideConnected(true);
        if (helperNameFromMsg) {
          setHelperName(helperNameFromMsg);
          if (isWebTTSAvailable()) {
            speakWeb(`${helperNameFromMsg} has joined as a helper.`);
          }
        } else {
          if (isWebTTSAvailable()) {
            speakWeb("Helper has joined. They can see your camera now.");
          }
        }
        // CRITICAL: Start sending frames immediately when guide connects
        // Don't wait for WebRTC - start fallback frame streaming right away
        if (
          streamRef.current &&
          videoRef.current &&
          isConnected &&
          cameraPermission === "granted"
        ) {
          console.log(
            "[AskAFriend] 🎥 Guide connected, starting frame streaming immediately",
          );
          // Start fallback frame streaming immediately
          if (!useFallbackMode) {
            activateFallbackMode();
          }
          // Also try WebRTC
          startWebRTC();
        }
      },
    );

    const unsubscribeGuideDisconnected = collaborationService.onMessage(
      "guide_disconnected",
      (msg) => {
        console.log("[AskAFriend] Guide disconnected:", msg);
        setGuideConnected(false);
        if (helperName && isWebTTSAvailable()) {
          speakWeb(`${helperName} has left the session.`);
        } else if (isWebTTSAvailable()) {
          speakWeb("Helper has left the session.");
        }
        setHelperName(null);
      },
    );

    // Register guidance message handler
    console.log("[AskAFriend] 📢 Registering guidance message handler");
    const unsubscribeGuidance = collaborationService.onMessage(
      "guidance",
      (msg) => {
        // Backend sends "text" field, but we check both "text" and "message" for compatibility
        const guidanceText = msg.text || msg.message || "";
        console.log("[AskAFriend] 📢 Received guidance message:", guidanceText);
        console.log(
          "[AskAFriend] 📢 Full message object:",
          JSON.stringify(msg, null, 2),
        );

        if (guidanceText && guidanceText.trim()) {
          const messageToDisplay = guidanceText.trim();
          console.log(
            "[AskAFriend] ✅ Setting guidance message:",
            messageToDisplay,
          );

          // Clear any previous message timeout
          if ((window as any).guidanceMessageTimeout) {
            clearTimeout((window as any).guidanceMessageTimeout);
          }

          // Set the message immediately
          setGuidanceMessage(messageToDisplay);
          setIsSpeakingGuidance(true);

          // Speak guidance using web TTS with enhanced settings for clarity
          if (isWebTTSAvailable()) {
            console.log(
              "[AskAFriend] 🔊 Speaking guidance message:",
              messageToDisplay,
            );
            // Use slower rate and maximum volume for better clarity and loudness
            speakWeb(messageToDisplay, {
              rate: 0.85, // Slower for better understanding
              pitch: 1.0, // Normal pitch
              volume: 1.0, // Maximum volume
            });

            // Monitor speaking status
            const checkSpeaking = setInterval(() => {
              if (!isWebSpeaking()) {
                setIsSpeakingGuidance(false);
                clearInterval(checkSpeaking);
              }
            }, 200);

            // Clear after 30 seconds max (safety timeout)
            setTimeout(() => {
              setIsSpeakingGuidance(false);
              clearInterval(checkSpeaking);
            }, 30000);
          } else {
            console.warn(
              "[AskAFriend] ⚠️ TTS not available, message displayed but not spoken",
            );
            setIsSpeakingGuidance(false);
          }

          // Clear message after 10 seconds (keep it visible while speaking)
          (window as any).guidanceMessageTimeout = setTimeout(() => {
            setGuidanceMessage("");
            setIsSpeakingGuidance(false);
            console.log(
              "[AskAFriend] 🧹 Cleared guidance message after timeout",
            );
          }, 10000);
        } else {
          console.warn(
            "[AskAFriend] ⚠️ Received guidance message but it was empty:",
            msg,
          );
        }
      },
    );

    const unsubscribeError = collaborationService.onMessage("error", (msg) => {
      console.error("[AskAFriend] Error:", msg);
      setError(msg.message || "Connection error");
    });

    // Helper acknowledgment that video was received
    const unsubscribeVideoReceived = collaborationService.onMessage(
      "video_received" as any,
      (msg) => {
        console.log("[AskAFriend] ✅ Helper confirmed video received!");
        setHelperReceivedVideo(true);

        // Clear fallback timeout since WebRTC is working
        if (fallbackTimeoutRef.current) {
          clearTimeout(fallbackTimeoutRef.current);
          fallbackTimeoutRef.current = null;
        }

        // Stop frame streaming if it was active
        if (useFallbackMode) {
          console.log("[AskAFriend] 🔄 WebRTC working, disabling fallback");
          setUseFallbackMode(false);
          stopFrameStreaming();
        }

        if (isWebTTSAvailable()) {
          speakWeb("Helper can now see your camera.");
        }
      },
    );

    // WebRTC signaling handlers
    const unsubscribeWebRTCAnswer = collaborationService.onMessage(
      "webrtc_answer",
      async (msg) => {
        const code = normalizeCode(sessionId || "");
        const room = roomFor(code);
        console.log(`[AskAFriend] 📥 Received WebRTC answer (room: ${room})`);
        if (peerConnectionRef.current && msg.sdp) {
          try {
            await peerConnectionRef.current.setRemoteDescription(
              new RTCSessionDescription(msg.sdp as RTCSessionDescriptionInit),
            );
            console.log("[AskAFriend] ✅ Set remote description (answer)");

            // Add any pending ICE candidates
            for (const candidate of iceCandidatesRef.current) {
              try {
                await peerConnectionRef.current.addIceCandidate(candidate);
              } catch (err) {
                console.warn(
                  "[AskAFriend] Failed to add pending ICE candidate:",
                  err,
                );
              }
            }
            iceCandidatesRef.current = [];
          } catch (error) {
            console.error(
              "[AskAFriend] ❌ Error handling WebRTC answer:",
              error,
            );
          }
        }
      },
    );

    const unsubscribeWebRTCICE = collaborationService.onMessage(
      "webrtc_ice",
      async (msg) => {
        const code = normalizeCode(sessionId || "");
        const room = roomFor(code);
        console.log(
          `[AskAFriend] 📥 Received WebRTC ICE candidate (room: ${room})`,
        );
        if (peerConnectionRef.current && msg.candidate) {
          try {
            const candidate = new RTCIceCandidate(
              msg.candidate as RTCIceCandidateInit,
            );
            if (peerConnectionRef.current.remoteDescription) {
              await peerConnectionRef.current.addIceCandidate(candidate);
              console.log("[AskAFriend] ✅ Added ICE candidate from helper");
            } else {
              // Store for later
              iceCandidatesRef.current.push(candidate);
              console.log(
                "[AskAFriend] ⏳ Storing ICE candidate (waiting for remote description)",
              );
            }
          } catch (error) {
            console.error("[AskAFriend] ❌ Error adding ICE candidate:", error);
          }
        }
      },
    );

    // Set up TTS completion callback
    if (typeof window !== "undefined") {
      (window as any).onTTSFinished = () => {
        setIsSpeakingGuidance(false);
      };
    }

    return () => {
      unsubscribeConnected();
      unsubscribeGuideConnected();
      unsubscribeGuideDisconnected();
      unsubscribeGuidance();
      unsubscribeError();
      unsubscribeWebRTCAnswer();
      unsubscribeWebRTCICE();
      unsubscribeVideoReceived();
      // Clean up TTS callback
      if (typeof window !== "undefined") {
        delete (window as any).onTTSFinished;
      }
    };
  }, [sessionId]);

  // CRITICAL: Start sending frames immediately when guide connects
  // This ensures frames are sent regardless of WebRTC state
  useEffect(() => {
    if (
      isConnected &&
      guideConnected &&
      cameraPermission === "granted" &&
      streamRef.current &&
      videoRef.current
    ) {
      console.log(
        "[AskAFriend] 🎥 Guide connected! Conditions met for frame streaming:",
        {
          isConnected,
          guideConnected,
          cameraPermission,
          hasStream: !!streamRef.current,
          hasVideo: !!videoRef.current,
          videoReadyState: videoRef.current?.readyState,
          videoWidth: videoRef.current?.videoWidth,
          useFallbackMode,
          hasFrameStreamInterval: !!frameStreamIntervalRef.current,
        },
      );

      // CRITICAL: Start fallback frame streaming immediately when guide connects
      // Don't wait for WebRTC - send frames right away so helper sees something
      if (!frameStreamIntervalRef.current) {
        console.log(
          "[AskAFriend] 🚀 Starting fallback frame streaming immediately (guide connected, don't wait for WebRTC)",
        );
        // Force start frame streaming
        if (!useFallbackMode) {
          setUseFallbackMode(true);
        }
        startFrameStreaming();
      } else {
        console.log("[AskAFriend] ✅ Frame streaming already active");
      }
    } else {
      console.log("[AskAFriend] ⏸️ Frame streaming conditions not met:", {
        isConnected,
        guideConnected,
        cameraPermission,
        hasStream: !!streamRef.current,
        hasVideo: !!videoRef.current,
      });
    }
  }, [isConnected, guideConnected, cameraPermission, cameraStreamReady]);

  // Show video element when user clicks enable (before permission is granted)
  // This ensures the video element exists when we try to attach the stream

  const createSession = async () => {
    try {
      console.log("[AskAFriend] 📝 Starting session creation...");
      setIsConnecting(true);
      setError(null);

      console.log(
        "[AskAFriend] 📝 Calling collaborationService.createSession()...",
      );
      const session: SessionInfo = await collaborationService.createSession();
      console.log("[AskAFriend] ✅ Session created:", session);
      console.log("[AskAFriend] ✅ Session ID:", session.session_id);

      // Set session ID FIRST so it displays even if connection fails
      setSessionId(session.session_id);
      console.log(
        "[AskAFriend] ✅ Session ID set in state:",
        session.session_id,
      );

      // Connect as user
      console.log("[AskAFriend] 📝 Connecting to session as user...");
      await collaborationService.connect(session.session_id, "user");
      console.log("[AskAFriend] ✅ Connected to session successfully");
    } catch (err) {
      console.error("[AskAFriend] ❌ Error creating session:", err);
      const errorMessage =
        err instanceof Error ? err.message : "Failed to create session";
      setError(errorMessage);
      setIsConnecting(false);

      // Show error alert to user
      Alert.alert(
        "Session Creation Failed",
        `Could not create session: ${errorMessage}\n\nPlease check:\n1. Backend is running on \n2. Network connection is working`,
        [{ text: "OK" }],
      );
    }
  };

  const requestCameraPermission = async () => {
    try {
      setCameraError(null);
      setCameraPermission("prompt");
      setCameraStreamReady(false);

      // Check if getUserMedia is available
      if (
        typeof navigator === "undefined" ||
        !navigator.mediaDevices ||
        !navigator.mediaDevices.getUserMedia
      ) {
        throw new Error("Camera API not available in this browser");
      }

      // CRITICAL: Show video element FIRST so it's rendered before we get the stream
      setShowVideoElement(true);

      // Wait for video element to be rendered in DOM
      await new Promise<void>((resolve) => {
        const checkVideo = () => {
          if (videoRef.current) {
            console.log("[AskAFriend] Video element is ready");
            resolve();
          } else {
            // Retry after React renders
            requestAnimationFrame(() => {
              setTimeout(() => {
                if (videoRef.current) {
                  resolve();
                } else {
                  // Try one more time
                  setTimeout(() => {
                    if (videoRef.current) {
                      resolve();
                    } else {
                      console.warn(
                        "[AskAFriend] Video element not found, proceeding anyway",
                      );
                      resolve(); // Proceed anyway, useEffect will handle attachment
                    }
                  }, 100);
                }
              }, 100);
            });
          }
        };
        requestAnimationFrame(checkVideo);
      });

      // Stop any existing stream first
      if (streamRef.current) {
        console.log("[AskAFriend] Stopping existing stream tracks");
        streamRef.current.getTracks().forEach((track) => {
          track.stop();
          console.log("[AskAFriend] Stopped track:", track.kind, track.label);
        });
        streamRef.current = null;
      }

      // Stop existing camera
      if (cameraRef.current) {
        cameraRef.current.stop();
        cameraRef.current = null;
      }

      console.log("[AskAFriend] Requesting camera and microphone access...");

      // Request camera and microphone stream with fallback strategy
      let stream: MediaStream | null = null;
      let lastError: any = null;

      // Try different camera configurations in order of preference
      const cameraConfigs = [
        // Try 1: Back camera with ideal resolution
        {
          video: {
            facingMode: "environment",
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        },
        // Try 2: Back camera without resolution constraints
        {
          video: {
            facingMode: "environment",
          },
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        },
        // Try 3: Any camera (user or environment) with ideal resolution
        {
          video: {
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        },
        // Try 4: Any camera without constraints
        {
          video: true,
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        },
        // Try 5: Just video, no audio constraints
        {
          video: true,
          audio: true,
        },
      ];

      for (let i = 0; i < cameraConfigs.length; i++) {
        try {
          console.log(
            `[AskAFriend] Trying camera config ${i + 1}/${cameraConfigs.length}...`,
          );
          stream = await navigator.mediaDevices.getUserMedia(cameraConfigs[i]);
          console.log(
            `[AskAFriend] ✅ Successfully got stream with config ${i + 1}`,
          );
          break;
        } catch (err: any) {
          console.warn(
            `[AskAFriend] Config ${i + 1} failed:`,
            err.name,
            err.message,
          );
          lastError = err;
          // If it's a permission error, don't try other configs
          if (
            err.name === "NotAllowedError" ||
            err.name === "PermissionDeniedError"
          ) {
            break;
          }
          // Continue to next config
        }
      }

      if (!stream) {
        throw (
          lastError ||
          new Error("Failed to access camera after trying all configurations")
        );
      }

      // Verify stream is valid
      if (!(stream instanceof MediaStream)) {
        throw new Error("Invalid stream returned from getUserMedia");
      }

      const videoTracks = stream.getVideoTracks();
      const audioTracks = stream.getAudioTracks();

      if (videoTracks.length === 0) {
        stream.getTracks().forEach((track) => track.stop());
        throw new Error("No video tracks in stream");
      }

      // Store audio track reference for mute/unmute
      if (audioTracks.length > 0) {
        localAudioTrackRef.current = audioTracks[0];
        setMicrophonePermission("granted");
        setHasAudioTrack(true);
        console.log("[AskAFriend] ✅ Microphone access granted:", {
          trackLabel: audioTracks[0].label,
          enabled: audioTracks[0].enabled,
        });
      } else {
        setMicrophonePermission("denied");
        console.warn("[AskAFriend] ⚠️ No audio tracks in stream");
      }

      console.log("[AskAFriend] Camera and microphone stream acquired:", {
        streamId: stream.id,
        videoTracks: videoTracks.length,
        audioTracks: audioTracks.length,
        videoTrackLabel: videoTracks[0].label,
        videoTrackSettings: videoTracks[0].getSettings(),
        videoElementReady: !!videoRef.current,
      });

      // Store stream in ref
      streamRef.current = stream;

      // Mark stream as ready - useEffect will attach it to video element
      setCameraStreamReady(true);

      // Initialize camera object for frame capture
      const camera = initWebCamera();
      cameraRef.current = camera;

      // Set permission to granted (video attachment happens in useEffect)
      setCameraPermission("granted");
    } catch (err: any) {
      console.error("[AskAFriend] Camera error:", err);
      setCameraPermission("denied");
      setCameraStreamReady(false);

      // Clean up stream on error
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }

      let errorMessage = "Failed to access camera";
      if (
        err.name === "NotAllowedError" ||
        err.name === "PermissionDeniedError"
      ) {
        errorMessage =
          "Camera permission denied. Please allow camera access in your browser settings and try again.";
      } else if (
        err.name === "NotFoundError" ||
        err.name === "DevicesNotFoundError"
      ) {
        errorMessage =
          "No camera found on this device. Please connect a camera or use a device with a camera.";
      } else if (
        err.name === "NotReadableError" ||
        err.name === "TrackStartError"
      ) {
        errorMessage =
          "Camera is already in use by another application. Please close other apps using the camera and try again.";
      } else if (err.name === "OverconstrainedError") {
        errorMessage =
          "Camera settings not supported. Please check your camera settings.";
      } else if (err.message) {
        errorMessage = err.message;
      } else {
        errorMessage =
          "Unable to access camera. Please check:\n1. Camera is connected\n2. Browser permissions are granted\n3. No other app is using the camera";
      }

      setCameraError(errorMessage);
      console.error("[AskAFriend] Camera access failed:", {
        errorName: err.name,
        errorMessage: err.message,
        errorStack: err.stack,
      });

      // Clean up camera on error
      if (cameraRef.current) {
        cameraRef.current.stop();
        cameraRef.current = null;
      }
    }
  };

  // Attach stream to video element when both are ready
  useEffect(() => {
    if (Platform.OS !== "web" || !cameraStreamReady || !streamRef.current) {
      return;
    }

    const attachStream = async () => {
      // Wait for video element to be available
      if (!videoRef.current) {
        console.log("[AskAFriend] Video element not ready, waiting...");
        // Retry after a short delay
        const retryTimeout = setTimeout(() => {
          if (videoRef.current && streamRef.current) {
            attachStream();
          }
        }, 100);
        return () => clearTimeout(retryTimeout);
      }

      const video = videoRef.current;
      const stream = streamRef.current;

      console.log("[AskAFriend] Attaching stream to video element:", {
        videoExists: !!video,
        videoTagName: video.tagName,
        streamId: stream.id,
        videoTracks: stream.getVideoTracks().length,
        trackLabel: stream.getVideoTracks()[0]?.label,
      });

      try {
        // Stop any existing stream on video element
        if (video.srcObject) {
          const oldStream = video.srcObject as MediaStream;
          oldStream.getTracks().forEach((track) => track.stop());
        }

        // Attach stream to video element
        video.srcObject = stream;
        video.muted = true;
        video.playsInline = true;
        video.setAttribute("playsinline", "true");
        video.setAttribute("webkit-playsinline", "true");

        // Position video element in camera preview container using nativeID
        const cameraPreview = document.getElementById(
          "camera-preview-container",
        );

        // Style video for camera preview - position it absolutely within preview container
        if (cameraPreview && video.parentElement !== cameraPreview) {
          // Move video into preview container
          cameraPreview.appendChild(video);
        }

        // Ensure video is styled correctly (apply styles after moving to container)
        requestAnimationFrame(() => {
          if (video) {
            video.style.width = "100%";
            video.style.height = "100%";
            video.style.objectFit = "cover";
            video.style.borderRadius = "12px";
            video.style.backgroundColor = "#000";
            video.style.display = "block";
            video.style.position = "absolute";
            video.style.top = "0";
            video.style.left = "0";
            video.style.zIndex = "2";
          }
        });

        console.log("[AskAFriend] Stream attached, waiting for metadata...");

        // Wait for video metadata
        await new Promise<void>((resolve, reject) => {
          const timeout = setTimeout(() => {
            reject(new Error("Video metadata timeout"));
          }, 10000);

          const onLoadedMetadata = () => {
            clearTimeout(timeout);
            video.removeEventListener("loadedmetadata", onLoadedMetadata);
            video.removeEventListener("error", onError);
            console.log("[AskAFriend] Video metadata loaded:", {
              videoWidth: video.videoWidth,
              videoHeight: video.videoHeight,
              readyState: video.readyState,
            });
            resolve();
          };

          const onError = (err: Event) => {
            clearTimeout(timeout);
            video.removeEventListener("loadedmetadata", onLoadedMetadata);
            video.removeEventListener("error", onError);
            reject(new Error("Video element error"));
          };

          video.addEventListener("loadedmetadata", onLoadedMetadata);
          video.addEventListener("error", onError);
        });

        // Start playing video
        console.log("[AskAFriend] Starting video playback...");
        try {
          await video.play();
          console.log("[AskAFriend] Video is playing:", {
            paused: video.paused,
            readyState: video.readyState,
            videoWidth: video.videoWidth,
            videoHeight: video.videoHeight,
          });

          // Clear any autoplay error
          if (cameraError && cameraError.includes("Tap the video")) {
            setCameraError(null);
          }

          // Update camera object with video reference
          if (cameraRef.current) {
            (cameraRef.current as any).video = video;
            (cameraRef.current as any).stream = stream;
          }
        } catch (playError: any) {
          console.warn(
            "[AskAFriend] Video play error (autoplay policy):",
            playError,
          );
          // Autoplay might be blocked - user will need to interact
          setCameraError("Tap the video to start playback");
        }
      } catch (err: any) {
        console.error("[AskAFriend] Error attaching stream:", err);
        setCameraError(err.message || "Failed to attach camera stream");
        setCameraPermission("denied");
        setCameraStreamReady(false);
        // Clean up on error
        if (stream) {
          stream.getTracks().forEach((track) => track.stop());
        }
        streamRef.current = null;
      }
    };

    attachStream();
  }, [cameraStreamReady, showVideoElement]);

  const copySessionCode = async () => {
    if (sessionId) {
      try {
        await navigator.clipboard.writeText(sessionId);
        Alert.alert("Copied!", "Session code copied to clipboard");
      } catch (err) {
        // Fallback for older browsers
        const textArea = document.createElement("textarea");
        textArea.value = sessionId;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        document.body.removeChild(textArea);
        Alert.alert("Copied!", "Session code copied to clipboard");
      }
    }
  };

  const getHelperWebUrl = () => {
    if (typeof window !== "undefined") {
      const origin = window.location.origin;
      // If on localhost, try to detect LAN IP for cross-device access
      if (origin.includes("localhost") || origin.includes("127.0.0.1")) {
        // Note: We can't automatically detect LAN IP from browser
        // User needs to manually replace localhost with their LAN IP
        console.log(
          "[AskAFriend] Running on localhost. For cross-device access:",
        );
        console.log(
          "[AskAFriend] 1. Find your LAN IP: ipconfig (Windows) or ifconfig (Mac/Linux)",
        );
        console.log(
          "[AskAFriend] 2. Replace 'localhost' with your LAN IP in the URL",
        );
        return `${origin}/helper-web`;
      }
      return `${origin}/helper-web`;
    }
    return "https://walkbuddy.com/helper-web";
  };

  const shareSession = async () => {
    if (!sessionId) return;

    const helperUrl = getHelperWebUrl();
    const normalizedCode = normalizeCode(sessionId || "");

    // Detect if we're on localhost and provide instructions
    let shareText = `I need help navigating!\n\nSession Code: ${normalizedCode}\n\nHelper can join via:\n🌐 Web: ${helperUrl}`;

    if (helperUrl.includes("localhost") || helperUrl.includes("127.0.0.1")) {
      shareText += `\n\n⚠️ NOTE: If helper is on a different device, replace "localhost" with your LAN IP address.\nFind your LAN IP: ipconfig (Windows) or ifconfig (Mac/Linux)`;
    }

    shareText += `\n📱 Or use the WalkBuddy app Helper Mode`;

    try {
      if (navigator.share) {
        await navigator.share({
          title: "WalkBuddy Helper Session",
          text: shareText,
        });
      } else {
        await navigator.clipboard.writeText(shareText);
        Alert.alert("Copied!", "Session details copied to clipboard");
      }
    } catch (err) {
      // User cancelled or error
      console.log("Share cancelled or failed:", err);
    }
  };

  // Activate fallback frame streaming mode
  const activateFallbackMode = () => {
    if (frameStreamIntervalRef.current) {
      console.log(
        "[FRAME] ⚠️ Frame streaming already active, skipping activation",
      );
      return; // Already active
    }

    console.log("[FRAME] 🔄 Activating fallback frame streaming mode");
    setUseFallbackMode(true);
    startFrameStreaming();
  };

  // Start frame streaming (fallback mode) - CHECKPOINT A
  const startFrameStreaming = () => {
    // Check if already running
    if (frameStreamIntervalRef.current) {
      console.log("[FRAME] ⚠️ Frame streaming already running, skipping start");
      return;
    }

    if (!streamRef.current || !videoRef.current) {
      console.error(
        "[FRAME] ❌ Frame streaming cannot start - missing stream or video:",
        {
          hasStream: !!streamRef.current,
          hasVideo: !!videoRef.current,
        },
      );
      return;
    }

    if (!isConnected || !guideConnected) {
      console.log(
        "[FRAME] ⏸️ Frame streaming conditions not met (will retry when connected):",
        {
          isConnected,
          guideConnected,
        },
      );
      return;
    }

    const video = videoRef.current;

    // Wait for video to be ready - CHECKPOINT A.1
    const waitForVideoReady = () => {
      if (!video) {
        console.error("[FRAME] ❌ Video element not found");
        return;
      }

      console.log("[FRAME] 📊 Video state check:", {
        readyState: video.readyState,
        videoWidth: video.videoWidth,
        videoHeight: video.videoHeight,
        paused: video.paused,
      });

      // Ensure video is ready (readyState >= 2 means HAVE_CURRENT_DATA or HAVE_FUTURE_DATA)
      if (video.readyState < 2 || video.videoWidth === 0) {
        console.log("[FRAME] ⏳ Video not ready, waiting...");
        requestAnimationFrame(waitForVideoReady);
        return;
      }

      console.log("[FRAME] ✅ Video ready, starting frame capture");
      console.log(
        "[FRAME] CHECKPOINT A.1: Video ready - videoWidth=" +
          video.videoWidth +
          ", videoHeight=" +
          video.videoHeight,
      );

      // Create canvas if it doesn't exist
      if (!canvasRef.current) {
        const canvas = document.createElement("canvas");
        canvas.width = 640; // Reasonable size for streaming
        canvas.height = 480;
        canvasRef.current = canvas;
        console.log(
          "[FRAME] ✅ Created canvas:",
          canvas.width,
          "x",
          canvas.height,
        );
      }

      const canvas = canvasRef.current;
      const ctx = canvas.getContext("2d");

      if (!ctx) {
        console.error("[FRAME] ❌ Failed to get canvas context");
        return;
      }

      console.log("[FRAME] 🎬 Starting frame streaming (fallback mode)");
      console.log("[FRAME] 🎬 Connection state:", {
        isConnected,
        guideConnected,
        wsReady: collaborationService.isConnected(),
        role: collaborationService.getRole(),
        sessionId: sessionId,
      });

      // Capture and send frames at ~8 FPS (every 125ms)
      const frameInterval = 125;
      framesSentCountRef.current = 0;

      const captureFrame = () => {
        if (!video || !canvas || !ctx) {
          console.warn("[FRAME] ⚠️ Video/canvas not available, stopping");
          return;
        }

        // Check connection state - use refs to avoid stale closures
        const currentIsConnected = collaborationService.isConnected();
        const currentRole = collaborationService.getRole();

        if (!currentIsConnected || currentRole !== "user") {
          console.warn(
            "[FRAME] ⚠️ Cannot send frame - not connected as user:",
            {
              isConnected: currentIsConnected,
              role: currentRole,
              expectedRole: "user",
            },
          );
          return;
        }

        // Check guide is connected (use state, but log if not)
        if (!guideConnected) {
          console.warn("[FRAME] ⚠️ Guide not connected yet, skipping frame");
          return;
        }

        try {
          // Draw video frame to canvas
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

          // Convert to JPEG (quality 0.6)
          const jpegBase64 = canvas.toDataURL("image/jpeg", 0.6);

          // Send frame via WebSocket - CHECKPOINT A.2
          const code = normalizeCode(sessionId || "");
          const room = roomFor(code);
          const ts = Date.now();

          // Always try to send - let sendCameraFrame handle validation
          framesSentCountRef.current++;

          // Log first frame and then once per second (throttled)
          if (framesSentCountRef.current === 1) {
            console.log(
              `[FRAME] ✅ FIRST FRAME sending {code: ${code.substring(0, 8)}, bytes: ${jpegBase64.length}, ts: ${ts}}`,
            );
            console.log(`[FRAME] ✅ Room: ${room}`);
            console.log(
              `[FRAME] ✅ Connection state: isConnected=${collaborationService.isConnected()}, role=${collaborationService.getRole()}, guideConnected=${guideConnected}`,
            );
          } else if (framesSentCountRef.current % 8 === 0) {
            console.log(
              `[FRAME] sending {code: ${code.substring(0, 8)}, bytes: ${jpegBase64.length}, ts: ${ts}}`,
            );
            console.log(
              `[FRAME] framesSent counter: ${framesSentCountRef.current}, room: ${room}`,
            );
          }

          // Send the frame
          collaborationService.sendCameraFrame(jpegBase64);

          // Log if send failed (sendCameraFrame logs warnings internally)
          if (
            !collaborationService.isConnected() ||
            collaborationService.getRole() !== "user"
          ) {
            console.warn(
              "[FRAME] ⚠️ Frame may not be sent - connection issue:",
              {
                isConnected: collaborationService.isConnected(),
                role: collaborationService.getRole(),
                expectedRole: "user",
              },
            );
          }
        } catch (error) {
          console.error("[FRAME] ❌ Error capturing frame:", error);
        }
      };

      // Start capturing frames
      console.log(
        "[FRAME] 🎬 Starting frame capture interval (every",
        frameInterval,
        "ms)",
      );
      frameStreamIntervalRef.current = setInterval(captureFrame, frameInterval);
      // Capture first frame immediately
      console.log("[FRAME] 🎬 Capturing first frame immediately...");
      setTimeout(() => {
        captureFrame();
        console.log("[FRAME] ✅ First frame capture attempt completed");
      }, 100);

      // Log frame stats every second - CHECKPOINT A.3
      frameStatsIntervalRef.current = setInterval(() => {
        const count = framesSentCountRef.current;
        if (count > 0) {
          // Estimate byte size (average frame size)
          const avgFrameSize = 50000; // ~50KB per frame estimate
          console.log(
            `[FRAME] 📊 Stats (1s): framesSent=${count}, fps=${count.toFixed(1)}, byteSize≈${(count * avgFrameSize).toLocaleString()}`,
          );
        }
        framesSentCountRef.current = 0; // Reset counter
      }, 1000);
    };

    // Start waiting for video ready
    waitForVideoReady();
  };

  // Stop frame streaming
  const stopFrameStreaming = () => {
    if (frameStreamIntervalRef.current) {
      console.log("[FRAME] 🛑 Stopping frame streaming");
      clearInterval(frameStreamIntervalRef.current);
      frameStreamIntervalRef.current = null;
    }
    if (frameStatsIntervalRef.current) {
      clearInterval(frameStatsIntervalRef.current);
      frameStatsIntervalRef.current = null;
    }
    framesSentCountRef.current = 0;
    console.log("[FRAME] ✅ Frame streaming stopped");
  };

  // Start WebRTC peer connection
  const startWebRTC = async () => {
    if (!streamRef.current || !isConnected || !guideConnected) {
      console.log("[AskAFriend] ⏸️ WebRTC start conditions not met:", {
        hasStream: !!streamRef.current,
        isConnected,
        guideConnected,
      });
      return;
    }

    // Clean up existing peer connection
    if (peerConnectionRef.current) {
      console.log("[AskAFriend] 🛑 Cleaning up existing peer connection");
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
      iceCandidatesRef.current = [];
    }

    try {
      console.log("[AskAFriend] 🎥 Starting WebRTC peer connection");
      const stream = streamRef.current;
      const videoTracks = stream.getVideoTracks();
      console.log("[AskAFriend] Stream info:", {
        videoTracks: videoTracks.length,
        trackLabel: videoTracks[0]?.label,
        trackSettings: videoTracks[0]?.getSettings(),
      });

      // Create peer connection with STUN
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
      });
      peerConnectionRef.current = pc;

      // Handle incoming tracks from helper (audio)
      pc.ontrack = (event) => {
        console.log(
          "[AskAFriend] 🎵 Received track:",
          event.track.kind,
          event.track.label,
        );
        console.log("[AskAFriend] 🎵 Track details:", {
          kind: event.track.kind,
          label: event.track.label,
          enabled: event.track.enabled,
          readyState: event.track.readyState,
          streams: event.streams.length,
        });

        if (event.track.kind === "audio") {
          setHelperReceivedAudio(true);
          // Attach audio track to audio element for playback
          if (audioRef.current && event.streams && event.streams[0]) {
            const audioElement = audioRef.current;
            const audioStream = event.streams[0];

            console.log(
              "[AskAFriend] 🎵 Attaching audio stream to audio element:",
              {
                streamId: audioStream.id,
                audioTracks: audioStream.getAudioTracks().length,
                audioElementReady: !!audioElement,
              },
            );

            // Set audio properties
            audioElement.srcObject = audioStream;
            audioElement.volume = 1.0; // Ensure volume is at maximum
            audioElement.muted = false; // Ensure not muted

            // Play audio
            audioElement
              .play()
              .then(() => {
                console.log(
                  "[AskAFriend] ✅ Helper audio playing successfully",
                );
                console.log("[AskAFriend] ✅ Audio element state:", {
                  volume: audioElement.volume,
                  muted: audioElement.muted,
                  paused: audioElement.paused,
                  readyState: audioElement.readyState,
                });
              })
              .catch((err) => {
                console.error("[AskAFriend] ❌ Audio play error:", err);
                // Try again after a short delay
                setTimeout(() => {
                  audioElement.play().catch((retryErr) => {
                    console.error(
                      "[AskAFriend] ❌ Audio play retry failed:",
                      retryErr,
                    );
                  });
                }, 500);
              });

            // Monitor audio track state
            event.track.onended = () => {
              console.log("[AskAFriend] ⚠️ Helper audio track ended");
              setHelperReceivedAudio(false);
            };

            event.track.onmute = () => {
              console.log("[AskAFriend] ⚠️ Helper audio track muted");
            };

            event.track.onunmute = () => {
              console.log("[AskAFriend] ✅ Helper audio track unmuted");
            };

            console.log("[AskAFriend] ✅ Helper audio attached and configured");
          } else {
            console.error(
              "[AskAFriend] ❌ Cannot attach audio - missing audioRef or streams:",
              {
                hasAudioRef: !!audioRef.current,
                hasStreams: !!(event.streams && event.streams[0]),
              },
            );
          }
        } else if (event.track.kind === "video") {
          setHelperReceivedVideo(true);
        }
      };

      // Add tracks to peer connection FIRST (before creating offer)
      const tracksAdded = stream.getTracks();
      console.log(
        "[AskAFriend] 📊 Adding",
        tracksAdded.length,
        "tracks to peer connection",
      );
      tracksAdded.forEach((track) => {
        pc.addTrack(track, stream);
        console.log(
          "[AskAFriend] ✅ Added track:",
          track.kind,
          track.label,
          "state:",
          track.readyState,
          "enabled:",
          track.enabled,
        );
        if (track.kind === "audio") {
          setHasAudioTrack(true);
        }
      });

      // Reset counters
      iceCandidateCountRef.current = 0;
      receivedIceCountRef.current = 0;

      // Handle ICE candidates
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          iceCandidateCountRef.current++;
          const code = normalizeCode(sessionId || "");
          const room = roomFor(code);
          console.log(
            `[AskAFriend] 📤 ICE candidate ${iceCandidateCountRef.current} generated (room: ${room}):`,
            event.candidate.candidate.substring(0, 50),
          );
          collaborationService.sendWebRTCICE(event.candidate.toJSON());
        } else {
          console.log(
            "[AskAFriend] ✅ ICE gathering complete. Sent",
            iceCandidateCountRef.current,
            "candidates",
          );
        }
      };

      // Monitor connection state
      pc.onconnectionstatechange = () => {
        const state = pc.connectionState;
        console.log("[AskAFriend] 🔌 Peer connection state:", state);
        console.log("[AskAFriend] 📊 Full state:", {
          connectionState: pc.connectionState,
          iceConnectionState: pc.iceConnectionState,
          signalingState: pc.signalingState,
        });

        if (state === "connected") {
          setWebrtcConnected(true);
          console.log("[AskAFriend] ✅ WebRTC connected!");
          // Clear fallback timeout if WebRTC succeeds
          if (fallbackTimeoutRef.current) {
            clearTimeout(fallbackTimeoutRef.current);
            fallbackTimeoutRef.current = null;
          }
          if (useFallbackMode) {
            console.log(
              "[AskAFriend] 🔄 WebRTC recovered, switching back from fallback",
            );
            setUseFallbackMode(false);
            stopFrameStreaming();
          }
        } else if (state === "failed" || state === "disconnected") {
          setWebrtcConnected(false);
          setHelperReceivedVideo(false);
          console.error("[AskAFriend] ❌ Peer connection", state);
          // Activate fallback if not already active
          if (!useFallbackMode && guideConnected && streamRef.current) {
            console.log(
              "[AskAFriend] 🔄 WebRTC failed, activating fallback frame streaming",
            );
            activateFallbackMode();
          }
        }
      };

      pc.oniceconnectionstatechange = () => {
        const iceState = pc.iceConnectionState;
        console.log("[AskAFriend] 🧊 ICE connection state:", iceState);
        console.log("[AskAFriend] 📊 ICE details:", {
          iceConnectionState: pc.iceConnectionState,
          iceGatheringState: pc.iceGatheringState,
        });

        if (iceState === "failed") {
          console.error("[AskAFriend] ❌ ICE connection failed");
          // Activate fallback instead of showing error
          if (!useFallbackMode && guideConnected && streamRef.current) {
            console.log(
              "[AskAFriend] 🔄 ICE failed, activating fallback frame streaming",
            );
            activateFallbackMode();
            setCameraError(null); // Clear error since fallback will work
          } else {
            setCameraError(
              "Video connection failed. Check network connectivity.",
            );
          }
        } else if (iceState === "connected" || iceState === "completed") {
          console.log("[AskAFriend] ✅ ICE connected/completed");
        }
      };

      // CRITICAL: Create and send offer AFTER tracks are added
      const code = normalizeCode(sessionId || "");
      const room = roomFor(code);
      console.log(
        "[AskAFriend] 📤 Creating offer (after",
        tracksAdded.length,
        "tracks added)...",
      );
      console.log(`[AskAFriend] 📤 Sending WebRTC offer (room: ${room})`);
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      console.log("[AskAFriend] ✅ Set local description (offer)");
      console.log("[AskAFriend] 📊 Offer SDP type:", offer.type);
      console.log("[AskAFriend] 📊 Signaling state:", pc.signalingState);

      collaborationService.sendWebRTCOffer(pc.localDescription!);
      console.log(`[AskAFriend] ✅ Sent WebRTC offer to guide (room: ${room})`);

      // Reset helper acknowledgment (will be set when helper confirms)
      setHelperReceivedVideo(false);

      // Set fallback timeout: if no video received within 8 seconds, ensure frame streaming is active
      if (fallbackTimeoutRef.current) {
        clearTimeout(fallbackTimeoutRef.current);
      }
      fallbackTimeoutRef.current = setTimeout(() => {
        if (!helperReceivedVideo && guideConnected) {
          console.log(
            "[AskAFriend] ⏰ WebRTC timeout (8s), ensuring fallback frame streaming is active",
          );
          if (!useFallbackMode) {
            activateFallbackMode();
          }
        }
      }, 8000);

      // CRITICAL: Also start fallback immediately (don't wait for WebRTC)
      // This ensures helper gets frames right away
      if (guideConnected && !useFallbackMode) {
        console.log(
          "[AskAFriend] 🚀 Starting fallback frame streaming immediately (WebRTC may take time)",
        );
        activateFallbackMode();
      }
    } catch (error) {
      console.error("[AskAFriend] ❌ Error starting WebRTC:", error);
      setCameraError("Failed to start video streaming. Please try again.");
    }
  };

  const cleanup = () => {
    stopWebSpeech();
    if (frameCaptureCleanupRef.current) {
      frameCaptureCleanupRef.current();
      frameCaptureCleanupRef.current = null;
    }
    if (cameraRef.current) {
      cameraRef.current.stop();
      cameraRef.current = null;
    }
    // Close WebRTC peer connection
    if (peerConnectionRef.current) {
      console.log("[AskAFriend] 🛑 Closing WebRTC peer connection");
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
      iceCandidatesRef.current = [];
    }
    setWebrtcConnected(false);
    setHelperReceivedVideo(false);
    setHelperReceivedAudio(false);
    // Stop stream tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    // Clear video element
    if (videoRef.current) {
      videoRef.current.srcObject = null;
      videoRef.current.pause();
    }
    // Clear audio element
    if (audioRef.current) {
      audioRef.current.srcObject = null;
      audioRef.current.pause();
    }
    // Stop local audio track
    if (localAudioTrackRef.current) {
      localAudioTrackRef.current.stop();
      localAudioTrackRef.current = null;
    }
    setIsConnected(false);
    setGuideConnected(false);
    setCameraStreamReady(false);
    setHelperReceivedAudio(false);
    setHelperReceivedVideo(false);
  };

  const toggleMute = () => {
    if (localAudioTrackRef.current) {
      const newMutedState = !isMuted;
      // When muted, disable the track; when unmuted, enable it
      localAudioTrackRef.current.enabled = newMutedState;
      setIsMuted(newMutedState);
      console.log(
        "[AskAFriend] 🎤 Microphone",
        newMutedState ? "unmuted" : "muted",
      );
    } else {
      console.warn("[AskAFriend] ⚠️ No audio track available to mute/unmute");
    }
  };

  const handleDisconnect = () => {
    // Prevent multiple disconnect calls
    if (isDisconnectingRef.current) {
      return;
    }

    isDisconnectingRef.current = true;
    console.log("[AskAFriend] 🛑 Disconnecting...");

    // Set flag to allow navigation
    isNavigatingAwayRef.current = true;

    // Perform cleanup
    cleanup();

    // Clear all state
    setSessionId(null);
    setGuidanceMessage("");
    setIsSpeakingGuidance(false);
    setHelperName(null);
    setError(null);
    setCameraError(null);
    setCameraPermission("prompt");
    setMicrophonePermission("prompt");
    setIsMuted(false);
    setHasAudioTrack(false);
    setUseFallbackMode(false);
    setShowVideoElement(false);
    collaborationService.disconnect();
    

    // Redirect to home screen immediately
    console.log("[AskAFriend] 🏠 Redirecting to home screen...");
    setTimeout(() => {
      const canGoBack = (router as any)?.canGoBack?.() ?? false;
      if (canGoBack) router.back();
      else router.replace("/" as any);

      if (Platform.OS === "web" && typeof window !== "undefined") {
        window.history.replaceState(null, "", "/");
      }

      isDisconnectingRef.current = false;
    }, 50);
  };

  if (Platform.OS !== "web") {
    return (
      <View style={styles.container}>
        <Text style={styles.errorText}>
          This screen is only available on web browsers.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.screen}>
      <ScrollView
        style={styles.scrollContainer}
        contentContainerStyle={styles.container}
      >
        {/* Header */}
        <View style={styles.header}>
          <Pressable
            onPress={handleDisconnect}
            style={styles.backBtnFloating}
            accessibilityLabel="Go back"
          >
            <Ionicons name="arrow-back" size={24} color="#F9A826" />
          </Pressable>
          <View style={{ width: 32 }} />
          <Text style={styles.headerTitle}>Ask a Friend</Text>
          <View style={{ width: 32 }} />
        </View>

      {/* Status Bar */}
      <View style={styles.statusBar}>
        <View
          style={[styles.statusDot, isConnected && styles.statusDotConnected]}
        />
        <Text style={styles.statusText}>
          {isConnecting
            ? "Connecting..."
            : isConnected
              ? guideConnected
                ? helperName
                  ? `${helperName} is helping you`
                  : "Helper is viewing your camera"
                : "Waiting for helper to join..."
              : "Not connected"}
        </Text>
      </View>

      {/* Session Code Display */}
      {sessionId ? (
        <View style={styles.sessionContainer}>
          <Text style={styles.sessionLabel}>Session Code:</Text>
          <Pressable onPress={copySessionCode} style={styles.sessionCode}>
            <Text style={styles.sessionCodeText}>{sessionId}</Text>
            <Ionicons name="copy-outline" size={20} color="#F9A826" />
          </Pressable>
          <Text style={styles.sessionHint}>
            Share this code with your helper so they can join
          </Text>

          {/* Web Helper Link */}
          <View style={styles.webHelperContainer}>
            <Ionicons name="globe-outline" size={16} color="#F9A826" />
            <Text style={styles.webHelperText}>
              Helper can join via web: {getHelperWebUrl()}
            </Text>
          </View>

          <Pressable style={styles.shareButton} onPress={shareSession}>
            <Ionicons name="share-social" size={20} color="#1B263B" />
            <Text style={styles.shareButtonText}>Share Session Code</Text>
          </Pressable>
        </View>
      ) : isConnecting ? (
        <View style={styles.sessionContainer}>
          <ActivityIndicator size="large" color="#F9A826" />
          <Text style={styles.sessionHint}>Creating session...</Text>
        </View>
      ) : (
        <View style={styles.sessionContainer}>
          <Text style={styles.sessionLabel}>Session Code:</Text>
          <Pressable
            style={[
              styles.shareButton,
              { backgroundColor: "#F9A826", marginTop: 8 },
            ]}
            onPress={createSession}
          >
            <Ionicons name="refresh" size={20} color="#1B263B" />
            <Text style={styles.shareButtonText}>Create Session</Text>
          </Pressable>
          {error && (
            <Text
              style={{
                color: "#FF6B6B",
                marginTop: 8,
                fontSize: 12,
                textAlign: "center",
              }}
            >
              {error}
            </Text>
          )}
        </View>
      )}

      {/* Camera Section */}
      <View style={styles.cameraSection} nativeID="camera-section-container">
        {/* Always render video element (hidden when not granted) so ref is always available */}
        {Platform.OS === "web" && showVideoElement && (
          <Fragment>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              onClick={() => {
                // Handle click to start playback if autoplay blocked
                if (videoRef.current && videoRef.current.paused) {
                  videoRef.current
                    .play()
                    .then(() => {
                      console.log(
                        "[AskAFriend] Video started after user click",
                      );
                      setCameraError(null);
                    })
                    .catch((err) => {
                      console.error(
                        "[AskAFriend] Failed to play on click:",
                        err,
                      );
                    });
                }
              }}
              style={{
                width: cameraPermission === "granted" ? "100%" : 0,
                height: cameraPermission === "granted" ? "100%" : 0,
                objectFit: "cover",
                borderRadius: 12,
                backgroundColor: "#000",
                display: cameraPermission === "granted" ? "block" : "none",
                position: cameraPermission === "granted" ? "absolute" : "fixed",
                top: cameraPermission === "granted" ? 0 : -9999,
                left: cameraPermission === "granted" ? 0 : -9999,
                opacity: cameraPermission === "granted" ? 1 : 0,
                pointerEvents: cameraPermission === "granted" ? "auto" : "none",
                zIndex: cameraPermission === "granted" ? 2 : -1,
              }}
            />
            {/* Audio element for receiving helper's audio */}
            <audio
              ref={audioRef}
              autoPlay
              playsInline
              volume={1.0}
              style={{ display: "none" }}
              onLoadedMetadata={() => {
                console.log("[AskAFriend] ✅ Audio element metadata loaded");
                if (audioRef.current) {
                  audioRef.current.volume = 1.0;
                  audioRef.current.muted = false;
                }
              }}
              onCanPlay={() => {
                console.log("[AskAFriend] ✅ Audio element can play");
                if (audioRef.current && audioRef.current.paused) {
                  audioRef.current.play().catch((err) => {
                    console.warn(
                      "[AskAFriend] ⚠️ Auto-play prevented, user interaction required:",
                      err,
                    );
                  });
                }
              }}
              onError={(e) => {
                console.error("[AskAFriend] ❌ Audio element error:", e);
              }}
            />
          </Fragment>
        )}

        {cameraPermission === "granted" ? (
          <Fragment>
            <View
              style={styles.cameraPreview}
              nativeID="camera-preview-container"
            >
              <View style={styles.cameraOverlay}>
                <Text style={styles.cameraStatusText}>
                  {useFallbackMode
                    ? "Camera Active - Fallback mode (frame stream)"
                    : webrtcConnected && helperReceivedVideo
                      ? "Camera Active - Helper viewing your camera"
                      : webrtcConnected
                        ? "Camera Active - Connecting video..."
                        : guideConnected
                          ? "Camera Active - Starting video stream..."
                          : "Camera Active - Waiting for helper"}
                </Text>
                {!!cameraError && cameraError.includes("Tap the video") && (
                  <Text style={styles.tapToPlayText}>
                    Tap video to start playback
                  </Text>
                )}
                {webrtcConnected &&
                  !helperReceivedVideo &&
                  !useFallbackMode && (
                    <Text style={styles.tapToPlayText}>
                      Establishing connection...
                    </Text>
                  )}
                {useFallbackMode && (
                  <Text style={styles.tapToPlayText}>
                    Using reliable frame streaming
                  </Text>
                )}
                {/* Audio Status */}
                {helperReceivedAudio && (
                  <View style={styles.audioStatus}>
                    <Ionicons name="volume-high" size={16} color="#4CAF50" />
                    <Text style={styles.audioStatusText}>
                      Receiving audio from helper
                    </Text>
                    <Pressable
                      onPress={() => {
                        if (audioRef.current) {
                          audioRef.current.volume = 1.0;
                          audioRef.current.muted = false;
                          audioRef.current.play().catch((err) => {
                            console.error(
                              "[AskAFriend] ❌ Manual audio play failed:",
                              err,
                            );
                            Alert.alert(
                              "Audio Playback",
                              "Unable to play audio. Check your browser's autoplay settings.",
                            );
                          });
                          console.log(
                            "[AskAFriend] 🎵 Manually playing helper audio",
                          );
                        }
                      }}
                      style={styles.testAudioButton}
                    >
                      <Ionicons name="play" size={14} color="#4CAF50" />
                      <Text style={styles.testAudioButtonText}>Test Audio</Text>
                    </Pressable>
                  </View>
                )}
                {/* Microphone Status Indicator */}
                {hasAudioTrack && !isMuted && (
                  <View style={styles.micActiveIndicator}>
                    <View style={styles.micPulse} />
                    <Ionicons name="mic" size={16} color="#4CAF50" />
                    <Text style={styles.micActiveText}>Microphone active</Text>
                  </View>
                )}
                {hasAudioTrack && isMuted && (
                  <View style={styles.micMutedIndicator}>
                    <Ionicons name="mic-off" size={16} color="#FF6B6B" />
                    <Text style={styles.micMutedText}>Microphone muted</Text>
                  </View>
                )}
              </View>
            </View>

            {/* Mute/Unmute Button - Always visible when camera is active */}
            <View style={styles.audioControlsContainer}>
              {hasAudioTrack ? (
                <Pressable
                  onPress={toggleMute}
                  style={[
                    styles.muteButton,
                    { backgroundColor: isMuted ? "#FF6B6B" : "#4CAF50" },
                  ]}
                >
                  <Ionicons
                    name={isMuted ? "mic-off" : "mic"}
                    size={20}
                    color="#FFFFFF"
                  />
                  <Text style={styles.muteButtonText}>
                    {isMuted ? "Unmute" : "Mute"}
                  </Text>
                </Pressable>
              ) : microphonePermission === "denied" ? (
                <View style={styles.micPermissionDenied}>
                  <Ionicons name="mic-off" size={20} color="#FF6B6B" />
                  <Text style={styles.micPermissionDeniedText}>
                    Microphone access denied
                  </Text>
                </View>
              ) : (
                <View style={styles.micLoading}>
                  <ActivityIndicator size="small" color="#F9A826" />
                  <Text style={styles.micLoadingText}>
                    Initializing microphone...
                  </Text>
                </View>
              )}
            </View>
          </Fragment>
        ) : cameraPermission === "denied" ? (
          <View style={styles.cameraError}>
            <Ionicons name="camera-outline" size={48} color="#FF6B6B" />
            <Text style={styles.cameraErrorText}>
              {cameraError || "Camera permission denied"}
            </Text>
            <Pressable
              style={styles.retryButton}
              onPress={requestCameraPermission}
            >
              <Text style={styles.retryButtonText}>Retry Camera Access</Text>
            </Pressable>
          </View>
        ) : (
          <View style={styles.cameraPrompt}>
            <Ionicons name="camera-outline" size={48} color="#F9A826" />
            <Text style={styles.cameraPromptText}>
              Enable camera to share your view with your helper
            </Text>
            <Pressable
              style={styles.enableButton}
              onPress={requestCameraPermission}
            >
              <Text style={styles.enableButtonText}>Enable Camera</Text>
            </Pressable>
          </View>
        )}
      </View>

      {/* Guidance Message Display */}
      {!!guidanceMessage && (
        <View
          style={[
            styles.guidanceContainer,
            isSpeakingGuidance && { borderWidth: 2, borderColor: "#4CAF50" },
          ]}
        >
          <Ionicons
            name={isSpeakingGuidance ? "volume-high" : "chatbubble-ellipses"}
            size={24}
            color={isSpeakingGuidance ? "#4CAF50" : "#F9A826"}
          />
          <View style={styles.guidanceTextContainer}>
            <Text style={styles.guidanceText}>{guidanceMessage}</Text>
            {isSpeakingGuidance && (
              <View style={styles.speakingIndicator}>
                <View style={styles.speakingDot} />
                <Text style={styles.speakingText}>Speaking...</Text>
              </View>
            )}
          </View>
          {isSpeakingGuidance && (
            <Pressable
              onPress={() => {
                stopWebSpeech();
                setIsSpeakingGuidance(false);
              }}
              style={styles.stopSpeakingButton}
            >
              <Ionicons name="stop" size={16} color="#FF6B6B" />
            </Pressable>
          )}
        </View>
      )}

      {/* Error Display */}
      {!!error && (
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={20} color="#FF6B6B" />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {/* Disconnect Button */}
      <Pressable style={styles.disconnectButton} onPress={handleDisconnect}>
        <Ionicons name="close-circle" size={24} color="#FF6B6B" />
        <Text style={styles.disconnectButtonText}>Disconnect</Text>
      </Pressable>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    position: "relative",
    backgroundColor: "#1B263B",
  },
  scrollContainer: {
    flex: 1,
    backgroundColor: "#1B263B",
  },
  container: {
    flex: 1,
    backgroundColor: "#1B263B",
    paddingBottom: 20,
  },
  header: {
    position: "relative",
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#2A2A2A",
  },
  backBtnFloating: {
    position: "absolute",
    top: 4,
    left: 8,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "rgba(27,38,59,0.65)",
    borderWidth: 1.5,
    borderColor: "#F9A826",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 20,
  },
  headerTitle: {
    flex: 1,
    color: "#FFF",
    fontSize: 20,
    fontWeight: "700",
    textAlign: "center",
  },
  statusBar: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: "#2A2A2A",
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#666",
    marginRight: 8,
  },
  statusDotConnected: {
    backgroundColor: "#4CAF50",
  },
  statusText: {
    color: "#FFF",
    fontSize: 14,
  },
  sessionContainer: {
    padding: 16,
    backgroundColor: "#2A2A2A",
    marginHorizontal: 16,
    marginTop: 16,
    borderRadius: 8,
  },
  sessionLabel: {
    color: "#AAA",
    fontSize: 12,
    marginBottom: 4,
  },
  sessionCode: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#1B263B",
    padding: 12,
    borderRadius: 8,
    marginBottom: 8,
  },
  sessionCodeText: {
    color: "#F9A826",
    fontSize: 24,
    fontWeight: "700",
    letterSpacing: 4,
  },
  sessionHint: {
    color: "#888",
    fontSize: 12,
    marginBottom: 12,
  },
  webHelperContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#1B263B",
    padding: 10,
    borderRadius: 8,
    marginBottom: 12,
    gap: 8,
  },
  webHelperText: {
    flex: 1,
    color: "#F9A826",
    fontSize: 11,
    lineHeight: 16,
  },
  shareButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F9A826",
    padding: 12,
    borderRadius: 8,
    gap: 8,
  },
  shareButtonText: {
    color: "#1B263B",
    fontSize: 14,
    fontWeight: "600",
  },
  cameraSection: {
    margin: 16,
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: "#000",
    minHeight: 300,
  },
  cameraPreview: {
    width: "100%",
    minHeight: 300,
    aspectRatio: 16 / 9,
    backgroundColor: "#000",
    position: "relative",
    borderRadius: 12,
    overflow: "hidden",
  },
  cameraOverlay: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: "rgba(0, 0, 0, 0.7)",
    padding: 8,
    alignItems: "center",
    zIndex: 10,
  },
  cameraStatusText: {
    color: "#4CAF50",
    fontSize: 12,
    fontWeight: "600",
  },
  tapToPlayText: {
    color: "#F9A826",
    fontSize: 11,
    marginTop: 4,
    fontStyle: "italic",
  },
  cameraPrompt: {
    padding: 32,
    alignItems: "center",
    justifyContent: "center",
    gap: 16,
  },
  cameraPromptText: {
    color: "#AAA",
    fontSize: 16,
    textAlign: "center",
  },
  enableButton: {
    backgroundColor: "#F9A826",
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
  },
  enableButtonText: {
    color: "#1B263B",
    fontSize: 16,
    fontWeight: "600",
  },
  cameraError: {
    padding: 32,
    alignItems: "center",
    justifyContent: "center",
    gap: 16,
  },
  cameraErrorText: {
    color: "#FF6B6B",
    fontSize: 16,
    textAlign: "center",
  },
  retryButton: {
    backgroundColor: "#F9A826",
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
  },
  retryButtonText: {
    color: "#1B263B",
    fontSize: 16,
    fontWeight: "600",
  },
  guidanceContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#2A2A2A",
    marginHorizontal: 16,
    marginTop: 16,
    padding: 12,
    borderRadius: 8,
    gap: 12,
  },
  guidanceTextContainer: {
    flex: 1,
    gap: 4,
  },
  guidanceText: {
    color: "#FFF",
    fontSize: 18,
    fontWeight: "600",
    lineHeight: 24,
  },
  speakingIndicator: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 4,
  },
  speakingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#4CAF50",
  },
  speakingText: {
    color: "#4CAF50",
    fontSize: 12,
    fontWeight: "500",
    fontStyle: "italic",
  },
  stopSpeakingButton: {
    padding: 6,
    borderRadius: 4,
    backgroundColor: "#3A1F1F",
  },
  errorContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#3A1F1F",
    marginHorizontal: 16,
    marginTop: 16,
    padding: 12,
    borderRadius: 8,
    gap: 8,
  },
  errorText: {
    flex: 1,
    color: "#FF6B6B",
    fontSize: 14,
  },
  disconnectButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#3A1F1F",
    marginHorizontal: 16,
    marginTop: 16,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#FF6B6B",
    gap: 8,
  },
  disconnectButtonText: {
    color: "#FF6B6B",
    fontSize: 16,
    fontWeight: "600",
  },
  audioControlsContainer: {
    marginTop: 12,
    marginBottom: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  muteButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 8,
    gap: 8,
    minWidth: 120,
  },
  muteButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "600",
  },
  micPermissionDenied: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
    backgroundColor: "#3A1F1F",
    gap: 8,
  },
  micPermissionDeniedText: {
    color: "#FF6B6B",
    fontSize: 12,
    fontWeight: "500",
  },
  micLoading: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 8,
    paddingHorizontal: 16,
    gap: 8,
  },
  micLoadingText: {
    color: "#F9A826",
    fontSize: 12,
    fontWeight: "500",
  },
  audioStatus: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 8,
    gap: 6,
  },
  audioStatusText: {
    color: "#4CAF50",
    fontSize: 12,
    fontWeight: "500",
  },
  micActiveIndicator: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 8,
    gap: 6,
    position: "relative",
  },
  micPulse: {
    position: "absolute",
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: "#4CAF50",
    opacity: 0.5,
  },
  micActiveText: {
    color: "#4CAF50",
    fontSize: 12,
    fontWeight: "500",
  },
  micMutedIndicator: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 8,
    gap: 6,
  },
  micMutedText: {
    color: "#FF6B6B",
    fontSize: 12,
    fontWeight: "500",
  },
  testAudioButton: {
    flexDirection: "row",
    alignItems: "center",
    marginLeft: 8,
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 4,
    backgroundColor: "#2A2A2A",
    gap: 4,
  },
  testAudioButtonText: {
    color: "#4CAF50",
    fontSize: 10,
    fontWeight: "500",
  },
});
