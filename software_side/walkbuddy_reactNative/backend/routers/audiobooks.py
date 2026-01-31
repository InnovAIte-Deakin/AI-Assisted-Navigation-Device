"""
Audiobooks Router - LibriVox Integration
Provides endpoints for searching, fetching details, and streaming audiobooks.
"""
import httpx
import xml.etree.ElementTree as ET
import re
import asyncio
import os
import time
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, Response
from typing import List, Dict, Optional

router = APIRouter(prefix="/audiobooks", tags=["audiobooks"])

# LibriVox API configuration
LIBRIVOX_API = "https://librivox.org/api/feed/audiobooks/"

# SSL verification toggle (for dev environments with cert issues)
# Set LIBRIVOX_VERIFY_SSL=0 in environment to disable SSL verification (dev only!)
VERIFY_SSL = os.getenv("LIBRIVOX_VERIFY_SSL", "1").lower() not in ("0", "false", "no")

# Simple in-memory cache for search results
SEARCH_CACHE: Dict[str, tuple[float, dict]] = {}
CACHE_TTL = 1800  # 30 minutes
CACHE_VERSION = "v2"  # Increment to invalidate old cache entries (changed from 'q' to 'title' parameter)

# Cache for Open Library cover lookups
COVER_CACHE: Dict[str, tuple[float, Optional[str]]] = {}
COVER_CACHE_TTL = 86400  # 24 hours - covers don't change often

# Cache for filter options
FILTERS_CACHE: Optional[tuple[float, dict]] = None
FILTERS_CACHE_TTL = 600  # 10 minutes


def cache_get(key: str) -> Optional[dict]:
    """Get cached item if it hasn't expired."""
    item = SEARCH_CACHE.get(key)
    if not item:
        return None
    expires_at, data = item
    if time.time() > expires_at:
        SEARCH_CACHE.pop(key, None)
        return None
    return data


def cache_set(key: str, data: dict, ttl: int = CACHE_TTL) -> None:
    """Set cache item with TTL."""
    SEARCH_CACHE[key] = (time.time() + ttl, data)


def normalize_genre(genre: str) -> str:
    """
    Normalize genre/subject string to match our standardized genre list.
    Maps various genre names from LibriVox to our 10 standard genres.
    """
    if not genre:
        return ""
    
    normalized = genre.strip().lower()
    
    # Map to our standardized genres
    genre_map = {
        # Fiction (Classics) - includes classic literature, general fiction
        "fiction": "Fiction (Classics)",
        "classics": "Fiction (Classics)",
        "classic": "Fiction (Classics)",
        "literature": "Fiction (Classics)",
        "novel": "Fiction (Classics)",
        "literary fiction": "Fiction (Classics)",
        
        # Fantasy
        "fantasy": "Fantasy",
        "fantasy fiction": "Fantasy",
        "magic": "Fantasy",
        "mythology": "Fantasy",
        
        # Mystery & Crime
        "mystery": "Mystery & Crime",
        "crime": "Mystery & Crime",
        "detective": "Mystery & Crime",
        "thriller": "Mystery & Crime",
        "suspense": "Mystery & Crime",
        "murder": "Mystery & Crime",
        "mystery fiction": "Mystery & Crime",
        "crime fiction": "Mystery & Crime",
        
        # Romance
        "romance": "Romance",
        "romantic": "Romance",
        "love story": "Romance",
        
        # Science Fiction
        "science fiction": "Science Fiction",
        "sci-fi": "Science Fiction",
        "scifi": "Science Fiction",
        "science-fiction": "Science Fiction",
        "sf": "Science Fiction",
        "speculative fiction": "Science Fiction",
        
        # Horror
        "horror": "Horror",
        "gothic": "Horror",
        "ghost story": "Horror",
        "supernatural": "Horror",
        "vampire": "Horror",
        "zombie": "Horror",
        
        # History
        "history": "History",
        "historical": "History",
        "historical fiction": "History",
        "biography": "History",
        "autobiography": "History",
        "memoir": "History",
        "war": "History",
        "military": "History",
        
        # Philosophy
        "philosophy": "Philosophy",
        "philosophical": "Philosophy",
        "ethics": "Philosophy",
        "metaphysics": "Philosophy",
        "logic": "Philosophy",
        
        # Religion & Spirituality
        "religion": "Religion & Spirituality",
        "spirituality": "Religion & Spirituality",
        "religious": "Religion & Spirituality",
        "theology": "Religion & Spirituality",
        "bible": "Religion & Spirituality",
        "christian": "Religion & Spirituality",
        "islam": "Religion & Spirituality",
        "judaism": "Religion & Spirituality",
        "buddhism": "Religion & Spirituality",
        "hinduism": "Religion & Spirituality",
        "prayer": "Religion & Spirituality",
        "meditation": "Religion & Spirituality",
        
        # Children's Books
        "children": "Children's Books",
        "children's": "Children's Books",
        "childrens": "Children's Books",
        "juvenile": "Children's Books",
        "young adult": "Children's Books",
        "ya": "Children's Books",
        "kids": "Children's Books",
        "fairy tale": "Children's Books",
        "fairy tales": "Children's Books",
        "nursery rhyme": "Children's Books",
    }
    
    # Check for exact match first
    if normalized in genre_map:
        return genre_map[normalized]
    
    # Check for partial matches (contains)
    for key, value in genre_map.items():
        if key in normalized or normalized in key:
            return value
    
    # Default: return original normalized (for genres not in our list, we'll filter them out)
    return normalized


