import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState, useRef, useCallback } from "react";
import {
  ActivityIndicator,
  Image,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Audio } from "expo-av";
import Slider from "@react-native-community/slider";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useFocusEffect } from "@react-navigation/native";
import * as Speech from "expo-speech";
import { API_BASE } from "@/src/config";
import { addToHistory } from "@/src/utils/audiobookStorage";
import { speakWeb, stopWebSpeech } from "@/src/utils/webTTS";

interface Chapter {
  id: string;
  title: string;
  duration: number;
  duration_formatted: string;
  audio_url: string;
}

interface BookDetails {
  id: string;
  title: string;
  author: string;
  duration: number;
  duration_formatted: string;
  language: string;
  description: string;
  cover_url: string;
  chapters: Chapter[];
}

const STORAGE_KEY_PREFIX = "@audiobook_progress_";
const SPEED_OPTIONS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

export default function AudiobookPlayerScreen() {
  const params = useLocalSearchParams<{
    bookId: string;
    title: string;
    author: string;
    coverUrl: string;
  }>();
  
  // Extract params with proper handling for arrays (expo-router sometimes returns arrays)
  const bookId = Array.isArray(params.bookId) ? params.bookId[0] : params.bookId;
  const paramTitle = Array.isArray(params.title) ? params.title[0] : params.title;
  const paramAuthor = Array.isArray(params.author) ? params.author[0] : params.author;
  const coverUrl = Array.isArray(params.coverUrl) ? params.coverUrl[0] : params.coverUrl;

  console.log("Player params:", { bookId, title: paramTitle, author: paramAuthor });

  const [bookDetails, setBookDetails] = useState<BookDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [playbackError, setPlaybackError] = useState<string | null>(null);

  const [sound, setSound] = useState<Audio.Sound | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoadingAudio, setIsLoadingAudio] = useState(false);
  const [currentChapterIndex, setCurrentChapterIndex] = useState(0);
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1.0);
  const [showSpeedMenu, setShowSpeedMenu] = useState(false);
  const [coverLoadError, setCoverLoadError] = useState(false);

  const positionUpdateInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);
  const titleAnnouncedRef = useRef<string | null>(null); // Track which title was already announced

  // Validate bookId exists
  useEffect(() => {
    if (!bookId) {
      console.error("No bookId provided in params");
      setError("No book ID provided. Please select a book from the search results.");
      setLoading(false);
      return;
    }
  }, [bookId]);

  // Configure audio mode once on mount
  useEffect(() => {
    const configureAudio = async () => {
      try {
        await Audio.setAudioModeAsync({
          playsInSilentModeIOS: true,
          staysActiveInBackground: true,
          shouldDuckAndroid: true,
        });
      } catch (err) {
        console.warn("Error configuring audio mode:", err);
      }
    };
    configureAudio();
  }, []);

  // Load book details when bookId changes
  useEffect(() => {
    if (!bookId) {
      return;
    }

    // Cleanup function to stop audio when bookId changes (only on bookId change, not sound change)
    return () => {
      const currentSound = soundRef.current || sound;
      if (currentSound) {
        currentSound.unloadAsync().catch(console.warn);
        setSound(null);
        soundRef.current = null;
      }
      if (positionUpdateInterval.current) {
        clearInterval(positionUpdateInterval.current);
        positionUpdateInterval.current = null;
      }
      setIsPlaying(false);
      stopPositionUpdates();
    };
  }, [bookId]); // Removed 'sound' from deps to prevent cleanup on every sound change

  // Load book details when bookId is available
  useEffect(() => {
    if (bookId) {
      // Reset title announcement flag when bookId changes
      titleAnnouncedRef.current = null;
      loadBookDetails(bookId);
    }
  }, [bookId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Function to announce the title and author for visually impaired users
  const spellOutTitle = useCallback((title: string, author?: string) => {
    // Clean title: remove extra spaces
    const cleanTitle = title.trim().replace(/\s+/g, " ");
    const cleanAuthor = author ? author.trim().replace(/\s+/g, " ") : "";
    
    // Create announcement text: "You are listening to Title by Author" format
    const announcementText = cleanAuthor
      ? `You are listening to ${cleanTitle} by ${cleanAuthor}`
      : `You are listening to ${cleanTitle}`;
    
    if (Platform.OS === "web") {
      // Web: Use webTTS
      stopWebSpeech(); // Stop any current speech
      
      // Announce the book title and author
      speakWeb(announcementText, { rate: 0.9 });
    } else {
      // Native: Use expo-speech
      Speech.stop(); // Stop any current speech
      
      // Announce the book title and author
      Speech.speak(announcementText, {
        rate: 0.9,
        pitch: 1.0,
        onError: (error) => {
          console.error("[TTS] Error speaking title:", error);
        },
      });
    }
  }, []);

  useEffect(() => {
    if (bookDetails && bookDetails.chapters.length > 0) {
      loadProgress();
    }
  }, [bookDetails]);

  // Spell out the audiobook title for visually impaired users when book loads
  useEffect(() => {
    if (bookDetails && bookDetails.title) {
      // Only announce if this is a new title (not already announced)
      if (titleAnnouncedRef.current !== bookDetails.title) {
        titleAnnouncedRef.current = bookDetails.title;
        
        // Small delay to ensure screen is ready
        const timer = setTimeout(() => {
          spellOutTitle(bookDetails.title, bookDetails.author);
        }, 800); // Slightly longer delay for better UX
        
        return () => clearTimeout(timer);
      }
    }
  }, [bookDetails, spellOutTitle]);

  // Stop audio when screen loses focus (user navigates away)
  useFocusEffect(
    useCallback(() => {
      // This runs when screen comes into focus
      return () => {
        // This runs when screen loses focus (user navigates away)
        const currentSound = soundRef.current;
        if (currentSound) {
          currentSound.pauseAsync().catch(console.warn);
          currentSound.unloadAsync().catch(console.warn);
          soundRef.current = null;
        }
        if (positionUpdateInterval.current) {
          clearInterval(positionUpdateInterval.current);
          positionUpdateInterval.current = null;
        }
        setIsPlaying(false);
      };
    }, [])
  );

  // Cleanup audio on unmount only (not on every sound change)
  useEffect(() => {
    return () => {
      // Only cleanup on component unmount, not when sound changes
      // This prevents interrupting playback when sound is updated
      const currentSound = soundRef.current;
      if (currentSound) {
        currentSound.unloadAsync().catch(console.warn);
        soundRef.current = null;
      }
      if (positionUpdateInterval.current) {
        clearInterval(positionUpdateInterval.current);
        positionUpdateInterval.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty deps = only run on mount/unmount

  const loadBookDetails = async (currentBookId?: string) => {
    // Use provided bookId or fall back to state bookId
    const idToLoad = currentBookId || bookId;
    
    // Validate bookId before fetching
    if (!idToLoad) {
      console.error("loadBookDetails called without bookId");
      setError("No book ID provided");
      setLoading(false);
      return;
    }

    try {
      // Clear previous state before loading new book
      setBookDetails(null);
      setError(null);
      setPlaybackError(null);
      setLoading(true);
      
      // Stop any currently playing audio
      const currentSound = soundRef.current || sound;
      if (currentSound) {
        try {
          await currentSound.unloadAsync();
          setSound(null);
          soundRef.current = null;
          setIsPlaying(false);
        } catch (unloadErr) {
          console.warn("Error unloading previous sound:", unloadErr);
        }
      }
      
      // Reset playback state
      setCurrentChapterIndex(0);
      setPosition(0);
      setDuration(0);
      stopPositionUpdates();

      console.log(`Fetching book details for bookId: ${idToLoad}`);
      const response = await fetch(`${API_BASE}/audiobooks/${idToLoad}`);

      if (!response.ok) {
        // Try to extract backend error detail for better error messages
        let detail = "";
        try {
          const errorData = await response.json();
          detail = errorData?.detail ? ` (${errorData.detail})` : "";
        } catch {
          // If JSON parsing fails, use status text
          detail = response.statusText ? ` (${response.statusText})` : "";
        }
        throw new Error(`HTTP ${response.status}${detail}`);
      }

      const data: BookDetails = await response.json();
      console.log(`Loaded book details: ${data.title} by ${data.author} (ID: ${data.id})`);
      
      // Verify the loaded book matches the requested bookId
      if (data.id !== idToLoad && String(data.id) !== String(idToLoad)) {
        console.warn(`Book ID mismatch! Requested: ${idToLoad}, Got: ${data.id}`);
        // Still set the data, but log the warning
      }
      
      // Only set state if bookId hasn't changed during fetch
      if (bookId === idToLoad) {
        setBookDetails(data);
      } else {
        console.log(`BookId changed during fetch. Ignoring response for ${idToLoad}`);
      }
    } catch (err) {
      console.error("Error loading book details:", err);
      // Only set error if bookId hasn't changed
      if (bookId === idToLoad) {
        setError(err instanceof Error ? err.message : "Failed to load audiobook");
      }
    } finally {
      // Only update loading state if bookId hasn't changed
      if (bookId === idToLoad) {
        setLoading(false);
      }
    }
  };

  const loadProgress = async () => {
    try {
      const storageKey = `${STORAGE_KEY_PREFIX}${bookId}`;
      const saved = await AsyncStorage.getItem(storageKey);
      if (saved) {
        const progress = JSON.parse(saved);
        if (progress.chapterIndex !== undefined && progress.position !== undefined) {
          setCurrentChapterIndex(progress.chapterIndex);
          // Position is stored in seconds, convert to milliseconds
          setPosition(progress.position * 1000);
        }
      }
    } catch (err) {
      console.error("Error loading progress:", err);
    }
  };

  const saveProgress = async (chapterIndex: number, position: number) => {
    try {
      const storageKey = `${STORAGE_KEY_PREFIX}${bookId}`;
      await AsyncStorage.setItem(
        storageKey,
        JSON.stringify({ chapterIndex, position, timestamp: Date.now() })
      );
    } catch (err) {
      console.error("Error saving progress:", err);
    }
  };

  const loadAudio = async (chapterIndex: number, startPosition: number = 0): Promise<Audio.Sound | null> => {
    if (!bookDetails || !bookDetails.chapters[chapterIndex]) {
      console.error("No book details or chapter not found");
      return null;
    }

    setIsLoadingAudio(true);
    try {
      // Unload previous sound BEFORE creating new one (prevents multiple sounds)
      // Store reference to avoid race conditions with useEffect cleanup
      const previousSound = sound;
      if (previousSound) {
        try {
          // Pause first to avoid "interrupted" errors
          const prevStatus = await previousSound.getStatusAsync();
          if (prevStatus.isLoaded && prevStatus.isPlaying) {
            await previousSound.pauseAsync();
          }
          await previousSound.unloadAsync();
        } catch (unloadErr) {
          console.warn("Error unloading previous sound:", unloadErr);
        }
      }
      // Clear sound state immediately to prevent useEffect cleanup from interfering
      setSound(null);
      soundRef.current = null;

      const chapter = bookDetails.chapters[chapterIndex];
      let audioUrl = chapter.audio_url;

      if (!audioUrl || audioUrl.trim() === '') {
        console.error("No audio URL for chapter:", chapter);
        setPlaybackError("No audio URL available for this chapter. Please try selecting a different chapter.");
        return null;
      }

      // Clean up the URL
      audioUrl = audioUrl.trim();
      
      console.log("Original audio URL:", audioUrl);
      
      // Try direct URL first (expo-av supports MP3 URLs directly)
      // Only use proxy if direct fails (for CORS issues on web) or if URL doesn't look like a direct audio file
      let finalUrl = audioUrl;
      let useProxy = false;
      
      // Check if URL looks like it might need proxy (not a direct MP3 link)
      // LibriVox URLs from archive.org should work directly, but use proxy for web CORS issues
      const isDirectAudioUrl = audioUrl.toLowerCase().endsWith('.mp3') || 
                               audioUrl.includes('archive.org/download') ||
                               audioUrl.includes('archive.org/stream');
      
      // On web, always use proxy for CORS issues
      if (Platform.OS === 'web') {
        useProxy = true;
        finalUrl = `${API_BASE}/audiobooks/stream?url=${encodeURIComponent(audioUrl)}`;
      } else if (!isDirectAudioUrl) {
        // On mobile, use proxy if URL doesn't look like a direct audio file
        useProxy = true;
        finalUrl = `${API_BASE}/audiobooks/stream?url=${encodeURIComponent(audioUrl)}`;
      }
      
      console.log("Attempting to load from:", finalUrl.substring(0, 200));
      console.log("Using proxy:", useProxy);

      // Try to load the audio
      let newSound: Audio.Sound;
      try {
        const result = await Audio.Sound.createAsync(
          { 
            uri: finalUrl,
            overrideFileExtensionAndroid: 'mp3',
          },
          {
            shouldPlay: false,
            positionMillis: startPosition * 1000,
            rate: playbackRate,
          },
          (status) => {
            if (status.isLoaded) {
              setDuration(status.durationMillis || 0);
              setPosition(status.positionMillis || 0);

              if (status.didJustFinish) {
                // Move to next chapter if available
                if (chapterIndex < bookDetails.chapters.length - 1) {
                  playChapter(chapterIndex + 1, 0);
                } else {
                  setIsPlaying(false);
                }
              }
            } else if (status.error) {
              console.error("Audio status error:", status.error);
              setPlaybackError(`Audio error: ${status.error}`);
            }
          }
        );
        newSound = result.sound;
      } catch (directError) {
        console.error("Direct URL failed, trying proxy:", directError);
        
        // If direct URL failed and we didn't use proxy, try proxy now
        if (!useProxy) {
          try {
            const proxyUrl = `${API_BASE}/audiobooks/stream?url=${encodeURIComponent(audioUrl)}`;
            console.log("Trying proxy URL:", proxyUrl.substring(0, 200));
            
            const proxyResult = await Audio.Sound.createAsync(
              { 
                uri: proxyUrl,
                overrideFileExtensionAndroid: 'mp3',
              },
              {
                shouldPlay: false,
                positionMillis: startPosition * 1000,
                rate: playbackRate,
              },
              (status) => {
                if (status.isLoaded) {
                  setDuration(status.durationMillis || 0);
                  setPosition(status.positionMillis || 0);
                  if (status.didJustFinish) {
                    if (chapterIndex < bookDetails.chapters.length - 1) {
                      playChapter(chapterIndex + 1, 0);
                    } else {
                      setIsPlaying(false);
                    }
                  }
                } else if (status.error) {
                  console.error("Proxy audio error:", status.error);
                  setPlaybackError(`Audio error: ${status.error}`);
                }
              }
            );
            newSound = proxyResult.sound;
            useProxy = true;
            finalUrl = proxyUrl;
          } catch (proxyError) {
            console.error("Both direct and proxy failed:", proxyError);
            throw proxyError;
          }
        } else {
          throw directError;
        }
      }

      // Check status immediately - no delay needed for streaming
      const status = await newSound.getStatusAsync();
      
      if (!status.isLoaded) {
        console.error("Sound not loaded after creation:", status);
        const errorMsg = status.error || "Unknown error";
        setPlaybackError(`Failed to load audio: ${errorMsg}. URL: ${finalUrl.substring(0, 100)}...`);
        await newSound.unloadAsync();
        return null;
      }
      
      // Clear any previous playback errors on successful load
      setPlaybackError(null);

      console.log("Audio loaded successfully. Duration:", status.durationMillis, "ms");
      
      // Set sound state AFTER ensuring it's loaded (prevents cleanup race conditions)
      setSound(newSound);
      soundRef.current = newSound; // Also update ref for cleanup
      setCurrentChapterIndex(chapterIndex);
      setDuration(status.durationMillis || 0);
      setPosition(startPosition * 1000);
      
      return newSound;
    } catch (err) {
      console.error("Error loading audio:", err);
      const errorMessage = err instanceof Error ? err.message : "Unknown error";
      
      // Provide more helpful error messages
      let userFriendlyError = "Failed to load audio. ";
      if (errorMessage.includes("Network") || errorMessage.includes("fetch")) {
        userFriendlyError += "Please check your internet connection.";
      } else if (errorMessage.includes("404") || errorMessage.includes("Not Found")) {
        userFriendlyError += "Audio file not found. The chapter URL may be invalid.";
      } else if (errorMessage.includes("CORS") || errorMessage.includes("cross-origin")) {
        userFriendlyError += "CORS error. Trying proxy...";
      } else {
        userFriendlyError += `Error: ${errorMessage}. Please try selecting a different chapter.`;
      }
      
      // Provide more specific error messages
      if (errorMessage.includes("503") || errorMessage.includes("Service Unavailable")) {
        userFriendlyError = "Archive.org service is temporarily unavailable. Please try again in a few moments.";
      } else if (errorMessage.includes("502") || errorMessage.includes("Bad Gateway")) {
        userFriendlyError = "Unable to connect to audio server. The file may be temporarily unavailable. Please try again.";
      } else if (errorMessage.includes("404") || errorMessage.includes("Not Found")) {
        userFriendlyError = "Audio file not found. The chapter may have been removed or the URL is incorrect.";
      } else if (errorMessage.includes("Network") || errorMessage.includes("fetch")) {
        userFriendlyError = "Network error. Please check your internet connection and try again.";
      }
      
      setPlaybackError(userFriendlyError);
      return null;
    } finally {
      setIsLoadingAudio(false);
    }
  };

  const playChapter = async (chapterIndex: number, startPosition: number = 0) => {
    try {
      setPlaybackError(null);
      
      // Atomic chapter switch: unload previous, load new, play immediately
      // loadAudio handles setIsLoadingAudio state
      const loadedSound = await loadAudio(chapterIndex, startPosition);
      if (loadedSound) {
        // Check sound is loaded before playing
        const status = await loadedSound.getStatusAsync();
        if (status.isLoaded) {
          // Start playback immediately - no delays
          try {
            await loadedSound.playAsync();
            setIsPlaying(true);
            startPositionUpdates();
            setIsLoadingAudio(false);
            console.log("Playback started immediately");
            
            // Add to history asynchronously (don't block playback)
            if (bookDetails) {
              addToHistory({
                id: bookDetails.id,
                title: bookDetails.title,
                author: bookDetails.author,
                duration: bookDetails.duration,
                duration_formatted: bookDetails.duration_formatted,
                language: bookDetails.language,
                description: bookDetails.description,
                cover_url: bookDetails.cover_url,
              }).catch((historyError) => {
                console.error("Failed to add to history:", historyError);
              });
            }
          } catch (playError: any) {
            // If play fails, try once more immediately (no delay)
            if (playError?.message?.includes("interrupted") || playError?.message?.includes("pause")) {
              console.warn("Play was interrupted, retrying immediately...");
              try {
                await loadedSound.playAsync();
                setIsPlaying(true);
                startPositionUpdates();
                setIsLoadingAudio(false);
                console.log("Playback started on retry");
                
                // Add to history asynchronously
                if (bookDetails) {
                  addToHistory({
                    id: bookDetails.id,
                    title: bookDetails.title,
                    author: bookDetails.author,
                    duration: bookDetails.duration,
                    duration_formatted: bookDetails.duration_formatted,
                    language: bookDetails.language,
                    description: bookDetails.description,
                    cover_url: bookDetails.cover_url,
                  }).catch((historyError) => {
                    console.error("Failed to add to history:", historyError);
                  });
                }
              } catch (retryError) {
                console.error("Retry play failed:", retryError);
                setPlaybackError("Failed to start playback. Please try again.");
                setIsLoadingAudio(false);
              }
            } else {
              console.error("Play failed:", playError);
              setPlaybackError("Failed to start playback. Please try again.");
              setIsLoadingAudio(false);
            }
          }
        } else {
          console.error("Sound not loaded, cannot play");
          setPlaybackError("Audio is not ready. Please try again.");
          setIsLoadingAudio(false);
        }
      } else {
        console.error("Failed to load sound");
        setPlaybackError("Failed to load audio. Please check the chapter URL.");
        setIsLoadingAudio(false);
      }
    } catch (err) {
      console.error("Error in playChapter:", err);
      setPlaybackError(err instanceof Error ? err.message : "Failed to play audio");
      setIsLoadingAudio(false);
    }
  };

  const togglePlayPause = async () => {
    if (!sound) {
      if (bookDetails && bookDetails.chapters.length > 0) {
        await playChapter(currentChapterIndex, position / 1000);
      } else {
        setPlaybackError("No audio loaded. Please select a chapter.");
      }
      return;
    }

    try {
      // Check if sound is loaded
      const status = await sound.getStatusAsync();
      if (!status.isLoaded) {
        console.error("Sound not loaded, reloading...");
        await playChapter(currentChapterIndex, position / 1000);
        return;
      }

      if (isPlaying) {
        await sound.pauseAsync();
        setIsPlaying(false);
        stopPositionUpdates();
      } else {
        // Start playback immediately - no delays
        try {
          await sound.playAsync();
          setIsPlaying(true);
          startPositionUpdates();
          
          // Add to history asynchronously (don't block playback)
          if (bookDetails) {
            addToHistory({
              id: bookDetails.id,
              title: bookDetails.title,
              author: bookDetails.author,
              duration: bookDetails.duration,
              duration_formatted: bookDetails.duration_formatted,
              language: bookDetails.language,
              description: bookDetails.description,
              cover_url: bookDetails.cover_url,
            }).catch((historyError) => {
              console.error("Failed to add to history:", historyError);
            });
          }
        } catch (playError: any) {
          // Handle "play() interrupted by pause()" error - retry immediately
          if (playError?.message?.includes("interrupted") || playError?.message?.includes("pause")) {
            console.warn("Play was interrupted, retrying immediately...");
            try {
              await sound.playAsync();
              setIsPlaying(true);
              startPositionUpdates();
              
              // Add to history asynchronously
              if (bookDetails) {
                addToHistory({
                  id: bookDetails.id,
                  title: bookDetails.title,
                  author: bookDetails.author,
                  duration: bookDetails.duration,
                  duration_formatted: bookDetails.duration_formatted,
                  language: bookDetails.language,
                  description: bookDetails.description,
                  cover_url: bookDetails.cover_url,
                }).catch((historyError) => {
                  console.error("Failed to add to history:", historyError);
                });
              }
            } catch (retryError) {
              console.error("Retry play failed:", retryError);
              setPlaybackError("Failed to start playback. Please try again.");
            }
          } else {
            throw playError;
          }
        }
      }
    } catch (err) {
      console.error("Error toggling play/pause:", err);
      setPlaybackError(err instanceof Error ? err.message : "Failed to play/pause audio");
      // Try to reload if there's an error
      if (bookDetails && bookDetails.chapters.length > 0) {
        await playChapter(currentChapterIndex, position / 1000);
      }
    }
  };

  const seekTo = async (value: number) => {
    if (sound) {
      try {
        await sound.setPositionAsync(value);
        setPosition(value);
        await saveProgress(currentChapterIndex, value / 1000);
      } catch (err) {
        console.error("Error seeking:", err);
      }
    }
  };

  const changeSpeed = async (speed: number) => {
    setPlaybackRate(speed);
    if (sound) {
      try {
        await sound.setRateAsync(speed, true);
      } catch (err) {
        console.error("Error changing speed:", err);
      }
    }
    setShowSpeedMenu(false);
  };

  const startPositionUpdates = () => {
    if (positionUpdateInterval.current) {
      clearInterval(positionUpdateInterval.current);
    }
    positionUpdateInterval.current = setInterval(async () => {
      if (sound) {
        try {
          const status = await sound.getStatusAsync();
          if (status.isLoaded) {
            setPosition(status.positionMillis || 0);
            await saveProgress(currentChapterIndex, (status.positionMillis || 0) / 1000);
          }
        } catch (err) {
          console.error("Error updating position:", err);
        }
      }
    }, 500);
  };

  const stopPositionUpdates = () => {
    if (positionUpdateInterval.current) {
      clearInterval(positionUpdateInterval.current);
      positionUpdateInterval.current = null;
    }
  };

  const formatTime = (millis: number) => {
    const totalSeconds = Math.floor(millis / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
    }
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
  };

  // Component to render text-based cover when image is missing or fails
  const TextCover = ({ title, author }: { title: string; author: string }) => {
    return (
      <View style={styles.textCover}>
        <View style={styles.textCoverIcon}>
          <Ionicons name="book" size={48} color="#F9A826" />
        </View>
        <Text style={styles.textCoverTitle} numberOfLines={2}>
          {title}
        </Text>
        <Text style={styles.textCoverAuthor} numberOfLines={1}>
          {author}
        </Text>
      </View>
    );
  };

  // Helper function to get cover URL with proxy fallback
  const getCoverUrl = (coverUrl: string | undefined | null): string | null => {
    if (!coverUrl || !coverUrl.trim()) {
      return null;
    }
    
    // Convert http to https for web compatibility
    let url = coverUrl.trim();
    if (url.startsWith("http://")) {
      url = url.replace("http://", "https://", 1);
    }
    
    // If cover failed to load and not already using proxy, use proxy
    if (coverLoadError && !url.includes("/audiobooks/cover-proxy?")) {
      return `${API_BASE}/audiobooks/cover-proxy?url=${encodeURIComponent(url)}`;
    }
    
    return url;
  };

  // Fetch Open Library cover when LibriVox doesn't provide one
  const [openLibraryCover, setOpenLibraryCover] = useState<string | null>(null);
  const [loadingOpenLibraryCover, setLoadingOpenLibraryCover] = useState(false);

  useEffect(() => {
    // Only fetch if no LibriVox cover and haven't fetched yet
    if (!coverUrl && bookDetails && !openLibraryCover && !loadingOpenLibraryCover) {
      setLoadingOpenLibraryCover(true);
      
      const fetchCover = async () => {
        try {
          const params = new URLSearchParams({
            title: bookDetails.title,
            author: bookDetails.author || "",
          });
          
          console.log(`[AudiobookPlayer] 🔍 Fetching Open Library cover for: "${bookDetails.title}" by ${bookDetails.author}`);
          
          const response = await fetch(`${API_BASE}/audiobooks/cover?${params.toString()}`);
          
          if (response.ok) {
            const data = await response.json();
            if (data.cover_url) {
              console.log(`[AudiobookPlayer] ✅ Found Open Library cover: ${data.cover_url}`);
              setOpenLibraryCover(data.cover_url);
            } else {
              console.log(`[AudiobookPlayer] ❌ No Open Library cover found`);
            }
          }
        } catch (error) {
          console.error(`[AudiobookPlayer] ❌ Error fetching Open Library cover:`, error);
        } finally {
          setLoadingOpenLibraryCover(false);
        }
      };
      
      fetchCover();
    }
  }, [coverUrl, bookDetails, openLibraryCover, loadingOpenLibraryCover]);

  const goBack = async () => {
    // Stop audio playback before navigating back
    const currentSound = soundRef.current || sound;
    if (currentSound) {
      try {
        const status = await currentSound.getStatusAsync();
        if (status.isLoaded && status.isPlaying) {
          await currentSound.pauseAsync();
        }
        await currentSound.unloadAsync();
        setSound(null);
        soundRef.current = null;
        setIsPlaying(false);
        stopPositionUpdates();
      } catch (err) {
        console.warn("Error stopping audio on back:", err);
      }
    }
    router.back();
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.root} edges={["top"]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#F9A826" />
          <Text style={styles.loadingText}>Loading audiobook...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (error || !bookDetails) {
    return (
      <SafeAreaView style={styles.root} edges={["top"]}>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={48} color="#FF6B6B" />
          <Text style={styles.errorText}>{error || "Failed to load audiobook"}</Text>
          <Pressable style={styles.backButtonError} onPress={goBack}>
            <Text style={styles.backButtonErrorText}>Go Back</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  const currentChapter = bookDetails.chapters[currentChapterIndex];
  const hasPrevious = currentChapterIndex > 0;
  const hasNext = currentChapterIndex < bookDetails.chapters.length - 1;

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.header}>
        <Pressable onPress={goBack} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#F9A826" />
        </Pressable>
        <Text style={styles.headerTitle} numberOfLines={1}>
          {bookDetails.title}
        </Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.contentContainer}>
        {playbackError && (
          <View style={styles.errorBanner}>
            <Ionicons name="alert-circle" size={20} color="#FF6B6B" />
            <Text style={styles.errorBannerText}>{playbackError}</Text>
            <Pressable
              onPress={() => setPlaybackError(null)}
              style={{ padding: 4 }}
            >
              <Ionicons name="close" size={18} color="#FF6B6B" />
            </Pressable>
          </View>
        )}

        {(() => {
          // Check for Open Library cover first (fallback when LibriVox has no cover)
          const libriVoxCover = getCoverUrl(coverUrl);
          const finalCoverUrl = openLibraryCover || libriVoxCover;
          const coverSource = openLibraryCover ? "openlibrary" : (libriVoxCover ? "librivox" : "none");
          
          // Show placeholder if no URL or if proxy also failed
          const showPlaceholder = !finalCoverUrl || (coverLoadError && finalCoverUrl.includes("/audiobooks/cover-proxy?"));
          
          if (showPlaceholder) {
            // Show text-based cover when image is missing or failed
            return bookDetails ? (
              <TextCover title={bookDetails.title} author={bookDetails.author} />
            ) : (
              <View style={styles.coverPlaceholder}>
                <Ionicons name="book" size={64} color="#888" />
                <Text style={styles.coverPlaceholderText} numberOfLines={2}>
                  No Cover
                </Text>
              </View>
            );
          }
          
          return (
            <Image
              source={{ uri: finalCoverUrl }}
              style={styles.coverImage}
              onError={(e) => {
                const error = e.nativeEvent.error;
                console.error(`[AudiobookPlayer] ❌ Cover image failed to load`);
                console.error(`[AudiobookPlayer]   Title: "${bookDetails?.title || 'Unknown'}"`);
                console.error(`[AudiobookPlayer]   Author: "${bookDetails?.author || 'Unknown'}"`);
                console.error(`[AudiobookPlayer]   Cover URL: ${finalCoverUrl}`);
                console.error(`[AudiobookPlayer]   Cover Source: ${coverSource}`);
                console.error(`[AudiobookPlayer]   Error:`, error);
                console.error(`[AudiobookPlayer]   Using proxy: ${finalCoverUrl.includes("/audiobooks/cover-proxy?")}`);
                
                // Try proxy if not already using it
                if (!finalCoverUrl.includes("/audiobooks/cover-proxy?")) {
                  console.log(`[AudiobookPlayer] 🔄 Retrying with proxy endpoint...`);
                  setCoverLoadError(true);
                } else {
                  // Proxy also failed, show text cover
                  console.error(`[AudiobookPlayer] ⚠️ Proxy also failed, showing text-based cover`);
                  setCoverLoadError(true);
                }
              }}
              onLoad={() => {
                console.log(`[AudiobookPlayer] ✅ Cover image loaded successfully`);
                console.log(`[AudiobookPlayer]   Title: "${bookDetails?.title || 'Unknown'}"`);
                console.log(`[AudiobookPlayer]   Cover URL: ${finalCoverUrl}`);
                console.log(`[AudiobookPlayer]   Cover Source: ${coverSource}`);
                setCoverLoadError(false);
              }}
            />
          );
        })()}

        <Text style={styles.title}>{bookDetails.title}</Text>
        <Text style={styles.author}>{bookDetails.author}</Text>

        {bookDetails.description && (
          <Text style={styles.description}>{bookDetails.description}</Text>
        )}

        <View style={styles.playerContainer}>
          <View style={styles.timeContainer}>
            <Text style={styles.timeText}>{formatTime(position)}</Text>
            <Text style={styles.timeText}>{formatTime(duration)}</Text>
          </View>

          <Slider
            style={styles.slider}
            minimumValue={0}
            maximumValue={duration || 1}
            value={position}
            onSlidingComplete={seekTo}
            minimumTrackTintColor="#F9A826"
            maximumTrackTintColor="#3A3A3A"
            thumbTintColor="#F9A826"
          />

          <View style={styles.controls}>
            <Pressable
              onPress={() => {
                if (hasPrevious) {
                  playChapter(currentChapterIndex - 1, 0);
                }
              }}
              disabled={!hasPrevious}
              style={[styles.controlButton, !hasPrevious && styles.controlButtonDisabled]}
            >
              <Ionicons
                name="play-skip-back"
                size={28}
                color={hasPrevious ? "#F9A826" : "#666"}
              />
            </Pressable>

            <Pressable 
              onPress={togglePlayPause} 
              style={[styles.playButton, (isLoadingAudio || !sound) && styles.playButtonDisabled]}
              disabled={isLoadingAudio}
            >
              {isLoadingAudio ? (
                <ActivityIndicator size="small" color="#1B263B" />
              ) : (
                <Ionicons
                  name={isPlaying ? "pause" : "play"}
                  size={40}
                  color="#1B263B"
                />
              )}
            </Pressable>

            <Pressable
              onPress={() => {
                if (hasNext) {
                  playChapter(currentChapterIndex + 1, 0);
                }
              }}
              disabled={!hasNext}
              style={[styles.controlButton, !hasNext && styles.controlButtonDisabled]}
            >
              <Ionicons
                name="play-skip-forward"
                size={28}
                color={hasNext ? "#F9A826" : "#666"}
              />
            </Pressable>

            <Pressable
              onPress={() => setShowSpeedMenu(!showSpeedMenu)}
              style={styles.speedButton}
            >
              <Text style={styles.speedButtonText}>{playbackRate}x</Text>
            </Pressable>
          </View>

          {showSpeedMenu && (
            <View style={styles.speedMenu}>
              {SPEED_OPTIONS.map((speed) => (
                <Pressable
                  key={speed}
                  onPress={() => changeSpeed(speed)}
                  style={[
                    styles.speedOption,
                    playbackRate === speed && styles.speedOptionActive,
                  ]}
                >
                  <Text
                    style={[
                      styles.speedOptionText,
                      playbackRate === speed && styles.speedOptionTextActive,
                    ]}
                  >
                    {speed}x
                  </Text>
                </Pressable>
              ))}
            </View>
          )}

          <Text style={styles.chapterInfo}>
            Chapter {currentChapterIndex + 1} of {bookDetails.chapters.length}
          </Text>
          {currentChapter && (
            <Text style={styles.chapterTitle}>{currentChapter.title}</Text>
          )}
        </View>

        <View style={styles.chaptersContainer}>
          <Text style={styles.chaptersTitle}>Chapters</Text>
          {bookDetails.chapters.length === 0 ? (
            <View style={styles.emptyChaptersContainer}>
              <Ionicons name="alert-circle-outline" size={48} color="#888" />
              <Text style={styles.emptyChaptersText}>
                No playable chapters available for this audiobook.
              </Text>
            </View>
          ) : (
            bookDetails.chapters.map((chapter, index) => (
              <Pressable
                key={chapter.id}
                onPress={() => playChapter(index, 0)}
                style={[
                  styles.chapterItem,
                  index === currentChapterIndex && styles.chapterItemActive,
                ]}
              >
                <View style={styles.chapterItemInfo}>
                  <Text
                    style={[
                      styles.chapterNumber,
                      index === currentChapterIndex && styles.chapterNumberActive,
                    ]}
                  >
                    {index + 1}
                  </Text>
                  <View style={styles.chapterDetails}>
                    <Text
                      style={[
                        styles.chapterName,
                        index === currentChapterIndex && styles.chapterNameActive,
                      ]}
                      numberOfLines={2}
                    >
                      {chapter.title}
                    </Text>
                    <Text style={styles.chapterDuration}>{chapter.duration_formatted}</Text>
                  </View>
                </View>
                {index === currentChapterIndex && isPlaying && (
                  <Ionicons name="volume-high" size={20} color="#F9A826" />
                )}
              </Pressable>
            ))
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#1B263B",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#2A2A2A",
  },
  backButton: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    flex: 1,
    color: "#FFF",
    fontSize: 18,
    fontWeight: "600",
    textAlign: "center",
  },
  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  loadingText: {
    color: "#FFF",
    marginTop: 16,
    fontSize: 16,
  },
  errorContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
  },
  errorText: {
    color: "#FF6B6B",
    fontSize: 16,
    textAlign: "center",
    marginTop: 16,
    marginBottom: 24,
  },
  backButtonError: {
    marginTop: 24,
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: "#F9A826",
    borderRadius: 8,
  },
  backButtonErrorText: {
    color: "#1B263B",
    fontSize: 16,
    fontWeight: "600",
  },
  content: {
    flex: 1,
  },
  contentContainer: {
    paddingBottom: 32,
  },
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: 16,
    marginTop: 12,
    padding: 12,
    backgroundColor: "#3A1F1F",
    borderRadius: 8,
    borderLeftWidth: 4,
    borderLeftColor: "#FF6B6B",
    gap: 8,
  },
  errorBannerText: {
    flex: 1,
    color: "#FF6B6B",
    fontSize: 14,
  },
  coverImage: {
    width: 200,
    height: 200,
    borderRadius: 12,
    alignSelf: "center",
    marginTop: 20,
    marginBottom: 16,
    backgroundColor: "#2A2A2A",
  },
  coverPlaceholder: {
    width: 200,
    height: 200,
    borderRadius: 12,
    alignSelf: "center",
    marginTop: 20,
    marginBottom: 16,
    backgroundColor: "#2A2A2A",
    alignItems: "center",
    justifyContent: "center",
    padding: 12,
  },
  coverPlaceholderText: {
    color: "#888",
    fontSize: 12,
    textAlign: "center",
    marginTop: 8,
  },
  textCover: {
    width: 200,
    height: 200,
    borderRadius: 12,
    alignSelf: "center",
    marginTop: 20,
    marginBottom: 16,
    backgroundColor: "#2A2A2A",
    alignItems: "center",
    justifyContent: "center",
    padding: 20,
    borderWidth: 2,
    borderColor: "#3A3A3A",
  },
  textCoverIcon: {
    marginBottom: 12,
  },
  textCoverTitle: {
    color: "#FFF",
    fontSize: 18,
    fontWeight: "700",
    textAlign: "center",
    lineHeight: 24,
    marginBottom: 8,
  },
  textCoverAuthor: {
    color: "#AAA",
    fontSize: 14,
    textAlign: "center",
  },
  title: {
    color: "#FFF",
    fontSize: 24,
    fontWeight: "700",
    textAlign: "center",
    marginHorizontal: 16,
    marginBottom: 8,
  },
  author: {
    color: "#AAA",
    fontSize: 18,
    textAlign: "center",
    marginBottom: 16,
  },
  description: {
    color: "#CCC",
    fontSize: 14,
    textAlign: "center",
    marginHorizontal: 16,
    marginBottom: 24,
    lineHeight: 20,
  },
  playerContainer: {
    marginHorizontal: 16,
    marginBottom: 24,
    padding: 20,
    backgroundColor: "#2A2A2A",
    borderRadius: 16,
  },
  timeContainer: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  timeText: {
    color: "#AAA",
    fontSize: 12,
  },
  slider: {
    width: "100%",
    height: 40,
    marginBottom: 16,
  },
  controls: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 16,
    marginBottom: 16,
  },
  controlButton: {
    width: 48,
    height: 48,
    alignItems: "center",
    justifyContent: "center",
  },
  controlButtonDisabled: {
    opacity: 0.5,
  },
  playButton: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#F9A826",
    alignItems: "center",
    justifyContent: "center",
  },
  playButtonDisabled: {
    opacity: 0.6,
  },
  speedButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: "#3A3A3A",
    borderRadius: 8,
  },
  speedButtonText: {
    color: "#F9A826",
    fontSize: 14,
    fontWeight: "600",
  },
  speedMenu: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 8,
    marginTop: 8,
    padding: 12,
    backgroundColor: "#1A1A1A",
    borderRadius: 8,
  },
  speedOption: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: "#2A2A2A",
    borderRadius: 6,
  },
  speedOptionActive: {
    backgroundColor: "#F9A826",
  },
  speedOptionText: {
    color: "#FFF",
    fontSize: 14,
  },
  speedOptionTextActive: {
    color: "#1B263B",
    fontWeight: "600",
  },
  chapterInfo: {
    color: "#AAA",
    fontSize: 12,
    textAlign: "center",
    marginBottom: 4,
  },
  chapterTitle: {
    color: "#F9A826",
    fontSize: 14,
    textAlign: "center",
    fontWeight: "600",
  },
  chaptersContainer: {
    marginHorizontal: 16,
  },
  chaptersTitle: {
    color: "#FFF",
    fontSize: 20,
    fontWeight: "700",
    marginBottom: 12,
  },
  chapterItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: 12,
    marginBottom: 8,
    backgroundColor: "#2A2A2A",
    borderRadius: 8,
  },
  chapterItemActive: {
    backgroundColor: "#3A3A3A",
    borderWidth: 1,
    borderColor: "#F9A826",
  },
  chapterItemInfo: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
  },
  chapterNumber: {
    color: "#888",
    fontSize: 16,
    fontWeight: "600",
    width: 32,
    textAlign: "center",
  },
  chapterNumberActive: {
    color: "#F9A826",
  },
  chapterDetails: {
    flex: 1,
    marginLeft: 12,
  },
  chapterName: {
    color: "#FFF",
    fontSize: 14,
    marginBottom: 4,
  },
  chapterNameActive: {
    color: "#F9A826",
    fontWeight: "600",
  },
  chapterDuration: {
    color: "#888",
    fontSize: 12,
  },
  emptyChaptersContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 48,
    paddingHorizontal: 24,
  },
  emptyChaptersText: {
    color: "#888",
    fontSize: 14,
    textAlign: "center",
    marginTop: 16,
  },
});
