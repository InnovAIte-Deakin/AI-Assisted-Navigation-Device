// Exterior Navigation Screen with Production Features
import { MaterialIcons } from "@expo/vector-icons";
import * as Location from "expo-location";
import * as Haptics from "expo-haptics";
import * as Speech from "expo-speech";
import { useFocusEffect } from "expo-router";
import { ExpoSpeechRecognitionModule, useSpeechRecognitionEvent } from "expo-speech-recognition";
import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  Alert,
  Dimensions,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import MapPanel from "../../src/components/MapPanel";
import { loadSettings, NavigationSettings } from "../../src/utils/settings";
import {
  Location as LocationType,
  Route,
  RouteStep,
} from "../../src/types/navigation";
import {
  calculateDistance,
  shouldAdvanceStep,
} from "../../src/utils/routing";
import { fetchRoute, RoutingOptions } from "../../src/utils/routingApi";
import { geocodePlaceName, GeocodeResult } from "../../src/utils/geocoding";
import { getAutocompleteSuggestions, formatSuggestion, AutocompleteSuggestion } from "../../src/utils/autocomplete";
import {
  metersBetween,
  updateStepIndex,
} from "../../src/utils/navigationHelpers";

const GOLD = "#f9b233";
const { height: SCREEN_H } = Dimensions.get("window");

// Milestone distances in meters
const MILESTONES = [200, 100, 50];