async def librivox_get(params: dict, timeout_total: float = 12.0, timeout_connect: float = 5.0, allow_404: bool = False) -> Optional[dict]:
    """
    Helper function for making requests to LibriVox API.
    Handles errors gracefully and returns proper HTTP exceptions.
    Uses shorter timeouts for faster failure (12s total, 5s connect).
    
    Args:
        params: Query parameters for the API request
        timeout_total: Total timeout in seconds
        timeout_connect: Connection timeout in seconds
        allow_404: If True, return None for 404 instead of raising exception (for search when no results)
    """
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_total, connect=timeout_connect),
            follow_redirects=True,
            verify=VERIFY_SSL,  # Can be disabled via env var for dev
        ) as client:
            r = await client.get(LIBRIVOX_API, params=params)
            # Handle 404 gracefully if allowed (e.g., for search when no results found)
            if r.status_code == 404 and allow_404:
                return None
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        # LibriVox returned an error status code
        status = e.response.status_code
        detail_msg = f"LibriVox API returned {status}"
        try:
            error_body = e.response.text[:200]
            if error_body:
                detail_msg += f": {error_body}"
        except:
            pass
        print(f"[Audiobooks] LibriVox HTTP error: {detail_msg}")
        raise HTTPException(status_code=502, detail=detail_msg)
    except httpx.ConnectError as e:
        # Cannot connect to LibriVox (DNS, network, firewall)
        detail_msg = f"Cannot reach LibriVox (connection error): {str(e)}"
        print(f"[Audiobooks] Connection error: {detail_msg}")
        raise HTTPException(status_code=502, detail=detail_msg)
    except httpx.ReadTimeout:
        # Request timed out
        detail_msg = "LibriVox request timed out. Please try again."
        print(f"[Audiobooks] Timeout error: {detail_msg}")
        raise HTTPException(status_code=502, detail=detail_msg)
    except httpx.ConnectTimeout:
        # Connection timeout
        detail_msg = "LibriVox connection timed out. Please check your internet connection."
        print(f"[Audiobooks] Connection timeout: {detail_msg}")
        raise HTTPException(status_code=502, detail=detail_msg)
    except httpx.RequestError as e:
        # Other request errors (SSL, etc.)
        detail_msg = f"LibriVox request failed: {str(e)}"
        print(f"[Audiobooks] Request error: {detail_msg}")
        raise HTTPException(status_code=502, detail=detail_msg)
    except Exception as e:
        # Unexpected errors
        detail_msg = f"Unexpected error contacting LibriVox: {str(e)}"
        print(f"[Audiobooks] Unexpected error: {detail_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=detail_msg)


@router.get("/search")
async def search_audiobooks(
    q: str = Query("", description="Search query (title, author, etc.) - optional if filters are provided"),
    language: Optional[str] = Query(None, description="Filter by language"),
    genre: Optional[str] = Query(None, description="Filter by genre/subject"),
    min_duration: Optional[int] = Query(None, ge=0, description="Minimum duration in seconds"),
    max_duration: Optional[int] = Query(None, ge=0, description="Maximum duration in seconds"),
    narrator_type: Optional[str] = Query(None, description="Narrator type (single/full_cast) - currently not supported by LibriVox API"),
    sort: Optional[str] = Query("relevance", description="Sort option: relevance, popular, newest, longest, title_az, author_az"),
    limit: int = Query(25, ge=1, le=100, description="Maximum number of results")
):
    """
    Search for audiobooks using LibriVox API.
    Returns a list of audiobooks matching the search query.
    Handles missing fields gracefully - never crashes.
    """
    # Check if filters are applied
    has_filters = bool(language or genre or min_duration is not None or max_duration is not None)
    
    # Normalize query - allow empty query if filters are applied
    search_query = q.strip() if q and q.strip() else ""
    
    # Validate query - allow empty query if filters are applied
    if not search_query and not has_filters:
        return {
            "query": "",
            "count": 0,
            "results": [],
            "filters_applied": {
                "language": language,
                "genre": genre,
                "min_duration": min_duration,
                "max_duration": max_duration,
                "sort": sort
            }
        }
    
    try:
        # Build cache key including filters
        filter_parts = []
        if language:
            filter_parts.append(f"lang:{language.lower().strip()}")
        if genre:
            filter_parts.append(f"genre:{normalize_genre(genre)}")
        if min_duration is not None:
            filter_parts.append(f"min:{min_duration}")
        if max_duration is not None:
            filter_parts.append(f"max:{max_duration}")
        if sort:
            filter_parts.append(f"sort:{sort}")
        filter_str = "|".join(filter_parts) if filter_parts else "none"
        cache_key = f"{CACHE_VERSION}:search:{search_query.lower() if search_query else '*'}::{filter_str}:{limit}"
        
        cached_result = cache_get(cache_key)
        if cached_result:
            print(f"[Audiobooks] Cache hit for query: {search_query[:50] if search_query else '*'}... with filters: {filter_str}")
            return cached_result
        
        # Multi-strategy search for better partial matching:
        # 1. Try exact title match first
        # 2. If no results, try prefix match (titles starting with query)
        # 3. If still no results and query is short, try substring matching via larger fetch + filter
        
        # If no query but filters exist, fetch a larger sample to filter
        fetch_limit = limit * 5 if not search_query and has_filters else limit
        
        # Use query for search, or "*" as wildcard if no query but filters exist
        query_clean = search_query if search_query else "*"
        print(f"[Audiobooks] Searching Librivox with query='{query_clean[:50]}...' (has_filters={has_filters})")
        
        # Strategy 1: Exact title match (or wildcard if no query)
        params_exact = {
            "format": "json",
            "title": query_clean,
            "extended": "1",
            "limit": fetch_limit
        }
        data = await librivox_get(params_exact, timeout_total=12.0, timeout_connect=5.0, allow_404=True)
        
        # Strategy 2: Prefix match (if exact match failed and query is short and not wildcard)
        if data is None and query_clean != "*" and len(query_clean.split()) <= 2:
            print(f"[Audiobooks] Exact match failed, trying prefix match with '^{query_clean[:30]}...'")
            params_prefix = {
                "format": "json",
                "title": f"^{query_clean}",  # Prefix search using ^ anchor
                "extended": "1",
                "limit": limit
            }
            data = await librivox_get(params_prefix, timeout_total=12.0, timeout_connect=5.0, allow_404=True)
        
        # Strategy 3: Try searching by first few characters (for partial word matching)
        # This helps find books where the search term appears in the middle of the title
        # Only for single-word queries that failed both exact and prefix match (not wildcard)
        if data is None and query_clean != "*" and len(query_clean.split()) == 1 and len(query_clean) >= 4:
            print(f"[Audiobooks] Exact and prefix match failed, trying first-character prefix search...")
            # Try prefix search with first 3-4 characters (helps catch variations)
            prefix_len = min(4, len(query_clean))
            prefix_query = query_clean[:prefix_len]
            params_prefix_short = {
                "format": "json",
                "title": f"^{prefix_query}",
                "extended": "1",
                "limit": min(100, limit * 5)  # Fetch more to filter
            }
            data_prefix = await librivox_get(params_prefix_short, timeout_total=12.0, timeout_connect=5.0, allow_404=True)
            
            if data_prefix:
                # Filter books that contain the full query word in title (case-insensitive)
                query_lower = query_clean.lower()
                books_prefix = []
                if isinstance(data_prefix, dict):
                    books_prefix = data_prefix.get("books", []) if isinstance(data_prefix.get("books"), list) else []
                elif isinstance(data_prefix, list):
                    books_prefix = data_prefix
                
                # Filter for substring match (query must appear anywhere in title)
                filtered_books = []
                for book in books_prefix:
                    if isinstance(book, dict):
                        title = book.get("title", "")
                        if query_lower in title.lower():
                            filtered_books.append(book)
                            if len(filtered_books) >= limit:
                                break
                
                if filtered_books:
                    print(f"[Audiobooks] Found {len(filtered_books)} books via prefix+substring matching")
                    # Create a response structure similar to what we'd get from API
                    data = {"books": filtered_books}
                else:
                    data = None
        
        # If all strategies failed, return empty results
        if data is None:
            print(f"[Audiobooks] No results found for query: {search_query[:50] if search_query else '*'}...")
            return {
                "query": search_query if search_query else "",
                "count": 0,
                "results": [],
                "filters_applied": {
                    "language": language,
                    "genre": genre,
                    "min_duration": min_duration,
                    "max_duration": max_duration,
                    "sort": sort
                }
            }
        
        # Extract books from response - handle various response formats
        books = []
        if isinstance(data, dict):
            if "books" in data:
                books = data["books"] if isinstance(data["books"], list) else []
            elif "book" in data:
                book_item = data["book"]
                if isinstance(book_item, dict):
                    books = [book_item]
                elif isinstance(book_item, list):
                    books = book_item
        elif isinstance(data, list):
            books = data
        
        # Transform to our format - defensive parsing
        results = []
        for book in books:
            if not isinstance(book, dict):
                continue
            
            try:
                # Get book ID safely
                book_id_raw = book.get("id")
                book_id = str(book_id_raw) if book_id_raw is not None else ""
                
                # Get title safely
                title = book.get("title") or "Untitled"
                
                # Get author safely - LibriVox API can have authors as list or string
                author = "Unknown Author"
                if "author" in book and book["author"]:
                    # String author
                    author = str(book["author"]).strip()
                elif "authors" in book and isinstance(book["authors"], list) and len(book["authors"]) > 0:
                    # List of authors - get first one
                    first_author = book["authors"][0]
                    if isinstance(first_author, dict):
                        first_name = first_author.get("first_name", "")
                        last_name = first_author.get("last_name", "")
                        author = f"{first_name} {last_name}".strip() or "Unknown Author"
                    elif isinstance(first_author, str):
                        author = first_author.strip() or "Unknown Author"
                
                # Parse duration safely
                total_duration = 0
                duration_formatted = "0:00"
                if "totaltime" in book and book["totaltime"]:
                    try:
                        time_str = str(book["totaltime"])
                        time_parts = time_str.split(":")
                        if len(time_parts) == 3:
                            total_duration = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])
                        elif len(time_parts) == 2:
                            total_duration = int(time_parts[0]) * 60 + int(time_parts[1])
                        
                        hours = total_duration // 3600
                        minutes = (total_duration % 3600) // 60
                        duration_formatted = f"{hours}:{minutes:02d}" if hours > 0 else f"{minutes}"
                    except (ValueError, TypeError, IndexError):
                        # Duration parsing failed - use defaults
                        pass
                
                # Get language safely
                book_language = book.get("language") or "Unknown"
                
                # Get genre/subject safely
                book_genre = None
                if "subject" in book and book["subject"]:
                    book_genre = normalize_genre(str(book["subject"]))
                elif "genre" in book and book["genre"]:
                    book_genre = normalize_genre(str(book["genre"]))
                elif "category" in book and book["category"]:
                    book_genre = normalize_genre(str(book["category"]))
                
                # Get description safely
                description = book.get("description") or ""
                
                # Get cover URL safely - try multiple possible fields
                # Log ALL cover-related fields with their values for debugging
                cover_fields = {k: v for k, v in book.items() if any(term in k.lower() for term in ["cover", "url", "image", "thumbnail", "art"])}
                print(f"[Audiobooks] 📚 Book '{title[:50]}...' - Cover-related fields:")
                for field_name, field_value in cover_fields.items():
                    value_preview = str(field_value)[:100] if field_value else "None"
                    print(f"[Audiobooks]   - {field_name}: {value_preview}")
                
                cover_url = ""
                cover_source = None
                if "coverart" in book and book["coverart"]:
                    cover_url = str(book["coverart"])
                    cover_source = "coverart"
                    print(f"[Audiobooks] ✅ Using 'coverart' field: {cover_url[:100]}...")
                elif "cover" in book and book["cover"]:
                    cover_url = str(book["cover"])
                    cover_source = "cover"
                    print(f"[Audiobooks] ✅ Using 'cover' field: {cover_url[:100]}...")
                elif "url_zip_file" in book and book["url_zip_file"]:
                    cover_url = str(book["url_zip_file"]).replace(".zip", "_1200.jpg")
                    cover_source = "url_zip_file"
                    print(f"[Audiobooks] ✅ Using 'url_zip_file' (converted): {cover_url[:100]}...")
                elif "url_librivox" in book and book["url_librivox"]:
                    # Fallback: try to construct from librivox URL
                    print(f"[Audiobooks] ⚠️ 'url_librivox' found but not used for cover: {book.get('url_librivox', '')[:100]}")
                    pass
                else:
                    print(f"[Audiobooks] ❌ No cover URL found for '{title[:50]}...' (will try Open Library fallback)")
                
                # Convert http to https for web compatibility
                if cover_url and cover_url.startswith("http://"):
                    cover_url = cover_url.replace("http://", "https://", 1)
                    print(f"[Audiobooks] Converted http to https for cover URL")
                
                # Apply filters before adding to results
                # Language filter
                if language and book_language.lower().strip() != language.lower().strip():
                    continue
                
                # Genre filter - match normalized book genre to requested genre
                if genre:
                    # Normalize the requested genre to our standard format
                    requested_genre = normalize_genre(genre)
                    # Normalize the book's genre
                    book_genre_normalized = normalize_genre(book_genre) if book_genre else ""
                    # Match if the normalized book genre matches the requested genre
                    if not book_genre_normalized or book_genre_normalized != requested_genre:
                        continue
                
                # Duration filters
                if min_duration is not None and total_duration < min_duration:
                    continue
                if max_duration is not None and total_duration > max_duration:
                    continue
                
                # Get sample/first track URL for preview
                sample_audio_url = ""
                if book_id:
                    # Try constructing first chapter URL
                    sample_audio_url = f"https://archive.org/download/{book_id}/{book_id}_01.mp3"
                
                results.append({
                    "id": book_id,
                    "title": title,
                    "author": author,
                    "duration": total_duration,
                    "duration_formatted": duration_formatted,
                    "language": book_language,
                    "description": description,
                    "cover_url": cover_url,
                    "genre": book_genre or "",  # Add genre to response
                    "sample_audio_url": sample_audio_url,
                    "first_track_url": sample_audio_url
                })
            except Exception as book_err:
                # Skip this book if parsing fails - don't crash entire search
                print(f"[Audiobooks] Error parsing book {book.get('id', 'unknown')}: {book_err}")
                continue
        
        # Apply sorting
        if sort:
            if sort == "title_az":
                results.sort(key=lambda x: x.get("title", "").lower())
            elif sort == "author_az":
                results.sort(key=lambda x: x.get("author", "").lower())
            elif sort == "longest":
                results.sort(key=lambda x: x.get("duration", 0), reverse=True)
            elif sort == "newest":
                # LibriVox doesn't provide publication date, so we'll use ID as proxy (newer IDs tend to be higher)
                # This is a best-effort approximation
                results.sort(key=lambda x: int(x.get("id", "0")) if x.get("id", "0").isdigit() else 0, reverse=True)
            elif sort == "popular":
                # LibriVox doesn't provide popularity metrics, so we'll keep relevance order
                pass  # Keep original order (relevance)
            # "relevance" - keep original order
        
        # Limit results after filtering and sorting
        results = results[:limit]
        
        response_data = {
            "query": search_query if search_query else "",
            "count": len(results),
            "results": results,
            "filters_applied": {
                "language": language,
                "genre": genre,
                "min_duration": min_duration,
                "max_duration": max_duration,
                "sort": sort
            }
        }
        
        # Debug logging to verify what we're returning
        if results:
            print(f"[Audiobooks] Search result titles (first 5):", [b.get("title", "Unknown")[:40] for b in results[:5]])
            print(f"[Audiobooks] Search result IDs (first 5):", [b.get("id", "?") for b in results[:5]])
            if language or genre or min_duration or max_duration:
                print(f"[Audiobooks] Filters applied: lang={language}, genre={genre}, duration={min_duration}-{max_duration}, sort={sort}")
        else:
            print(f"[Audiobooks] Search returned 0 results for query: {search_query[:50] if search_query else '*'}")
        
        # Cache the results
        cache_set(cache_key, response_data)
        
        return response_data
            
    except HTTPException:
        # Re-raise HTTP exceptions (already properly formatted by librivox_get)
        raise
    except Exception as e:
        # Unexpected errors - log but return 502, not 500
        print(f"[Audiobooks] Search error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Search failed: {str(e)}")


