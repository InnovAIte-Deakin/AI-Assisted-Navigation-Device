import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useState, useCallback, useEffect, useRef } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Image,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import AsyncStorage from "@react-native-async-storage/async-storage";
// import { API_BASE } from "@/src/config";
import { addFavorite, removeFavorite, addToListenLater, removeFromListenLater, getFavorites, getListenLater } from "@/src/utils/audiobookStorage";
import FilterBar, { FilterOptions, ActiveFilters } from "@/components/FilterBar";
import FilterModal from "@/components/FilterModal";
import UserGuideModal from "@/components/UserGuideModal";
const API_BASE = "http://127.0.0.1:8003";

// Debounce hook
function useDebouncedValue<T>(value: T, delay: number = 500): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

interface Audiobook {
  id: string;
  title: string;
  author: string;
  duration: number;
  duration_formatted: string;
  language: string;
  description: string;
  cover_url: string;
  genre?: string;
}

interface SearchResponse {
  query: string;
  count: number;
  results: Audiobook[];
  books?: Audiobook[];
  message?: string;
}

export default function AudiobooksScreen() {
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Audiobook[]>([]);
  const [popularBooks, setPopularBooks] = useState<Audiobook[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingPopular, setLoadingPopular] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set());
  const [listenLaterIds, setListenLaterIds] = useState<Set<string>>(new Set());
  const [showMenu, setShowMenu] = useState(false);
  const [failedCoverUrls, setFailedCoverUrls] = useState<Set<string>>(new Set());
  const [openLibraryCovers, setOpenLibraryCovers] = useState<Map<string, string>>(new Map()); // bookId -> coverUrl
  const [loadingOpenLibraryCovers, setLoadingOpenLibraryCovers] = useState<Set<string>>(new Set()); // bookId
  
  // Filter state
  const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null);
  const [loadingFilters, setLoadingFilters] = useState(false);
  const [activeFilters, setActiveFilters] = useState<ActiveFilters>({});
  const [filterModalVisible, setFilterModalVisible] = useState(false);
  const [currentFilterType, setCurrentFilterType] = useState<"language" | "genre" | "duration" | "sort" | null>(null);
  
  // Voice input state
  const [isListening, setIsListening] = useState(false);
  const [sttAvailable, setSttAvailable] = useState(false);
  const recognitionRef = useRef<any>(null);
  
  // User guide state
  const [showUserGuide, setShowUserGuide] = useState(false);
  const [showAsFirstTime, setShowAsFirstTime] = useState(false);
  
  // Debounce search query (500ms delay)
  const debouncedQuery = useDebouncedValue(query, 500);
  
  // AbortController ref for canceling requests
  const abortControllerRef = useRef<AbortController | null>(null);

  // Check for speech recognition availability (web)
  useEffect(() => {
    if (Platform.OS === "web") {
      const W = globalThis as any;
      const SR = W.SpeechRecognition || W.webkitSpeechRecognition;
      setSttAvailable(!!SR);
      console.log(`[Voice] Speech recognition available: ${!!SR}`);
    }
  }, []);

  // Check if first-time user and show guide
  useEffect(() => {
    const checkFirstTimeUser = async () => {
      try {
        const hasSeenGuide = await AsyncStorage.getItem("@audiobooks_has_seen_guide");
        if (!hasSeenGuide) {
          // Show guide after a short delay for better UX
          setTimeout(() => {
            setShowAsFirstTime(true);
            setShowUserGuide(true);
          }, 1000);
        }
      } catch (error) {
        console.error("[UserGuide] Error checking first-time user:", error);
      }
    };
    checkFirstTimeUser();
  }, []);

  // Mark guide as seen when closed
  const handleCloseUserGuide = async () => {
    setShowUserGuide(false);
    if (showAsFirstTime) {
      try {
        await AsyncStorage.setItem("@audiobooks_has_seen_guide", "true");
        setShowAsFirstTime(false);
      } catch (error) {
        console.error("[UserGuide] Error saving guide status:", error);
      }
    }
  };

  // Load filter options and popular books in parallel on mount
  useEffect(() => {
    const loadInitialData = async () => {
      // Load both in parallel for faster initial load
      // Add timeout to prevent hanging (10 seconds max)
      const fetchWithTimeout = (url: string, timeout = 10000) => {
        return Promise.race([
          fetch(url),
          new Promise<Response>((_, reject) =>
            setTimeout(() => reject(new Error("Request timeout")), timeout)
          ),
        ]);
      };

      const [filterResponse, popularResponse] = await Promise.allSettled([
        fetchWithTimeout(`${API_BASE}/audiobooks/filters`, 8000), // 8s timeout for filters
        fetchWithTimeout(`${API_BASE}/audiobooks/popular?limit=10`, 10000), // 10s timeout for popular
      ]);

      // Handle filter options
      setLoadingFilters(true);
      try {
        if (filterResponse.status === "fulfilled" && filterResponse.value.ok) {
          const data = await filterResponse.value.json();
          console.log(`[Filters] Loaded filter options:`, {
            languages: data.languages?.length || 0,
            genres: data.genres?.length || 0,
            durationBuckets: data.durationBuckets?.length || 0,
            sortOptions: data.sortOptions?.length || 0,
          });
          setFilterOptions(data);
        } else {
          console.error(`[Filters] Failed to load filter options`);
          // Set default options on error
          setFilterOptions({
            languages: ["English"],
            genres: ["fiction", "non-fiction"],
            durationBuckets: ["<1h", "1-3h", "3-10h", "10h+"],
            sortOptions: ["relevance", "popular", "newest", "longest", "title_az", "author_az"],
          });
        }
      } catch (error) {
        console.error("[Filters] Error loading filter options:", error);
        // Set default options on error
        setFilterOptions({
          languages: ["English"],
          genres: ["fiction", "non-fiction"],
          durationBuckets: ["<1h", "1-3h", "3-10h", "10h+"],
          sortOptions: ["relevance", "popular", "newest", "longest", "title_az", "author_az"],
        });
      } finally {
        setLoadingFilters(false);
      }

      // Handle popular books
      setLoadingPopular(true);
      try {
        if (popularResponse.status === "fulfilled" && popularResponse.value.ok) {
          const data: SearchResponse = await popularResponse.value.json();
          const books = data.results || data.books || [];
          setPopularBooks(books);
          console.log(`[Popular] Loaded ${books.length} popular books`);
        } else {
          console.error("Failed to load popular books:", popularResponse.status === "fulfilled" ? popularResponse.value.status : "rejected");
        }
      } catch (error) {
        console.error("Error loading popular books:", error);
      } finally {
        setLoadingPopular(false);
      }
    };
    
    loadInitialData();
  }, []);

  // Load favorite and listen later status for displayed books
  useEffect(() => {
    const loadStatus = async () => {
      const favorites = await getFavorites();
      const listenLater = await getListenLater();
      setFavoriteIds(new Set(favorites.map(f => f.id)));
      setListenLaterIds(new Set(listenLater.map(l => l.id)));
    };
    const booksToCheck = searchResults.length > 0 ? searchResults : popularBooks;
    if (booksToCheck.length > 0) {
      loadStatus();
    }
  }, [searchResults, popularBooks]);

  const searchAudiobooks = useCallback(async (searchQuery: string) => {
    const trimmedQuery = searchQuery.trim();
    const hasAnyFilter = Object.values(activeFilters).some(v => v !== undefined && v !== "");
    
    console.log(`[Search] Starting search for: "${trimmedQuery}"`);
    console.log(`[Search] Active filters:`, activeFilters);
    console.log(`[Search] Has any filter: ${hasAnyFilter}`);
    
    // Cancel previous request if still pending
    if (abortControllerRef.current) {
      console.log(`[Search] Cancelling previous search request`);
      abortControllerRef.current.abort();
    }
    
    // Create new AbortController for this request
    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Clear previous results immediately when starting new search
    console.log(`[Search] Clearing previous results`);
    setSearchResults([]);
    setLoading(true);
    setError(null);

    try {
      // Build search URL with filters
      // Allow empty query if filters are present
      const queryParam = trimmedQuery || "";
      const params = new URLSearchParams({
        q: queryParam,
        limit: "25",
      });
      
      // Add filters to params
      if (activeFilters.language) {
        params.append("language", activeFilters.language);
        console.log(`[Search] ✅ Adding language filter: ${activeFilters.language}`);
      }
      if (activeFilters.genre) {
        params.append("genre", activeFilters.genre);
        console.log(`[Search] ✅ Adding genre filter: ${activeFilters.genre}`);
      }
      if (activeFilters.duration) {
        // Convert duration bucket to min/max seconds
        const durationMap: Record<string, { min?: number; max?: number }> = {
          "<1h": { max: 3600 },
          "1-3h": { min: 3600, max: 10800 },
          "3-10h": { min: 10800, max: 36000 },
          "10h+": { min: 36000 },
        };
        const durationRange = durationMap[activeFilters.duration];
        if (durationRange) {
          if (durationRange.min !== undefined) {
            params.append("min_duration", durationRange.min.toString());
            console.log(`[Search] ✅ Adding min_duration filter: ${durationRange.min}s`);
          }
          if (durationRange.max !== undefined) {
            params.append("max_duration", durationRange.max.toString());
            console.log(`[Search] ✅ Adding max_duration filter: ${durationRange.max}s`);
          }
        }
      }
      if (activeFilters.sort) {
        params.append("sort", activeFilters.sort);
        console.log(`[Search] ✅ Adding sort filter: ${activeFilters.sort}`);
      }
      
      const searchUrl = `${API_BASE}/audiobooks/search?${params.toString()}`;
      console.log(`[Search] 🔍 Full search URL: ${searchUrl}`);
      
      const response = await fetch(
        searchUrl,
        { signal: controller.signal }
      );

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

      const data: SearchResponse = await response.json();
      
      // Debug: Log the raw response structure
      console.log(`[Search] Raw response keys:`, Object.keys(data));
      console.log(`[Search] Response has 'results':`, 'results' in data, data.results?.length || 0);
      console.log(`[Search] Response has 'books':`, 'books' in data, data.books?.length || 0);
      
      // IMPORTANT: Backend returns {"results": [...]}, so use data.results first
      const results = data.results || data.books || [];
      
      // Debug logging to verify search results
      console.log(`[Search] Query: "${searchQuery}"`);
      console.log(`[Search] Results count: ${results.length}`);
      if (results.length > 0) {
        console.log(`[Search] First 5 result titles:`, results.slice(0, 5).map(b => b.title.substring(0, 40)));
        console.log(`[Search] First 5 result IDs:`, results.slice(0, 5).map(b => b.id));
      } else {
        console.log(`[Search] WARNING: No results found in response!`);
        console.log(`[Search] Full response:`, JSON.stringify(data, null, 2).substring(0, 500));
      }
      
      // Verify this request wasn't cancelled before setting results
      if (controller.signal.aborted) {
        console.log(`[Search] Request was cancelled, not setting results`);
        return;
      }
      
      // Set results - this should trigger re-render
      console.log(`[Search] Setting searchResults state with ${results.length} items for query: "${searchQuery}"`);
      setSearchResults(results);
      
      // Verify state was set correctly (async, but helps debug)
      setTimeout(() => {
        console.log(`[Search] State check - searchResults should now have ${results.length} items`);
      }, 100);
      
      if (data.message && data.count === 0) {
        setError(data.message);
      } else {
        setError(null);
      }
    } catch (err: any) {
      // Ignore abort errors (they're expected when canceling)
      if (err.name === "AbortError") {
        console.log("Search request cancelled");
        return;
      }
      console.error("Search error:", err);
      setError(err instanceof Error ? err.message : "Failed to search audiobooks");
      setSearchResults([]);
    } finally {
      // Only update loading state if this request wasn't cancelled
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [activeFilters]);

  // Trigger search when debounced query changes or filters change
  useEffect(() => {
    const trimmedQuery = debouncedQuery.trim();
    const hasAnyFilter = Object.values(activeFilters).some(v => v !== undefined && v !== "");
    
    console.log(`[useEffect] Debounced query changed: "${trimmedQuery}", hasAnyFilter: ${hasAnyFilter}`);
    
    // Search if query is at least 3 characters OR if filters are applied
    if (trimmedQuery.length >= 3 || hasAnyFilter) {
      const searchQuery = trimmedQuery.length >= 3 ? trimmedQuery : "";
      console.log(`[useEffect] Triggering search for: "${searchQuery}" with filters`);
      searchAudiobooks(searchQuery);
    } else if (trimmedQuery.length === 0 && !hasAnyFilter) {
      // Clear results when query is empty and no filters
      console.log(`[useEffect] Query is empty and no filters, clearing results`);
      setSearchResults([]);
      setError(null);
      setLoading(false);
    } else {
      // Query too short and no filters - clear results but don't show error
      console.log(`[useEffect] Query too short (${trimmedQuery.length} chars) and no filters, clearing results`);
      setSearchResults([]);
      setError(null);
      setLoading(false);
    }
  }, [debouncedQuery, activeFilters, searchAudiobooks]);

  const handleBookPress = (book: Audiobook) => {
    console.log("[BookPress] Selected book:", {
      bookId: book.id,
      title: book.title,
      author: book.author,
      fromQuery: query.trim(),
      currentResultsCount: searchResults.length,
    });
    
    // Verify the book ID matches what we expect
    if (!book.id) {
      console.error("[BookPress] ERROR: Book has no ID!", book);
      return;
    }
    
    router.push({
      pathname: "/audiobooks-player",
      params: {
        bookId: book.id,
        title: book.title,
        author: book.author,
        coverUrl: book.cover_url || "",
      },
    });
  };

  const goHomeIcon = () => router.push("/" as const);

  // Voice input handlers - Fixed implementation
  const startListening = useCallback(() => {
    console.log(`[Voice] startListening called, Platform.OS: ${Platform.OS}`);
    
    if (Platform.OS !== "web") {
      Alert.alert(
        "Voice Input",
        "Voice input requires a custom dev client or production build. For now, please type your search."
      );
      return;
    }

    const W = globalThis as any;
    const SR = W.SpeechRecognition || W.webkitSpeechRecognition;
    
    // Check browser support
    if (!SR) {
      console.warn(`[Voice] SpeechRecognition not available. Check: ${('SpeechRecognition' in window) || ('webkitSpeechRecognition' in window)}`);
      Alert.alert(
        "Voice Search Not Supported",
        "Speech recognition is not available in this browser. Please use Chrome or Edge for voice search."
      );
      return;
    }
    
    try {
      // Stop any existing recognition
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {
          // Ignore errors when stopping
        }
        recognitionRef.current = null;
      }
      
      const rec = new SR();
      recognitionRef.current = rec;
      
      // Configure recognition
      rec.lang = "en-US"; // Default to English, could match language filter if available
      rec.continuous = false; // Stop after user stops speaking
      rec.interimResults = true; // Show interim results for real-time feedback
      
      // Track accumulated transcript
      let accumulatedTranscript = "";
      
      rec.onresult = (event: any) => {
        console.log(`[Voice] onresult called, resultIndex: ${event.resultIndex}, results.length: ${event.results.length}`);
        
        // Process results starting from resultIndex (only new results)
        let transcript = "";
        let hasFinal = false;
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          const resultTranscript = result[0].transcript;
          
          transcript += resultTranscript;
          
          if (result.isFinal) {
            hasFinal = true;
          }
        }
        
        // Accumulate transcript
        accumulatedTranscript = transcript.trim();
        
        // Update React state immediately (controlled input)
        if (accumulatedTranscript) {
          console.log(`[Voice] Setting query to: "${accumulatedTranscript}" (isFinal: ${hasFinal})`);
          setQuery(accumulatedTranscript);
        }
        
        // If final result, stop listening after a brief delay
        if (hasFinal) {
          console.log(`[Voice] Final result received: "${accumulatedTranscript}"`);
          setTimeout(() => {
            if (recognitionRef.current) {
              try {
                recognitionRef.current.stop();
              } catch (err) {
                console.error(`[Voice] Error stopping:`, err);
              }
            }
            setIsListening(false);
            recognitionRef.current = null;
            
            // Optionally auto-trigger search if query is long enough
            if (accumulatedTranscript.trim().length >= 3) {
              console.log(`[Voice] Auto-triggering search for: "${accumulatedTranscript}"`);
              setTimeout(() => {
                searchAudiobooks(accumulatedTranscript.trim());
              }, 500);
            }
          }, 500);
        }
      };
      
      rec.onend = () => {
        console.log(`[Voice] Recognition ended`);
        setIsListening(false);
        recognitionRef.current = null;
      };
      
      rec.onerror = (error: any) => {
        console.error(`[Voice] Recognition error:`, error);
        setIsListening(false);
        recognitionRef.current = null;
        
        const errorType = error.error || "unknown";
        let errorMessage = "Speech recognition failed. Please try again.";
        
        switch (errorType) {
          case "not-allowed":
            errorMessage = "Microphone permission denied. Please allow microphone access in your browser settings and try again.";
            break;
          case "no-speech":
            errorMessage = "No speech detected. Please speak clearly into the microphone.";
            break;
          case "audio-capture":
            errorMessage = "No microphone found. Please connect a microphone and try again.";
            break;
          case "network":
            errorMessage = "Network error. Please check your connection and try again.";
            break;
          case "aborted":
            // User stopped manually, don't show error
            console.log(`[Voice] Recognition aborted by user`);
            return;
          default:
            errorMessage = `Speech recognition error: ${errorType}. Please try again.`;
        }
        
        Alert.alert("Voice Search Error", errorMessage);
      };
      
      // Start recognition
      setIsListening(true);
      rec.start();
      console.log(`[Voice] ✅ Started listening (lang: ${rec.lang}, continuous: ${rec.continuous}, interim: ${rec.interimResults})`);
      
    } catch (error: any) {
      console.error(`[Voice] Failed to start recognition:`, error);
      Alert.alert(
        "Error",
        `Failed to start speech recognition: ${error.message || "Unknown error"}. Please try typing instead.`
      );
      setIsListening(false);
      recognitionRef.current = null;
    }
  }, [searchAudiobooks]);

  const stopListening = useCallback(() => {
    if (Platform.OS === "web" && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
        console.log(`[Voice] Stopped listening`);
      } catch (error) {
        console.error(`[Voice] Error stopping recognition:`, error);
      }
    }
    setIsListening(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {}
      }
    };
  }, []);

  // Filter handlers
  const handleFilterPress = (filterType: "language" | "genre" | "duration" | "sort" | "more") => {
    if (filterType === "more") {
      // Could open additional filters modal if needed
      return;
    }
    console.log(`[Filter] Opening ${filterType} filter modal, filterOptions:`, filterOptions);
    setCurrentFilterType(filterType);
    setFilterModalVisible(true);
  };

  const handleFilterSelect = (filterType: string, value: string | undefined) => {
    setActiveFilters((prev) => {
      const next = { ...prev };
      if (value) {
        next[filterType as keyof ActiveFilters] = value;
      } else {
        delete next[filterType as keyof ActiveFilters];
      }
      return next;
    });
    // Search will be triggered by useEffect when activeFilters changes
  };

  const handleClearFilters = () => {
    setActiveFilters({});
    // Search will be triggered by useEffect when activeFilters changes
  };

  // Component to render text-based cover when image is missing or fails
  const TextCover = ({ title, author }: { title: string; author: string }) => {
    // Get initials for a nice visual
    const getInitials = (text: string): string => {
      const words = text.trim().split(/\s+/);
      if (words.length >= 2) {
        return (words[0][0] + words[words.length - 1][0]).toUpperCase();
      }
      return text.substring(0, 2).toUpperCase();
    };
    
    const titleInitials = getInitials(title);
    const authorInitials = getInitials(author);
    
    return (
      <View style={styles.textCover}>
        <View style={styles.textCoverIcon}>
          <Ionicons name="book" size={24} color="#F9A826" />
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
    
    // If cover failed to load before, use proxy
    if (failedCoverUrls.has(coverUrl) || failedCoverUrls.has(url)) {
      return `${API_BASE}/audiobooks/cover-proxy?url=${encodeURIComponent(url)}`;
    }
    
    return url;
  };

  // Fetch Open Library cover for a book when LibriVox doesn't provide one
  const fetchOpenLibraryCover = async (book: Audiobook) => {
    const bookKey = book.id;
    
    // Skip if already have cover or already loading
    if (openLibraryCovers.has(bookKey) || loadingOpenLibraryCovers.has(bookKey)) {
      return;
    }
    
    // Skip if LibriVox already provided a cover URL
    if (book.cover_url && book.cover_url.trim()) {
      return;
    }
    
    setLoadingOpenLibraryCovers(prev => new Set(prev).add(bookKey));
    
    try {
      const params = new URLSearchParams({
        title: book.title,
        author: book.author || "",
      });
      
      console.log(`[Audiobooks] 🔍 Fetching Open Library cover for: "${book.title}" by ${book.author}`);
      
      const response = await fetch(`${API_BASE}/audiobooks/cover?${params.toString()}`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.cover_url) {
        console.log(`[Audiobooks] ✅ Found Open Library cover: ${data.cover_url}`);
        setOpenLibraryCovers(prev => {
          const next = new Map(prev);
          next.set(bookKey, data.cover_url);
          return next;
        });
      } else {
        console.log(`[Audiobooks] ❌ No Open Library cover found for: "${book.title}"`);
      }
    } catch (error) {
      console.error(`[Audiobooks] ❌ Error fetching Open Library cover:`, error);
    } finally {
      setLoadingOpenLibraryCovers(prev => {
        const next = new Set(prev);
        next.delete(bookKey);
        return next;
      });
    }
  };

  // Handle cover image load error
  const handleCoverError = (coverUrl: string | undefined | null, originalUrl: string) => {
    if (!coverUrl) return;
    
    console.log(`[Audiobooks] Cover image failed to load: ${coverUrl}`);
    
    // If not already using proxy, try proxy
    if (!coverUrl.includes("/audiobooks/cover?")) {
      const proxyUrl = `${API_BASE}/audiobooks/cover?url=${encodeURIComponent(originalUrl)}`;
      console.log(`[Audiobooks] Retrying with proxy: ${proxyUrl}`);
      setFailedCoverUrls(prev => new Set(prev).add(originalUrl));
      // Force re-render by updating state
      return proxyUrl;
    }
    
    // Already tried proxy, mark as failed
    setFailedCoverUrls(prev => new Set(prev).add(originalUrl));
    return null;
  };

  // Determine what to display - show search results if query exists, otherwise show popular books
  // Consider it a query if there's a search term OR if filters are active
  const hasAnyFilter = Object.values(activeFilters).some(v => v !== undefined && v !== "");
  const hasQuery = query.trim().length >= 3 || (searchResults.length > 0 && hasAnyFilter);
  const displayBooks = (hasQuery || searchResults.length > 0) ? searchResults : popularBooks;

  const handleToggleFavorite = async (book: Audiobook, e: any) => {
    e.stopPropagation();
    try {
      const isFav = favoriteIds.has(book.id);
      if (isFav) {
        await removeFavorite(book.id);
        setFavoriteIds(prev => {
          const next = new Set(prev);
          next.delete(book.id);
          return next;
        });
      } else {
        await addFavorite({
          id: book.id,
          title: book.title,
          author: book.author,
          duration: book.duration,
          duration_formatted: book.duration_formatted,
          language: book.language,
          description: book.description,
          cover_url: book.cover_url,
        });
        setFavoriteIds(prev => new Set(prev).add(book.id));
      }
    } catch (error) {
      console.error('Failed to toggle favorite:', error);
    }
  };

  const handleToggleListenLater = async (book: Audiobook, e: any) => {
    e.stopPropagation();
    try {
      const isInList = listenLaterIds.has(book.id);
      if (isInList) {
        await removeFromListenLater(book.id);
        setListenLaterIds(prev => {
          const next = new Set(prev);
          next.delete(book.id);
          return next;
        });
      } else {
        await addToListenLater({
          id: book.id,
          title: book.title,
          author: book.author,
          duration: book.duration,
          duration_formatted: book.duration_formatted,
          language: book.language,
          description: book.description,
          cover_url: book.cover_url,
        });
        setListenLaterIds(prev => new Set(prev).add(book.id));
      }
    } catch (error) {
      console.error('Failed to toggle listen later:', error);
    }
  };

  const renderBookItem = ({ item, index }: { item: Audiobook; index: number }) => {
    // Debug log to verify which book is being rendered
    if (index < 3) {
      console.log(`[RenderItem] Index ${index}: ID=${item.id}, Title="${item.title.substring(0, 30)}"`);
    }
    
    const isFav = favoriteIds.has(item.id);
    const isInList = listenLaterIds.has(item.id);
    
    return (
    <Pressable
      style={styles.bookCard}
      onPress={() => {
        console.log(`[Press] Clicked index ${index}, book ID: ${item.id}, title: "${item.title}"`);
        handleBookPress(item);
      }}
      accessibilityRole="button"
      accessibilityLabel={`Play ${item.title} by ${item.author}`}
    >
      {(() => {
        // Check for Open Library cover first (fallback when LibriVox has no cover)
        const openLibraryCover = openLibraryCovers.get(item.id);
        const libriVoxCover = getCoverUrl(item.cover_url);
        
        // Determine which cover to use: Open Library > LibriVox > Text Cover
        let coverUrl: string | null = null;
        let coverSource = "none";
        
        if (openLibraryCover) {
          coverUrl = openLibraryCover;
          coverSource = "openlibrary";
        } else if (libriVoxCover) {
          coverUrl = libriVoxCover;
          coverSource = "librivox";
        }
        
        // If no LibriVox cover and haven't tried Open Library yet, fetch it
        if (!libriVoxCover && !openLibraryCover && !loadingOpenLibraryCovers.has(item.id)) {
          fetchOpenLibraryCover(item);
        }
        
        // Show placeholder if no URL or if proxy also failed
        const originalUrl = item.cover_url || "";
        const proxyFailed = failedCoverUrls.has(originalUrl) && coverUrl?.includes("/audiobooks/cover-proxy?");
        
        if (!coverUrl || proxyFailed) {
          // Show text-based cover when image is missing or failed
          return <TextCover title={item.title} author={item.author} />;
        }
        
        return (
          <Image
            source={{ uri: coverUrl }}
            style={styles.coverImage}
            onError={(e) => {
              const error = e.nativeEvent.error;
              console.error(`[Audiobooks] ❌ Cover image failed to load`);
              console.error(`[Audiobooks]   Title: "${item.title}"`);
              console.error(`[Audiobooks]   Author: "${item.author}"`);
              console.error(`[Audiobooks]   Cover URL: ${coverUrl}`);
              console.error(`[Audiobooks]   Cover Source: ${coverSource}`);
              console.error(`[Audiobooks]   Original URL: ${originalUrl}`);
              console.error(`[Audiobooks]   Error:`, error);
              console.error(`[Audiobooks]   Using proxy: ${coverUrl.includes("/audiobooks/cover-proxy?")}`);
              
              // If not already using proxy, mark original URL as failed to trigger proxy on next render
              if (!coverUrl.includes("/audiobooks/cover-proxy?")) {
                console.log(`[Audiobooks] 🔄 Retrying with proxy endpoint...`);
                setFailedCoverUrls(prev => new Set(prev).add(coverUrl || originalUrl));
              } else {
                // Proxy also failed, mark as failed to show text cover
                console.error(`[Audiobooks] ⚠️ Proxy also failed, showing text-based cover`);
                setFailedCoverUrls(prev => new Set(prev).add(coverUrl || originalUrl));
              }
            }}
            onLoad={() => {
              console.log(`[Audiobooks] ✅ Cover image loaded successfully`);
              console.log(`[Audiobooks]   Title: "${item.title}"`);
              console.log(`[Audiobooks]   Cover URL: ${coverUrl}`);
              console.log(`[Audiobooks]   Cover Source: ${coverSource}`);
              // Clear failure state on successful load
              const urlToCheck = coverUrl || originalUrl;
              if (failedCoverUrls.has(urlToCheck)) {
                setFailedCoverUrls(prev => {
                  const next = new Set(prev);
                  next.delete(urlToCheck);
                  return next;
                });
              }
            }}
          />
        );
      })()}
      <View style={styles.bookInfo}>
        <Text style={styles.bookTitle} numberOfLines={2}>
          {item.title}
        </Text>
        <Text style={styles.bookAuthor} numberOfLines={1}>
          {item.author}
        </Text>
        <View style={styles.bookMeta}>
          <Text style={styles.bookDuration}>{item.duration_formatted}</Text>
          <Text style={styles.bookLanguage}>{item.language}</Text>
        </View>
      </View>
      <View style={styles.bookActions}>
        <Pressable
          onPress={(e) => handleToggleFavorite(item, e)}
          style={styles.actionButton}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        >
          <Ionicons 
            name={isFav ? "heart" : "heart-outline"} 
            size={24} 
            color={isFav ? "#FF6B6B" : "#888"} 
          />
        </Pressable>
        <Pressable
          onPress={(e) => handleToggleListenLater(item, e)}
          style={styles.actionButton}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        >
          <Ionicons 
            name={isInList ? "bookmark" : "bookmark-outline"} 
            size={24} 
            color={isInList ? "#F9A826" : "#888"} 
          />
        </Pressable>
        <Ionicons name="play-circle" size={32} color="#F9A826" />
      </View>
    </Pressable>
    );
  };

  
  // Debug logging for rendering - track when searchResults actually changes
  useEffect(() => {
    console.log(`[Render] Query: "${query.trim()}", searchResults.length: ${searchResults.length}, displayBooks.length: ${displayBooks.length}`);
    console.log(`[Render] Mode: ${hasQuery ? "search" : "empty"}`);
    if (searchResults.length > 0) {
      console.log(`[Render] searchResults IDs (first 5):`, searchResults.map(b => b.id).slice(0, 5));
      console.log(`[Render] searchResults titles (first 3):`, searchResults.slice(0, 3).map(b => b.title.substring(0, 40)));
    } else if (query.trim().length >= 3) {
      console.log(`[Render] WARNING: Query exists but searchResults is empty!`);
    }
  }, [query, searchResults, displayBooks.length, hasQuery]);

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      {/* Header and Search - Fixed at top */}
      <View style={styles.fixedHeader}>
        <View style={styles.headerRow}>
          <Pressable
            onPress={goHomeIcon}
            accessibilityRole="button"
            accessibilityLabel="Go to Home"
            style={styles.iconBtn}
          >
            <Ionicons name="home-outline" size={22} color="#F9A826" />
          </Pressable>
          <Text accessibilityRole="header" style={styles.headerText}>
            AUDIOBOOKS
          </Text>
          <View style={styles.headerRightButtons}>
            <Pressable 
              onPress={() => setShowMenu(!showMenu)} 
              style={styles.iconBtn}
              accessibilityRole="button"
              accessibilityLabel="Menu"
            >
              <Ionicons name="ellipsis-vertical" size={24} color="#FFF" />
            </Pressable>
            <Pressable
              onPress={() => setShowUserGuide(true)}
              style={styles.iconBtn}
              accessibilityRole="button"
              accessibilityLabel="User Guide and Settings"
            >
              <Ionicons name="information-circle-outline" size={24} color="#F9A826" />
            </Pressable>
          </View>
        </View>

        {/* Dropdown Menu - Positioned absolutely */}
        {showMenu && (
          <View style={styles.dropdownMenu}>
            <Pressable 
              style={styles.menuItem}
              onPress={() => {
                setShowMenu(false);
                router.push("/audiobooks-favourites");
              }}
            >
              <Ionicons name="heart" size={20} color="#FF6B6B" />
              <Text style={styles.menuItemText}>Favourites</Text>
            </Pressable>
            <Pressable 
              style={styles.menuItem}
              onPress={() => {
                setShowMenu(false);
                router.push("/audiobooks-history");
              }}
            >
              <Ionicons name="time" size={20} color="#F9A826" />
              <Text style={styles.menuItemText}>History</Text>
            </Pressable>
            <Pressable 
              style={[styles.menuItem, styles.menuItemLast]}
              onPress={() => {
                setShowMenu(false);
                router.push("/audiobooks-listen-later");
              }}
            >
              <Ionicons name="bookmark" size={20} color="#F9A826" />
              <Text style={styles.menuItemText}>Listen Later</Text>
            </Pressable>
          </View>
        )}

        <View style={styles.searchWrap}>
          <Ionicons name="search" size={16} color="#888" style={{ marginRight: 8 }} />
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Search audiobooks (e.g., Sherlock, Dracula, Austen)..."
            placeholderTextColor="#888"
            accessibilityLabel="Search audiobooks"
            style={styles.searchInput}
            returnKeyType="search"
            onSubmitEditing={() => query.trim().length >= 3 && searchAudiobooks(query.trim())}
          />
          {/* Microphone button */}
          <View style={styles.micButtonContainer}>
            <Pressable
              onPress={isListening ? stopListening : startListening}
              style={[styles.micButton, isListening && styles.micButtonActive]}
              disabled={Platform.OS !== "web" && !sttAvailable}
              accessibilityRole="button"
              accessibilityLabel={isListening ? "Stop listening" : "Start voice input"}
              accessibilityLiveRegion="polite"
            >
              <Ionicons 
                name={isListening ? "mic" : "mic-outline"} 
                size={20} 
                color={isListening ? "#FFF" : "#888"} 
              />
            </Pressable>
            {isListening && (
              <Text 
                style={styles.listeningText}
                accessibilityLiveRegion="polite"
                accessibilityLabel="Listening"
              >
                Listening...
              </Text>
            )}
          </View>
          {query.trim() && (
            <Pressable 
              onPress={() => searchAudiobooks(query.trim())} 
              style={styles.searchButton}
              disabled={loading || query.trim().length < 3}
            >
              {loading ? (
                <ActivityIndicator size="small" color="#F9A826" />
              ) : (
                <Ionicons name="arrow-forward" size={20} color="#F9A826" />
              )}
            </Pressable>
          )}
        </View>

        {error && (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}
        {(loading && query.trim().length >= 3) || (loadingPopular && !query.trim()) ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="small" color="#F9A826" />
            <Text style={styles.loadingText}>
              {query.trim().length >= 3 ? "Searching Librivox..." : "Loading popular books..."}
            </Text>
          </View>
        ) : null}
      </View>

      {/* Filter Bar - Always visible */}
      <FilterBar
        filterOptions={filterOptions}
        activeFilters={activeFilters}
        onFilterPress={handleFilterPress}
        onClearFilters={handleClearFilters}
        onSearch={() => {
          // Trigger search with current query or empty string if filters are active
          const hasAnyFilter = Object.values(activeFilters).some(v => v !== undefined && v !== "");
          if (hasAnyFilter) {
            const searchQuery = query.trim().length >= 3 ? query.trim() : "";
            searchAudiobooks(searchQuery);
          }
        }}
        loading={loadingFilters}
      />

      {/* Search Button - Centered below filters */}
      <View style={styles.searchButtonContainer}>
        <Pressable
          style={[
            styles.searchButtonMain, 
            (loading || (!query.trim() && !hasAnyFilter)) && styles.searchButtonDisabled
          ]}
          onPress={() => {
            const trimmedQuery = query.trim();
            
            console.log(`[SearchButton] Clicked - Query: "${trimmedQuery}", HasFilters: ${hasAnyFilter}`, activeFilters);
            
            // Search if query is valid OR if filters are active
            if (trimmedQuery.length >= 3 || hasAnyFilter) {
              const searchQuery = trimmedQuery.length >= 3 ? trimmedQuery : "";
              console.log(`[SearchButton] ✅ Triggering search with query: "${searchQuery}" and filters:`, activeFilters);
              searchAudiobooks(searchQuery);
            } else {
              console.log(`[SearchButton] ❌ No query or filters - cannot search`);
              setError("Please enter a search query (at least 3 characters) or select filters to search.");
            }
          }}
          disabled={loading || (!query.trim() && !hasAnyFilter)}
          accessibilityRole="button"
          accessibilityLabel="Search audiobooks"
        >
          <Ionicons name="search" size={20} color="#FFF" />
          <Text style={styles.searchButtonText}>Search Audiobooks</Text>
        </Pressable>
      </View>

      {/* Popular Books Header */}
      {!hasQuery && !hasAnyFilter && popularBooks.length > 0 && (
        <View style={styles.popularHeader}>
          <Text style={styles.popularHeaderText}>Popular Audiobooks</Text>
        </View>
      )}
      
      {/* Filtered Results Header */}
      {hasAnyFilter && searchResults.length > 0 && (
        <View style={styles.popularHeader}>
          <Text style={styles.popularHeaderText}>
            {searchResults.length} result{searchResults.length !== 1 ? "s" : ""} found
          </Text>
        </View>
      )}

      <FlatList
        data={displayBooks}
        extraData={(hasQuery || searchResults.length > 0) ? searchResults : popularBooks} // Force re-render when data changes
        keyExtractor={(item) => item.id}
        contentContainerStyle={{ paddingBottom: 24 }}
        renderItem={renderBookItem}
        ListEmptyComponent={
          !loading && !loadingPopular && (query.trim() || hasAnyFilter) ? (
            <View style={styles.emptyContainer}>
              <Ionicons name="book-outline" size={64} color="#666" />
              <Text style={styles.emptyText}>
                {error || (hasAnyFilter && !query.trim()
                  ? `No books found matching your filters. Try adjusting your filters or search for a specific book.`
                  : query.trim().length < 3 
                  ? "Type at least 3 characters to search..." 
                  : `Ooh! Sorry, the book with the title "${query.trim()}" not found.`)}
              </Text>
            </View>
          ) : (!loading && !loadingPopular && !query.trim() && !hasAnyFilter && popularBooks.length === 0 ? (
            <View style={styles.emptyContainer}>
              <Ionicons name="book-outline" size={64} color="#666" />
              <Text style={styles.emptyText}>
                Failed to load popular books. Please try again.
              </Text>
            </View>
          ) : null)
        }
      />

      {/* Filter Modal */}
      <FilterModal
        visible={filterModalVisible}
        filterType={currentFilterType}
        filterOptions={filterOptions}
        activeFilters={activeFilters}
        onSelect={handleFilterSelect}
        onClose={() => {
          setFilterModalVisible(false);
          setCurrentFilterType(null);
        }}
      />

      {/* User Guide Modal */}
      <UserGuideModal
        visible={showUserGuide}
        onClose={handleCloseUserGuide}
        showAsFirstTime={showAsFirstTime}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#1B263B",
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingTop: 6,
    paddingBottom: 10,
    borderBottomWidth: 1.25,
    borderBottomColor: "#F9A826",
  },
  iconBtn: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 8,
  },
  headerRightButtons: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  headerText: {
    flex: 1,
    color: "#ffffffff",
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: 1.1,
    textAlign: "center",
  },
  searchWrap: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 12,
    marginBottom: 10,
    marginHorizontal: 16,
    paddingHorizontal: 12,
    height: 40,
    borderRadius: 12,
    borderWidth: 1.25,
    borderColor: "#2A2A2A",
    backgroundColor: "#141414",
  },
  searchInput: {
    flex: 1,
    color: "#EEE",
    fontSize: 15,
    marginRight: 4,
  },
  micButtonContainer: {
    flexDirection: "row",
    alignItems: "center",
    marginRight: 4,
  },
  micButton: {
    padding: 6,
    borderRadius: 20,
    backgroundColor: "transparent",
    justifyContent: "center",
    alignItems: "center",
  },
  micButtonActive: {
    backgroundColor: "#FF4444",
    borderRadius: 20,
  },
  listeningText: {
    fontSize: 10,
    color: "#FF4444",
    marginLeft: 4,
    fontWeight: "500",
  },
  searchButton: {
    padding: 4,
    marginLeft: 4,
  },
  errorContainer: {
    marginHorizontal: 16,
    marginTop: 8,
    padding: 12,
    backgroundColor: "#3A1F1F",
    borderRadius: 8,
    borderLeftWidth: 4,
    borderLeftColor: "#FF6B6B",
  },
  errorText: {
    color: "#FF6B6B",
    fontSize: 14,
  },
  loadingContainer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginHorizontal: 16,
    marginTop: 8,
    padding: 12,
  },
  loadingText: {
    color: "#F9A826",
    fontSize: 14,
    marginLeft: 8,
  },
  bookCard: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: 16,
    marginTop: 12,
    padding: 12,
    backgroundColor: "#2A2A2A",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#3A3A3A",
  },
  coverImage: {
    width: 60,
    height: 60,
    borderRadius: 8,
    backgroundColor: "#1A1A1A",
  },
  coverPlaceholder: {
    width: 60,
    height: 60,
    borderRadius: 8,
    backgroundColor: "#1A1A1A",
    alignItems: "center",
    justifyContent: "center",
  },
  textCover: {
    width: 60,
    height: 60,
    borderRadius: 8,
    backgroundColor: "#2A2A2A",
    alignItems: "center",
    justifyContent: "center",
    padding: 4,
    borderWidth: 1,
    borderColor: "#3A3A3A",
  },
  textCoverIcon: {
    marginBottom: 2,
  },
  textCoverTitle: {
    color: "#FFF",
    fontSize: 8,
    fontWeight: "700",
    textAlign: "center",
    lineHeight: 10,
  },
  textCoverAuthor: {
    color: "#AAA",
    fontSize: 6,
    textAlign: "center",
    marginTop: 1,
  },
  bookInfo: {
    flex: 1,
    marginLeft: 12,
    marginRight: 8,
  },
  bookActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  actionButton: {
    padding: 4,
  },
  bookTitle: {
    color: "#FFF",
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 4,
  },
  bookAuthor: {
    color: "#AAA",
    fontSize: 14,
    marginBottom: 4,
  },
  bookMeta: {
    flexDirection: "row",
    gap: 12,
  },
  bookDuration: {
    color: "#888",
    fontSize: 12,
  },
  bookLanguage: {
    color: "#888",
    fontSize: 12,
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 60,
    paddingHorizontal: 32,
  },
  emptyText: {
    color: "#888",
    fontSize: 16,
    textAlign: "center",
    marginTop: 16,
  },
  searchButtonContainer: {
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: 16,
    backgroundColor: "#1B263B",
  },
  searchButtonMain: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F9A826",
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 25,
    gap: 8,
    minWidth: 200,
    shadowColor: "#F9A826",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 5,
  },
  searchButtonDisabled: {
    opacity: 0.6,
  },
  searchButtonText: {
    color: "#1B263B",
    fontSize: 16,
    fontWeight: "700",
  },
  popularHeader: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
  },
  popularHeaderText: {
    color: "#F9A826",
    fontSize: 18,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  fixedHeader: {
    backgroundColor: "#1B263B",
    zIndex: 10,
    position: "relative",
  },
  dropdownMenu: {
    position: "absolute",
    top: 60,
    right: 16,
    backgroundColor: "#2A2A2A",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#3A3A3A",
    minWidth: 200,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
    overflow: "hidden",
    zIndex: 1000,
  },
  menuItem: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 16,
    gap: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#3A3A3A",
  },
  menuItemLast: {
    borderBottomWidth: 0,
  },
  menuItemText: {
    color: "#FFF",
    fontSize: 15,
    fontWeight: "500",
    flex: 1,
  },
});
