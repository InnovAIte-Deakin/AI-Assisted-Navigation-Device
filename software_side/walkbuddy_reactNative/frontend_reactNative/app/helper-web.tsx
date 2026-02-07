// app/helper-web.tsx
// Simple web-only helper interface for browsers
// This allows helpers to help without downloading the app
// Accessible at: https://your-app-url.com/helper-web

import { useEffect, useState, useRef } from "react";
import {
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
  Image,
  ActivityIndicator,
  Alert,
  ScrollView,
} from "react-native";
import { Platform, Linking } from "react-native";
import { useRouter, usePathname, useSegments } from "expo-router";
import {
  collaborationService,
  normalizeCode,
  roomFor,
} from "@/src/utils/collaboration";
// import { API_BASE } from "@/src/config";
import { Ionicons } from "@expo/vector-icons";

const API_BASE = "http://127.0.0.1:8000";

// Connection state machine
type ConnectionState =
  | "idle"
  | "socket_connected"
  | "joined_room"
  | "webrtc_connecting"
  | "webrtc_connected"
  | "fallback_active";

// Only render on web
export default function HelperWebScreen() {
  console.log("[HelperWeb] 🚀 HelperWebScreen mounted");

  const router = useRouter();
  const pathname = usePathname();
  const segments = useSegments();
  const isNavigatingAwayRef = useRef(false);

  // Authentication state
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [helperName, setHelperName] = useState<string | null>(null);
  const [helperData, setHelperData] = useState<any>(null);
  const [showSignup, setShowSignup] = useState(false);
  const [isLoadingAuth, setIsLoadingAuth] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  // Settings state
  const [showSettings, setShowSettings] = useState(false);
  const [settingsSection, setSettingsSection] = useState<
    "account" | "privacy" | "help" | "about" | null
  >(null);
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [supportMessage, setSupportMessage] = useState("");
  const [isSendingSupport, setIsSendingSupport] = useState(false);

  // Signup form state
  const [signupData, setSignupData] = useState({
    name: "",
    age: "",
    email: "",
    phone: "",
    address: "",
    emergency_contact_name: "",
    emergency_contact_phone: "",
    experience_level: "",
    password: "",
    confirmPassword: "",
  });
  const [termsAccepted, setTermsAccepted] = useState(false);

  // Login form state
  const [loginData, setLoginData] = useState({
    email: "",
    password: "",
  });

  const [sessionId, setSessionId] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [userConnected, setUserConnected] = useState(false);
  const [cameraFrame, setCameraFrame] = useState<string | null>(null);
  const [guidanceText, setGuidanceText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<{
    user_connected: boolean;
    expires_in: number;
  } | null>(null);
  const [isCheckingStatus, setIsCheckingStatus] = useState(false);

  // WebRTC peer connection
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const remoteVideoRef = useRef<HTMLVideoElement | null>(null);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null); // For receiving user's audio
  const iceCandidatesRef = useRef<RTCIceCandidate[]>([]);
  const [hasVideoTrack, setHasVideoTrack] = useState(false);
  const [hasAudioTrack, setHasAudioTrack] = useState(false);
  const [userReceivedAudio, setUserReceivedAudio] = useState(false);
  const [microphonePermission, setMicrophonePermission] = useState<
    "granted" | "denied" | "prompt"
  >("prompt");
  const [isMuted, setIsMuted] = useState(false);
  const [localAudioStream, setLocalAudioStream] = useState<MediaStream | null>(
    null,
  );
  const localAudioTrackRef = useRef<MediaStreamTrack | null>(null);
  const [webrtcError, setWebrtcError] = useState<string | null>(null);

  // Connection state machine
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("idle");
  const connectionStateRef = useRef<ConnectionState>("idle");

  // Fallback frame streaming
  const [useFallbackMode, setUseFallbackMode] = useState(false);
  const [lastFrameDataUrl, setLastFrameDataUrl] = useState<string | null>(null);
  const fallbackTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const frameStatsIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const frameReceivedCountRef = useRef(0); // Use ref for counter to persist across renders
  const hasVideoTrackRef = useRef(false); // Use ref to avoid stale closure in message handlers
  const useFallbackModeRef = useRef(false); // Use ref to avoid stale closure in message handlers
  const webrtcStartTimeRef = useRef<number | null>(null);

  // Check for existing authentication token on mount
  useEffect(() => {
    if (Platform.OS === "web" && typeof window !== "undefined") {
      const storedToken = localStorage.getItem("helper_auth_token");
      const storedName = localStorage.getItem("helper_name");
      if (storedToken) {
        // Verify token is still valid
        verifyToken(storedToken);
      }
      if (storedName) {
        setHelperName(storedName);
      }
    }
  }, []);

  // Verify authentication token
  const verifyToken = async (token: string) => {
    try {
      const response = await fetch(`${API_BASE}helpers/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (response.ok) {
        const helperData = await response.json();
        setAuthToken(token);
        setHelperName(helperData.name);
        setHelperData(helperData);
        setIsAuthenticated(true);
        if (typeof window !== "undefined") {
          localStorage.setItem("helper_auth_token", token);
          localStorage.setItem("helper_name", helperData.name);
        }
      } else {
        // Token invalid, clear it
        if (typeof window !== "undefined") {
          localStorage.removeItem("helper_auth_token");
          localStorage.removeItem("helper_name");
        }
      }
    } catch (error) {
      console.error("[HelperWeb] Token verification failed:", error);
      if (typeof window !== "undefined") {
        localStorage.removeItem("helper_auth_token");
        localStorage.removeItem("helper_name");
      }
    }
  };

  // Fetch helper data for account section
  const fetchHelperData = async () => {
    if (!authToken) return;
    try {
      const response = await fetch(`${API_BASE}helpers/me`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setHelperData(data);
      }
    } catch (error) {
      console.error("[HelperWeb] Error fetching helper data:", error);
    }
  };

  // Delete account - show confirmation modal
  const handleDeleteAccount = () => {
    if (!authToken) {
      if (Platform.OS === "web" && typeof window !== "undefined") {
        window.alert("You must be logged in to delete your account.");
      } else {
        Alert.alert("Error", "You must be logged in to delete your account.");
      }
      return;
    }
    setShowDeleteConfirm(true);
  };

  // Confirm and execute account deletion
  const confirmDeleteAccount = async () => {
    if (!authToken) return;

    setShowDeleteConfirm(false);
    setIsDeletingAccount(true);

    try {
      console.log("[HelperWeb] 🗑️ Deleting account...");
      const response = await fetch(`${API_BASE}helpers/delete-account`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      console.log("[HelperWeb] Delete account response:", response.status);

      if (response.ok) {
        // Close settings modal first
        setShowSettings(false);
        setSettingsSection(null);

        // Clear all auth data
        setAuthToken(null);
        setHelperName(null);
        setHelperData(null);
        setIsAuthenticated(false);
        if (typeof window !== "undefined") {
          localStorage.removeItem("helper_auth_token");
          localStorage.removeItem("helper_name");
        }

        // Disconnect from any active session
        if (isConnected) {
          handleDisconnect();
        }

        console.log("[HelperWeb] ✅ Account deleted successfully");

        if (Platform.OS === "web" && typeof window !== "undefined") {
          window.alert(
            "Your account has been deleted successfully. You will be redirected to the login page.",
          );
        } else {
          Alert.alert(
            "Success",
            "Your account has been deleted successfully. You will be redirected to the login page.",
          );
        }
      } else {
        const errorData = await response.json();
        const errorMessage = errorData.detail || "Failed to delete account";
        console.error("[HelperWeb] ❌ Delete account error:", errorMessage);
        throw new Error(errorMessage);
      }
    } catch (error: any) {
      console.error("[HelperWeb] ❌ Error deleting account:", error);
      const errorMessage =
        error.message || "Failed to delete account. Please try again.";
      if (Platform.OS === "web" && typeof window !== "undefined") {
        window.alert(`Error: ${errorMessage}`);
      } else {
        Alert.alert("Error", errorMessage);
      }
    } finally {
      setIsDeletingAccount(false);
    }
  };

  // Password validation function
  const validatePassword = (
    password: string,
  ): { isValid: boolean; errors: string[] } => {
    const errors: string[] = [];

    if (password.length < 8) {
      errors.push("Password must be at least 8 characters long");
    }

    if (!/[A-Z]/.test(password)) {
      errors.push("Password must contain at least one capital letter");
    }

    if (!/[a-z]/.test(password)) {
      errors.push("Password must contain at least one small letter");
    }

    if (!/[0-9]/.test(password)) {
      errors.push("Password must contain at least one number");
    }

    if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) {
      errors.push(
        "Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;':\",./<>?)",
      );
    }

    return {
      isValid: errors.length === 0,
      errors,
    };
  };

  // Handle signup
  const handleSignup = async () => {
    setIsLoadingAuth(true);
    setAuthError(null);

    // Validation
    if (!signupData.name || !signupData.email || !signupData.password) {
      setAuthError("Name, email, and password are required");
      setIsLoadingAuth(false);
      return;
    }

    // Password validation
    const passwordValidation = validatePassword(signupData.password);
    if (!passwordValidation.isValid) {
      setAuthError(
        `Password requirements:\n${passwordValidation.errors.join("\n")}`,
      );
      setIsLoadingAuth(false);
      return;
    }

    if (signupData.password !== signupData.confirmPassword) {
      setAuthError("Passwords do not match");
      setIsLoadingAuth(false);
      return;
    }

    if (!termsAccepted) {
      setAuthError(
        "You must accept the Terms and Conditions to sign up. Please check the box to continue.",
      );
      setIsLoadingAuth(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE}helpers/signup`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: signupData.name,
          age: signupData.age ? parseInt(signupData.age) : null,
          email: signupData.email,
          phone: signupData.phone || null,
          address: signupData.address || null,
          emergency_contact_name: signupData.emergency_contact_name || null,
          emergency_contact_phone: signupData.emergency_contact_phone || null,
          experience_level: signupData.experience_level || null,
          password: signupData.password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Signup failed");
      }

      // Signup successful - show success message and redirect to login
      const signupEmail = signupData.email;

      // Clear form
      setSignupData({
        name: "",
        age: "",
        email: "",
        phone: "",
        address: "",
        emergency_contact_name: "",
        emergency_contact_phone: "",
        experience_level: "",
        password: "",
        confirmPassword: "",
      });
      setTermsAccepted(false);

      // Show success message and switch to login
      if (Platform.OS === "web" && typeof window !== "undefined") {
        window.alert(
          "Account created successfully! Please login with your credentials.",
        );
      } else {
        Alert.alert(
          "Success",
          "Account created successfully! Please login with your credentials.",
        );
      }

      // Switch to login tab and pre-fill email
      setShowSignup(false);
      setLoginData({ email: signupEmail, password: "" });
      setAuthError(null);
    } catch (error: any) {
      console.error("[HelperWeb] Signup error:", error);
      const errorMessage = error.message || "Signup failed. Please try again.";

      // Check if it's a duplicate account error
      if (
        errorMessage.includes("already exists") ||
        errorMessage.includes("already registered")
      ) {
        setAuthError(errorMessage + " Click 'Login' to access your account.");
      } else {
        setAuthError(errorMessage);
      }
    } finally {
      setIsLoadingAuth(false);
    }
  };

  // Handle login
  const handleLogin = async () => {
    setIsLoadingAuth(true);
    setAuthError(null);

    if (!loginData.email || !loginData.password) {
      setAuthError("Email and password are required");
      setIsLoadingAuth(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE}helpers/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(loginData),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Login failed");
      }

      // Store token and authenticate
      setAuthToken(data.token);
      setHelperName(data.helper.name);
      setHelperData(data.helper);
      setIsAuthenticated(true);
      if (typeof window !== "undefined") {
        localStorage.setItem("helper_auth_token", data.token);
        localStorage.setItem("helper_name", data.helper.name);
      }

      // Clear form
      setLoginData({ email: "", password: "" });
    } catch (error: any) {
      console.error("[HelperWeb] Login error:", error);
      setAuthError(
        error.message || "Login failed. Please check your credentials.",
      );
    } finally {
      setIsLoadingAuth(false);
    }
  };

  // Handle logout
  const handleLogout = async () => {
    if (authToken) {
      try {
        await fetch(`${API_BASE}helpers/logout`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        });
      } catch (error) {
        console.error("[HelperWeb] Logout error:", error);
      }
    }

    setAuthToken(null);
    setHelperName(null);
    setIsAuthenticated(false);
    if (typeof window !== "undefined") {
      localStorage.removeItem("helper_auth_token");
      localStorage.removeItem("helper_name");
    }

    // Disconnect from any active session
    if (isConnected) {
      handleDisconnect();
    }
  };

  // Prevent any navigation redirects on web - this screen must stay on web
  useEffect(() => {
    if (Platform.OS !== "web") {
      // On mobile, redirect to home instead
      router.replace("/");
      return;
    }

    // CRITICAL: Prevent Expo Router's anchor redirect and splash screen redirect
    // Check if pathname changed away from helper-web
    if (
      pathname &&
      pathname !== "/helper-web" &&
      !isNavigatingAwayRef.current
    ) {
      console.log(
        "[HelperWeb] Detected redirect attempt, preventing:",
        pathname,
      );
      // Force navigation back to helper-web immediately
      // Use replace to prevent back button issues
      router.replace("/helper-web");
    }

    // Also check window.location as a fallback (for web)
    if (
      typeof window !== "undefined" &&
      window.location.pathname !== "/helper-web"
    ) {
      window.history.replaceState(null, "", "/helper-web");
    }
  }, [pathname, router]);

  // Monitor segments to catch redirects to tabs/home
  // useEffect(() => {
  //   if (Platform.OS === "web") {
  //     // If segments indicate we're being redirected to tabs/home, prevent it
  //     if (segments.length > 0) {
  //       const isRedirectingToTabs =
  //         segments.includes("(tabs)") || segments.includes("home");
  //       const isOnHelperWeb =
  //         pathname === "/helper-web" || segments[0] === "helper-web";

  //       if (isRedirectingToTabs && !isOnHelperWeb) {
  //         console.log(
  //           "[HelperWeb] Preventing redirect to tabs/home, segments:",
  //           segments,
  //         );
  //         router.replace("/helper-web");
  //       }
  //     }
  //   }
  // }, [segments, pathname, router]);

  // Handle WebRTC offer from user (defined before useEffect to avoid scope issues)
  const handleWebRTCOffer = async (sdp: RTCSessionDescriptionInit) => {
    try {
      console.log("[HelperWeb] 🎥 Handling WebRTC offer");

      // Clean up existing peer connection
      if (peerConnectionRef.current) {
        console.log("[HelperWeb] 🛑 Cleaning up existing peer connection");
        peerConnectionRef.current.close();
        peerConnectionRef.current = null;
        iceCandidatesRef.current = [];
      }

      // Create peer connection with STUN
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
      });
      peerConnectionRef.current = pc;

      // Handle remote track (video and audio streams)
      pc.ontrack = (event) => {
        console.log(
          "[HelperWeb] ✅ Received remote track:",
          event.track.kind,
          event.track.label,
        );
        console.log("[HelperWeb] 📊 Track details:", {
          kind: event.track.kind,
          label: event.track.label,
          enabled: event.track.enabled,
          readyState: event.track.readyState,
          streams: event.streams.length,
        });

        const remoteStream = event.streams[0];

        if (event.track.kind === "audio") {
          // Handle audio track
          setUserReceivedAudio(true);
          if (remoteAudioRef.current && remoteStream) {
            const audioElement = remoteAudioRef.current;

            console.log("[HelperWeb] 🎵 Attaching user audio stream:", {
              streamId: remoteStream.id,
              audioTracks: remoteStream.getAudioTracks().length,
              trackLabel: event.track.label,
              trackEnabled: event.track.enabled,
            });

            audioElement.srcObject = remoteStream;
            audioElement.volume = 1.0; // Ensure volume is at maximum
            audioElement.muted = false; // Ensure not muted

            audioElement
              .play()
              .then(() => {
                console.log("[HelperWeb] ✅ User audio playing successfully");
                console.log("[HelperWeb] ✅ Audio element state:", {
                  volume: audioElement.volume,
                  muted: audioElement.muted,
                  paused: audioElement.paused,
                  readyState: audioElement.readyState,
                });
              })
              .catch((err) => {
                console.error("[HelperWeb] ❌ Audio play error:", err);
                // Try again after a short delay
                setTimeout(() => {
                  audioElement.play().catch((retryErr) => {
                    console.error(
                      "[HelperWeb] ❌ Audio play retry failed:",
                      retryErr,
                    );
                  });
                }, 500);
              });

            // Monitor audio track state
            event.track.onended = () => {
              console.log("[HelperWeb] ⚠️ User audio track ended");
              setUserReceivedAudio(false);
            };

            event.track.onmute = () => {
              console.log("[HelperWeb] ⚠️ User audio track muted");
            };

            event.track.onunmute = () => {
              console.log("[HelperWeb] ✅ User audio track unmuted");
            };

            console.log("[HelperWeb] ✅ User audio attached and configured");
          } else {
            console.error(
              "[HelperWeb] ❌ Cannot attach audio - missing audioRef or stream:",
              {
                hasAudioRef: !!remoteAudioRef.current,
                hasStream: !!remoteStream,
              },
            );
          }
          return;
        }

        // Handle video track
        if (remoteStream && remoteVideoRef.current) {
          const videoTracks = remoteStream.getVideoTracks();
          console.log(
            "[HelperWeb] 📊 Remote stream has",
            videoTracks.length,
            "video track(s)",
          );

          remoteVideoRef.current.srcObject = remoteStream;
          remoteVideoRef.current.playsInline = true;
          remoteVideoRef.current.autoplay = true;

          // Wait for video metadata to check if track is valid
          const checkVideoFrames = () => {
            if (
              remoteVideoRef.current &&
              remoteVideoRef.current.videoWidth > 0
            ) {
              console.log("[HelperWeb] ✅ Video track active:", {
                width: remoteVideoRef.current.videoWidth,
                height: remoteVideoRef.current.videoHeight,
                readyState: remoteVideoRef.current.readyState,
              });
              setHasVideoTrack(true);
              hasVideoTrackRef.current = true;
              setWebrtcError(null);
              setConnectionState("webrtc_connected");
              connectionStateRef.current = "webrtc_connected";

              // Log successful video attachment
              console.log(
                "[HelperWeb] ✅ Successfully attached remote MediaStream to video element",
              );

              // Clear timeout if set
              if ((pc as any)._trackTimeoutCleanup) {
                (pc as any)._trackTimeoutCleanup();
              }
              if (fallbackTimeoutRef.current) {
                clearTimeout(fallbackTimeoutRef.current);
                fallbackTimeoutRef.current = null;
              }

              // If WebRTC is working, disable fallback mode
              if (useFallbackModeRef.current) {
                console.log(
                  "[HelperWeb] 🔄 WebRTC track received, disabling fallback mode",
                );
                setUseFallbackMode(false);
                useFallbackModeRef.current = false;
                setCameraFrame(null); // Clear frame display
                setLastFrameDataUrl(null);
              }

              // Send acknowledgment to user that video was received
              console.log(
                "[HelperWeb] 📤 Sending video_received acknowledgment",
              );
              collaborationService.sendMessage("video_received" as any, {});
            } else {
              // Retry after a short delay
              setTimeout(() => {
                if (
                  remoteVideoRef.current &&
                  remoteVideoRef.current.videoWidth > 0
                ) {
                  checkVideoFrames();
                }
              }, 500);
            }
          };

          remoteVideoRef.current.onloadedmetadata = () => {
            console.log("[HelperWeb] 📊 Video metadata loaded");
            checkVideoFrames();
          };

          remoteVideoRef.current
            .play()
            .then(() => {
              console.log("[HelperWeb] ✅ Video element play() succeeded");
            })
            .catch((err) => {
              console.warn(
                "[HelperWeb] ⚠️ Video play error (may be expected):",
                err,
              );
            });

          // Also check immediately in case metadata already loaded
          if (remoteVideoRef.current.readyState >= 2) {
            checkVideoFrames();
          }
        } else {
          console.error("[HelperWeb] ❌ No remote stream or video element");
        }
      };

      // Handle ICE candidates
      let iceCandidateCount = 0;
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          iceCandidateCount++;
          console.log(
            "[HelperWeb] 📤 ICE candidate",
            iceCandidateCount,
            "generated:",
            event.candidate.candidate.substring(0, 50),
          );
          collaborationService.sendWebRTCICE(event.candidate.toJSON());
        } else {
          console.log(
            "[HelperWeb] ✅ ICE gathering complete. Sent",
            iceCandidateCount,
            "candidates",
          );
        }
      };

      // Monitor connection state
      pc.onconnectionstatechange = () => {
        const state = pc.connectionState;
        console.log("[HelperWeb] 🔌 Peer connection state:", state);
        console.log("[HelperWeb] 📊 Full state:", {
          connectionState: pc.connectionState,
          iceConnectionState: pc.iceConnectionState,
          signalingState: pc.signalingState,
        });

        if (state === "failed") {
          console.error("[HelperWeb] ❌ Peer connection failed");
          // If we're receiving frames, switch to fallback mode instead of showing error
          if (cameraFrame) {
            console.log(
              "[HelperWeb] 🔄 WebRTC failed but frames received, switching to fallback mode",
            );
            setUseFallbackMode(true);
            setWebrtcError(null);
          } else {
            setWebrtcError("WebRTC connection failed. Please try again.");
          }
        } else if (state === "connected") {
          console.log("[HelperWeb] ✅ Peer connection established");
          setWebrtcError(null);
        } else if (state === "disconnected") {
          setHasVideoTrack(false);
          setWebrtcError(null);
          // If disconnected but frames are coming, use fallback
          if (cameraFrame) {
            setUseFallbackMode(true);
          }
        }
      };

      pc.oniceconnectionstatechange = () => {
        const iceState = pc.iceConnectionState;
        console.log("[HelperWeb] 🧊 ICE connection state:", iceState);
        console.log("[HelperWeb] 📊 ICE details:", {
          iceConnectionState: pc.iceConnectionState,
          iceGatheringState: pc.iceGatheringState,
        });

        if (iceState === "failed") {
          console.error("[HelperWeb] ❌ ICE connection failed");
          // If we're receiving frames, switch to fallback mode instead of showing error
          if (cameraFrame) {
            console.log(
              "[HelperWeb] 🔄 ICE failed but frames received, switching to fallback mode",
            );
            setUseFallbackMode(true);
            setWebrtcError(null);
          } else {
            setWebrtcError(
              "ICE connection failed. Check network connectivity.",
            );
          }
        } else if (iceState === "connected" || iceState === "completed") {
          console.log("[HelperWeb] ✅ ICE connected/completed");
        }
      };

      // Set remote description (offer)
      await pc.setRemoteDescription(new RTCSessionDescription(sdp));
      console.log("[HelperWeb] ✅ Set remote description (offer)");

      // Add any pending ICE candidates
      for (const candidate of iceCandidatesRef.current) {
        try {
          await pc.addIceCandidate(candidate);
        } catch (err) {
          console.warn("[HelperWeb] Failed to add pending ICE candidate:", err);
        }
      }
      iceCandidatesRef.current = [];

      // Request microphone access and add audio track
      try {
        console.log("[HelperWeb] 🎤 Requesting microphone access...");
        const audioStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });

        const audioTracks = audioStream.getAudioTracks();
        if (audioTracks.length > 0) {
          localAudioTrackRef.current = audioTracks[0];
          setMicrophonePermission("granted");
          setHasAudioTrack(true);
          setLocalAudioStream(audioStream);

          // Add audio track to peer connection
          audioTracks.forEach((track) => {
            pc.addTrack(track, audioStream);
            console.log(
              "[HelperWeb] ✅ Added audio track:",
              track.label,
              "enabled:",
              track.enabled,
            );
          });
        }
      } catch (err: any) {
        console.warn("[HelperWeb] ⚠️ Microphone access denied or failed:", err);
        setMicrophonePermission("denied");
        // Continue without audio - video will still work
      }

      // Create and send answer
      console.log("[HelperWeb] 📤 Creating answer...");
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      console.log("[HelperWeb] ✅ Set local description (answer)");

      collaborationService.sendWebRTCAnswer(pc.localDescription!);
      console.log("[HelperWeb] ✅ Sent WebRTC answer to user");

      // Set timeout to detect if no track received - switch to fallback if frames are coming
      const trackTimeout = setTimeout(() => {
        if (!hasVideoTrackRef.current && peerConnectionRef.current) {
          console.warn(
            "[HelperWeb] ⚠️ No video track received within 10 seconds",
          );
          console.log("[HelperWeb] 📊 Connection state at timeout:", {
            connectionState: peerConnectionRef.current.connectionState,
            iceConnectionState: peerConnectionRef.current.iceConnectionState,
            signalingState: peerConnectionRef.current.signalingState,
          });

          // If we're receiving frames, switch to fallback mode
          if (lastFrameDataUrl) {
            console.log(
              "[HelperWeb] 🔄 WebRTC failed but frames received, switching to fallback mode",
            );
            setUseFallbackMode(true);
            useFallbackModeRef.current = true;
            setConnectionState("fallback_active");
            connectionStateRef.current = "fallback_active";
            setWebrtcError(null); // Clear error since fallback is working
          } else {
            setWebrtcError(
              "No video track received. Check ICE/signaling. Connection state: " +
                peerConnectionRef.current.connectionState,
            );
          }
        }
      }, 10000);

      // Store cleanup function
      (pc as any)._trackTimeoutCleanup = () => {
        clearTimeout(trackTimeout);
      };
    } catch (error) {
      console.error("[HelperWeb] ❌ Error handling WebRTC offer:", error);
      setWebrtcError("Failed to establish video connection. Please try again.");
    }
  };

  // Connection state machine: enforce fallback after 8-10s if no WebRTC
  useEffect(() => {
    if (
      connectionState === "webrtc_connecting" &&
      !webrtcStartTimeRef.current
    ) {
      webrtcStartTimeRef.current = Date.now();

      // Set timeout to force fallback if WebRTC doesn't connect within 8-10s
      const webrtcTimeout = setTimeout(() => {
        if (
          connectionStateRef.current === "webrtc_connecting" &&
          !hasVideoTrackRef.current
        ) {
          console.log(
            "[HelperWeb] ⏰ WebRTC timeout (8s), forcing fallback mode",
          );
          if (lastFrameDataUrl) {
            setUseFallbackMode(true);
            useFallbackModeRef.current = true;
            setConnectionState("fallback_active");
            connectionStateRef.current = "fallback_active";
          } else {
            console.log(
              "[HelperWeb] ⚠️ WebRTC timeout but no frames received yet",
            );
          }
        }
      }, 8000);

      return () => {
        clearTimeout(webrtcTimeout);
      };
    }
  }, [connectionState, lastFrameDataUrl]);

  // CRITICAL: When user connects, immediately expect frames (don't wait for WebRTC)
  useEffect(() => {
    if (
      userConnected &&
      !hasVideoTrackRef.current &&
      !useFallbackModeRef.current
    ) {
      console.log(
        "[HelperWeb] 👤 User connected, expecting frames soon. Will switch to fallback mode when frames arrive.",
      );
      // Don't set fallback mode yet - wait for first frame
      // But log that we're ready to receive frames
    }
  }, [userConnected]);

  // CHECKPOINT D: Monitor cameraFrame state changes for rendering
  useEffect(() => {
    if (cameraFrame) {
      // Ensure data URL format
      let frameDataUrl = cameraFrame;
      if (!frameDataUrl.startsWith("data:image")) {
        frameDataUrl = `data:image/jpeg;base64,${frameDataUrl}`;
      }

      console.log(
        `[FRAME] CHECKPOINT D: cameraFrame state updated (length=${frameDataUrl.length}), UI should render <img>`,
      );
      console.log(
        `[FRAME] CHECKPOINT D: useFallbackMode=${useFallbackMode}, lastFrameDataUrl will be set`,
      );
      // Set lastFrameDataUrl to trigger immediate render
      setLastFrameDataUrl(frameDataUrl);

      // If we have frames but fallback mode not set, set it
      if (!useFallbackMode && !hasVideoTrack) {
        console.log(
          `[FRAME] CHECKPOINT D: Activating fallback mode because frames are available`,
        );
        setUseFallbackMode(true);
        useFallbackModeRef.current = true;
      }
    } else {
      // Only clear if we don't have WebRTC track
      if (!hasVideoTrack) {
        console.log(
          `[FRAME] CHECKPOINT D: cameraFrame state cleared, will show placeholder`,
        );
        setLastFrameDataUrl(null);
      }
    }
  }, [cameraFrame, useFallbackMode, hasVideoTrack]);

  // Set up message handlers
  useEffect(() => {
    console.log("[HelperWeb] 🔧 Setting up message handlers...");
    console.log("[HelperWeb] 🔧 Current sessionId:", sessionId);
    console.log("[HelperWeb] 🔧 Current isConnected:", isConnected);

    const unsubscribeConnected = collaborationService.onMessage(
      "connected",
      (msg) => {
        const code = normalizeCode(msg.session_id || "");
        const room = roomFor(code);
        console.log(
          `[HelperWeb] ✅ Socket connected, received 'connected' event`,
        );
        console.log(`[HelperWeb] ✅ Connected to session: ${code}`);
        console.log(`[HelperWeb] ✅ Joined room: ${room}`);
        setIsConnected(true);
        setIsConnecting(false);
        setError(null);
        setConnectionState("socket_connected");
        connectionStateRef.current = "socket_connected";

        // Check if user is already connected (from connection message)
        if ((msg as any).user_connected) {
          console.log(
            "[HelperWeb] ✅ User is already connected (peer_connected event)",
          );
          setUserConnected(true);
          setConnectionState("joined_room");
          connectionStateRef.current = "joined_room";
        }
      },
    );

    const unsubscribeUserConnected = collaborationService.onMessage(
      "user_connected",
      () => {
        console.log(
          "[HelperWeb] ✅ User connected event received (peer_connected)",
        );
        setUserConnected(true);
        setConnectionState("joined_room");
        connectionStateRef.current = "joined_room";
        // User might send WebRTC offer, wait for it
      },
    );

    const unsubscribeUserDisconnected = collaborationService.onMessage(
      "user_disconnected",
      () => {
        setUserConnected(false);
        setCameraFrame(null);
        setUseFallbackMode(false);
        useFallbackModeRef.current = false;
        setHasVideoTrack(false);
        hasVideoTrackRef.current = false;
        // Clear timeout
        if (fallbackTimeoutRef.current) {
          clearTimeout(fallbackTimeoutRef.current);
          fallbackTimeoutRef.current = null;
        }
      },
    );

    // Reset counter on mount
    frameReceivedCountRef.current = 0;

    // CHECKPOINT C - Helper listening to frame events
    console.log("[FRAME] 🔌 Helper subscribed to 'frame' events");
    console.log("[FRAME] 🔌 Message handler registered, waiting for frames...");
    const unsubscribeCameraFrame = collaborationService.onMessage(
      "frame",
      (msg) => {
        console.log("[FRAME] 📨 Frame message received! Processing...", {
          hasImage: !!(msg.image || msg.data),
          imageLength: (msg.image || msg.data || "").length,
          sessionId: msg.session_id,
        });
        // CHECKPOINT C.1 - Helper received frame
        let imageData = msg.image || msg.data;
        const code = normalizeCode(msg.session_id || sessionId || "");
        const room = roomFor(code);
        const ts = msg.timestamp
          ? new Date(msg.timestamp).getTime()
          : Date.now();

        if (imageData) {
          // Ensure data URL format
          if (!imageData.startsWith("data:image")) {
            imageData = `data:image/jpeg;base64,${imageData}`;
          }

          frameReceivedCountRef.current++;
          const currentCount = frameReceivedCountRef.current;

          // Log once per second (throttled)
          if (currentCount === 1 || currentCount % 8 === 0) {
            console.log(
              `[FRAME] received {code: ${code.substring(0, 8)}, bytes: ${imageData.length}, ts: ${ts}}`,
            );
            console.log(
              `[FRAME] framesReceived counter: ${currentCount}, room: ${room}`,
            );
          }

          if (currentCount === 1) {
            console.log(
              "[FRAME] ✅ First camera frame received! Switching to fallback mode immediately.",
            );
          }

          // CRITICAL: Set frame for UI rendering FIRST, then switch to fallback mode
          // This ensures frames are shown immediately
          setCameraFrame(imageData);
          setLastFrameDataUrl(imageData); // Set directly to ensure immediate render

          // If we receive frames but don't have WebRTC track, switch to fallback mode immediately
          if (!hasVideoTrackRef.current) {
            if (!useFallbackModeRef.current) {
              console.log(
                "[FRAME] 🔄 Receiving frames but no WebRTC track, switching to fallback mode immediately",
              );
              setUseFallbackMode(true);
              useFallbackModeRef.current = true;
              setConnectionState("fallback_active");
              connectionStateRef.current = "fallback_active";
            }
            // Clear WebRTC timeout if set
            if (fallbackTimeoutRef.current) {
              clearTimeout(fallbackTimeoutRef.current);
              fallbackTimeoutRef.current = null;
            }
          }
        } else {
          console.warn(
            "[FRAME] ⚠️ Frame message received but no image data:",
            msg,
          );
        }
      },
    );

    // Log frame stats every second - CHECKPOINT C.3
    // Clear any existing interval first
    if (frameStatsIntervalRef.current) {
      clearInterval(frameStatsIntervalRef.current);
    }
    frameStatsIntervalRef.current = setInterval(() => {
      const count = frameReceivedCountRef.current;
      if (count > 0) {
        console.log(
          `[FRAME] 📊 Helper stats (1s): framesReceived=${count}, fps=${count.toFixed(1)}, byteSize=${lastFrameDataUrl?.length || 0}`,
        );
      }
      frameReceivedCountRef.current = 0; // Reset counter
    }, 1000);

    // Also listen for legacy camera_frame messages
    const unsubscribeLegacyFrame = collaborationService.onMessage(
      "camera_frame" as any,
      (msg) => {
        if (msg.data) {
          console.log("[HelperWeb] 📥 Received legacy camera_frame");
          setCameraFrame(msg.data);
        }
      },
    );

    const unsubscribeError = collaborationService.onMessage("error", (msg) => {
      setError(msg.message || "Connection error");
    });

    // WebRTC signaling handlers
    const unsubscribeWebRTCOffer = collaborationService.onMessage(
      "webrtc_offer",
      async (msg) => {
        const code = normalizeCode(msg.session_id || sessionId || "");
        const room = roomFor(code);
        console.log(`[HelperWeb] 📥 Received WebRTC offer (room: ${room})`);
        setConnectionState("webrtc_connecting");
        connectionStateRef.current = "webrtc_connecting";
        webrtcStartTimeRef.current = Date.now();
        if (msg.sdp) {
          await handleWebRTCOffer(msg.sdp as RTCSessionDescriptionInit);
        }
      },
    );

    const unsubscribeWebRTCAnswer = collaborationService.onMessage(
      "webrtc_answer",
      async (msg) => {
        const code = normalizeCode(msg.session_id || sessionId || "");
        const room = roomFor(code);
        console.log(`[HelperWeb] 📥 Received WebRTC answer (room: ${room})`);
        // This shouldn't happen for helper, but log it
      },
    );

    const unsubscribeWebRTCICE = collaborationService.onMessage(
      "webrtc_ice",
      async (msg) => {
        const code = normalizeCode(msg.session_id || sessionId || "");
        const room = roomFor(code);
        console.log(
          `[HelperWeb] 📥 Received WebRTC ICE candidate (room: ${room})`,
        );
        if (peerConnectionRef.current && msg.candidate) {
          try {
            const candidate = new RTCIceCandidate(
              msg.candidate as RTCIceCandidateInit,
            );
            if (peerConnectionRef.current.remoteDescription) {
              await peerConnectionRef.current.addIceCandidate(candidate);
              console.log("[HelperWeb] ✅ Added ICE candidate from user");
            } else {
              // Store for later
              iceCandidatesRef.current.push(candidate);
              console.log(
                "[HelperWeb] ⏳ Storing ICE candidate (waiting for remote description)",
              );
            }
          } catch (error) {
            console.error("[HelperWeb] ❌ Error adding ICE candidate:", error);
          }
        }
      },
    );

    return () => {
      unsubscribeConnected();
      unsubscribeUserConnected();
      unsubscribeUserDisconnected();
      unsubscribeCameraFrame();
      unsubscribeLegacyFrame();
      unsubscribeError();
      unsubscribeWebRTCOffer();
      unsubscribeWebRTCAnswer();
      unsubscribeWebRTCICE();
      if (frameStatsIntervalRef.current) {
        clearInterval(frameStatsIntervalRef.current);
        frameStatsIntervalRef.current = null;
      }
    };
  }, []); // Empty deps - handlers use refs/state setters that don't need deps

  // Use shared normalization function
  const normalizeSessionCode = normalizeCode;

  const handleCheckStatus = async () => {
    const normalizedCode = normalizeSessionCode(sessionId);

    if (!normalizedCode) {
      Alert.alert("Error", "Please enter a session code");
      return;
    }

    if (normalizedCode.length !== 8 || !/^[A-Z0-9]+$/.test(normalizedCode)) {
      Alert.alert(
        "Invalid Code",
        "Session code must be exactly 8 alphanumeric characters.",
      );
      setError("Invalid session code format");
      return;
    }

    try {
      setIsCheckingStatus(true);
      setError(null);

      console.log(
        `[HelperWeb] Checking status for code: "${sessionId}" → normalized: "${normalizedCode}"`,
      );
      const status =
        await collaborationService.getSessionStatus(normalizedCode);
      setSessionStatus({
        user_connected: status.user_connected,
        expires_in: (status as any).expires_in || 3600,
      });

      if (!status.user_connected) {
        Alert.alert(
          "Session Status",
          `Session found but user is not connected yet.\n\nExpires in: ${Math.floor((status as any).expires_in / 60)} minutes`,
        );
      } else {
        Alert.alert("Session Status", "User is connected and ready!");
      }
    } catch (err) {
      console.error("Error checking status:", err);
      const errorMsg =
        err instanceof Error ? err.message : "Failed to check session status";
      setError(errorMsg);

      // Provide helpful error messages
      let alertMessage = errorMsg;
      if (errorMsg.includes("not found")) {
        alertMessage =
          "Session not found. Please check the code and make sure the user has created a session.";
      } else if (errorMsg.includes("expired")) {
        alertMessage =
          "Session expired. Please ask the user to create a new session.";
      } else if (errorMsg.includes("Invalid")) {
        alertMessage =
          "Invalid session code format. Must be 8 alphanumeric characters.";
      }

      Alert.alert("Error", alertMessage);
      setSessionStatus(null);
    } finally {
      setIsCheckingStatus(false);
    }
  };

  const handleJoinSession = async () => {
    const normalizedCode = normalizeSessionCode(sessionId);

    console.log(
      `[HelperWeb] 🚀 handleJoinSession called with code: "${sessionId}" → normalized: "${normalizedCode}"`,
    );

    if (!normalizedCode) {
      Alert.alert("Error", "Please enter a session code");
      return;
    }

    if (normalizedCode.length !== 8 || !/^[A-Z0-9]+$/.test(normalizedCode)) {
      Alert.alert(
        "Invalid Code",
        "Session code must be exactly 8 alphanumeric characters.",
      );
      setError("Invalid session code format");
      return;
    }

    try {
      setIsConnecting(true);
      setError(null);

      const room = roomFor(normalizedCode);
      console.log(
        `[HelperWeb] 📍 Joining session with code: "${sessionId}" → normalized: "${normalizedCode}"`,
      );
      console.log(`[HelperWeb] 📍 Joining room: ${room}`);
      console.log(`[HelperWeb] 📍 API_BASE: ${API_BASE}`);

      // Verify session exists
      console.log(`[HelperWeb] 📍 Checking session status...`);
      const status =
        await collaborationService.getSessionStatus(normalizedCode);
      console.log(`[HelperWeb] 📍 Session status:`, status);
      setSessionStatus({
        user_connected: status.user_connected,
        expires_in: (status as any).expires_in || 3600,
      });

      if (!status.user_connected) {
        Alert.alert(
          "User Not Connected",
          "The user is not connected yet. They need to:\n1. Open 'Ask a Friend'\n2. Enable camera\n\nThe session will connect automatically once they're ready.",
        );
      }

      // Connect as guide
      console.log(
        `[HelperWeb] 📍 Calling collaborationService.connect(${normalizedCode}, "guide")...`,
      );
      await collaborationService.connect(normalizedCode, "guide");
      console.log(
        `[HelperWeb] ✅ collaborationService.connect() completed successfully`,
      );

      // Send helper name after connection
      if (helperName) {
        console.log(`[HelperWeb] 📤 Sending helper name: "${helperName}"`);
        collaborationService.sendMessage("helper_info" as any, {
          helper_name: helperName,
        });
      }
    } catch (err) {
      console.error("[HelperWeb] ❌ Error joining session:", err);
      const errorMsg =
        err instanceof Error ? err.message : "Failed to join session";
      setError(errorMsg);

      // Provide helpful error messages
      let alertMessage = errorMsg;
      if (errorMsg.includes("not found")) {
        alertMessage =
          "Session not found. Please check the code and make sure the user has created a session.";
      } else if (errorMsg.includes("expired")) {
        alertMessage =
          "Session expired. Please ask the user to create a new session.";
      } else if (errorMsg.includes("Invalid")) {
        alertMessage =
          "Invalid session code format. Must be 8 alphanumeric characters.";
      }

      Alert.alert("Error", alertMessage);
      setIsConnecting(false);
    }
  };

  const handleSendGuidance = () => {
    if (!guidanceText.trim() || !userConnected) {
      return;
    }

    collaborationService.sendGuidance(guidanceText.trim());
    setGuidanceText("");

    // Visual feedback
    if (typeof window !== "undefined" && window.speechSynthesis) {
      const utterance = new SpeechSynthesisUtterance("Sent");
      utterance.rate = 1.5;
      window.speechSynthesis.speak(utterance);
    }
  };

  const handleQuickGuidance = (message: string) => {
    if (!userConnected) return;
    collaborationService.sendGuidance(message);
    if (typeof window !== "undefined" && window.speechSynthesis) {
      const utterance = new SpeechSynthesisUtterance("Sent");
      utterance.rate = 1.5;
      window.speechSynthesis.speak(utterance);
    }
  };

  const handleDisconnect = () => {
    // Close WebRTC peer connection
    if (peerConnectionRef.current) {
      console.log("[HelperWeb] 🛑 Closing WebRTC peer connection");
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
      iceCandidatesRef.current = [];
    }
    // Clear remote video
    if (remoteVideoRef.current) {
      remoteVideoRef.current.srcObject = null;
      remoteVideoRef.current.pause();
    }
    // Clear remote audio
    if (remoteAudioRef.current) {
      remoteAudioRef.current.srcObject = null;
      remoteAudioRef.current.pause();
    }
    // Stop local audio track
    if (localAudioTrackRef.current) {
      localAudioTrackRef.current.stop();
      localAudioTrackRef.current = null;
    }
    if (localAudioStream) {
      localAudioStream.getTracks().forEach((track) => track.stop());
      setLocalAudioStream(null);
    }
    collaborationService.disconnect();
    setIsConnected(false);
    setUserConnected(false);
    setCameraFrame(null);
    setHasVideoTrack(false);
    setHasAudioTrack(false);
    setUserReceivedAudio(false);
    hasVideoTrackRef.current = false;
    setUseFallbackMode(false);
    useFallbackModeRef.current = false;
    setWebrtcError(null);
    setSessionId("");
    setMicrophonePermission("prompt");
    setIsMuted(false);
  };

  // Show message if not on web
  if (Platform.OS !== "web") {
    return (
      <View style={styles.container}>
        <Text style={styles.errorText}>
          This helper interface is only available on web browsers. Please open
          this page in a browser.
        </Text>
      </View>
    );
  }

  // Show authentication UI if not authenticated
  if (!isAuthenticated) {
    return (
      <ScrollView
        style={styles.scrollContainer}
        contentContainerStyle={styles.container}
      >
        <View style={styles.header}>
          <Image
            source={require("../assets/images/company_logo.png")}
            style={styles.companyLogo}
            resizeMode="contain"
          />
          <Text style={styles.headerTitle}>WalkBuddy Helper</Text>
          <Text style={styles.headerSubtitle}>
            Help someone navigate in real-time
          </Text>
        </View>

        <View style={styles.authContainer}>
          {/* Toggle between Login and Signup */}
          <View style={styles.authToggle}>
            <Pressable
              style={[
                styles.authToggleButton,
                !showSignup && styles.authToggleButtonActive,
              ]}
              onPress={() => {
                setShowSignup(false);
                setAuthError(null);
              }}
            >
              <Text
                style={[
                  styles.authToggleText,
                  !showSignup && styles.authToggleTextActive,
                ]}
              >
                Login
              </Text>
            </Pressable>
            <Pressable
              style={[
                styles.authToggleButton,
                showSignup && styles.authToggleButtonActive,
              ]}
              onPress={() => {
                setShowSignup(true);
                setAuthError(null);
              }}
            >
              <Text
                style={[
                  styles.authToggleText,
                  showSignup && styles.authToggleTextActive,
                ]}
              >
                Sign Up
              </Text>
            </Pressable>
          </View>

          {/* Error Message */}
          {authError && (
            <View style={styles.errorContainer}>
              <Text style={styles.errorText}>{authError}</Text>
              {authError.includes("already exists") && (
                <Pressable
                  style={styles.switchToLoginButton}
                  onPress={() => {
                    setShowSignup(false);
                    setAuthError(null);
                    // Pre-fill email if available
                    if (signupData.email) {
                      setLoginData({ ...loginData, email: signupData.email });
                    }
                  }}
                >
                  <Text style={styles.switchToLoginButtonText}>
                    Go to Login →
                  </Text>
                </Pressable>
              )}
            </View>
          )}

          {/* Login Form */}
          {!showSignup ? (
            <View style={styles.authForm}>
              <Text style={styles.authLabel}>Email</Text>
              <TextInput
                style={styles.authInput}
                value={loginData.email}
                onChangeText={(text) =>
                  setLoginData({ ...loginData, email: text })
                }
                placeholder="Enter your email"
                placeholderTextColor="#888"
                keyboardType="email-address"
                autoCapitalize="none"
                editable={!isLoadingAuth}
              />

              <Text style={styles.authLabel}>Password</Text>
              <TextInput
                style={styles.authInput}
                value={loginData.password}
                onChangeText={(text) =>
                  setLoginData({ ...loginData, password: text })
                }
                placeholder="Enter your password"
                placeholderTextColor="#888"
                secureTextEntry
                editable={!isLoadingAuth}
              />

              <Pressable
                style={[
                  styles.authSubmitButton,
                  isLoadingAuth && styles.authSubmitButtonDisabled,
                ]}
                onPress={handleLogin}
                disabled={isLoadingAuth}
              >
                {isLoadingAuth ? (
                  <ActivityIndicator color="#1B263B" />
                ) : (
                  <Text style={styles.authSubmitButtonText}>Login</Text>
                )}
              </Pressable>
            </View>
          ) : (
            /* Signup Form */
            <View style={styles.authForm}>
              <Text style={styles.authLabel}>Name *</Text>
              <TextInput
                style={styles.authInput}
                value={signupData.name}
                onChangeText={(text) =>
                  setSignupData({ ...signupData, name: text })
                }
                placeholder="Enter your full name"
                placeholderTextColor="#888"
                editable={!isLoadingAuth}
              />

              <Text style={styles.authLabel}>Age</Text>
              <TextInput
                style={styles.authInput}
                value={signupData.age}
                onChangeText={(text) =>
                  setSignupData({
                    ...signupData,
                    age: text.replace(/[^0-9]/g, ""),
                  })
                }
                placeholder="Enter your age"
                placeholderTextColor="#888"
                keyboardType="numeric"
                editable={!isLoadingAuth}
              />

              <Text style={styles.authLabel}>Email *</Text>
              <TextInput
                style={styles.authInput}
                value={signupData.email}
                onChangeText={(text) =>
                  setSignupData({ ...signupData, email: text })
                }
                placeholder="Enter your email"
                placeholderTextColor="#888"
                keyboardType="email-address"
                autoCapitalize="none"
                editable={!isLoadingAuth}
              />

              <Text style={styles.authLabel}>Phone Number</Text>
              <TextInput
                style={styles.authInput}
                value={signupData.phone}
                onChangeText={(text) =>
                  setSignupData({ ...signupData, phone: text })
                }
                placeholder="Enter your phone number"
                placeholderTextColor="#888"
                keyboardType="phone-pad"
                editable={!isLoadingAuth}
              />

              <Text style={styles.authLabel}>Address</Text>
              <TextInput
                style={[styles.authInput, styles.authTextArea]}
                value={signupData.address}
                onChangeText={(text) =>
                  setSignupData({ ...signupData, address: text })
                }
                placeholder="Enter your address"
                placeholderTextColor="#888"
                multiline
                numberOfLines={2}
                editable={!isLoadingAuth}
              />

              <Text style={styles.authLabel}>Emergency Contact Name</Text>
              <TextInput
                style={styles.authInput}
                value={signupData.emergency_contact_name}
                onChangeText={(text) =>
                  setSignupData({ ...signupData, emergency_contact_name: text })
                }
                placeholder="Emergency contact name"
                placeholderTextColor="#888"
                editable={!isLoadingAuth}
              />

              <Text style={styles.authLabel}>Emergency Contact Phone</Text>
              <TextInput
                style={styles.authInput}
                value={signupData.emergency_contact_phone}
                onChangeText={(text) =>
                  setSignupData({
                    ...signupData,
                    emergency_contact_phone: text,
                  })
                }
                placeholder="Emergency contact phone"
                placeholderTextColor="#888"
                keyboardType="phone-pad"
                editable={!isLoadingAuth}
              />

              <Text style={styles.authLabel}>Experience Level</Text>
              <TextInput
                style={styles.authInput}
                value={signupData.experience_level}
                onChangeText={(text) =>
                  setSignupData({ ...signupData, experience_level: text })
                }
                placeholder="e.g., Beginner, Intermediate, Expert"
                placeholderTextColor="#888"
                editable={!isLoadingAuth}
              />

              <Text style={styles.authLabel}>Password *</Text>
              <TextInput
                style={styles.authInput}
                value={signupData.password}
                onChangeText={(text) => {
                  setSignupData({ ...signupData, password: text });
                  // Clear error when user starts typing if it was a password error
                  if (
                    authError &&
                    authError.includes("Password requirements")
                  ) {
                    setAuthError(null);
                  }
                }}
                placeholder="Enter password (min 8 chars: A-Z, a-z, 0-9, special)"
                placeholderTextColor="#888"
                secureTextEntry
                editable={!isLoadingAuth}
              />
              <Text style={styles.passwordHint}>
                Password must be at least 8 characters and include: uppercase,
                lowercase, number, and special character
              </Text>

              <Text style={styles.authLabel}>Confirm Password *</Text>
              <TextInput
                style={styles.authInput}
                value={signupData.confirmPassword}
                onChangeText={(text) =>
                  setSignupData({ ...signupData, confirmPassword: text })
                }
                placeholder="Confirm your password"
                placeholderTextColor="#888"
                secureTextEntry
                editable={!isLoadingAuth}
              />

              {/* Terms and Conditions Checkbox */}
              <View style={styles.termsContainer}>
                <Pressable
                  style={styles.checkboxContainer}
                  onPress={() => setTermsAccepted(!termsAccepted)}
                  disabled={isLoadingAuth}
                >
                  <View
                    style={[
                      styles.checkbox,
                      termsAccepted && styles.checkboxChecked,
                    ]}
                  >
                    {termsAccepted && (
                      <Ionicons name="checkmark" size={16} color="#1B263B" />
                    )}
                  </View>
                  <Text style={styles.termsText}>
                    I accept the{" "}
                    <Text
                      style={styles.termsLink}
                      onPress={(e) => {
                        e.stopPropagation();
                        // Show terms in a simple alert for now (since settings modal requires auth)
                        Alert.alert(
                          "Terms and Conditions",
                          "By using WalkBuddy Helper, you agree to:\n\n" +
                            "• Use the service responsibly and in accordance with applicable laws\n" +
                            "• Provide accurate information\n" +
                            "• Maintain the confidentiality of your account\n" +
                            "• Respect the privacy of users you assist\n" +
                            "• Not use the service for any illegal purposes\n\n" +
                            "WalkBuddy Helper is provided 'as is' without warranties. " +
                            "We are not liable for any damages arising from the use of our service.",
                          [{ text: "OK" }],
                        );
                      }}
                    >
                      Terms and Conditions
                    </Text>
                  </Text>
                </Pressable>
              </View>

              <Pressable
                style={[
                  styles.authSubmitButton,
                  (isLoadingAuth || !termsAccepted) &&
                    styles.authSubmitButtonDisabled,
                ]}
                onPress={handleSignup}
                disabled={isLoadingAuth || !termsAccepted}
              >
                {isLoadingAuth ? (
                  <ActivityIndicator color="#1B263B" />
                ) : (
                  <Text style={styles.authSubmitButtonText}>Sign Up</Text>
                )}
              </Pressable>
            </View>
          )}
        </View>
      </ScrollView>
    );
  }

  // Main interface (shown after authentication)
  return (
    <ScrollView
      style={styles.scrollContainer}
      contentContainerStyle={styles.container}
    >
      <View style={styles.header}>
        {/* Settings Button - Top Right */}
        {isAuthenticated && (
          <Pressable
            style={styles.settingsButton}
            onPress={() => {
              setShowSettings(true);
              setSettingsSection(null);
              fetchHelperData();
            }}
          >
            <Ionicons name="settings-outline" size={24} color="#F9A826" />
          </Pressable>
        )}

        <Image
          source={require("../assets/images/company_logo.png")}
          style={styles.companyLogo}
          resizeMode="contain"
        />
        <Text style={styles.headerTitle}>WalkBuddy Helper</Text>
        <Text style={styles.headerSubtitle}>
          Help someone navigate in real-time
        </Text>
        <Text style={styles.headerDescription}>
          No app download required. Just enter the session code to start
          helping.
        </Text>
        {/* Logout Button */}
        <Pressable style={styles.logoutButton} onPress={handleLogout}>
          <Ionicons name="log-out-outline" size={16} color="#FF6B6B" />
          <Text style={styles.logoutButtonText}>Logout</Text>
        </Pressable>
      </View>

      {!isConnected ? (
        <View style={styles.joinContainer}>
          <Text style={styles.title}>Enter Session Code</Text>
          <Text style={styles.subtitle}>
            Ask the person needing help for their 8-character session code
          </Text>

          <TextInput
            style={styles.input}
            value={sessionId}
            onChangeText={(text) => {
              // Auto-uppercase and limit to 8 characters
              const normalized = text.trim().toUpperCase().slice(0, 8);
              setSessionId(normalized);
            }}
            placeholder="Enter 8-character code"
            autoCapitalize="characters"
            maxLength={8}
            placeholder="Enter session code (e.g., ABC12345)"
            placeholderTextColor="#888"
            autoCapitalize="characters"
            maxLength={8}
            editable={!isConnecting}
          />

          {/* Session Status Display */}
          {sessionStatus && (
            <View style={styles.statusContainer}>
              <View style={styles.statusRow}>
                <View
                  style={[
                    styles.statusDot,
                    sessionStatus.user_connected && styles.statusDotActive,
                  ]}
                />
                <Text style={styles.statusText}>
                  {sessionStatus.user_connected
                    ? "User Connected"
                    : "Waiting for user"}
                </Text>
              </View>
              <Text style={styles.statusSubtext}>
                Expires in: {Math.floor(sessionStatus.expires_in / 60)} minutes
              </Text>
            </View>
          )}

          {error && (
            <View style={styles.errorContainer}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          <View style={styles.buttonRow}>
            <Pressable
              style={[
                styles.secondaryButton,
                isCheckingStatus && styles.secondaryButtonDisabled,
              ]}
              onPress={handleCheckStatus}
              disabled={isCheckingStatus || !sessionId.trim()}
            >
              {isCheckingStatus ? (
                <ActivityIndicator size="small" color="#1B263B" />
              ) : (
                <Text style={styles.secondaryButtonText}>Check Status</Text>
              )}
            </Pressable>

            <Pressable
              style={[
                styles.primaryButton,
                isConnecting && styles.primaryButtonDisabled,
              ]}
              onPress={handleJoinSession}
              disabled={isConnecting || !sessionId.trim()}
            >
              {isConnecting ? (
                <ActivityIndicator size="small" color="#FFF" />
              ) : (
                <Text style={styles.primaryButtonText}>Join Session</Text>
              )}
            </Pressable>
          </View>
        </View>
      ) : (
        <View style={styles.helperContainer}>
          {/* Status Bar */}
          <View style={styles.statusBar}>
            <View
              style={[
                styles.statusDot,
                userConnected && styles.statusDotConnected,
              ]}
            />
            <Text style={styles.statusText}>
              {userConnected &&
              (hasVideoTrack || useFallbackMode || lastFrameDataUrl)
                ? useFallbackMode || lastFrameDataUrl
                  ? "Viewing user's camera (Fallback mode)"
                  : "Viewing user's camera"
                : userConnected
                  ? "Waiting for camera feed..."
                  : "Waiting for user to connect..."}
            </Text>
            {webrtcError && !useFallbackMode && (
              <Text style={styles.errorText}>{webrtcError}</Text>
            )}
            {useFallbackMode && (
              <Text style={styles.statusSubtext}>
                Using reliable frame streaming
              </Text>
            )}
            {/* Audio Status */}
            {userReceivedAudio && (
              <View style={styles.audioStatus}>
                <Ionicons name="volume-high" size={16} color="#4CAF50" />
                <Text style={styles.audioStatusText}>
                  Receiving audio from user
                </Text>
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

          {/* Camera Feed Display */}
          <View style={styles.cameraDisplay}>
            {hasVideoTrack && !useFallbackMode && !lastFrameDataUrl ? (
              <>
                {/* WebRTC video stream - only show if we have track AND no fallback frames */}
                {Platform.OS === "web" && (
                  <>
                    <video
                      ref={remoteVideoRef}
                      autoPlay
                      playsInline
                      muted
                      style={{
                        width: "100%",
                        height: "100%",
                        objectFit: "cover",
                        borderRadius: 12,
                        backgroundColor: "#000",
                      }}
                    />
                    {/* Audio element for receiving user's audio */}
                    <audio
                      ref={remoteAudioRef}
                      autoPlay
                      playsInline
                      volume={1.0}
                      style={{ display: "none" }}
                      onLoadedMetadata={() => {
                        console.log(
                          "[HelperWeb] ✅ Audio element metadata loaded",
                        );
                        if (remoteAudioRef.current) {
                          remoteAudioRef.current.volume = 1.0;
                          remoteAudioRef.current.muted = false;
                        }
                      }}
                      onCanPlay={() => {
                        console.log("[HelperWeb] ✅ Audio element can play");
                        if (
                          remoteAudioRef.current &&
                          remoteAudioRef.current.paused
                        ) {
                          remoteAudioRef.current.play().catch((err) => {
                            console.warn(
                              "[HelperWeb] ⚠️ Auto-play prevented, user interaction required:",
                              err,
                            );
                          });
                        }
                      }}
                      onError={(e) => {
                        console.error("[HelperWeb] ❌ Audio element error:", e);
                      }}
                    />
                  </>
                )}
              </>
            ) : lastFrameDataUrl ? (
              <>
                {/* Fallback frame streaming - CHECKPOINT D - Show frames immediately when available */}
                {Platform.OS === "web" ? (
                  <img
                    key={`frame-${Date.now()}`} // Force re-render on every frame update
                    src={lastFrameDataUrl}
                    alt="User camera feed"
                    onLoad={() => {
                      console.log(
                        "[FRAME] CHECKPOINT D: ✅ Frame image loaded in UI (img src set, placeholder hidden)",
                      );
                      console.log("[FRAME] CHECKPOINT D: Image dimensions:", {
                        naturalWidth: (
                          document.querySelector(
                            'img[alt="User camera feed"]',
                          ) as HTMLImageElement
                        )?.naturalWidth,
                        naturalHeight: (
                          document.querySelector(
                            'img[alt="User camera feed"]',
                          ) as HTMLImageElement
                        )?.naturalHeight,
                      });
                    }}
                    onError={(e) => {
                      console.error(
                        "[FRAME] CHECKPOINT D: ❌ Frame image failed to load:",
                        e,
                      );
                      console.error(
                        "[FRAME] CHECKPOINT D: Failed image src length:",
                        lastFrameDataUrl.length,
                      );
                      console.error(
                        "[FRAME] CHECKPOINT D: Failed image src preview:",
                        lastFrameDataUrl.substring(0, 100),
                      );
                    }}
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                      borderRadius: 12,
                      backgroundColor: "#000",
                      display: "block",
                    }}
                  />
                ) : (
                  <Image
                    key={`frame-${Date.now()}`}
                    source={{ uri: lastFrameDataUrl }}
                    style={{
                      width: "100%",
                      height: "100%",
                    }}
                    resizeMode="cover"
                    onLoad={() => {
                      console.log(
                        "[FRAME] CHECKPOINT D: ✅ Frame image loaded in UI (Image component)",
                      );
                    }}
                    onError={(e) => {
                      console.error(
                        "[FRAME] CHECKPOINT D: ❌ Frame image failed to load:",
                        e,
                      );
                    }}
                  />
                )}
              </>
            ) : (
              <View style={styles.cameraPlaceholder}>
                <Ionicons name="camera-outline" size={64} color="#666" />
                <Text style={styles.cameraPlaceholderText}>
                  {userConnected
                    ? webrtcError || "Waiting for camera feed..."
                    : "No user connected"}
                </Text>
                {userConnected && !webrtcError && (
                  <Text style={styles.cameraPlaceholderHint}>
                    Establishing video connection...
                  </Text>
                )}
              </View>
            )}
          </View>

          {/* Mute/Unmute Button - Always visible when user is connected */}
          {userConnected && (
            <View style={styles.audioControls}>
              {hasAudioTrack ? (
                <Pressable
                  onPress={() => {
                    if (localAudioTrackRef.current) {
                      const newMutedState = !isMuted;
                      localAudioTrackRef.current.enabled = newMutedState;
                      setIsMuted(newMutedState);
                      console.log(
                        "[HelperWeb] 🎤 Microphone",
                        newMutedState ? "unmuted" : "muted",
                      );
                    }
                  }}
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
                <Pressable
                  onPress={async () => {
                    try {
                      console.log(
                        "[HelperWeb] 🎤 Manually requesting microphone access...",
                      );
                      const audioStream =
                        await navigator.mediaDevices.getUserMedia({
                          audio: {
                            echoCancellation: true,
                            noiseSuppression: true,
                            autoGainControl: true,
                          },
                        });

                      const audioTracks = audioStream.getAudioTracks();
                      if (audioTracks.length > 0) {
                        localAudioTrackRef.current = audioTracks[0];
                        setMicrophonePermission("granted");
                        setHasAudioTrack(true);
                        setLocalAudioStream(audioStream);

                        // Add audio track to peer connection if it exists
                        if (peerConnectionRef.current) {
                          audioTracks.forEach((track) => {
                            peerConnectionRef.current!.addTrack(
                              track,
                              audioStream,
                            );
                            console.log(
                              "[HelperWeb] ✅ Added audio track:",
                              track.label,
                            );
                          });
                        }
                        console.log("[HelperWeb] ✅ Microphone access granted");
                      }
                    } catch (err: any) {
                      console.error(
                        "[HelperWeb] ❌ Microphone access failed:",
                        err,
                      );
                      Alert.alert(
                        "Microphone Access",
                        "Failed to access microphone. Please check your browser permissions.",
                      );
                    }
                  }}
                  style={styles.requestMicButton}
                >
                  <Ionicons name="mic" size={20} color="#FFFFFF" />
                  <Text style={styles.requestMicButtonText}>
                    Enable Microphone
                  </Text>
                </Pressable>
              ) : (
                <Pressable
                  onPress={async () => {
                    try {
                      console.log(
                        "[HelperWeb] 🎤 Requesting microphone access...",
                      );
                      setMicrophonePermission("prompt");
                      const audioStream =
                        await navigator.mediaDevices.getUserMedia({
                          audio: {
                            echoCancellation: true,
                            noiseSuppression: true,
                            autoGainControl: true,
                          },
                        });

                      const audioTracks = audioStream.getAudioTracks();
                      if (audioTracks.length > 0) {
                        localAudioTrackRef.current = audioTracks[0];
                        setMicrophonePermission("granted");
                        setHasAudioTrack(true);
                        setLocalAudioStream(audioStream);

                        // Add audio track to peer connection if it exists
                        if (peerConnectionRef.current) {
                          audioTracks.forEach((track) => {
                            peerConnectionRef.current!.addTrack(
                              track,
                              audioStream,
                            );
                            console.log(
                              "[HelperWeb] ✅ Added audio track:",
                              track.label,
                            );
                          });
                        }
                        console.log("[HelperWeb] ✅ Microphone access granted");
                      }
                    } catch (err: any) {
                      console.error(
                        "[HelperWeb] ❌ Microphone access failed:",
                        err,
                      );
                      setMicrophonePermission("denied");
                      Alert.alert(
                        "Microphone Access",
                        "Microphone access was denied. Please allow microphone access in your browser settings.",
                      );
                    }
                  }}
                  style={styles.requestMicButton}
                >
                  <Ionicons name="mic" size={20} color="#FFFFFF" />
                  <Text style={styles.requestMicButtonText}>
                    Enable Microphone
                  </Text>
                </Pressable>
              )}
            </View>
          )}

          {/* Guidance Input */}
          <View style={styles.guidanceContainer}>
            <Text style={styles.guidanceLabel}>Send Guidance</Text>
            <View style={styles.guidanceInputRow}>
              <TextInput
                style={styles.guidanceInput}
                value={guidanceText}
                onChangeText={setGuidanceText}
                placeholder="Type guidance message..."
                placeholderTextColor="#888"
                multiline
                editable={userConnected}
              />
              <Pressable
                style={[
                  styles.sendButton,
                  (!userConnected || !guidanceText.trim()) &&
                    styles.sendButtonDisabled,
                ]}
                onPress={handleSendGuidance}
                disabled={!userConnected || !guidanceText.trim()}
              >
                <Text style={styles.sendButtonText}>Send</Text>
              </Pressable>
            </View>
          </View>

          {/* Quick Guidance Buttons */}
          {userConnected && (
            <View style={styles.quickGuidanceContainer}>
              <Text style={styles.quickGuidanceLabel}>Quick Guidance</Text>
              <View style={styles.quickGuidanceButtons}>
                {[
                  "Turn left",
                  "Turn right",
                  "Go straight",
                  "Stop",
                  "You're on the right path",
                ].map((msg) => (
                  <Pressable
                    key={msg}
                    style={styles.quickGuidanceButton}
                    onPress={() => handleQuickGuidance(msg)}
                    disabled={!userConnected}
                  >
                    <Text style={styles.quickGuidanceButtonText}>{msg}</Text>
                  </Pressable>
                ))}
              </View>
            </View>
          )}

          {/* Disconnect Button */}
          <Pressable style={styles.disconnectButton} onPress={handleDisconnect}>
            <Text style={styles.disconnectButtonText}>Disconnect</Text>
          </Pressable>
        </View>
      )}

      {/* Settings Modal */}
      {showSettings && (
        <View style={styles.modalOverlay}>
          <View style={styles.modalContainer}>
            {/* Modal Header */}
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>
                {settingsSection === "account"
                  ? "Account"
                  : settingsSection === "privacy"
                    ? "Privacy & Policy"
                    : settingsSection === "help"
                      ? "Help Center"
                      : settingsSection === "about"
                        ? "About"
                        : "Settings"}
              </Text>
              <Pressable
                onPress={() => {
                  setShowSettings(false);
                  setSettingsSection(null);
                }}
                style={styles.modalCloseButton}
              >
                <Ionicons name="close" size={24} color="#FFF" />
              </Pressable>
            </View>

            {/* Settings Menu */}
            {!settingsSection && (
              <View style={styles.settingsMenu}>
                <Pressable
                  style={styles.settingsMenuItem}
                  onPress={() => setSettingsSection("account")}
                >
                  <Ionicons name="person-outline" size={24} color="#F9A826" />
                  <Text style={styles.settingsMenuItemText}>Account</Text>
                  <Ionicons name="chevron-forward" size={20} color="#AAA" />
                </Pressable>
                <Pressable
                  style={styles.settingsMenuItem}
                  onPress={() => setSettingsSection("privacy")}
                >
                  <Ionicons
                    name="lock-closed-outline"
                    size={24}
                    color="#F9A826"
                  />
                  <Text style={styles.settingsMenuItemText}>
                    Privacy & Policy
                  </Text>
                  <Ionicons name="chevron-forward" size={20} color="#AAA" />
                </Pressable>
                <Pressable
                  style={styles.settingsMenuItem}
                  onPress={() => setSettingsSection("help")}
                >
                  <Ionicons
                    name="help-circle-outline"
                    size={24}
                    color="#F9A826"
                  />
                  <Text style={styles.settingsMenuItemText}>Help Center</Text>
                  <Ionicons name="chevron-forward" size={20} color="#AAA" />
                </Pressable>
                <Pressable
                  style={styles.settingsMenuItem}
                  onPress={() => setSettingsSection("about")}
                >
                  <Ionicons
                    name="information-circle-outline"
                    size={24}
                    color="#F9A826"
                  />
                  <Text style={styles.settingsMenuItemText}>About</Text>
                  <Ionicons name="chevron-forward" size={20} color="#AAA" />
                </Pressable>
              </View>
            )}

            {/* Account Section */}
            {settingsSection === "account" && (
              <ScrollView style={styles.settingsContent}>
                {helperData ? (
                  <>
                    <View style={styles.accountSection}>
                      <Text style={styles.accountLabel}>Name</Text>
                      <Text style={styles.accountValue}>
                        {helperData.name || "N/A"}
                      </Text>
                    </View>
                    <View style={styles.accountSection}>
                      <Text style={styles.accountLabel}>Age</Text>
                      <Text style={styles.accountValue}>
                        {helperData.age || "N/A"}
                      </Text>
                    </View>
                    <View style={styles.accountSection}>
                      <Text style={styles.accountLabel}>Email</Text>
                      <Text style={styles.accountValue}>
                        {helperData.email || "N/A"}
                      </Text>
                    </View>
                    <View style={styles.accountSection}>
                      <Text style={styles.accountLabel}>Phone Number</Text>
                      <Text style={styles.accountValue}>
                        {helperData.phone || "N/A"}
                      </Text>
                    </View>
                    <View style={styles.accountSection}>
                      <Text style={styles.accountLabel}>Address</Text>
                      <Text style={styles.accountValue}>
                        {helperData.address || "N/A"}
                      </Text>
                    </View>
                    <View style={styles.accountSection}>
                      <Text style={styles.accountLabel}>
                        Emergency Contact Name
                      </Text>
                      <Text style={styles.accountValue}>
                        {helperData.emergency_contact_name || "N/A"}
                      </Text>
                    </View>
                    <View style={styles.accountSection}>
                      <Text style={styles.accountLabel}>
                        Emergency Contact Phone
                      </Text>
                      <Text style={styles.accountValue}>
                        {helperData.emergency_contact_phone || "N/A"}
                      </Text>
                    </View>
                    <View style={styles.accountSection}>
                      <Text style={styles.accountLabel}>Experience Level</Text>
                      <Text style={styles.accountValue}>
                        {helperData.experience_level || "N/A"}
                      </Text>
                    </View>
                    <View style={styles.accountSection}>
                      <Text style={styles.accountLabel}>Account Created</Text>
                      <Text style={styles.accountValue}>
                        {helperData.created_at
                          ? new Date(helperData.created_at).toLocaleDateString()
                          : "N/A"}
                      </Text>
                    </View>
                    <View style={styles.accountSection}>
                      <Text style={styles.accountLabel}>Last Login</Text>
                      <Text style={styles.accountValue}>
                        {helperData.last_login
                          ? new Date(helperData.last_login).toLocaleDateString()
                          : "N/A"}
                      </Text>
                    </View>
                    <Pressable
                      style={styles.deleteAccountButton}
                      onPress={handleDeleteAccount}
                      disabled={isDeletingAccount}
                    >
                      {isDeletingAccount ? (
                        <ActivityIndicator color="#FFF" />
                      ) : (
                        <>
                          <Ionicons
                            name="trash-outline"
                            size={20}
                            color="#FFF"
                          />
                          <Text style={styles.deleteAccountButtonText}>
                            Delete Account
                          </Text>
                        </>
                      )}
                    </Pressable>
                  </>
                ) : (
                  <ActivityIndicator size="large" color="#F9A826" />
                )}
              </ScrollView>
            )}

            {/* Privacy & Policy Section */}
            {settingsSection === "privacy" && (
              <ScrollView style={styles.settingsContent}>
                <Text style={styles.sectionTitle}>Privacy & Policy</Text>
                <Text style={styles.sectionText}>
                  WalkBuddy Helper is committed to protecting your privacy. This
                  Privacy Policy explains how we collect, use, and safeguard
                  your personal information.
                </Text>
                <Text style={styles.sectionSubtitle}>
                  Information We Collect
                </Text>
                <Text style={styles.sectionText}>
                  We collect information you provide during registration,
                  including your name, email, phone number, address, and
                  emergency contact details.
                </Text>
                <Text style={styles.sectionSubtitle}>
                  How We Use Your Information
                </Text>
                <Text style={styles.sectionText}>
                  Your information is used to facilitate the assistance service,
                  connect helpers with users, and ensure the safety and security
                  of our platform.
                </Text>
                <Text style={styles.sectionSubtitle}>Data Security</Text>
                <Text style={styles.sectionText}>
                  We implement appropriate security measures to protect your
                  personal information. However, no method of transmission over
                  the internet is 100% secure.
                </Text>
                <Text style={styles.sectionSubtitle}>Your Rights</Text>
                <Text style={styles.sectionText}>
                  You have the right to access, update, or delete your personal
                  information at any time through your account settings.
                </Text>
              </ScrollView>
            )}

            {/* Help Center Section */}
            {settingsSection === "help" && (
              <ScrollView style={styles.settingsContent}>
                <Text style={styles.sectionTitle}>Help Center</Text>
                <Text style={styles.sectionText}>
                  Need assistance? We're here to help! Contact our support team
                  for any questions or issues you may have.
                </Text>

                <Text style={styles.sectionSubtitle}>Contact Support</Text>

                {/* Email Support */}
                <Pressable
                  style={styles.helpContactItem}
                  onPress={() => {
                    const email = "support@walkbuddy.com";
                    const subject = encodeURIComponent(
                      "WalkBuddy Helper - Support Request",
                    );
                    const body = encodeURIComponent(
                      `Hello WalkBuddy Support Team,\n\n` +
                        `I need assistance with:\n\n` +
                        `[Please describe your issue here]\n\n` +
                        `Helper Name: ${helperName || "N/A"}\n` +
                        `Email: ${helperData?.email || "N/A"}\n\n` +
                        `Thank you!`,
                    );
                    const mailtoLink = `mailto:${email}?subject=${subject}&body=${body}`;
                    if (
                      Platform.OS === "web" &&
                      typeof window !== "undefined"
                    ) {
                      window.location.href = mailtoLink;
                    } else {
                      Linking.openURL(mailtoLink);
                    }
                  }}
                >
                  <Ionicons name="mail-outline" size={24} color="#F9A826" />
                  <View style={styles.helpContactTextContainer}>
                    <Text style={styles.helpContactTitle}>Email Support</Text>
                    <Text style={styles.helpContactSubtitle}>
                      support@walkbuddy.com
                    </Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color="#AAA" />
                </Pressable>

                {/* Send Message Form */}
                <Text style={styles.sectionSubtitle}>Send Us a Message</Text>
                <TextInput
                  style={[styles.authInput, styles.supportMessageInput]}
                  value={supportMessage}
                  onChangeText={setSupportMessage}
                  placeholder="Describe your issue or question..."
                  placeholderTextColor="#888"
                  multiline
                  numberOfLines={6}
                  textAlignVertical="top"
                />
                <Pressable
                  style={[
                    styles.supportSendButton,
                    (!supportMessage.trim() || isSendingSupport) &&
                      styles.supportSendButtonDisabled,
                  ]}
                  onPress={async () => {
                    if (!supportMessage.trim()) return;

                    setIsSendingSupport(true);
                    try {
                      const email = "support@walkbuddy.com";
                      const subject = encodeURIComponent(
                        "WalkBuddy Helper - Support Request",
                      );
                      const body = encodeURIComponent(
                        `Hello WalkBuddy Support Team,\n\n` +
                          `${supportMessage}\n\n` +
                          `Helper Name: ${helperName || "N/A"}\n` +
                          `Email: ${helperData?.email || "N/A"}\n` +
                          `Phone: ${helperData?.phone || "N/A"}\n\n` +
                          `Thank you!`,
                      );
                      const mailtoLink = `mailto:${email}?subject=${subject}&body=${body}`;

                      if (
                        Platform.OS === "web" &&
                        typeof window !== "undefined"
                      ) {
                        window.location.href = mailtoLink;
                        setSupportMessage("");
                        if (
                          Platform.OS === "web" &&
                          typeof window !== "undefined"
                        ) {
                          window.alert(
                            "Your message has been prepared. Please send it from your email client.",
                          );
                        } else {
                          Alert.alert(
                            "Success",
                            "Your message has been prepared. Please send it from your email client.",
                          );
                        }
                      } else {
                        await Linking.openURL(mailtoLink);
                        setSupportMessage("");
                        Alert.alert(
                          "Success",
                          "Your message has been prepared. Please send it from your email client.",
                        );
                      }
                    } catch (error) {
                      console.error("[HelperWeb] Error opening email:", error);
                      if (
                        Platform.OS === "web" &&
                        typeof window !== "undefined"
                      ) {
                        window.alert(
                          "Unable to open email client. Please email support@walkbuddy.com directly.",
                        );
                      } else {
                        Alert.alert(
                          "Error",
                          "Unable to open email client. Please email support@walkbuddy.com directly.",
                        );
                      }
                    } finally {
                      setIsSendingSupport(false);
                    }
                  }}
                  disabled={!supportMessage.trim() || isSendingSupport}
                >
                  {isSendingSupport ? (
                    <ActivityIndicator color="#FFF" />
                  ) : (
                    <>
                      <Ionicons name="send-outline" size={20} color="#FFF" />
                      <Text style={styles.supportSendButtonText}>
                        Send Message
                      </Text>
                    </>
                  )}
                </Pressable>

                {/* FAQ Section */}
                <Text style={styles.sectionSubtitle}>
                  Frequently Asked Questions
                </Text>

                <View style={styles.faqItem}>
                  <Text style={styles.faqQuestion}>
                    How do I join a session?
                  </Text>
                  <Text style={styles.faqAnswer}>
                    Enter the 8-character session code provided by the user in
                    the "Enter Session Code" field and click "Join Session".
                  </Text>
                </View>

                <View style={styles.faqItem}>
                  <Text style={styles.faqQuestion}>
                    I can't see the user's camera feed
                  </Text>
                  <Text style={styles.faqAnswer}>
                    Make sure the user has enabled their camera and is
                    connected. Try refreshing the page or ask the user to check
                    their connection.
                  </Text>
                </View>

                <View style={styles.faqItem}>
                  <Text style={styles.faqQuestion}>
                    How do I send guidance to the user?
                  </Text>
                  <Text style={styles.faqAnswer}>
                    Type your guidance message in the "Send Guidance" field and
                    click "Send". The user will hear your message spoken aloud.
                  </Text>
                </View>

                <View style={styles.faqItem}>
                  <Text style={styles.faqQuestion}>
                    Can I use my microphone?
                  </Text>
                  <Text style={styles.faqAnswer}>
                    Yes! Click the "Enable Microphone" button to allow audio
                    communication with the user. Make sure to grant microphone
                    permissions when prompted.
                  </Text>
                </View>

                <View style={styles.faqItem}>
                  <Text style={styles.faqQuestion}>
                    How do I delete my account?
                  </Text>
                  <Text style={styles.faqAnswer}>
                    Go to Settings → Account → Delete Account. This action
                    cannot be undone, so make sure you want to permanently
                    delete your account.
                  </Text>
                </View>
              </ScrollView>
            )}

            {/* About Section */}
            {settingsSection === "about" && (
              <ScrollView style={styles.settingsContent}>
                <Text style={styles.sectionTitle}>About WalkBuddy Helper</Text>
                <Text style={styles.sectionText}>
                  WalkBuddy Helper is a real-time assistance platform designed
                  to help people navigate and receive guidance from trusted
                  helpers.
                </Text>
                <Text style={styles.sectionSubtitle}>Our Mission</Text>
                <Text style={styles.sectionText}>
                  To provide accessible, real-time assistance to those who need
                  help navigating their environment, connecting helpers with
                  users in a safe and secure manner.
                </Text>
                <Text style={styles.sectionSubtitle}>Version</Text>
                <Text style={styles.sectionText}>1.0.0</Text>
                <Text style={styles.sectionSubtitle}>Contact</Text>
                <Text style={styles.sectionText}>
                  For support or inquiries, please contact us through the app or
                  visit our website.
                </Text>
                <Text style={styles.sectionSubtitle}>Developed by</Text>
                <Text style={styles.sectionText}>
                  Mekong Inclusive Ventures
                </Text>
              </ScrollView>
            )}

            {/* Back Button for Sections */}
            {settingsSection && (
              <Pressable
                style={styles.backButton}
                onPress={() => setSettingsSection(null)}
              >
                <Ionicons name="arrow-back" size={20} color="#F9A826" />
                <Text style={styles.backButtonText}>Back to Settings</Text>
              </Pressable>
            )}
          </View>
        </View>
      )}

      {/* Delete Account Confirmation Modal */}
      {showDeleteConfirm && (
        <View style={styles.modalOverlay}>
          <View style={styles.confirmModalContainer}>
            <Text style={styles.confirmModalTitle}>Delete Account</Text>
            <Text style={styles.confirmModalText}>
              Are you sure you want to delete your account? This action cannot
              be undone and all your data will be permanently removed.
            </Text>
            <View style={styles.confirmModalButtons}>
              <Pressable
                style={[
                  styles.confirmModalButton,
                  styles.confirmModalButtonCancel,
                ]}
                onPress={() => setShowDeleteConfirm(false)}
              >
                <Text style={styles.confirmModalButtonCancelText}>Cancel</Text>
              </Pressable>
              <Pressable
                style={[
                  styles.confirmModalButton,
                  styles.confirmModalButtonDelete,
                ]}
                onPress={confirmDeleteAccount}
                disabled={isDeletingAccount}
              >
                {isDeletingAccount ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <Text style={styles.confirmModalButtonDeleteText}>
                    Delete
                  </Text>
                )}
              </Pressable>
            </View>
          </View>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scrollContainer: {
    flex: 1,
    backgroundColor: "#1B263B",
  },
  container: {
    flex: 1,
    backgroundColor: "#1B263B",
    padding: 20,
    minHeight: "100vh",
  },
  header: {
    marginBottom: 32,
    alignItems: "center",
    position: "relative",
  },
  companyLogo: {
    width: 200,
    height: 80,
    marginBottom: 16,
  },
  logoContainer: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: "#2A2A2A",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  headerTitle: {
    color: "#FFF",
    fontSize: 32,
    fontWeight: "700",
    marginBottom: 8,
  },
  headerSubtitle: {
    color: "#F9A826",
    fontSize: 18,
    fontWeight: "600",
    marginBottom: 8,
  },
  headerDescription: {
    color: "#AAA",
    fontSize: 14,
    textAlign: "center",
    marginTop: 8,
  },
  joinContainer: {
    maxWidth: 500,
    width: "100%",
    alignSelf: "center",
  },
  title: {
    color: "#FFF",
    fontSize: 24,
    fontWeight: "700",
    marginBottom: 8,
    textAlign: "center",
  },
  subtitle: {
    color: "#AAA",
    fontSize: 16,
    textAlign: "center",
    marginBottom: 32,
  },
  input: {
    backgroundColor: "#2A2A2A",
    color: "#FFF",
    fontSize: 20,
    fontWeight: "700",
    letterSpacing: 4,
    padding: 16,
    borderRadius: 8,
    textAlign: "center",
    marginBottom: 16,
  },
  errorContainer: {
    backgroundColor: "#3A1F1F",
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
  },
  errorText: {
    color: "#FF6B6B",
    fontSize: 14,
    textAlign: "center",
    marginBottom: 8,
  },
  switchToLoginButton: {
    marginTop: 8,
    paddingVertical: 8,
    paddingHorizontal: 16,
    backgroundColor: "#F9A826",
    borderRadius: 6,
    alignSelf: "center",
  },
  switchToLoginButtonText: {
    color: "#1B263B",
    fontSize: 14,
    fontWeight: "600",
  },
  buttonRow: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 16,
  },
  secondaryButton: {
    flex: 1,
    backgroundColor: "#2A2A2A",
    padding: 16,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "#F9A826",
  },
  secondaryButtonDisabled: {
    opacity: 0.5,
  },
  secondaryButtonText: {
    color: "#F9A826",
    fontSize: 16,
    fontWeight: "600",
  },
  statusContainer: {
    backgroundColor: "#2A2A2A",
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 4,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#666",
    marginRight: 8,
  },
  statusDotActive: {
    backgroundColor: "#4CAF50",
  },
  statusText: {
    color: "#FFF",
    fontSize: 14,
    fontWeight: "600",
  },
  statusSubtext: {
    color: "#AAA",
    fontSize: 12,
    marginTop: 4,
  },
  primaryButton: {
    backgroundColor: "#F9A826",
    paddingVertical: 16,
    paddingHorizontal: 32,
    borderRadius: 12,
    alignItems: "center",
  },
  primaryButtonDisabled: {
    opacity: 0.6,
  },
  primaryButtonText: {
    color: "#1B263B",
    fontSize: 18,
    fontWeight: "700",
  },
  helperContainer: {
    flex: 1,
    maxWidth: 800,
    width: "100%",
    alignSelf: "center",
  },
  statusBar: {
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    backgroundColor: "#2A2A2A",
    borderRadius: 8,
    marginBottom: 16,
  },
  statusDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: "#666",
    marginRight: 12,
  },
  statusDotConnected: {
    backgroundColor: "#4CAF50",
  },
  statusText: {
    color: "#FFF",
    fontSize: 14,
  },
  cameraDisplay: {
    width: "100%",
    aspectRatio: 16 / 9,
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: "#000",
    marginBottom: 16,
  },
  cameraPlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  cameraPlaceholderText: {
    color: "#888",
    fontSize: 16,
    textAlign: "center",
  },
  cameraPlaceholderHint: {
    color: "#666",
    fontSize: 12,
    marginTop: 8,
    textAlign: "center",
    fontStyle: "italic",
  },
  guidanceContainer: {
    backgroundColor: "#2A2A2A",
    padding: 16,
    borderRadius: 8,
    marginBottom: 16,
  },
  guidanceLabel: {
    color: "#FFF",
    fontSize: 14,
    fontWeight: "600",
    marginBottom: 8,
  },
  guidanceInputRow: {
    flexDirection: "row",
    gap: 8,
    alignItems: "flex-end",
  },
  guidanceInput: {
    flex: 1,
    backgroundColor: "#1B263B",
    color: "#FFF",
    padding: 12,
    borderRadius: 8,
    minHeight: 44,
    maxHeight: 100,
  },
  sendButton: {
    backgroundColor: "#F9A826",
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
  },
  sendButtonDisabled: {
    backgroundColor: "#666",
    opacity: 0.5,
  },
  sendButtonText: {
    color: "#FFF",
    fontWeight: "600",
  },
  quickGuidanceContainer: {
    marginBottom: 16,
  },
  quickGuidanceLabel: {
    color: "#AAA",
    fontSize: 12,
    marginBottom: 8,
  },
  quickGuidanceButtons: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  quickGuidanceButton: {
    backgroundColor: "#2A2A2A",
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#F9A826",
  },
  quickGuidanceButtonText: {
    color: "#F9A826",
    fontSize: 12,
  },
  disconnectButton: {
    backgroundColor: "#3A1F1F",
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#FF6B6B",
    alignItems: "center",
  },
  disconnectButtonText: {
    color: "#FF6B6B",
    fontSize: 16,
    fontWeight: "600",
  },
  audioControls: {
    marginTop: 16,
    marginBottom: 16,
    alignItems: "center",
    justifyContent: "center",
    width: "100%",
    paddingVertical: 8,
  },
  muteButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
    gap: 8,
    minWidth: 140,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
    elevation: 5,
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
  requestMicButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F9A826",
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
    gap: 8,
    minWidth: 180,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
    elevation: 5,
  },
  requestMicButtonText: {
    color: "#1B263B",
    fontSize: 14,
    fontWeight: "600",
  },
  audioStatus: {
    flexDirection: "row",
    alignItems: "center",
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
  footer: {
    marginTop: 32,
    padding: 16,
    backgroundColor: "#2A2A2A",
    borderRadius: 8,
    alignItems: "center",
  },
  footerText: {
    color: "#AAA",
    fontSize: 12,
    textAlign: "center",
    marginBottom: 4,
  },
  // Authentication styles
  authContainer: {
    maxWidth: 500,
    width: "100%",
    alignSelf: "center",
    backgroundColor: "#2A2A2A",
    borderRadius: 12,
    padding: 24,
    marginTop: 32,
  },
  authToggle: {
    flexDirection: "row",
    marginBottom: 24,
    backgroundColor: "#1B263B",
    borderRadius: 8,
    padding: 4,
  },
  authToggleButton: {
    flex: 1,
    paddingVertical: 12,
    alignItems: "center",
    borderRadius: 6,
  },
  authToggleButtonActive: {
    backgroundColor: "#F9A826",
  },
  authToggleText: {
    color: "#AAA",
    fontSize: 16,
    fontWeight: "600",
  },
  authToggleTextActive: {
    color: "#1B263B",
  },
  authForm: {
    gap: 16,
  },
  authLabel: {
    color: "#FFF",
    fontSize: 14,
    fontWeight: "600",
    marginBottom: 4,
  },
  authInput: {
    backgroundColor: "#1B263B",
    color: "#FFF",
    fontSize: 16,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#3A3A3A",
  },
  authTextArea: {
    minHeight: 60,
    textAlignVertical: "top",
  },
  passwordHint: {
    color: "#888",
    fontSize: 11,
    marginTop: 4,
    marginBottom: 8,
    lineHeight: 14,
  },
  authSubmitButton: {
    backgroundColor: "#F9A826",
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: "center",
    marginTop: 8,
  },
  authSubmitButtonDisabled: {
    opacity: 0.6,
  },
  authSubmitButtonText: {
    color: "#1B263B",
    fontSize: 18,
    fontWeight: "700",
  },
  logoutButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginTop: 16,
    paddingVertical: 8,
    paddingHorizontal: 16,
    backgroundColor: "#3A1F1F",
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#FF6B6B",
  },
  logoutButtonText: {
    color: "#FF6B6B",
    fontSize: 14,
    fontWeight: "600",
  },
  // Settings styles
  settingsButton: {
    position: "absolute",
    top: 20,
    right: 20,
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#2A2A2A",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 10,
  },
  modalOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0, 0, 0, 0.8)",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },
  modalContainer: {
    width: "90%",
    maxWidth: 600,
    maxHeight: "90%",
    backgroundColor: "#1B263B",
    borderRadius: 12,
    padding: 20,
  },
  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 20,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#2A2A2A",
  },
  modalTitle: {
    color: "#FFF",
    fontSize: 24,
    fontWeight: "700",
  },
  modalCloseButton: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  settingsMenu: {
    gap: 12,
  },
  settingsMenuItem: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#2A2A2A",
    padding: 16,
    borderRadius: 8,
    gap: 12,
  },
  settingsMenuItemText: {
    flex: 1,
    color: "#FFF",
    fontSize: 16,
    fontWeight: "600",
  },
  settingsContent: {
    maxHeight: 500,
  },
  accountSection: {
    marginBottom: 20,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#2A2A2A",
  },
  accountLabel: {
    color: "#AAA",
    fontSize: 12,
    marginBottom: 4,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  accountValue: {
    color: "#FFF",
    fontSize: 16,
    fontWeight: "500",
  },
  deleteAccountButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FF6B6B",
    padding: 16,
    borderRadius: 8,
    marginTop: 32,
    gap: 8,
  },
  deleteAccountButtonText: {
    color: "#FFF",
    fontSize: 16,
    fontWeight: "700",
  },
  sectionTitle: {
    color: "#FFF",
    fontSize: 22,
    fontWeight: "700",
    marginBottom: 16,
  },
  sectionSubtitle: {
    color: "#F9A826",
    fontSize: 18,
    fontWeight: "600",
    marginTop: 20,
    marginBottom: 8,
  },
  sectionText: {
    color: "#AAA",
    fontSize: 14,
    lineHeight: 22,
    marginBottom: 12,
  },
  backButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 20,
    paddingVertical: 12,
    gap: 8,
  },
  backButtonText: {
    color: "#F9A826",
    fontSize: 16,
    fontWeight: "600",
  },
  // Terms and Conditions checkbox styles
  termsContainer: {
    marginTop: 8,
    marginBottom: 16,
  },
  checkboxContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 4,
    borderWidth: 2,
    borderColor: "#F9A826",
    backgroundColor: "#1B263B",
    alignItems: "center",
    justifyContent: "center",
  },
  checkboxChecked: {
    backgroundColor: "#F9A826",
  },
  termsText: {
    flex: 1,
    color: "#AAA",
    fontSize: 14,
    lineHeight: 20,
  },
  termsLink: {
    color: "#F9A826",
    fontWeight: "600",
    textDecorationLine: "underline",
  },
  termsErrorText: {
    color: "#FF6B6B",
    fontSize: 12,
    marginTop: 4,
    marginLeft: 36,
  },
  // Delete confirmation modal styles
  confirmModalContainer: {
    width: "90%",
    maxWidth: 400,
    backgroundColor: "#1B263B",
    borderRadius: 12,
    padding: 24,
  },
  confirmModalTitle: {
    color: "#FFF",
    fontSize: 24,
    fontWeight: "700",
    marginBottom: 16,
  },
  confirmModalText: {
    color: "#AAA",
    fontSize: 16,
    lineHeight: 24,
    marginBottom: 24,
  },
  confirmModalButtons: {
    flexDirection: "row",
    gap: 12,
    justifyContent: "flex-end",
  },
  confirmModalButton: {
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
    minWidth: 100,
    alignItems: "center",
    justifyContent: "center",
  },
  confirmModalButtonCancel: {
    backgroundColor: "#2A2A2A",
    borderWidth: 1,
    borderColor: "#666",
  },
  confirmModalButtonCancelText: {
    color: "#FFF",
    fontSize: 16,
    fontWeight: "600",
  },
  confirmModalButtonDelete: {
    backgroundColor: "#FF6B6B",
  },
  confirmModalButtonDeleteText: {
    color: "#FFF",
    fontSize: 16,
    fontWeight: "700",
  },
  // Help Center styles
  helpContactItem: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#2A2A2A",
    padding: 16,
    borderRadius: 8,
    marginBottom: 12,
    gap: 12,
  },
  helpContactTextContainer: {
    flex: 1,
  },
  helpContactTitle: {
    color: "#FFF",
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 4,
  },
  helpContactSubtitle: {
    color: "#AAA",
    fontSize: 14,
  },
  supportMessageInput: {
    minHeight: 120,
    marginBottom: 12,
  },
  supportSendButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F9A826",
    padding: 16,
    borderRadius: 8,
    gap: 8,
    marginBottom: 24,
  },
  supportSendButtonDisabled: {
    opacity: 0.5,
  },
  supportSendButtonText: {
    color: "#1B263B",
    fontSize: 16,
    fontWeight: "700",
  },
  faqItem: {
    backgroundColor: "#2A2A2A",
    padding: 16,
    borderRadius: 8,
    marginBottom: 12,
  },
  faqQuestion: {
    color: "#F9A826",
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 8,
  },
  faqAnswer: {
    color: "#AAA",
    fontSize: 14,
    lineHeight: 20,
  },
});