@router.get("/filters")
async def get_filter_options():
    """
    Get available filter options for audiobooks.
    Returns languages, genres/subjects, duration buckets, and sort options.
    Cached for 10 minutes.
    """
    try:
        # Check cache first
        global FILTERS_CACHE
        if FILTERS_CACHE:
            expires_at, cached_data = FILTERS_CACHE
            if time.time() < expires_at:
                print(f"[Audiobooks] Using cached filter options")
                return cached_data
            else:
                FILTERS_CACHE = None
        
        print(f"[Audiobooks] Fetching filter options from LibriVox...")
        
        # Fetch a sample of books to extract filter options
        # We'll fetch popular/recent books to get a good sample
        params = {
            "format": "json",
            "extended": "1",
            "limit": 100  # Get a good sample
        }
        
        data = await librivox_get(params, timeout_total=15.0, timeout_connect=5.0, allow_404=False)
        
        if not data:
            # Return default options if API fails
            return {
                "languages": ["English"],
                "genres": [],
                "durationBuckets": ["<1h", "1-3h", "3-10h", "10h+"],
                "sortOptions": ["relevance", "popular", "newest", "longest", "title_az", "author_az"]
            }
        
        # Extract books from response
        books = []
        if isinstance(data, dict):
            if "books" in data:
                books = data["books"] if isinstance(data["books"], list) else []
            elif "book" in data:
                book_item = data["book"]
                if isinstance(book_item, dict):
                    books = [book_item]
                elif isinstance(book_item, list):
                    books = book_item
        elif isinstance(data, list):
            books = data
        
        # Extract unique languages (we still extract languages from LibriVox)
        languages_set = set()
        
        for book in books:
            if not isinstance(book, dict):
                continue
            
            # Extract language
            lang = book.get("language", "").strip()
            if lang:
                languages_set.add(lang)
            
            # Note: We no longer extract genres from LibriVox - we use our fixed standardized list
        
        # Comprehensive list of 100+ languages (common + world languages + LibriVox languages)
        # Note: Using set() to automatically deduplicate, then converting back to sorted list
        comprehensive_languages = sorted(list(set([
            # Major World Languages (15)
            "English", "Spanish", "French", "German", "Italian", "Portuguese", "Russian", 
            "Chinese", "Japanese", "Korean", "Arabic", "Hindi", "Bengali", "Urdu", "Turkish",
            
            # European Languages (40)
            "Polish", "Dutch", "Greek", "Hebrew", "Swedish", "Norwegian", "Danish", "Finnish",
            "Czech", "Hungarian", "Romanian", "Bulgarian", "Croatian", "Serbian", "Slovak",
            "Slovenian", "Ukrainian", "Lithuanian", "Latvian", "Estonian", "Icelandic",
            "Irish", "Welsh", "Scottish Gaelic", "Catalan", "Basque", "Galician", "Maltese",
            "Albanian", "Macedonian", "Bosnian", "Montenegrin", "Moldovan", "Belarusian",
            "Georgian", "Armenian", "Azerbaijani", "Breton", "Corsican", "Luxembourgish", "Faroese",
            
            # Central Asian & Turkic (10)
            "Kazakh", "Kyrgyz", "Uzbek", "Tajik", "Turkmen", "Tatar", "Bashkir", "Chuvash", "Yakut", "Uyghur",
            
            # Asian Languages (30)
            "Tibetan", "Burmese", "Thai", "Vietnamese", "Lao", "Khmer", "Indonesian", "Malay",
            "Tagalog", "Javanese", "Sundanese", "Cebuano", "Ilocano", "Hiligaynon", "Waray",
            "Tamil", "Telugu", "Kannada", "Malayalam", "Gujarati", "Punjabi", "Marathi",
            "Nepali", "Sinhala", "Pashto", "Persian", "Kurdish", "Dari", "Dzongkha", "Manchu",
            
            # Middle Eastern (10)
            "Sindhi", "Balochi", "Kashmiri", "Hazaragi", "Aramaic", "Syriac", "Coptic", "Assyrian", "Chaldean", "Mandaic",
            
            # African Languages (20)
            "Swahili", "Hausa", "Yoruba", "Igbo", "Zulu", "Xhosa", "Afrikaans", "Amharic",
            "Somali", "Oromo", "Kinyarwanda", "Kirundi", "Luganda", "Shona", "Ndebele",
            "Tswana", "Sesotho", "Swati", "Venda", "Tsonga", "Malagasy", "Wolof",
            "Fula", "Mandinka", "Bambara", "Ewe", "Twi", "Ga", "Kikuyu", "Luo",
            
            # Pacific & Southeast Asian (10)
            "Hawaiian", "Maori", "Samoan", "Tongan", "Fijian", "Chamorro", "Palauan",
            "Marshallese", "Gilbertese", "Nauruan", "Tok Pisin", "Hiri Motu",
            
            # Constructed & Historical Languages (15)
            "Esperanto", "Latin", "Ancient Greek", "Sanskrit", "Old English", "Middle English",
            "Old French", "Old Norse", "Gothic", "Pali", "Classical Arabic", "Classical Chinese", 
            "Old Church Slavonic", "Old Irish", "Medieval Latin",
            
            # Additional Regional Languages (15)
            "Asturian", "Occitan", "Romansh", "Ladino", "Yiddish", "Romani", "Sami", 
            "Karelian", "Veps", "Livonian", "Mari", "Udmurt", "Komi", "Mordvin", "Chechen",
            "Ingush", "Avar", "Lezgian", "Kabardian", "Adyghe", "Abkhaz", "Ossetian",
            "Balkar", "Karachay", "Nogai", "Kumyk", "Lak", "Dargwa", "Tabasaran", "Rutul"
        ])))
        
        # Merge discovered languages with comprehensive list
        all_languages = sorted(list(set(comprehensive_languages) | languages_set))
        
        # Standardized genre list (always return these 10 genres)
        standard_genres = [
            "Fiction (Classics)",
            "Fantasy",
            "Mystery & Crime",
            "Romance",
            "Science Fiction",
            "Horror",
            "History",
            "Philosophy",
            "Religion & Spirituality",
            "Children's Books"
        ]
        
        # Use standardized genres (don't extract from LibriVox - use our fixed list)
        genres = standard_genres
        
        filter_options = {
            "languages": all_languages,
            "genres": genres,
            "durationBuckets": ["<1h", "1-3h", "3-10h", "10h+"],
            "sortOptions": ["relevance", "popular", "newest", "longest", "title_az", "author_az"]
        }
        
        # Cache the results
        FILTERS_CACHE = (time.time() + FILTERS_CACHE_TTL, filter_options)
        
        print(f"[Audiobooks] Filter options: {len(all_languages)} languages, {len(genres)} genres")
        return filter_options
        
    except Exception as e:
        print(f"[Audiobooks] Error fetching filter options: {e}")
        import traceback
        traceback.print_exc()
        # Return default options on error (never crash)
        return {
            "languages": ["English"],
            "genres": [
                "Fiction (Classics)",
                "Fantasy",
                "Mystery & Crime",
                "Romance",
                "Science Fiction",
                "Horror",
                "History",
                "Philosophy",
                "Religion & Spirituality",
                "Children's Books"
            ],
            "durationBuckets": ["<1h", "1-3h", "3-10h", "10h+"],
            "sortOptions": ["relevance", "popular", "newest", "longest", "title_az", "author_az"]
        }