export default function ExteriorNavigationScreen() {
  const [isNavigating, setIsNavigating] = useState(false);
  const [showDestinationModal, setShowDestinationModal] = useState(false);
  const [settings, setSettings] = useState<NavigationSettings>({
    showMapVisuals: true,
    voiceEnabled: true,
  });
  const [currentLocation, setCurrentLocation] = useState<LocationType | null>(
    null
  );
  const [destination, setDestination] = useState<{
    lat: number;
    lng: number;
    name?: string;
  } | null>(null);
  const [origin, setOrigin] = useState<{
    lat: number;
    lng: number;
    name?: string;
  } | null>(null);
  const [originMode, setOriginMode] = useState<"current" | "custom">("current");
  const [originCoords, setOriginCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [fromInput, setFromInput] = useState("Current Location");
  const [toInput, setToInput] = useState("");
  const [useCurrentLocation, setUseCurrentLocation] = useState(true);
  const [isGeocoding, setIsGeocoding] = useState(false);
  const [isListeningDestination, setIsListeningDestination] = useState(false);
  const [autocompleteSuggestions, setAutocompleteSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [fromAutocompleteSuggestions, setFromAutocompleteSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [showFromSuggestions, setShowFromSuggestions] = useState(false);
  const autocompleteTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const fromAutocompleteTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const recognitionRef = useRef<any>(null);
  const nativeRecognitionResultRef = useRef<string>("");
  const [route, setRoute] = useState<Route | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [locationPermission, setLocationPermission] = useState(false);
  const [isLoadingRoute, setIsLoadingRoute] = useState(false);
  const [eta, setEta] = useState<number | null>(null);
  const [startTime, setStartTime] = useState<number | null>(null);

  const locationSubscriptionRef = useRef<Location.LocationSubscription | null>(
    null
  );
  const lastSpokenStepRef = useRef<number>(-1);
  const lastSpokenTimeRef = useRef<number>(0);
  const spokeApproachRef = useRef<boolean>(false);
  const lastMilestoneRef = useRef<number | null>(null);
  const speakingRef = useRef(false);
  const routeRef = useRef<Route | null>(null);
  const currentStepIndexRef = useRef<number>(0);
  const deviationCheckRef = useRef<number>(0);
  const lastLocationRef = useRef<LocationType | null>(null);
  const lastRouteUpdateRef = useRef<number>(0);

  // Navigation constants
  const ARRIVAL_THRESHOLD_M = 20; // meters - when to advance to next step
  const PRE_SPEAK_M = 80; // meters - speak early warning
  const VOICE_COOLDOWN_MS = 2500; // milliseconds - prevent spam
  const ROUTE_UPDATE_INTERVAL_MS = 2000; // Update route state every 2 seconds

  // Load settings when screen comes into focus
  useFocusEffect(
    useCallback(() => {
      loadSettings().then(setSettings);
    }, [])
  );

  // Request location permission with high accuracy
  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      setLocationPermission(status === "granted");
      if (status === "granted") {
        // Request high accuracy location
        const loc = await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.BestForNavigation, // Highest accuracy
        });
        const newLocation: LocationType = {
          latitude: loc.coords.latitude,
          longitude: loc.coords.longitude,
          accuracy: loc.coords.accuracy,
        };
        setCurrentLocation(newLocation);
        lastLocationRef.current = newLocation;
      }
    })();
  }, []);

  // Update ETA based on remaining distance
  useEffect(() => {
    if (isNavigating && route && currentStepIndex < route.steps.length) {
      const remainingSteps = route.steps.slice(currentStepIndex);
      const remainingDistance = remainingSteps.reduce(
        (sum, step) => sum + step.distanceToNext,
        0
      );
      const walkingSpeed = 1.4; // m/s
      const remainingTime = Math.round(remainingDistance / walkingSpeed);
      setEta(remainingTime);
    }
  }, [isNavigating, route, currentStepIndex]);

  // Voice instruction hook
  const speakInstruction = useCallback(
    (text: string) => {
      if (!settings.voiceEnabled || speakingRef.current) return;
      speakingRef.current = true;
      Speech.stop();
      Speech.speak(text, {
        rate: 1.0,
        pitch: 1.0,
        onDone: () => {
          speakingRef.current = false;
        },
        onStopped: () => {
          speakingRef.current = false;
        },
        onError: () => {
          speakingRef.current = false;
        },
      });
    },
    [settings.voiceEnabled]
  );

  // Check for milestone announcements
  const checkMilestones = useCallback(
    (distanceToNext: number) => {
      if (!settings.voiceEnabled) return;

      for (const milestone of MILESTONES) {
        if (
          distanceToNext <= milestone &&
          distanceToNext > milestone - 10 &&
          lastMilestoneRef.current !== milestone
        ) {
          speakInstruction(`In ${milestone} meters, ${milestone === 50 ? 'prepare to' : ''} ${milestone === 50 ? 'turn' : 'continue'}`);
          lastMilestoneRef.current = milestone;
          break;
        }
      }

      // Reset milestone if we're past all of them
      if (distanceToNext < 30) {
        lastMilestoneRef.current = null;
      }
    },
    [settings.voiceEnabled, speakInstruction]
  );

  // Check if user has deviated from route
  const checkDeviation = useCallback(
    async (location: LocationType) => {
      if (!routeRef.current || currentStepIndexRef.current >= routeRef.current.steps.length) {
        return;
      }

      const currentStep = routeRef.current.steps[currentStepIndexRef.current];
      if (!currentStep.endLat || !currentStep.endLng) return;

      // Check distance to current step's path
      const distanceToStepEnd = calculateDistance(
        location.latitude,
        location.longitude,
        currentStep.endLat,
        currentStep.endLng
      );

      // If user is more than 50m away from expected path, recalculate
      if (distanceToStepEnd > 50 && deviationCheckRef.current < Date.now() - 10000) {
        deviationCheckRef.current = Date.now();
        
        if (destination) {
          Alert.alert(
            "Route Deviation",
            "Recalculating route...",
            [{ text: "OK" }]
          );
          
          await recalculateRoute(location, destination);
        }
      }
    },
    [destination]
  );

  // Recalculate route
  const recalculateRoute = useCallback(
    async (originLoc: LocationType, dest: { lat: number; lng: number }) => {
      setIsLoadingRoute(true);
      try {
        const options: RoutingOptions = {
          originLat: originLoc.latitude,
          originLng: originLoc.longitude,
          destLat: dest.lat,
          destLng: dest.lng,
          profile: "foot-walking",
        };

        const newRoute = await fetchRoute(options);
        setRoute(newRoute);
        routeRef.current = newRoute;
        setCurrentStepIndex(0);
        currentStepIndexRef.current = 0;
        lastSpokenStepRef.current = -1;
        lastMilestoneRef.current = null;

        if (newRoute.steps[0]) {
          speakInstruction(newRoute.steps[0].instructionText);
          lastSpokenStepRef.current = 0;
        }
      } catch (error) {
        console.error("Failed to recalculate route:", error);
        Alert.alert("Error", "Failed to recalculate route. Continuing with current route.");
      } finally {
        setIsLoadingRoute(false);
      }
    },
    [speakInstruction]
  );

  // Start navigation
  // Use planned origin if custom, otherwise use current GPS location
  const startNavigation = useCallback(async () => {
    if (!destination) {
      setShowDestinationModal(true);
      return;
    }

    // Determine the origin to use for navigation
    let startOrigin: { lat: number; lng: number; name?: string };
    
    if (originMode === "custom" && originCoords) {
      // Use planned custom origin (e.g., Melbourne Uni)
      startOrigin = {
        lat: originCoords.lat,
        lng: originCoords.lng,
        name: origin?.name || "Planned Origin",
      };
    } else {
      // Use current GPS location
      if (!currentLocation) {
        Alert.alert("Error", "Location not available. Please enable location services.");
        return;
      }
      if (!locationPermission) {
        Alert.alert("Error", "Location permission required for navigation.");
        return;
      }
      startOrigin = {
        lat: currentLocation.latitude,
        lng: currentLocation.longitude,
        name: "Current Location",
      };
    }

    setIsLoadingRoute(true);
    try {
      const options: RoutingOptions = {
        originLat: startOrigin.lat,
        originLng: startOrigin.lng,
        destLat: destination.lat,
        destLng: destination.lng,
        profile: "foot-walking",
      };

      // Update origin state to reflect what we're actually using
      setOrigin(startOrigin);

      const newRoute = await fetchRoute(options);
      setRoute(newRoute);
      routeRef.current = newRoute;
      setCurrentStepIndex(0);
      currentStepIndexRef.current = 0;
      setIsNavigating(true);
      setStartTime(Date.now());
      lastSpokenStepRef.current = -1;
      lastSpokenTimeRef.current = 0;
      spokeApproachRef.current = false;
      lastMilestoneRef.current = null;
      deviationCheckRef.current = 0;

      // Speak first instruction
      if (newRoute.steps[0]) {
        speakInstruction(newRoute.steps[0].instructionText);
        lastSpokenStepRef.current = 0;
      }

      // Stop any existing location watcher before starting a new one
      if (locationSubscriptionRef.current) {
        try {
          locationSubscriptionRef.current.remove();
        } catch (error) {
          console.warn("Error removing old location subscription:", error);
        }
        locationSubscriptionRef.current = null;
      }

      // Start location tracking with high accuracy
      locationSubscriptionRef.current = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.BestForNavigation, // Highest accuracy
          timeInterval: 2000, // 2 seconds
          distanceInterval: 5, // 5 meters
        },
        async (loc) => {
          // ✅ MUST be first - define now at the very top before any use
          const now = Date.now();

          const newLocation: LocationType = {
            latitude: loc.coords.latitude,
            longitude: loc.coords.longitude,
            accuracy: loc.coords.accuracy,
            heading: loc.coords.heading,
          };
          setCurrentLocation(newLocation);

          // Check for deviation
          await checkDeviation(newLocation);

          // Check step progression using refs to avoid stale closures
          const currentRoute = routeRef.current;
          let currentIdx = currentStepIndexRef.current;

          if (currentRoute && currentRoute.steps.length > 0) {
            // Update step index based on GPS position
            const newStepIndex = updateStepIndex(
              newLocation.latitude,
              newLocation.longitude,
              currentRoute.steps,
              currentIdx,
              ARRIVAL_THRESHOLD_M
            );

            // If step advanced, update state
            if (newStepIndex !== currentIdx) {
              currentIdx = newStepIndex;
              setCurrentStepIndex(newStepIndex);
              currentStepIndexRef.current = newStepIndex;
              lastMilestoneRef.current = null; // Reset milestone on step change
              spokeApproachRef.current = false; // Reset approach flag for new step
            }

            const currentStep = currentRoute.steps[currentIdx];
            if (!currentStep) {
              lastLocationRef.current = newLocation;
              return;
            }

            // Calculate distance to next maneuver
            let distanceToManeuver = 0;
            if (currentStep.maneuverLocation) {
              const [maneuverLat, maneuverLng] = currentStep.maneuverLocation;
              distanceToManeuver = metersBetween(
                newLocation.latitude,
                newLocation.longitude,
                maneuverLat,
                maneuverLng
              );
            } else if (currentStep.endLat && currentStep.endLng) {
              distanceToManeuver = metersBetween(
                newLocation.latitude,
                newLocation.longitude,
                currentStep.endLat,
                currentStep.endLng
              );
            }

            // Update step distance (for UI display) - update state periodically
            const roundedDistance = Math.round(distanceToManeuver);
            if (Math.abs(currentStep.distanceToNext - roundedDistance) > 5) {
              // Only update if difference is significant (5m) to avoid excessive re-renders
              const updatedSteps = [...currentRoute.steps];
              updatedSteps[currentIdx] = {
                ...currentStep,
                distanceToNext: roundedDistance,
              };
              const updatedRoute = { ...currentRoute, steps: updatedSteps };
              routeRef.current = updatedRoute;
              
              // Update state (throttled to avoid excessive re-renders)
              if (now - lastRouteUpdateRef.current > ROUTE_UPDATE_INTERVAL_MS) {
                setRoute(updatedRoute);
                lastRouteUpdateRef.current = now;
              }
            }

            // Voice instructions with proper timing
            const instruction = currentStep.instructionText;

            // Speak when step changes (with cooldown)
            if (
              currentIdx !== lastSpokenStepRef.current &&
              now - lastSpokenTimeRef.current > VOICE_COOLDOWN_MS &&
              settings.voiceEnabled
            ) {
              speakInstruction(instruction);
              lastSpokenStepRef.current = currentIdx;
              lastSpokenTimeRef.current = now;
              spokeApproachRef.current = false; // Reset approach flag for new step
            }

            // Approach callout (speak early warning)
            if (
              !spokeApproachRef.current &&
              distanceToManeuver < PRE_SPEAK_M &&
              distanceToManeuver > ARRIVAL_THRESHOLD_M &&
              now - lastSpokenTimeRef.current > VOICE_COOLDOWN_MS &&
              settings.voiceEnabled &&
              currentStep.maneuverType !== 'arrive' &&
              currentStep.maneuverType !== 'depart'
            ) {
              const distanceText = Math.round(distanceToManeuver);
              speakInstruction(`In ${distanceText} meters, ${instruction}`);
              spokeApproachRef.current = true;
              lastSpokenTimeRef.current = now;
            }
          }

          lastLocationRef.current = newLocation;
        }
      );
    } catch (error) {
      console.error("Failed to start navigation:", error);
      Alert.alert("Error", "Failed to fetch route. Please try again.");
    } finally {
      setIsLoadingRoute(false);
    }
  }, [
    currentLocation,
    locationPermission,
    destination,
    originMode,
    originCoords,
    origin,
    speakInstruction,
    checkDeviation,
    checkMilestones,
  ]);

  // Stop navigation
  const stopNavigation = useCallback(() => {
    setIsNavigating(false);
    
    // Safely remove location subscription
    if (locationSubscriptionRef.current) {
      try {
        locationSubscriptionRef.current.remove();
      } catch (error) {
        console.warn("Error removing location subscription:", error);
      }
      locationSubscriptionRef.current = null;
    }
    
    Speech.stop();
    setRoute(null);
    routeRef.current = null;
    setCurrentStepIndex(0);
    currentStepIndexRef.current = 0;
    setEta(null);
    setStartTime(null);
    lastSpokenStepRef.current = -1;
    lastSpokenTimeRef.current = 0;
    spokeApproachRef.current = false;
    lastMilestoneRef.current = null;
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // Safely remove location subscription on unmount
      if (locationSubscriptionRef.current) {
        try {
          locationSubscriptionRef.current.remove();
        } catch (error) {
          console.warn("Error removing location subscription on unmount:", error);
        }
        locationSubscriptionRef.current = null;
      }
      // Clear autocomplete timeout
      if (autocompleteTimeoutRef.current) {
        clearTimeout(autocompleteTimeoutRef.current);
      }
      Speech.stop();
    };
  }, []);

  // Handle geocoding search for both From and To
  const handleSearchRoute = useCallback(async () => {
    if (!toInput.trim()) {
      Alert.alert("Error", "Please enter a destination name");
      return;
    }

    setIsGeocoding(true);
    try {
      // 1) Always geocode destination
      const destResult = await geocodePlaceName(toInput.trim());
      const destCoords = {
        lat: destResult.lat,
        lng: destResult.lng,
        name: destResult.name,
      };
      setDestination(destCoords);

      // 2) Determine origin based on mode
      let originLatLng: { lat: number; lng: number };
      let originName: string;

      if (useCurrentLocation && currentLocation) {
        // Use current GPS location
        originLatLng = {
          lat: currentLocation.latitude,
          lng: currentLocation.longitude,
        };
        originName = "Current Location";
        setOriginMode("current");
        setOriginCoords(null);
        setOrigin({
          lat: originLatLng.lat,
          lng: originLatLng.lng,
          name: originName,
        });
      } else if (fromInput.trim() && fromInput.trim().toLowerCase() !== "current location") {
        // Geocode custom origin
        const fromResult = await geocodePlaceName(fromInput.trim());
        originLatLng = {
          lat: fromResult.lat,
          lng: fromResult.lng,
        };
        originName = fromResult.name;
        setOriginMode("custom");
        setOriginCoords(originLatLng);
        setOrigin({
          lat: originLatLng.lat,
          lng: originLatLng.lng,
          name: originName,
        });
      } else {
        // Fallback to current location if available
        if (!currentLocation) {
          Alert.alert("Error", "Current location not available. Please enable location services or enter a starting point.");
          setIsGeocoding(false);
          return;
        }
        originLatLng = {
          lat: currentLocation.latitude,
          lng: currentLocation.longitude,
        };
        originName = "Current Location";
        setOriginMode("current");
        setOriginCoords(null);
        setOrigin({
          lat: originLatLng.lat,
          lng: originLatLng.lng,
          name: originName,
        });
      }

      // 3) Fetch route using the determined origin and destination
      const options: RoutingOptions = {
        originLat: originLatLng.lat,
        originLng: originLatLng.lng,
        destLat: destCoords.lat,
        destLng: destCoords.lng,
        profile: "foot-walking",
      };

      const newRoute = await fetchRoute(options);
      setRoute(newRoute);
      routeRef.current = newRoute;
      setCurrentStepIndex(0);
      currentStepIndexRef.current = 0;

      setShowDestinationModal(false);
      setFromInput("Current Location");
      setToInput("");
      setUseCurrentLocation(true);
      
      // If already navigating, stop and let user restart with new route
      if (isNavigating) {
        stopNavigation();
      }
    } catch (error: any) {
      Alert.alert("Error", error.message || "Failed to find location. Please try again.");
    } finally {
      setIsGeocoding(false);
    }
  }, [fromInput, toInput, useCurrentLocation, currentLocation, isNavigating, stopNavigation]);

  // Autocomplete handler for "To" input
  const handleToInputChange = useCallback((text: string) => {
    setToInput(text);
    setShowSuggestions(true);

    // Clear previous timeout
    if (autocompleteTimeoutRef.current) {
      clearTimeout(autocompleteTimeoutRef.current);
    }

    // Debounce autocomplete search
    if (text.trim().length >= 2) {
      autocompleteTimeoutRef.current = setTimeout(async () => {
        try {
          const suggestions = await getAutocompleteSuggestions(text.trim());
          setAutocompleteSuggestions(suggestions);
        } catch (error) {
          console.error('Autocomplete error:', error);
          setAutocompleteSuggestions([]);
        }
      }, 300); // 300ms delay
    } else {
      setAutocompleteSuggestions([]);
    }
  }, []);

  // Handle suggestion selection for "To" field
  const handleSelectSuggestion = useCallback((suggestion: AutocompleteSuggestion) => {
    const displayText = formatSuggestion(suggestion);
    setToInput(displayText);
    setShowSuggestions(false);
    setAutocompleteSuggestions([]);
    
    // Auto-set destination when suggestion is selected
    setDestination({
      lat: suggestion.lat,
      lng: suggestion.lng,
      name: suggestion.displayName,
    });
  }, []);

  // Autocomplete handler for "From" input
  const handleFromInputChange = useCallback((text: string) => {
    setFromInput(text);
    
    // Don't show suggestions if it's "Current Location"
    if (text.trim().toLowerCase() === "current location" || text.trim() === "") {
      setShowFromSuggestions(false);
      setFromAutocompleteSuggestions([]);
      setUseCurrentLocation(true);
      return;
    }

    setUseCurrentLocation(false);
    setShowFromSuggestions(true);

    // Clear previous timeout
    if (fromAutocompleteTimeoutRef.current) {
      clearTimeout(fromAutocompleteTimeoutRef.current);
    }

    // Debounce autocomplete search
    if (text.trim().length >= 2) {
      fromAutocompleteTimeoutRef.current = setTimeout(async () => {
        try {
          const suggestions = await getAutocompleteSuggestions(text.trim());
          setFromAutocompleteSuggestions(suggestions);
        } catch (error) {
          console.error('From autocomplete error:', error);
          setFromAutocompleteSuggestions([]);
        }
      }, 300); // 300ms delay
    } else {
      setFromAutocompleteSuggestions([]);
    }
  }, []);

  // Handle suggestion selection for "From" field
  const handleSelectFromSuggestion = useCallback((suggestion: AutocompleteSuggestion) => {
    const displayText = formatSuggestion(suggestion);
    setFromInput(displayText);
    setShowFromSuggestions(false);
    setFromAutocompleteSuggestions([]);
    setUseCurrentLocation(false);
    
    // Auto-set origin when suggestion is selected
    setOrigin({
      lat: suggestion.lat,
      lng: suggestion.lng,
      name: suggestion.displayName,
    });
    setOriginMode("custom");
    setOriginCoords({
      lat: suggestion.lat,
      lng: suggestion.lng,
    });
  }, []);

  // Handle speech recognition results for native platforms
  useSpeechRecognitionEvent('result', useCallback((event: any) => {
    if (isListeningDestination && event.results && event.results.length > 0) {
      const transcript = event.results[0]?.transcript || "";
      if (transcript.trim()) {
        nativeRecognitionResultRef.current = transcript.trim();
        setToInput(transcript.trim());
      }
    }
  }, [isListeningDestination]));

  useSpeechRecognitionEvent('end', useCallback(() => {
    if (isListeningDestination) {
      setIsListeningDestination(false);
      const finalText = nativeRecognitionResultRef.current;
      if (finalText) {
        // Auto-trigger search after a short delay if destination is set
        setTimeout(() => {
          handleSearchRoute();
        }, 500);
      }
      nativeRecognitionResultRef.current = "";
    }
  }, [isListeningDestination, handleSearchRoute]));

  useSpeechRecognitionEvent('error', useCallback((event: any) => {
    if (isListeningDestination) {
      setIsListeningDestination(false);
      const errorMsg = event?.error || "Speech recognition failed";
      Alert.alert("Error", `${errorMsg}. Please try typing instead.`);
      nativeRecognitionResultRef.current = "";
    }
  }, [isListeningDestination]));

  // Handle voice input for destination
  const handleVoiceInput = useCallback(async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    
    if (isListeningDestination) {
      // Stop listening
      if (Platform.OS === "web") {
        if (recognitionRef.current) {
          try {
            recognitionRef.current.stop();
          } catch {}
        }
      } else {
        try {
          await ExpoSpeechRecognitionModule.stop();
        } catch (error) {
          console.error("Error stopping recognition:", error);
        }
      }
      setIsListeningDestination(false);
      nativeRecognitionResultRef.current = "";
      return;
    }

    // Start listening
    if (Platform.OS === "web") {
      // Web implementation using Web Speech API
      const W = globalThis as any;
      const SR = W.SpeechRecognition || W.webkitSpeechRecognition;
      if (!SR) {
        Alert.alert(
          "Error",
          "Speech recognition is not available in this browser. Please use Chrome, Edge, or Safari."
        );
        return;
      }

      try {
        const rec = new SR();
        recognitionRef.current = rec;
        rec.lang = "en-US";
        rec.continuous = false;
        rec.interimResults = false;
        
        rec.onresult = async (e: any) => {
          let text = "";
          for (let i = e.resultIndex; i < e.results.length; i++) {
            text += e.results[i][0].transcript;
          }
          const destinationText = text.trim();
          setToInput(destinationText);
          setIsListeningDestination(false);
          
          // Auto-trigger search after a short delay if destination is set
          if (destinationText) {
            setTimeout(() => {
              handleSearchRoute();
            }, 500);
          }
        };
        
        rec.onend = () => setIsListeningDestination(false);
        rec.onerror = (error: any) => {
          setIsListeningDestination(false);
          let errorMsg = "Speech recognition failed.";
          if (error.error === "no-speech") {
            errorMsg = "No speech detected. Please try again.";
          } else if (error.error === "not-allowed") {
            errorMsg = "Microphone permission denied. Please allow microphone access and try again.";
          }
          Alert.alert("Error", errorMsg);
        };
        
        setIsListeningDestination(true);
        rec.start();
      } catch (error) {
        Alert.alert("Error", "Failed to start speech recognition. Please try typing instead.");
      }
    } else {
      // Native implementation using expo-speech-recognition
      try {
        // Request permissions
        const permission = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
        if (!permission.granted) {
          Alert.alert(
            "Permission Required",
            "Microphone and speech recognition permissions are required for voice input. Please enable them in your device settings."
          );
          return;
        }

        // Start recognition
        nativeRecognitionResultRef.current = "";
        setIsListeningDestination(true);
        await ExpoSpeechRecognitionModule.start({
          lang: "en-US",
          interimResults: true,
          continuous: false,
        });
      } catch (error: any) {
        setIsListeningDestination(false);
        const errorMsg = error?.message || "Failed to start speech recognition";
        Alert.alert("Error", `${errorMsg}. Please try typing instead.`);
      }
    }
  }, [isListeningDestination, handleSearchRoute]);

  // Format ETA
  const formatETA = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return secs > 0 ? `${minutes}m ${secs}s` : `${minutes}m`;
  };

  const currentStep = route?.steps[currentStepIndex];
  const progress =
    route && currentStepIndex > 0
      ? Math.round(
          ((route.steps
            .slice(0, currentStepIndex)
            .reduce((sum, s) => sum + s.distanceToNext, 0) /
            route.totalDistance) *
            100)
        )
      : 0;

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>EXTERIOR NAVIGATION</Text>
        {destination && (
          <Pressable
            onPress={() => setShowDestinationModal(true)}
            style={styles.headerDestinationBtn}
          >
            <MaterialIcons name="edit-location" size={20} color={GOLD} />
          </Pressable>
        )}
      </View>

      {/* Visual Panel - Map or Minimal */}
      <View style={styles.previewBox}>
        <MapPanel
          currentLocation={currentLocation || undefined}
          routeSteps={route?.steps}
          routeGeometry={route?.geometry}
          destination={destination || undefined}
          showMap={settings.showMapVisuals}
        />
      </View>

      {/* Route Planning Modal */}
      <Modal
        visible={showDestinationModal}
        transparent
        animationType="slide"
        onRequestClose={() => {
          setShowDestinationModal(false);
          setIsListeningDestination(false);
        }}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Plan Route</Text>
            
            <ScrollView 
              style={styles.modalScrollView}
              contentContainerStyle={styles.modalScrollContent}
              keyboardShouldPersistTaps="handled"
            >
              {/* FROM Field */}
            <View style={[
              styles.inputGroup,
              showFromSuggestions && fromAutocompleteSuggestions.length > 0 && styles.inputGroupWithSuggestions
            ]}>
              <Text style={styles.inputLabel}>From</Text>
              <View style={styles.inputWithMic}>
                <View style={styles.inputContainer}>
                  <TextInput
                    style={[styles.input, styles.inputFlex]}
                    placeholder="e.g., Monash University"
                    placeholderTextColor="#8fa3bf"
                    value={fromInput}
                    onChangeText={handleFromInputChange}
                    onFocus={() => {
                      if (fromInput.trim().length >= 2 && 
                          fromInput.trim().toLowerCase() !== "current location" &&
                          fromAutocompleteSuggestions.length > 0) {
                        setShowFromSuggestions(true);
                      }
                    }}
                    onBlur={() => {
                      // Delay hiding suggestions to allow click
                      setTimeout(() => setShowFromSuggestions(false), 200);
                    }}
                    autoCapitalize="words"
                  />
                  {/* Autocomplete Dropdown for From */}
                  {showFromSuggestions && fromAutocompleteSuggestions.length > 0 && (
                    <View style={styles.suggestionsContainer}>
                      <ScrollView 
                        nestedScrollEnabled
                        keyboardShouldPersistTaps="handled"
                        style={styles.suggestionsScrollView}
                      >
                        {fromAutocompleteSuggestions.map((suggestion, index) => (
                          <Pressable
                            key={`from-${suggestion.lat}-${suggestion.lng}-${index}`}
                            style={styles.suggestionItem}
                            onPress={() => handleSelectFromSuggestion(suggestion)}
                          >
                            <MaterialIcons name="place" size={18} color={GOLD} />
                            <View style={styles.suggestionTextContainer}>
                              <Text style={styles.suggestionName}>
                                {formatSuggestion(suggestion)}
                              </Text>
                              <Text style={styles.suggestionAddress} numberOfLines={1}>
                                {suggestion.displayName}
                              </Text>
                            </View>
                          </Pressable>
                        ))}
                      </ScrollView>
                    </View>
                  )}
                </View>
                <Pressable
                  style={styles.iconButton}
                  onPress={() => {
                    setFromInput("Current Location");
                    setUseCurrentLocation(true);
                    setShowFromSuggestions(false);
                    setFromAutocompleteSuggestions([]);
                  }}
                >
                  <MaterialIcons name="my-location" size={20} color={GOLD} />
                </Pressable>
              </View>
              <Text style={styles.hintText}>Tap 📍 to use Current Location</Text>
            </View>

            {/* TO Field */}
            <View style={[
              styles.inputGroup,
              showSuggestions && autocompleteSuggestions.length > 0 && styles.inputGroupWithSuggestions
            ]}>
              <Text style={styles.inputLabel}>To</Text>
              <View style={styles.inputWithMic}>
                <View style={styles.inputContainer}>
                  <TextInput
                    style={[styles.input, styles.inputFlex]}
                    placeholder="e.g., Monash University"
                    placeholderTextColor="#8fa3bf"
                    value={toInput}
                    onChangeText={handleToInputChange}
                    onFocus={() => {
                      if (toInput.trim().length >= 2 && autocompleteSuggestions.length > 0) {
                        setShowSuggestions(true);
                      }
                    }}
                    onBlur={() => {
                      // Delay hiding suggestions to allow click
                      setTimeout(() => setShowSuggestions(false), 200);
                    }}
                    autoCapitalize="words"
                  />
                  {/* Autocomplete Dropdown */}
                  {showSuggestions && autocompleteSuggestions.length > 0 && (
                    <View style={styles.suggestionsContainer}>
                      <ScrollView 
                        nestedScrollEnabled
                        keyboardShouldPersistTaps="handled"
                        style={styles.suggestionsScrollView}
                      >
                        {autocompleteSuggestions.map((suggestion, index) => (
                          <Pressable
                            key={`${suggestion.lat}-${suggestion.lng}-${index}`}
                            style={styles.suggestionItem}
                            onPress={() => handleSelectSuggestion(suggestion)}
                          >
                            <MaterialIcons name="place" size={18} color={GOLD} />
                            <View style={styles.suggestionTextContainer}>
                              <Text style={styles.suggestionName}>
                                {formatSuggestion(suggestion)}
                              </Text>
                              <Text style={styles.suggestionAddress} numberOfLines={1}>
                                {suggestion.displayName}
                              </Text>
                            </View>
                          </Pressable>
                        ))}
                      </ScrollView>
                    </View>
                  )}
                </View>
                <Pressable
                  style={[styles.iconButton, isListeningDestination && styles.iconButtonActive]}
                  onPress={handleVoiceInput}
                >
                  <MaterialIcons
                    name={isListeningDestination ? "mic" : "mic-none"}
                    size={20}
                    color={isListeningDestination ? "#1B263B" : GOLD}
                  />
                </Pressable>
              </View>
              {isListeningDestination && (
                <Text style={styles.listeningHint}>Listening... speak the destination name</Text>
              )}
              <Text style={styles.hintText}>Tap 🎤 to speak destination (optional)</Text>
            </View>

            {/* Preview */}
            {(origin || destination) && (
              <View style={styles.previewContainer}>
                {origin && (
                  <View style={styles.previewRow}>
                    <MaterialIcons name="radio-button-checked" size={16} color={GOLD} />
                    <Text style={styles.previewText}>
                      {origin.name || `${origin.lat.toFixed(4)}, ${origin.lng.toFixed(4)}`}
                      {originMode === "custom" && (
                        <Text style={styles.previewModeText}> (custom)</Text>
                      )}
                    </Text>
                  </View>
                )}
                {destination && (
                  <View style={styles.previewRow}>
                    <MaterialIcons name="place" size={16} color={GOLD} />
                    <Text style={styles.previewText}>
                      {destination.name || `${destination.lat.toFixed(4)}, ${destination.lng.toFixed(4)}`}
                    </Text>
                  </View>
                )}
              </View>
            )}

            {/* Error Message */}
            {!toInput.trim() && (
              <Text style={styles.errorText}>Destination is required.</Text>
            )}
            </ScrollView>

            {/* Action Buttons - Outside ScrollView so they stay fixed */}
            <View style={styles.modalButtons}>
              <Pressable
                style={[styles.modalButton, styles.cancelButton]}
                onPress={() => {
                  setShowDestinationModal(false);
                  setIsListeningDestination(false);
                }}
              >
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </Pressable>
              <Pressable
                style={[styles.modalButton, styles.confirmButton]}
                onPress={handleSearchRoute}
                disabled={isGeocoding || !toInput.trim()}
              >
                <Text style={styles.confirmButtonText}>
                  {isGeocoding ? "Searching..." : "Search Route"}
                </Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>

      {/* Instruction Card */}
      {isNavigating && currentStep ? (
        <View style={styles.instructionCard}>
          <Text style={styles.instructionText}>
            {currentStep.instructionText}
          </Text>
          {currentStep.roadName && (
            <Text style={styles.roadNameText}>{currentStep.roadName}</Text>
          )}
          <View style={styles.statsRow}>
            <Text style={styles.distanceText}>
              {currentStep.distanceToNext > 0
                ? `${Math.round(currentStep.distanceToNext)}m to ${currentStep.maneuverType === 'arrive' ? 'destination' : 'turn'}`
                : "Arriving"}
            </Text>
            {eta !== null && (
              <Text style={styles.etaText}>ETA: {formatETA(eta)}</Text>
            )}
          </View>
          {route && (
            <Text style={styles.progressText}>{progress}% completed</Text>
          )}
        </View>
      ) : (
        <View style={styles.instructionCard}>
          <Text style={styles.instructionText}>
            {destination
              ? `Ready to navigate${origin && origin.name !== "Current Location" ? ` from ${origin.name}` : ""} to ${destination.name || "destination"}. Tap Start to begin.`
              : "Set a destination to begin navigation."}
          </Text>
          {destination && (
            <>
              <View style={styles.navOriginIndicator}>
                <MaterialIcons 
                  name={originMode === "custom" ? "place" : "my-location"} 
                  size={14} 
                  color={GOLD} 
                />
                <Text style={styles.navOriginText}>
                  Nav Origin: {originMode === "custom" && originCoords 
                    ? `Planned (${origin?.name || "Custom"})` 
                    : "Live GPS"}
                </Text>
              </View>
              {origin && origin.name !== "Current Location" && (
                <Text style={styles.destinationInfo}>
                  From: {origin.name || `${origin.lat.toFixed(4)}, ${origin.lng.toFixed(4)}`}
                </Text>
              )}
              <Text style={styles.destinationInfo}>
                To: {destination.name || `${destination.lat.toFixed(4)}, ${destination.lng.toFixed(4)}`}
              </Text>
            </>
          )}
        </View>
      )}

      {/* Control Buttons */}
      <View style={styles.controlBar}>
        {!isNavigating ? (
          <>
            <Pressable
              style={[styles.controlBtn, styles.destinationBtn]}
              onPress={() => {
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                setShowDestinationModal(true);
              }}
            >
              <MaterialIcons name="place" size={24} color={GOLD} />
              <Text style={styles.destinationBtnText}>DESTINATION</Text>
            </Pressable>
            <Pressable
              style={[styles.controlBtn, styles.startBtn]}
              onPress={() => {
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
                startNavigation();
              }}
              disabled={isLoadingRoute || !destination}
            >
              {isLoadingRoute ? (
                <Text style={styles.startBtnText}>Loading...</Text>
              ) : (
                <>
                  <MaterialIcons name="play-arrow" size={32} color="#1B263B" />
                  <Text style={styles.startBtnText}>START</Text>
                </>
              )}
            </Pressable>
          </>
        ) : (
          <Pressable
            style={[styles.controlBtn, styles.stopBtn]}
            onPress={() => {
              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
              stopNavigation();
            }}
          >
            <MaterialIcons name="stop" size={32} color={GOLD} />
            <Text style={styles.stopBtnText}>STOP</Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: "#1B263B" },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 8,
    borderBottomWidth: 2,
    borderBottomColor: GOLD,
  },
  headerTitle: { color: GOLD, fontSize: 20, fontWeight: "800", flex: 1 },
  destinationBtn: {
    padding: 8,
  },
  headerDestinationBtn: {
    padding: 8,
  },
  previewBox: {
    height: SCREEN_H * 0.55,
    margin: 12,
    borderRadius: 10,
    overflow: "hidden",
    backgroundColor: "#1B263B",
  },
  instructionCard: {
    backgroundColor: "#242424",
    marginHorizontal: 16,
    marginVertical: 12,
    padding: 16,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: GOLD,
  },
  instructionText: {
    color: GOLD,
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 8,
  },
  statsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  distanceText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  etaText: {
    color: GOLD,
    fontSize: 16,
    fontWeight: "600",
  },
  progressText: {
    color: GOLD,
    fontSize: 14,
    fontWeight: "600",
    marginTop: 8,
  },
  roadNameText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "500",
    marginTop: 4,
    fontStyle: "italic",
  },
  destinationInfo: {
    color: "#aaa",
    fontSize: 12,
    marginTop: 4,
  },
  navOriginIndicator: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 8,
    marginBottom: 4,
  },
  navOriginText: {
    color: GOLD,
    fontSize: 12,
    fontWeight: "600",
    fontStyle: "italic",
  },
  controlBar: {
    paddingHorizontal: 16,
    paddingBottom: 20,
    flexDirection: "row",
    gap: 12,
  },
  controlBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 16,
    borderRadius: 10,
    gap: 8,
    flex: 1,
  },
  startBtn: {
    backgroundColor: GOLD,
    flex: 2,
  },
  startBtnText: {
    color: "#1B263B",
    fontSize: 18,
    fontWeight: "800",
  },
  stopBtn: {
    backgroundColor: "transparent",
    borderWidth: 2,
    borderColor: GOLD,
  },
  stopBtnText: {
    color: GOLD,
    fontSize: 18,
    fontWeight: "800",
  },
  destinationBtnText: {
    color: GOLD,
    fontSize: 14,
    fontWeight: "700",
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.7)",
    justifyContent: "center",
    alignItems: "center",
  },
  modalContent: {
    backgroundColor: "#1B263B",
    borderRadius: 12,
    padding: 20,
    width: "85%",
    maxWidth: 400,
    maxHeight: "90%",
    borderWidth: 2,
    borderColor: GOLD,
  },
  modalScrollView: {
    maxHeight: 500,
  },
  modalScrollContent: {
    paddingBottom: 10,
  },
  inputGroupWithSuggestions: {
    marginBottom: 160,
  },
  modalTitle: {
    color: GOLD,
    fontSize: 22,
    fontWeight: "800",
    marginBottom: 20,
    textAlign: "center",
  },
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    color: GOLD,
    fontSize: 14,
    fontWeight: "600",
    marginBottom: 8,
  },
  input: {
    backgroundColor: "#242424",
    borderWidth: 1,
    borderColor: GOLD,
    borderRadius: 8,
    padding: 12,
    color: "#fff",
    fontSize: 16,
  },
  inputWithMic: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  inputFlex: {
    flex: 1,
  },
  inputContainer: {
    position: "relative",
    flex: 1,
  },
  suggestionsContainer: {
    position: "absolute",
    top: "100%",
    left: 0,
    right: 0,
    backgroundColor: "#1B263B",
    borderRadius: 8,
    borderWidth: 1,
    borderColor: GOLD,
    marginTop: 4,
    maxHeight: 150,
    zIndex: 9999,
    elevation: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.5,
    shadowRadius: 6,
    overflow: "hidden",
  },
  suggestionsScrollView: {
    maxHeight: 200,
  },
  suggestionItem: {
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#333",
    gap: 12,
  },
  suggestionTextContainer: {
    flex: 1,
  },
  suggestionName: {
    color: GOLD,
    fontSize: 15,
    fontWeight: "600",
    marginBottom: 2,
  },
  suggestionAddress: {
    color: "#8fa3bf",
    fontSize: 12,
  },
  iconButton: {
    width: 44,
    height: 44,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: GOLD,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#242424",
  },
  iconButtonActive: {
    backgroundColor: GOLD,
  },
  micButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 2,
    borderColor: GOLD,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "transparent",
  },
  micButtonActive: {
    backgroundColor: GOLD,
  },
  hintText: {
    color: "#9bb0cc",
    fontSize: 12,
    marginTop: 6,
  },
  listeningHint: {
    color: GOLD,
    fontSize: 12,
    marginTop: 4,
    fontStyle: "italic",
  },
  previewContainer: {
    backgroundColor: "#242424",
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: GOLD,
    gap: 8,
  },
  previewRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  previewText: {
    color: GOLD,
    fontSize: 14,
    fontWeight: "600",
    flex: 1,
  },
  previewModeText: {
    color: "#9bb0cc",
    fontSize: 12,
    fontStyle: "italic",
  },
  errorText: {
    color: "#ff6b6b",
    fontSize: 12,
    marginTop: 8,
    textAlign: "center",
  },
  modalButtons: {
    flexDirection: "row",
    gap: 12,
    marginTop: 8,
  },
  modalButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: "center",
  },
  cancelButton: {
    backgroundColor: "#333",
    borderWidth: 1,
    borderColor: GOLD,
  },
  cancelButtonText: {
    color: GOLD,
    fontSize: 16,
    fontWeight: "700",
  },
  confirmButton: {
    backgroundColor: GOLD,
  },
  confirmButtonText: {
    color: "#1B263B",
    fontSize: 16,
    fontWeight: "800",
  },
});
