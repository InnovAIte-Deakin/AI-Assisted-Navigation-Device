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
  snapToRoute,
  calculateRemainingDistance,
} from "../../src/utils/navigationHelpers";

const GOLD = "#f9b233";
const { height: SCREEN_H } = Dimensions.get("window");

const MILESTONES = [200, 100, 50];

export default function ExteriorNavigationScreen() {
  const [isNavigating, setIsNavigating] = useState(false);
  const [showDestinationModal, setShowDestinationModal] = useState(false);
  const [settings, setSettings] = useState<NavigationSettings>({
    showMapVisuals: true,
    voiceEnabled: true,
  });
  const [currentLocation, setCurrentLocation] = useState<LocationType | null>(null);
  const [destination, setDestination] = useState<{ lat: number; lng: number; name?: string } | null>(null);
  const [origin, setOrigin] = useState<{ lat: number; lng: number; name?: string } | null>(null);
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
  const routeSearchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const routeCacheRef = useRef<Map<string, Route>>(new Map());
  const [route, setRoute] = useState<Route | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [locationPermission, setLocationPermission] = useState(false);
  const [isLoadingRoute, setIsLoadingRoute] = useState(false);
  const [eta, setEta] = useState<number | null>(null);
  const [startTime, setStartTime] = useState<number | null>(null);

  const locationSubscriptionRef = useRef<Location.LocationSubscription | null>(null);
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

  const ARRIVAL_THRESHOLD_M = 20;
  const MANEUVER_REACHED_THRESHOLD_M = 20;
  const SNAP_TO_ROUTE_THRESHOLD_M = 100;
  const MIN_ROUTE_START_DISTANCE_M = 50;
  const DESTINATION_ARRIVAL_THRESHOLD_M = 15;
  const PRE_SPEAK_M = 80;
  const VOICE_COOLDOWN_MS = 2500;
  const ROUTE_UPDATE_INTERVAL_MS = 2000;

  useFocusEffect(
    useCallback(() => {
      loadSettings().then(setSettings);
    }, [])
  );

  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      setLocationPermission(status === "granted");
      if (status === "granted") {
        const loc = await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.BestForNavigation,
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

  useEffect(() => {
    if (isNavigating && route && currentLocation && destination) {
      let remainingDistance: number;
      if (route.geometry && route.geometry.length > 0) {
        remainingDistance = calculateRemainingDistance(
          currentLocation.latitude,
          currentLocation.longitude,
          route.geometry,
          destination.lat,
          destination.lng,
          SNAP_TO_ROUTE_THRESHOLD_M
        );
      } else {
        const remainingSteps = route.steps.slice(currentStepIndex);
        remainingDistance = remainingSteps.reduce((sum, step) => sum + step.distanceToNext, 0);
      }
      const walkingSpeed = 1.4;
      const remainingTime = Math.round(remainingDistance / walkingSpeed);
      setEta(remainingTime);
    } else if (!isNavigating) {
      setEta(null);
    }
  }, [isNavigating, route, currentLocation, destination, currentStepIndex]);

  const speakInstruction = useCallback(
    (text: string) => {
      if (!settings.voiceEnabled || speakingRef.current) return;
      speakingRef.current = true;
      Speech.stop();
      Speech.speak(text, {
        rate: 1.0,
        pitch: 1.0,
        onDone: () => { speakingRef.current = false; },
        onStopped: () => { speakingRef.current = false; },
        onError: () => { speakingRef.current = false; },
      });
    },
    [settings.voiceEnabled]
  );

  const checkMilestones = useCallback(
    (distanceToNext: number) => {
      if (!settings.voiceEnabled) return;
      for (const milestone of MILESTONES) {
        if (distanceToNext <= milestone && distanceToNext > milestone - 10 && lastMilestoneRef.current !== milestone) {
          speakInstruction(`In ${milestone} meters, ${milestone === 50 ? 'prepare to' : ''} ${milestone === 50 ? 'turn' : 'continue'}`);
          lastMilestoneRef.current = milestone;
          break;
        }
      }
      if (distanceToNext < 30) lastMilestoneRef.current = null;
    },
    [settings.voiceEnabled, speakInstruction]
  );

  const checkDeviation = useCallback(
    async (location: LocationType) => {
      if (!routeRef.current || currentStepIndexRef.current >= routeRef.current.steps.length) return;
      const currentStep = routeRef.current.steps[currentStepIndexRef.current];
      if (!currentStep.endLat || !currentStep.endLng) return;
      const distanceToStepEnd = calculateDistance(location.latitude, location.longitude, currentStep.endLat, currentStep.endLng);
      if (distanceToStepEnd > 50 && deviationCheckRef.current < Date.now() - 10000) {
        deviationCheckRef.current = Date.now();
        if (destination) {
          Alert.alert("Route Deviation", "Recalculating route...", [{ text: "OK" }]);
          await recalculateRoute(location, destination);
        }
      }
    },
    [destination]
  );

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

  const startNavigation = useCallback(async () => {
    if (!destination) {
      setShowDestinationModal(true);
      return;
    }
    let startOrigin: { lat: number; lng: number; name?: string };
    if (originMode === "custom" && originCoords) {
      startOrigin = { lat: originCoords.lat, lng: originCoords.lng, name: origin?.name || "Planned Origin" };
    } else {
      if (!currentLocation) {
        Alert.alert("Error", "Location not available. Please enable location services.");
        return;
      }
      if (!locationPermission) {
        Alert.alert("Error", "Location permission required for navigation.");
        return;
      }
      startOrigin = { lat: currentLocation.latitude, lng: currentLocation.longitude, name: "Current Location" };
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

      if (newRoute.steps[0]) {
        speakInstruction(newRoute.steps[0].instructionText);
        lastSpokenStepRef.current = 0;
      }

      if (locationSubscriptionRef.current) {
        try { locationSubscriptionRef.current.remove(); } catch (error) { console.warn("Error removing old location subscription:", error); }
        locationSubscriptionRef.current = null;
      }

      locationSubscriptionRef.current = await Location.watchPositionAsync(
        { accuracy: Location.Accuracy.BestForNavigation, timeInterval: 2000, distanceInterval: 5 },
        async (loc) => {
          const now = Date.now();
          const newLocation: LocationType = {
            latitude: loc.coords.latitude,
            longitude: loc.coords.longitude,
            accuracy: loc.coords.accuracy,
            heading: loc.coords.heading,
          };
          setCurrentLocation(newLocation);
          await checkDeviation(newLocation);

          const currentRoute = routeRef.current;
          let currentIdx = currentStepIndexRef.current;

          if (currentRoute && currentRoute.steps.length > 0) {
            if (destination) {
              const distanceToDestination = metersBetween(newLocation.latitude, newLocation.longitude, destination.lat, destination.lng);
              if (distanceToDestination <= DESTINATION_ARRIVAL_THRESHOLD_M) {
                const arriveStepIndex = currentRoute.steps.length - 1;
                if (currentIdx !== arriveStepIndex) {
                  currentIdx = arriveStepIndex;
                  setCurrentStepIndex(arriveStepIndex);
                  currentStepIndexRef.current = arriveStepIndex;
                }
              } else {
                const newStepIndex = updateStepIndex(newLocation.latitude, newLocation.longitude, currentRoute.steps, currentIdx, MANEUVER_REACHED_THRESHOLD_M, currentRoute.geometry);
                if (newStepIndex !== currentIdx) {
                  currentIdx = newStepIndex;
                  setCurrentStepIndex(newStepIndex);
                  currentStepIndexRef.current = newStepIndex;
                  lastMilestoneRef.current = null;
                  spokeApproachRef.current = false;
                }
              }
            } else {
              const newStepIndex = updateStepIndex(newLocation.latitude, newLocation.longitude, currentRoute.steps, currentIdx, MANEUVER_REACHED_THRESHOLD_M, currentRoute.geometry);
              if (newStepIndex !== currentIdx) {
                currentIdx = newStepIndex;
                setCurrentStepIndex(newStepIndex);
                currentStepIndexRef.current = newStepIndex;
                lastMilestoneRef.current = null;
                spokeApproachRef.current = false;
              }
            }

            const currentStep = currentRoute.steps[currentIdx];
            if (!currentStep) { lastLocationRef.current = newLocation; return; }

            if (currentStep.maneuverType === 'arrive' && destination) {
              const distanceToDest = metersBetween(newLocation.latitude, newLocation.longitude, destination.lat, destination.lng);
              if (distanceToDest > DESTINATION_ARRIVAL_THRESHOLD_M) {
                const prevStepIndex = Math.max(0, currentIdx - 1);
                currentIdx = prevStepIndex;
                setCurrentStepIndex(prevStepIndex);
                currentStepIndexRef.current = prevStepIndex;
                const prevStep = currentRoute.steps[prevStepIndex];
                if (prevStep) { lastLocationRef.current = newLocation; return; }
              }
            }

            let distanceToManeuver = 0;
            if (currentStep.maneuverLocation) {
              const [maneuverLat, maneuverLng] = currentStep.maneuverLocation;
              distanceToManeuver = metersBetween(newLocation.latitude, newLocation.longitude, maneuverLat, maneuverLng);
            } else if (currentStep.endLat && currentStep.endLng) {
              distanceToManeuver = metersBetween(newLocation.latitude, newLocation.longitude, currentStep.endLat, currentStep.endLng);
            }

            if (distanceToManeuver > 0 && currentStep.maneuverType !== 'arrive' && currentStep.maneuverType !== 'depart') {
              checkMilestones(distanceToManeuver);
            }

            const roundedDistance = Math.round(distanceToManeuver);
            if (Math.abs(currentStep.distanceToNext - roundedDistance) > 5) {
              const updatedSteps = [...currentRoute.steps];
              updatedSteps[currentIdx] = { ...currentStep, distanceToNext: roundedDistance };
              const updatedRoute = { ...currentRoute, steps: updatedSteps };
              routeRef.current = updatedRoute;
              if (now - lastRouteUpdateRef.current > ROUTE_UPDATE_INTERVAL_MS) {
                setRoute(updatedRoute);
                lastRouteUpdateRef.current = now;
              }
            }

            const instruction = currentStep.instructionText;
            if (currentIdx !== lastSpokenStepRef.current && now - lastSpokenTimeRef.current > VOICE_COOLDOWN_MS && settings.voiceEnabled) {
              speakInstruction(instruction);
              lastSpokenStepRef.current = currentIdx;
              lastSpokenTimeRef.current = now;
              spokeApproachRef.current = false;
            }

            if (!spokeApproachRef.current && distanceToManeuver < 50 && distanceToManeuver > ARRIVAL_THRESHOLD_M && now - lastSpokenTimeRef.current > VOICE_COOLDOWN_MS && settings.voiceEnabled && currentStep.maneuverType !== 'arrive' && currentStep.maneuverType !== 'depart') {
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
  }, [currentLocation, locationPermission, destination, originMode, originCoords, origin, speakInstruction, checkDeviation, checkMilestones]);

  const stopNavigation = useCallback(() => {
    setIsNavigating(false);
    if (locationSubscriptionRef.current) {
      try { locationSubscriptionRef.current.remove(); } catch (error) { console.warn("Error removing location subscription:", error); }
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

  useEffect(() => {
    return () => {
      if (locationSubscriptionRef.current) {
        try { locationSubscriptionRef.current.remove(); } catch (error) { console.warn("Error removing location subscription on unmount:", error); }
        locationSubscriptionRef.current = null;
      }
      if (autocompleteTimeoutRef.current) clearTimeout(autocompleteTimeoutRef.current);
      if (fromAutocompleteTimeoutRef.current) clearTimeout(fromAutocompleteTimeoutRef.current);
      if (routeSearchTimeoutRef.current) clearTimeout(routeSearchTimeoutRef.current);
      Speech.stop();
    };
  }, []);

  const handleSearchRoute = useCallback(async () => {
    if (!toInput.trim()) {
      Alert.alert("Error", "Please enter a destination name");
      return;
    }
    if (routeSearchTimeoutRef.current) {
      clearTimeout(routeSearchTimeoutRef.current);
      routeSearchTimeoutRef.current = null;
    }
    setIsGeocoding(true);
    routeSearchTimeoutRef.current = setTimeout(async () => {
      try {
        const destResult = await geocodePlaceName(toInput.trim());
        const destCoords = { lat: destResult.lat, lng: destResult.lng, name: destResult.name };
        setDestination(destCoords);

        let originLatLng: { lat: number; lng: number };
        let originName: string;

        if (useCurrentLocation && currentLocation) {
          originLatLng = { lat: currentLocation.latitude, lng: currentLocation.longitude };
          originName = "Current Location";
          setOriginMode("current");
          setOriginCoords(null);
          setOrigin({ lat: originLatLng.lat, lng: originLatLng.lng, name: originName });
        } else if (fromInput.trim() && fromInput.trim().toLowerCase() !== "current location") {
          const fromResult = await geocodePlaceName(fromInput.trim());
          originLatLng = { lat: fromResult.lat, lng: fromResult.lng };
          originName = fromResult.name;
          setOriginMode("custom");
          setOriginCoords(originLatLng);
          setOrigin({ lat: originLatLng.lat, lng: originLatLng.lng, name: originName });
        } else {
          if (!currentLocation) {
            Alert.alert("Error", "Current location not available. Please enable location services or enter a starting point.");
            setIsGeocoding(false);
            return;
          }
          originLatLng = { lat: currentLocation.latitude, lng: currentLocation.longitude };
          originName = "Current Location";
          setOriginMode("current");
          setOriginCoords(null);
          setOrigin({ lat: originLatLng.lat, lng: originLatLng.lng, name: originName });
        }

        const options: RoutingOptions = {
          originLat: originLatLng.lat,
          originLng: originLatLng.lng,
          destLat: destCoords.lat,
          destLng: destCoords.lng,
          profile: "foot-walking",
        };

        const cacheKey = `${options.originLat.toFixed(4)},${options.originLng.toFixed(4)}_${options.destLat.toFixed(4)},${options.destLng.toFixed(4)}_${options.profile}`;
        let newRoute = routeCacheRef.current.get(cacheKey);

        if (!newRoute) {
          newRoute = await fetchRoute(options);
          routeCacheRef.current.set(cacheKey, newRoute);
          if (routeCacheRef.current.size > 10) {
            const firstKey = routeCacheRef.current.keys().next().value;
            routeCacheRef.current.delete(firstKey);
          }
        }

        if (!newRoute || !newRoute.steps || newRoute.steps.length === 0) {
          throw new Error("No route found. Please try different locations.");
        }

        const isMockRoute = (newRoute as any)._isMockRoute === true;
        if (isMockRoute) {
          Alert.alert("⚠️ Mock Route Warning", "This route uses a straight-line path that may cut through buildings.\n\nFor real road-following routes:\n• Set ORS_API_KEY environment variable, or\n• Ensure internet connectivity for OSM routing\n\nThis route is NOT suitable for actual navigation.", [{ text: "OK" }]);
        }

        setRoute(newRoute);
        routeRef.current = newRoute;
        setCurrentStepIndex(0);
        currentStepIndexRef.current = 0;
        setShowDestinationModal(false);
        setFromInput("Current Location");
        setToInput("");
        setUseCurrentLocation(true);
        if (isNavigating) stopNavigation();
        if (!isMockRoute) {
          Alert.alert("Success", `Route found! ${newRoute.steps.length} steps, ${Math.round(newRoute.totalDistance)}m total.`);
        }
      } catch (error: any) {
        const errorMessage = error.message || "Failed to find route. Please check your internet connection and try again.";
        Alert.alert("Error", errorMessage);
      } finally {
        setIsGeocoding(false);
        routeSearchTimeoutRef.current = null;
      }
    }, 400);
  }, [fromInput, toInput, useCurrentLocation, currentLocation, isNavigating, stopNavigation]);

  const handleToInputChange = useCallback((text: string) => {
    setToInput(text);
    setShowSuggestions(true);
    if (autocompleteTimeoutRef.current) clearTimeout(autocompleteTimeoutRef.current);
    if (text.trim().length >= 2) {
      autocompleteTimeoutRef.current = setTimeout(async () => {
        try {
          const suggestions = await getAutocompleteSuggestions(text.trim());
          setAutocompleteSuggestions(suggestions);
        } catch (error) {
          setAutocompleteSuggestions([]);
        }
      }, 300);
    } else {
      setAutocompleteSuggestions([]);
    }
  }, []);

  const handleSelectSuggestion = useCallback((suggestion: AutocompleteSuggestion) => {
    const displayText = formatSuggestion(suggestion);
    setToInput(displayText);
    setShowSuggestions(false);
    setAutocompleteSuggestions([]);
    setDestination({ lat: suggestion.lat, lng: suggestion.lng, name: suggestion.displayName });
  }, []);

  const handleFromInputChange = useCallback((text: string) => {
    setFromInput(text);
    if (text.trim().toLowerCase() === "current location" || text.trim() === "") {
      setShowFromSuggestions(false);
      setFromAutocompleteSuggestions([]);
      setUseCurrentLocation(true);
      return;
    }
    setUseCurrentLocation(false);
    setShowFromSuggestions(true);
    if (fromAutocompleteTimeoutRef.current) clearTimeout(fromAutocompleteTimeoutRef.current);
    if (text.trim().length >= 2) {
      fromAutocompleteTimeoutRef.current = setTimeout(async () => {
        try {
          const suggestions = await getAutocompleteSuggestions(text.trim());
          setFromAutocompleteSuggestions(suggestions);
        } catch (error) {
          setFromAutocompleteSuggestions([]);
        }
      }, 300);
    } else {
      setFromAutocompleteSuggestions([]);
    }
  }, []);

  const handleSelectFromSuggestion = useCallback((suggestion: AutocompleteSuggestion) => {
    const displayText = formatSuggestion(suggestion);
    setFromInput(displayText);
    setShowFromSuggestions(false);
    setFromAutocompleteSuggestions([]);
    setUseCurrentLocation(false);
    setOrigin({ lat: suggestion.lat, lng: suggestion.lng, name: suggestion.displayName });
    setOriginMode("custom");
    setOriginCoords({ lat: suggestion.lat, lng: suggestion.lng });
  }, []);

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
      if (finalText) setTimeout(() => { handleSearchRoute(); }, 500);
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

  const handleVoiceInput = useCallback(async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    if (isListeningDestination) {
      if (Platform.OS === "web") {
        if (recognitionRef.current) { try { recognitionRef.current.stop(); } catch {} }
      } else {
        try { await ExpoSpeechRecognitionModule.stop(); } catch (error) { console.error("Error stopping recognition:", error); }
      }
      setIsListeningDestination(false);
      nativeRecognitionResultRef.current = "";
      return;
    }

    if (Platform.OS === "web") {
      const W = globalThis as any;
      const SR = W.SpeechRecognition || W.webkitSpeechRecognition;
      if (!SR) {
        Alert.alert("Error", "Speech recognition is not available in this browser. Please use Chrome, Edge, or Safari.");
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
          for (let i = e.resultIndex; i < e.results.length; i++) text += e.results[i][0].transcript;
          const destinationText = text.trim();
          setToInput(destinationText);
          setIsListeningDestination(false);
          if (destinationText) setTimeout(() => { handleSearchRoute(); }, 500);
        };
        rec.onend = () => setIsListeningDestination(false);
        rec.onerror = (error: any) => {
          setIsListeningDestination(false);
          let errorMsg = "Speech recognition failed.";
          if (error.error === "no-speech") errorMsg = "No speech detected. Please try again.";
          else if (error.error === "not-allowed") errorMsg = "Microphone permission denied. Please allow microphone access and try again.";
          Alert.alert("Error", errorMsg);
        };
        setIsListeningDestination(true);
        rec.start();
      } catch (error) {
        Alert.alert("Error", "Failed to start speech recognition. Please try typing instead.");
      }
    } else {
      try {
        const permission = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
        if (!permission.granted) {
          Alert.alert("Permission Required", "Microphone and speech recognition permissions are required for voice input. Please enable them in your device settings.");
          return;
        }
        nativeRecognitionResultRef.current = "";
        setIsListeningDestination(true);
        await ExpoSpeechRecognitionModule.start({ lang: "en-US", interimResults: true, continuous: false });
      } catch (error: any) {
        setIsListeningDestination(false);
        const errorMsg = error?.message || "Failed to start speech recognition";
        Alert.alert("Error", `${errorMsg}. Please try typing instead.`);
      }
    }
  }, [isListeningDestination, handleSearchRoute]);

  const formatETA = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return secs > 0 ? `${minutes}m ${secs}s` : `${minutes}m`;
  };

  const currentStep = route?.steps[currentStepIndex];

  const progress = (() => {
    if (!route || !currentLocation || !destination) return 0;
    if (route.geometry && route.geometry.length > 0) {
      const remainingDistance = calculateRemainingDistance(currentLocation.latitude, currentLocation.longitude, route.geometry, destination.lat, destination.lng, SNAP_TO_ROUTE_THRESHOLD_M);
      const totalDistance = route.totalDistance || 0;
      if (totalDistance > 0) {
        const traveledDistance = totalDistance - remainingDistance;
        return Math.max(0, Math.min(100, Math.round((traveledDistance / totalDistance) * 100)));
      }
    }
    if (currentStepIndex > 0 && route.steps.length > 0) {
      const traveledSteps = route.steps.slice(0, currentStepIndex);
      const traveledDistance = traveledSteps.reduce((sum, s) => sum + s.distanceToNext, 0);
      const totalDistance = route.totalDistance || traveledDistance;
      if (totalDistance > 0) return Math.max(0, Math.min(100, Math.round((traveledDistance / totalDistance) * 100)));
    }
    return 0;
  })();

  return (
    <View style={styles.wrap}>
      <View style={styles.headerCard}>
        <View style={styles.headerContent}>
          <Text style={styles.headerSmall}>Exterior</Text>
          <Text style={styles.headerMain}>NAVIGATION</Text>
        </View>
        {destination && (
          <Pressable onPress={() => setShowDestinationModal(true)} style={styles.headerEditBtn}>
            <MaterialIcons name="edit-location" size={20} color={GOLD} />
          </Pressable>
        )}
      </View>

      <View style={styles.previewBox}>
        <View style={styles.mapInner}>
          <MapPanel
            currentLocation={currentLocation || undefined}
            routeSteps={route?.steps}
            routeGeometry={route?.geometry}
            destination={destination || undefined}
            showMap={settings.showMapVisuals}
          />
        </View>
      </View>

      {/* ─── Modernised Route Planning Modal ─── */}
      <Modal
        visible={showDestinationModal}
        transparent
        animationType="fade"
        onRequestClose={() => {
          setShowDestinationModal(false);
          setIsListeningDestination(false);
        }}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>

            {/* Header */}
            <View style={styles.modalHeader}>
              <MaterialIcons name="map" size={22} color={GOLD} />
              <Text style={styles.modalTitle}>Plan Route</Text>
            </View>

            <View style={styles.modalDivider} />

            <ScrollView
              style={styles.modalScrollView}
              contentContainerStyle={styles.modalScrollContent}
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator={false}
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
                      placeholder="Current Location"
                      placeholderTextColor="#6b7f99"
                      value={fromInput}
                      onChangeText={handleFromInputChange}
                      onFocus={() => {
                        if (fromInput.trim().length >= 2 && fromInput.trim().toLowerCase() !== "current location" && fromAutocompleteSuggestions.length > 0) {
                          setShowFromSuggestions(true);
                        }
                      }}
                      onBlur={() => { setTimeout(() => setShowFromSuggestions(false), 200); }}
                      autoCapitalize="words"
                    />
                    {showFromSuggestions && fromAutocompleteSuggestions.length > 0 && (
                      <View style={styles.suggestionsContainer}>
                        <ScrollView nestedScrollEnabled keyboardShouldPersistTaps="handled" style={styles.suggestionsScrollView}>
                          {fromAutocompleteSuggestions.map((suggestion, index) => (
                            <Pressable
                              key={`from-${suggestion.lat}-${suggestion.lng}-${index}`}
                              style={styles.suggestionItem}
                              onPress={() => handleSelectFromSuggestion(suggestion)}
                            >
                              <MaterialIcons name="place" size={18} color={GOLD} />
                              <View style={styles.suggestionTextContainer}>
                                <Text style={styles.suggestionName}>{formatSuggestion(suggestion)}</Text>
                                <Text style={styles.suggestionAddress} numberOfLines={1}>{suggestion.displayName}</Text>
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

              {/* Connector Line */}
              <View style={styles.routeConnector}>
                <View style={styles.connectorLine} />
                <MaterialIcons name="arrow-downward" size={16} color={GOLD} />
                <View style={styles.connectorLine} />
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
                      placeholderTextColor="#6b7f99"
                      value={toInput}
                      onChangeText={handleToInputChange}
                      onFocus={() => {
                        if (toInput.trim().length >= 2 && autocompleteSuggestions.length > 0) setShowSuggestions(true);
                      }}
                      onBlur={() => { setTimeout(() => setShowSuggestions(false), 200); }}
                      autoCapitalize="words"
                    />
                    {showSuggestions && autocompleteSuggestions.length > 0 && (
                      <View style={styles.suggestionsContainer}>
                        <ScrollView nestedScrollEnabled keyboardShouldPersistTaps="handled" style={styles.suggestionsScrollView}>
                          {autocompleteSuggestions.map((suggestion, index) => (
                            <Pressable
                              key={`${suggestion.lat}-${suggestion.lng}-${index}`}
                              style={styles.suggestionItem}
                              onPress={() => handleSelectSuggestion(suggestion)}
                            >
                              <MaterialIcons name="place" size={18} color={GOLD} />
                              <View style={styles.suggestionTextContainer}>
                                <Text style={styles.suggestionName}>{formatSuggestion(suggestion)}</Text>
                                <Text style={styles.suggestionAddress} numberOfLines={1}>{suggestion.displayName}</Text>
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
                  <Text style={styles.listeningHint}>🎙 Listening… speak your destination</Text>
                )}
                <Text style={styles.hintText}>Tap 🎤 to speak destination (optional)</Text>
              </View>

              {/* Route Preview */}
              {(origin || destination) && (
                <View style={styles.previewContainer}>
                  {origin && (
                    <View style={styles.previewRow}>
                      <MaterialIcons name="radio-button-checked" size={16} color={GOLD} />
                      <Text style={styles.previewText}>
                        {origin.name || `${origin.lat.toFixed(4)}, ${origin.lng.toFixed(4)}`}
                        {originMode === "custom" && <Text style={styles.previewModeText}> (custom)</Text>}
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

              {!toInput.trim() && (
                <Text style={styles.errorText}>⚠ Destination is required.</Text>
              )}
            </ScrollView>

            <View style={styles.modalDivider} />

            {/* Buttons */}
            <View style={styles.modalButtons}>
              <Pressable
                style={styles.cancelButton}
                onPress={() => {
                  setShowDestinationModal(false);
                  setIsListeningDestination(false);
                }}
              >
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </Pressable>
              <Pressable
                style={[styles.confirmButton, (!toInput.trim() || isGeocoding) && styles.confirmButtonDisabled]}
                onPress={handleSearchRoute}
                disabled={isGeocoding || !toInput.trim()}
              >
                <MaterialIcons name="search" size={18} color="#1B263B" />
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
          <Text style={styles.instructionText}>{currentStep.instructionText}</Text>
          {currentStep.roadName && <Text style={styles.roadNameText}>{currentStep.roadName}</Text>}
          <View style={styles.statsRow}>
            <Text style={styles.distanceText}>
              {(() => {
                if (currentStep.maneuverType === 'arrive' && destination && currentLocation) {
                  const distanceToDest = metersBetween(currentLocation.latitude, currentLocation.longitude, destination.lat, destination.lng);
                  if (distanceToDest <= DESTINATION_ARRIVAL_THRESHOLD_M) return "You have arrived at your destination";
                }
                if (currentStep.distanceToNext > 0) return `${Math.round(currentStep.distanceToNext)}m to ${currentStep.maneuverType === 'arrive' ? 'destination' : 'turn'}`;
                return "Calculating distance...";
              })()}
            </Text>
            {eta !== null && eta > 0 && <Text style={styles.etaText}>ETA: {formatETA(eta)}</Text>}
          </View>
          {route && <Text style={styles.progressText}>{progress}% completed</Text>}
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
                <MaterialIcons name={originMode === "custom" ? "place" : "my-location"} size={14} color={GOLD} />
                <Text style={styles.navOriginText}>
                  Nav Origin: {originMode === "custom" && originCoords ? `Planned (${origin?.name || "Custom"})` : "Live GPS"}
                </Text>
              </View>
              {origin && origin.name !== "Current Location" && (
                <Text style={styles.destinationInfo}>From: {origin.name || `${origin.lat.toFixed(4)}, ${origin.lng.toFixed(4)}`}</Text>
              )}
              <Text style={styles.destinationInfo}>To: {destination.name || `${destination.lat.toFixed(4)}, ${destination.lng.toFixed(4)}`}</Text>
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

  headerCard: {
    marginHorizontal: 16,
    marginTop: 14,
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 20,
    backgroundColor: "#12304d",
    shadowColor: "#000",
    shadowOpacity: 0.22,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 8,
    position: "relative",
  },
  headerContent: { alignItems: "center", justifyContent: "center" },
  headerSmall: { color: "#d1d5db", fontSize: 15, fontWeight: "700", marginBottom: 6 },
  headerMain: { color: GOLD, fontSize: 22, fontWeight: "900", letterSpacing: 0.8 },
  headerEditBtn: {
    position: "absolute", right: 14, top: 14,
    width: 40, height: 40, borderRadius: 12,
    alignItems: "center", justifyContent: "center",
    backgroundColor: "#10233d", borderWidth: 1.5,
    borderColor: "rgba(249,178,51,0.45)",
  },
  headerDestinationBtn: { padding: 8 },

  mapInner: { flex: 1, width: "100%", height: "100%" },
  previewBox: {
    height: SCREEN_H * 0.5,
    marginHorizontal: 16, marginTop: 16,
    borderRadius: 22, overflow: "hidden",
    backgroundColor: "#243247",
    borderWidth: 2, borderColor: "rgba(249,178,51,0.85)",
    shadowColor: GOLD, shadowOpacity: 0.28,
    shadowRadius: 18, shadowOffset: { width: 0, height: 4 },
    elevation: 10, position: "relative",
  },

  instructionCard: {
    backgroundColor: "#242424", marginHorizontal: 16,
    marginVertical: 12, padding: 16,
    borderRadius: 10, borderWidth: 1, borderColor: GOLD,
  },
  instructionText: { color: GOLD, fontSize: 18, fontWeight: "700", marginBottom: 8 },
  statsRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  distanceText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  etaText: { color: GOLD, fontSize: 16, fontWeight: "600" },
  progressText: { color: GOLD, fontSize: 14, fontWeight: "600", marginTop: 8 },
  roadNameText: { color: "#fff", fontSize: 14, fontWeight: "500", marginTop: 4, fontStyle: "italic" },
  destinationInfo: { color: "#aaa", fontSize: 12, marginTop: 4 },
  navOriginIndicator: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 8, marginBottom: 4 },
  navOriginText: { color: GOLD, fontSize: 12, fontWeight: "600", fontStyle: "italic" },

  controlBar: { paddingHorizontal: 16, paddingBottom: 20, flexDirection: "row", gap: 12 },
  controlBtn: { flexDirection: "row", alignItems: "center", justifyContent: "center", paddingVertical: 16, borderRadius: 10, gap: 8, flex: 1 },
  startBtn: { backgroundColor: GOLD, flex: 2 },
  startBtnText: { color: "#1B263B", fontSize: 18, fontWeight: "800" },
  stopBtn: { backgroundColor: "transparent", borderWidth: 2, borderColor: GOLD },
  stopBtnText: { color: GOLD, fontSize: 18, fontWeight: "800" },
  destinationBtn: { backgroundColor: "transparent", borderWidth: 2, borderColor: GOLD },
  destinationBtnText: { color: GOLD, fontSize: 14, fontWeight: "700" },

  // ─── Modal ───
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.75)",
    justifyContent: "center",
    alignItems: "center",
  },
  modalContent: {
    backgroundColor: "#0f1e2e",
    borderRadius: 28,
    width: "88%",
    maxWidth: 420,
    maxHeight: "90%",
    borderWidth: 1.5,
    borderColor: "rgba(249,178,51,0.5)",
    overflow: "hidden",
    shadowColor: GOLD,
    shadowOpacity: 0.2,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 8 },
    elevation: 16,
  },
  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    paddingTop: 24,
    paddingBottom: 16,
    paddingHorizontal: 24,
  },
  modalTitle: {
    color: GOLD,
    fontSize: 20,
    fontWeight: "900",
    letterSpacing: 0.5,
  },
  modalDivider: {
    height: 1,
    backgroundColor: "rgba(249,178,51,0.2)",
    marginHorizontal: 0,
  },
  modalScrollView: { maxHeight: 460 },
  modalScrollContent: { padding: 24, paddingBottom: 8 },

  inputGroup: { marginBottom: 12 },
  inputGroupWithSuggestions: { marginBottom: 160 },

  inputLabel: {
    color: "#9bb0cc",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.8,
    textTransform: "uppercase",
    marginBottom: 8,
  },
  inputWithMic: { flexDirection: "row", alignItems: "center", gap: 10 },
  inputContainer: { position: "relative", flex: 1 },
  input: {
    backgroundColor: "#162233",
    borderWidth: 1.5,
    borderColor: "rgba(249,178,51,0.35)",
    borderRadius: 14,
    paddingVertical: 13,
    paddingHorizontal: 16,
    color: "#e8eef6",
    fontSize: 15,
    fontWeight: "600",
  },
  inputFlex: { flex: 1 },

  iconButton: {
    width: 46,
    height: 46,
    borderRadius: 14,
    borderWidth: 1.5,
    borderColor: "rgba(249,178,51,0.45)",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#162233",
  },
  iconButtonActive: { backgroundColor: GOLD },

  hintText: { color: "#5a7a99", fontSize: 11, marginTop: 6, fontWeight: "500" },
  listeningHint: {
    color: GOLD, fontSize: 12, marginTop: 6,
    fontStyle: "italic", fontWeight: "600",
  },

  routeConnector: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginVertical: 6,
  },
  connectorLine: {
    flex: 1,
    height: 1,
    backgroundColor: "rgba(249,178,51,0.2)",
  },

  suggestionsContainer: {
    position: "absolute", top: "100%", left: 0, right: 0,
    backgroundColor: "#0f1e2e",
    borderRadius: 14, borderWidth: 1.5,
    borderColor: "rgba(249,178,51,0.4)",
    marginTop: 6, maxHeight: 150,
    zIndex: 9999, elevation: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.5, shadowRadius: 6,
    overflow: "hidden",
  },
  suggestionsScrollView: { maxHeight: 200 },
  suggestionItem: {
    flexDirection: "row", alignItems: "center",
    padding: 12, borderBottomWidth: 1,
    borderBottomColor: "rgba(255,255,255,0.06)", gap: 12,
  },
  suggestionTextContainer: { flex: 1 },
  suggestionName: { color: "#e8eef6", fontSize: 14, fontWeight: "600", marginBottom: 2 },
  suggestionAddress: { color: "#6b7f99", fontSize: 12 },

  previewContainer: {
    backgroundColor: "#162233",
    padding: 14, borderRadius: 14,
    marginTop: 4, marginBottom: 8,
    borderWidth: 1, borderColor: "rgba(249,178,51,0.25)",
    gap: 8,
  },
  previewRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  previewText: { color: "#e8eef6", fontSize: 13, fontWeight: "600", flex: 1 },
  previewModeText: { color: "#6b7f99", fontSize: 12, fontStyle: "italic" },

  errorText: { color: "#ff6b6b", fontSize: 12, marginTop: 4, fontWeight: "600" },

  modalButtons: {
    flexDirection: "row",
    gap: 12,
    padding: 20,
    paddingTop: 16,
  },
  cancelButton: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#162233",
    borderWidth: 1.5,
    borderColor: "rgba(249,178,51,0.3)",
  },
  cancelButtonText: { color: "#9bb0cc", fontSize: 15, fontWeight: "700" },
  confirmButton: {
    flex: 2,
    flexDirection: "row",
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: GOLD,
    gap: 8,
    shadowColor: GOLD,
    shadowOpacity: 0.4,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  confirmButtonDisabled: { opacity: 0.5 },
  confirmButtonText: { color: "#1B263B", fontSize: 15, fontWeight: "900" },

  micButton: {
    width: 44, height: 44, borderRadius: 22,
    borderWidth: 2, borderColor: GOLD,
    alignItems: "center", justifyContent: "center",
    backgroundColor: "transparent",
  },
  micButtonActive: { backgroundColor: GOLD },
});