@router.get("/popular")
async def get_popular_audiobooks(
    limit: int = Query(10, ge=1, le=50, description="Number of popular audiobooks to return")
):
    """
    Get popular/recent audiobooks from LibriVox.
    Returns a list of popular audiobooks when no search query is provided.
    """
    try:
        # Check cache first
        cache_key = f"{CACHE_VERSION}:popular:{limit}"
        cached_result = cache_get(cache_key)
        if cached_result:
            print(f"[Audiobooks] Cache hit for popular books")
            return cached_result
        
        # Fetch popular/recent books from Librivox (no search params = popular books)
        params = {
            "format": "json",
            "extended": "1",
            "limit": limit
        }
        
        print(f"[Audiobooks] Fetching {limit} popular books from Librivox...")
        # Use shorter timeout for popular books to fail faster (8s total, 3s connect)
        data = await librivox_get(params, timeout_total=8.0, timeout_connect=3.0, allow_404=False)
        
        # Extract books from response - handle various response formats
        books = []
        if isinstance(data, dict):
            if "books" in data:
                books = data["books"] if isinstance(data["books"], list) else []
            elif "book" in data:
                book_item = data["book"]
                if isinstance(book_item, dict):
                    books = [book_item]
                elif isinstance(book_item, list):
                    books = book_item
        elif isinstance(data, list):
            books = data
        
        # Transform to our format - defensive parsing (same as search endpoint)
        results = []
        for book in books:
            if not isinstance(book, dict):
                continue
            
            try:
                # Get book ID safely
                book_id_raw = book.get("id")
                book_id = str(book_id_raw) if book_id_raw is not None else ""
                
                # Get title safely
                title = book.get("title") or "Untitled"
                
                # Get author safely - LibriVox API can have authors as list or string
                author = "Unknown Author"
                if "author" in book and book["author"]:
                    # String author
                    author = str(book["author"]).strip()
                elif "authors" in book and isinstance(book["authors"], list) and len(book["authors"]) > 0:
                    # List of authors - get first one
                    first_author = book["authors"][0]
                    if isinstance(first_author, dict):
                        first_name = first_author.get("first_name", "")
                        last_name = first_author.get("last_name", "")
                        author = f"{first_name} {last_name}".strip() or "Unknown Author"
                    elif isinstance(first_author, str):
                        author = first_author.strip() or "Unknown Author"
                
                # Parse duration safely
                total_duration = 0
                duration_formatted = "0:00"
                if "totaltime" in book and book["totaltime"]:
                    try:
                        time_str = str(book["totaltime"])
                        time_parts = time_str.split(":")
                        if len(time_parts) == 3:
                            total_duration = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])
                        elif len(time_parts) == 2:
                            total_duration = int(time_parts[0]) * 60 + int(time_parts[1])
                        
                        hours = total_duration // 3600
                        minutes = (total_duration % 3600) // 60
                        duration_formatted = f"{hours}:{minutes:02d}" if hours > 0 else f"{minutes}"
                    except (ValueError, TypeError, IndexError):
                        # Duration parsing failed - use defaults
                        pass
                
                # Get language safely
                language = book.get("language") or "Unknown"
                
                # Get description safely
                description = book.get("description") or ""
                
                # Get cover URL safely - try multiple possible fields
                # Log ALL cover-related fields with their values for debugging
                cover_fields = {k: v for k, v in book.items() if any(term in k.lower() for term in ["cover", "url", "image", "thumbnail", "art"])}
                print(f"[Audiobooks] 📚 Popular book '{title[:50]}...' - Cover-related fields:")
                for field_name, field_value in cover_fields.items():
                    value_preview = str(field_value)[:100] if field_value else "None"
                    print(f"[Audiobooks]   - {field_name}: {value_preview}")
                
                cover_url = ""
                cover_source = None
                if "coverart" in book and book["coverart"]:
                    cover_url = str(book["coverart"])
                    cover_source = "coverart"
                    print(f"[Audiobooks] ✅ Using 'coverart' field: {cover_url[:100]}...")
                elif "cover" in book and book["cover"]:
                    cover_url = str(book["cover"])
                    cover_source = "cover"
                    print(f"[Audiobooks] ✅ Using 'cover' field: {cover_url[:100]}...")
                elif "url_zip_file" in book and book["url_zip_file"]:
                    cover_url = str(book["url_zip_file"]).replace(".zip", "_1200.jpg")
                    cover_source = "url_zip_file"
                    print(f"[Audiobooks] ✅ Using 'url_zip_file' (converted): {cover_url[:100]}...")
                else:
                    print(f"[Audiobooks] ❌ No cover URL found for '{title[:50]}...' (will try Open Library fallback)")
                
                # Convert http to https for web compatibility
                if cover_url and cover_url.startswith("http://"):
                    cover_url = cover_url.replace("http://", "https://", 1)
                    print(f"[Audiobooks] Converted http to https for cover URL")
                
                # Get sample/first track URL for preview
                sample_audio_url = ""
                if book_id:
                    # Try constructing first chapter URL
                    sample_audio_url = f"https://archive.org/download/{book_id}/{book_id}_01.mp3"
                
                results.append({
                    "id": book_id,
                    "title": title,
                    "author": author,
                    "duration": total_duration,
                    "duration_formatted": duration_formatted,
                    "language": language,
                    "description": description,
                    "cover_url": cover_url,
                    "sample_audio_url": sample_audio_url,
                    "first_track_url": sample_audio_url
                })
            except Exception as book_err:
                # Skip this book if parsing fails - don't crash entire request
                print(f"[Audiobooks] Error parsing book {book.get('id', 'unknown')}: {book_err}")
                continue
        
        response_data = {
            "query": "",
            "count": len(results),
            "results": results
        }
        
        # Debug logging
        if results:
            print(f"[Audiobooks] Popular books fetched: {len(results)} books")
            print(f"[Audiobooks] Popular book titles (first 5):", [b.get("title", "Unknown")[:40] for b in results[:5]])
        
        # Cache the results (shorter TTL for popular books - 1 hour)
        cache_set(cache_key, response_data, ttl=3600)
        
        return response_data
            
    except HTTPException:
        # Re-raise HTTP exceptions (already properly formatted by librivox_get)
        raise
    except Exception as e:
        # Unexpected errors - log but return 502, not 500
        print(f"[Audiobooks] Popular books error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Failed to fetch popular books: {str(e)}")


@router.get("/stream")
@router.head("/stream")  # Support HEAD requests for browser preflight checks
async def stream_audiobook(
    request: Request,
    url: str = Query(..., description="Audio file URL to stream")
):
    """
    Proxy endpoint to stream audiobook audio files.
    Handles CORS and supports range requests for seeking.
    Uses streaming to avoid buffering delays - starts sending bytes immediately.
    """
    try:
        # Validate URL
        if not url or not url.startswith('http'):
            raise HTTPException(status_code=400, detail="Invalid audio URL provided")
        
        print(f"[Audiobooks] Streaming audio from: {url[:100]}...")
        
        # Build headers for upstream request - use a more realistic user-agent
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "accept": "audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5",
            "accept-language": "en-US,en;q=0.9",
            "referer": "https://archive.org/",
        }
        
        # Forward Range header (required for browser audio seeking/loading)
        rng = request.headers.get("range")
        if rng:
            headers["range"] = rng
            print(f"[Audiobooks] Forwarding Range header: {rng}")
        else:
            # No Range header - request first chunk for fast-start
            # This helps browsers start decoding quickly instead of waiting for full file
            headers["range"] = "bytes=0-1048575"  # first 1MB
            print(f"[Audiobooks] No Range header, requesting first chunk for fast-start")
        
        # Retry logic for 503 errors (service unavailable)
        max_retries = 3
        retry_delays = [0.5, 1.0, 2.0]  # Exponential backoff: 0.5s, 1s, 2s
        
        resp = None
        client = None
        
        for attempt in range(max_retries):
            # Create client that stays open for the entire stream lifetime
            client = httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(30.0, connect=10.0))
            
            try:
                # Build request and send with stream=True to keep connection open
                req = client.build_request("GET", url, headers=headers)
                resp = await client.send(req, stream=True)
                
                # Browser can receive 200 (full) or 206 (partial)
                if resp.status_code in (200, 206):
                    # Success - break out of retry loop
                    print(f"[Audiobooks] ✅ Successfully connected to archive.org (attempt {attempt + 1})")
                    break
                elif resp.status_code == 503 and attempt < max_retries - 1:
                    # Service unavailable - retry with backoff
                    error_text = ""
                    try:
                        error_text = await resp.aread()
                    except:
                        pass
                    await resp.aclose()
                    resp = None
                    await client.aclose()
                    client = None
                    
                    wait_time = retry_delays[attempt]
                    print(f"[Audiobooks] ⚠️ Archive.org returned 503 (Service Unavailable), retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                    await asyncio.sleep(wait_time)
                    continue  # Retry
                else:
                    # Other error or final retry failed
                    error_text = ""
                    is_html_error = False
                    try:
                        error_text = await resp.aread()
                        # Check if response is HTML (error page) instead of audio
                        if error_text and (b"<!DOCTYPE" in error_text[:100] or b"<html" in error_text[:100].lower()):
                            is_html_error = True
                            print(f"[Audiobooks] ❌ Archive.org returned HTML error page (not audio)")
                    except:
                        pass
                    await resp.aclose()
                    resp = None
                    await client.aclose()
                    client = None
                    
                    error_detail = f"Upstream audio fetch failed: {resp.status_code}"
                    if resp.status_code == 503:
                        error_detail = "Archive.org service is temporarily unavailable. Please try again in a few moments."
                    elif is_html_error:
                        error_detail = f"Archive.org returned an error page (status {resp.status_code}). The audio file may not be available."
                    elif resp.status_code == 404:
                        error_detail = "Audio file not found. The file may have been removed or the URL is incorrect."
                    
                    print(f"[Audiobooks] ❌ {error_detail}")
                    print(f"[Audiobooks] Error response preview: {error_text[:200] if error_text else 'No error text'}")
                    raise HTTPException(
                        status_code=502 if resp.status_code != 503 else 503,
                        detail=error_detail
                    )
            except HTTPException:
                # Re-raise HTTP exceptions (don't retry)
                if client:
                    try:
                        await client.aclose()
                    except:
                        pass
                raise
            except Exception as e:
                # Connection errors - retry if not final attempt
                if resp:
                    try:
                        await resp.aclose()
                    except:
                        pass
                    resp = None
                if client:
                    try:
                        await client.aclose()
                    except:
                        pass
                    client = None
                
                if attempt < max_retries - 1:
                    wait_time = retry_delays[attempt]
                    print(f"[Audiobooks] ⚠️ Connection error, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries}): {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Final attempt failed
                    print(f"[Audiobooks] ❌ All retry attempts failed: {e}")
                    raise HTTPException(
                        status_code=502,
                        detail=f"Failed to connect to audio server after {max_retries} attempts: {str(e)}"
                    )
        
        # If we get here, we have a successful response (status 200 or 206)
        if not resp or resp.status_code not in (200, 206):
            if client:
                try:
                    await client.aclose()
                except:
                    pass
            raise HTTPException(status_code=502, detail="Failed to establish audio stream")
        
        # Determine content type
        content_type = resp.headers.get("content-type", "audio/mpeg")
        if "audio" not in content_type.lower() and "mpeg" not in content_type.lower():
            content_type = "audio/mpeg"
        
        # Build response headers - pass through relevant upstream headers
        out_headers = {
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600",
        }
        
        # Copy accept-ranges, content-range, content-length if present
        for h in ["accept-ranges", "content-range", "content-length"]:
            v = resp.headers.get(h)
            if v:
                out_headers[h] = v
        
        print(f"[Audiobooks] Streaming audio: status={resp.status_code}, content-type={content_type}, url={url[:80]}...")
        
        # Stream chunks immediately as they arrive (64KB chunks for efficiency)
        # Keep client and response open until generator finishes
        async def iter_bytes():
            try:
                async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                    yield chunk
            except (httpx.StreamClosed, asyncio.CancelledError):
                # Client disconnected / navigation away — not a server error
                print(f"[Audiobooks] Stream closed by client (normal)")
                pass
            finally:
                # Close response and client when generator finishes
                try:
                    await resp.aclose()
                except:
                    pass
                try:
                    await client.aclose()
                except:
                    pass
        
        return StreamingResponse(
            iter_bytes(),
            status_code=resp.status_code,
            media_type=content_type,
            headers=out_headers
        )
                
    except httpx.TimeoutException:
        print(f"[Audiobooks] Stream timeout for URL: {url[:100]}...")
        raise HTTPException(status_code=504, detail="Audio stream timeout")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Audiobooks] Stream error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to stream audio: {str(e)}")


@router.get("/cover")
async def get_cover_fallback(
    title: str = Query(..., description="Book title"),
    author: str = Query("", description="Book author (optional)")
):
    """
    Fetch book cover from Open Library API as a fallback when LibriVox doesn't have a cover.
    Returns the cover URL or None if not found.
    Uses caching to avoid repeated API calls.
    """
    try:
        import urllib.parse
        
        # Clean and encode search parameters
        clean_title = title.strip()
        clean_author = author.strip() if author else ""
        
        # Build cache key
        cache_key = f"{clean_title.lower()}|{clean_author.lower()}"
        
        # Check cache first
        cached = COVER_CACHE.get(cache_key)
        if cached:
            expires_at, cover_url = cached
            if time.time() < expires_at:
                print(f"[Audiobooks] 📦 Using cached Open Library cover for: '{clean_title}'")
                return {"cover_url": cover_url, "source": "openlibrary", "cached": True}
            else:
                # Cache expired
                COVER_CACHE.pop(cache_key, None)
        
        # Build search query
        if clean_author:
            query = f"{clean_title} {clean_author}"
        else:
            query = clean_title
        
        encoded_query = urllib.parse.quote(query)
        
        # Open Library Search API
        search_url = f"https://openlibrary.org/search.json?q={encoded_query}&limit=1"
        
        print(f"[Audiobooks] 🔍 Searching Open Library for: '{query}'")
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=5.0, verify=VERIFY_SSL) as client:
            headers = {"user-agent": "Mozilla/5.0 (AudiobooksProxy)"}
            resp = await client.get(search_url, headers=headers)
            
            if resp.status_code != 200:
                print(f"[Audiobooks] ❌ Open Library search failed with status {resp.status_code}")
                # Cache negative result (shorter TTL for failures)
                COVER_CACHE[cache_key] = (time.time() + 3600, None)  # 1 hour cache for failures
                return {"cover_url": None, "source": "openlibrary", "error": f"HTTP {resp.status_code}"}
            
            data = resp.json()
            
            # Check if we have results
            if "docs" not in data or len(data["docs"]) == 0:
                print(f"[Audiobooks] ❌ No Open Library results for: '{query}'")
                # Cache negative result
                COVER_CACHE[cache_key] = (time.time() + 3600, None)  # 1 hour cache for failures
                return {"cover_url": None, "source": "openlibrary", "error": "No results"}
            
            # Get first result
            first_result = data["docs"][0]
            
            # Try to get cover image URL
            cover_url = None
            
            # Check for cover_i (cover ID) - this is the most reliable
            if "cover_i" in first_result:
                cover_id = first_result["cover_i"]
                cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                print(f"[Audiobooks] ✅ Found Open Library cover (ID: {cover_id}): {cover_url}")
            elif "isbn" in first_result and isinstance(first_result["isbn"], list) and len(first_result["isbn"]) > 0:
                # Try ISBN-based cover
                isbn = first_result["isbn"][0]
                cover_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
                print(f"[Audiobooks] ✅ Found Open Library cover (ISBN: {isbn}): {cover_url}")
            
            if cover_url:
                # Cache successful result
                COVER_CACHE[cache_key] = (time.time() + COVER_CACHE_TTL, cover_url)
                return {
                    "cover_url": cover_url,
                    "source": "openlibrary",
                    "title": first_result.get("title", title),
                    "author": ", ".join(first_result.get("author_name", [])) if isinstance(first_result.get("author_name"), list) else first_result.get("author_name", author),
                    "cached": False
                }
            else:
                print(f"[Audiobooks] ❌ No cover found in Open Library result for: '{query}'")
                # Cache negative result
                COVER_CACHE[cache_key] = (time.time() + 3600, None)  # 1 hour cache for failures
                return {"cover_url": None, "source": "openlibrary", "error": "No cover in result"}
                
    except httpx.TimeoutException:
        print(f"[Audiobooks] ⏱️ Open Library search timeout for: '{title}'")
        return {"cover_url": None, "source": "openlibrary", "error": "Timeout"}
    except Exception as e:
        print(f"[Audiobooks] ❌ Open Library search error: {e}")
        import traceback
        traceback.print_exc()
        return {"cover_url": None, "source": "openlibrary", "error": str(e)}


@router.get("/cover-proxy")
async def proxy_cover_image(
    url: str = Query(..., description="Cover image URL to proxy")
):
    """
    Proxy endpoint to serve cover images.
    Handles CORS and hotlinking issues by fetching and serving images through backend.
    """
    try:
        # Validate URL
        if not url or not url.startswith('http'):
            raise HTTPException(status_code=400, detail="Invalid cover URL provided")
        
        print(f"[Audiobooks] Proxying cover image from: {url[:100]}...")
        
        # Convert http to https for security
        if url.startswith("http://"):
            url = url.replace("http://", "https://", 1)
        
        # Fetch image with timeout
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0, verify=VERIFY_SSL) as client:
            headers = {"user-agent": "Mozilla/5.0 (AudiobooksProxy)"}
            resp = await client.get(url, headers=headers)
            
            if resp.status_code != 200:
                print(f"[Audiobooks] Cover fetch failed with status {resp.status_code}")
                raise HTTPException(status_code=502, detail=f"Failed to fetch cover image: {resp.status_code}")
            
            # Determine content type from response or URL
            content_type = resp.headers.get("content-type", "image/jpeg")
            if not content_type.startswith("image/"):
                # Try to infer from URL extension
                if url.lower().endswith(".png"):
                    content_type = "image/png"
                elif url.lower().endswith(".gif"):
                    content_type = "image/gif"
                elif url.lower().endswith(".webp"):
                    content_type = "image/webp"
                else:
                    content_type = "image/jpeg"  # Default to JPEG
            
            # Return image with proper headers
            return Response(
                content=resp.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
                    "Access-Control-Allow-Origin": "*",
                }
            )
            
    except httpx.TimeoutException:
        print(f"[Audiobooks] Cover fetch timeout for URL: {url[:100]}...")
        raise HTTPException(status_code=504, detail="Cover image fetch timeout")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Audiobooks] Cover proxy error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Cover proxy error: {str(e)}")


@router.get("/{book_id}")
async def get_audiobook_details(book_id: str):
    """
    Get detailed information about an audiobook including all tracks/chapters.
    Handles missing fields gracefully - returns empty chapters if none available.
    """
    try:
        # Use helper function for robust LibriVox requests
        params = {
            "id": book_id,
            "format": "json",
            "extended": "1"
        }
        
        data = await librivox_get(params)
        
        # Extract book data - handle various response formats
        book = None
        if isinstance(data, dict):
            if "books" in data and isinstance(data["books"], list) and len(data["books"]) > 0:
                book = data["books"][0]
            elif "book" in data:
                book_item = data["book"]
                if isinstance(book_item, dict):
                    book = book_item
                elif isinstance(book_item, list) and len(book_item) > 0:
                    book = book_item[0]
        elif isinstance(data, list) and len(data) > 0:
            book = data[0]
        
        if not book or not isinstance(book, dict):
            raise HTTPException(status_code=404, detail="Audiobook not found")
        
        # Get book metadata safely
        book_id_actual = str(book.get("id", book_id)) if book.get("id") else book_id
        title = book.get("title") or "Untitled"
        
        # Get author safely - handle both string and list formats
        author = "Unknown Author"
        if "author" in book and book["author"]:
            author = str(book["author"]).strip()
        elif "authors" in book and isinstance(book["authors"], list) and len(book["authors"]) > 0:
            first_author = book["authors"][0]
            if isinstance(first_author, dict):
                first_name = first_author.get("first_name", "")
                last_name = first_author.get("last_name", "")
                author = f"{first_name} {last_name}".strip() or "Unknown Author"
            elif isinstance(first_author, str):
                author = first_author.strip() or "Unknown Author"
        
        language = book.get("language") or "Unknown"
        description = book.get("description") or ""
        
        # Get cover URL safely - try multiple possible fields
        # Log ALL cover-related fields with their values for debugging
        cover_fields = {k: v for k, v in book.items() if any(term in k.lower() for term in ["cover", "url", "image", "thumbnail", "art"])}
        print(f"[Audiobooks] 📚 Book details '{title[:50]}...' - Cover-related fields:")
        for field_name, field_value in cover_fields.items():
            value_preview = str(field_value)[:100] if field_value else "None"
            print(f"[Audiobooks]   - {field_name}: {value_preview}")
        
        cover_url = ""
        cover_source = None
        if "coverart" in book and book["coverart"]:
            cover_url = str(book["coverart"])
            cover_source = "coverart"
            print(f"[Audiobooks] ✅ Using 'coverart' field: {cover_url[:100]}...")
        elif "cover" in book and book["cover"]:
            cover_url = str(book["cover"])
            cover_source = "cover"
            print(f"[Audiobooks] ✅ Using 'cover' field: {cover_url[:100]}...")
        elif "url_zip_file" in book and book["url_zip_file"]:
            cover_url = str(book["url_zip_file"]).replace(".zip", "_1200.jpg")
            cover_source = "url_zip_file"
            print(f"[Audiobooks] ✅ Using 'url_zip_file' (converted): {cover_url[:100]}...")
        else:
            print(f"[Audiobooks] ❌ No cover URL found for '{title[:50]}...' (will try Open Library fallback)")
        
        # Convert http to https for web compatibility
        if cover_url and cover_url.startswith("http://"):
            cover_url = cover_url.replace("http://", "https://", 1)
            print(f"[Audiobooks] Converted http to https for cover URL")
        
        # Get tracks/chapters
        tracks = []
        num_sections_raw = book.get("num_sections", 0)
        try:
            num_sections = int(num_sections_raw) if num_sections_raw else 0
        except (ValueError, TypeError):
            num_sections = 0
        
        url_rss = book.get("url_rss", "")
        
        # Try to get tracks from RSS feed (need separate client for RSS)
        if url_rss and num_sections > 0:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0), verify=VERIFY_SSL) as rss_client:
                    rss_response = await rss_client.get(url_rss, timeout=10.0)
                    if rss_response.status_code == 200:
                        root = ET.fromstring(rss_response.text)
                        items = root.findall(".//item")
                        
                        print(f"[Audiobooks] Found {len(items)} items in RSS feed for book {book_id}")
                        
                        for idx, item in enumerate(items[:num_sections]):
                            try:
                                audio_url = ""
                                
                                # Get URL from enclosure tag
                                enclosure = item.find("enclosure")
                                if enclosure is not None:
                                    audio_url = enclosure.get("url", "")
                                
                                # Get title
                                title_elem = item.find("title")
                                title_text = title_elem.text if title_elem is not None and title_elem.text else f"Chapter {idx + 1}"
                                
                                # Clean up title
                                if title_text:
                                    title_text = title_text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
                                
                                if audio_url:
                                    audio_url = audio_url.strip().replace("&amp;", "&")
                                
                                # If no URL from RSS, construct it
                                if not audio_url or not audio_url.startswith('http'):
                                    audio_url = f"https://archive.org/download/{book_id}/{book_id}_{idx + 1:02d}.mp3"
                                
                                # Only add if we have a valid URL
                                if audio_url and audio_url.startswith('http'):
                                    tracks.append({
                                        "id": str(idx + 1),
                                        "title": title_text,
                                        "duration": 0,
                                        "duration_formatted": "0:00",
                                        "audio_url": audio_url
                                    })
                            except Exception as item_err:
                                # Skip this chapter if parsing fails
                                print(f"[Audiobooks] Error parsing chapter {idx + 1}: {item_err}")
                                continue
            except Exception as rss_err:
                print(f"[Audiobooks] RSS parsing error: {rss_err}")
        
        # Fallback: construct tracks from num_sections if we have no tracks yet
        if not tracks and num_sections > 0:
            print(f"[Audiobooks] Constructing {num_sections} tracks from book ID")
            for i in range(1, num_sections + 1):
                tracks.append({
                    "id": str(i),
                    "title": f"Chapter {i:02d}",
                    "duration": 0,
                    "duration_formatted": "0:00",
                    "audio_url": f"https://archive.org/download/{book_id}/{book_id}_{i:02d}.mp3"
                })
        
        # Calculate total duration
        total_duration = sum(t.get("duration", 0) for t in tracks)
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        duration_formatted = f"{hours}:{minutes:02d}" if hours > 0 else f"{minutes}"
        
        return {
            "id": book_id_actual,
            "title": title,
            "author": author,
            "duration": total_duration,
            "duration_formatted": duration_formatted,
            "language": language,
            "description": description,
            "cover_url": cover_url,
            "chapters": tracks  # Frontend expects "chapters" - can be empty list
        }
            
    except HTTPException:
        # Re-raise HTTP exceptions (already properly formatted by librivox_get)
        raise
    except Exception as e:
        # Unexpected errors - log but return 502, not 500
        print(f"[Audiobooks] Get book error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Failed to load audiobook: {str(e)}")