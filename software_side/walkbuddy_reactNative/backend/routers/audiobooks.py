"""
Audiobooks Router - LibriVox Integration
Provides endpoints for searching, fetching details, and streaming audiobooks.
"""
import httpx
import os
import time
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, Response
from typing import Dict, Optional
from opentelemetry import trace

router = APIRouter(prefix="/audiobooks", tags=["audiobooks"])
tracer = trace.get_tracer("audiobooks.router")

# LibriVox API configuration
LIBRIVOX_API = "https://librivox.org/api/feed/audiobooks/"

# SSL verification toggle (for dev environments with cert issues)
VERIFY_SSL = os.getenv("LIBRIVOX_VERIFY_SSL", "1").lower() not in ("0", "false", "no")

# Simple in-memory cache for search results
SEARCH_CACHE: Dict[str, tuple] = {}
CACHE_TTL = 1800  # 30 minutes
CACHE_VERSION = "v2"

# Cache for Open Library cover lookups
COVER_CACHE: Dict[str, tuple] = {}
COVER_CACHE_TTL = 86400  # 24 hours

# Cache for filter options
FILTERS_CACHE: Optional[tuple] = None
FILTERS_CACHE_TTL = 600  # 10 minutes


def cache_get(key: str) -> Optional[dict]:
    item = SEARCH_CACHE.get(key)
    if not item:
        return None
    expires_at, data = item
    if time.time() > expires_at:
        SEARCH_CACHE.pop(key, None)
        return None
    return data


def cache_set(key: str, data: dict, ttl: int = CACHE_TTL) -> None:
    SEARCH_CACHE[key] = (time.time() + ttl, data)


def normalize_genre(genre: str) -> str:
    if not genre:
        return ""
    normalized = genre.strip().lower()
    genre_map = {
        "fiction": "Fiction (Classics)", "classics": "Fiction (Classics)",
        "classic": "Fiction (Classics)", "literature": "Fiction (Classics)",
        "fantasy": "Fantasy", "fantasy fiction": "Fantasy", "mythology": "Fantasy",
        "mystery": "Mystery & Crime", "crime": "Mystery & Crime",
        "detective": "Mystery & Crime", "thriller": "Mystery & Crime",
        "romance": "Romance", "romantic": "Romance",
        "science fiction": "Science Fiction", "sci-fi": "Science Fiction",
        "scifi": "Science Fiction", "sf": "Science Fiction",
        "horror": "Horror", "gothic": "Horror", "supernatural": "Horror",
        "history": "History", "historical": "History", "biography": "History",
        "autobiography": "History", "war": "History",
        "philosophy": "Philosophy", "ethics": "Philosophy",
        "religion": "Religion & Spirituality", "spirituality": "Religion & Spirituality",
        "theology": "Religion & Spirituality", "bible": "Religion & Spirituality",
        "children": "Children's Books", "children's": "Children's Books",
        "juvenile": "Children's Books", "young adult": "Children's Books",
        "fairy tale": "Children's Books", "fairy tales": "Children's Books",
    }
    if normalized in genre_map:
        return genre_map[normalized]
    for key, value in genre_map.items():
        if key in normalized or normalized in key:
            return value
    return normalized


async def librivox_get(
    params: dict,
    timeout_total: float = 12.0,
    timeout_connect: float = 5.0,
    allow_404: bool = False,
) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_total, connect=timeout_connect),
            follow_redirects=True,
            verify=VERIFY_SSL,
        ) as client:
            r = await client.get(LIBRIVOX_API, params=params)
            if r.status_code == 404 and allow_404:
                return None
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        raise HTTPException(status_code=502, detail=f"LibriVox API returned {status}")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Cannot reach LibriVox (connection error)")
    except (httpx.ReadTimeout, httpx.ConnectTimeout):
        raise HTTPException(status_code=502, detail="LibriVox request timed out")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"LibriVox request failed: {e}")


def _parse_book(book: dict) -> Optional[dict]:
    """Parse a LibriVox book dict into our response format. Returns None on error."""
    if not isinstance(book, dict):
        return None
    try:
        book_id = str(book.get("id") or "")
        title = book.get("title") or "Untitled"

        author = "Unknown Author"
        if book.get("author"):
            author = str(book["author"]).strip()
        elif isinstance(book.get("authors"), list) and book["authors"]:
            a = book["authors"][0]
            if isinstance(a, dict):
                author = f"{a.get('first_name', '')} {a.get('last_name', '')}".strip() or "Unknown Author"
            elif isinstance(a, str):
                author = a.strip() or "Unknown Author"

        total_duration = 0
        duration_formatted = "0:00"
        if book.get("totaltime"):
            try:
                parts = str(book["totaltime"]).split(":")
                if len(parts) == 3:
                    total_duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:
                    total_duration = int(parts[0]) * 60 + int(parts[1])
                hours = total_duration // 3600
                minutes = (total_duration % 3600) // 60
                duration_formatted = f"{hours}:{minutes:02d}" if hours > 0 else f"{minutes}"
            except (ValueError, TypeError):
                pass

        book_language = book.get("language") or "Unknown"

        book_genre = None
        for field in ("subject", "genre", "category"):
            if book.get(field):
                book_genre = normalize_genre(str(book[field]))
                break

        description = book.get("description") or ""

        # Extract archive.org identifier (slug, not numeric LibriVox ID)
        ia_id = None
        if book.get("url_iarchive"):
            # e.g. "https://archive.org/details/penguin_island_ms_librivox"
            url_ia = str(book["url_iarchive"]).rstrip("/")
            ia_id = url_ia.split("/")[-1]
        elif book.get("url_zip_file"):
            # e.g. "https://archive.org/compress/penguin_island_ms_librivox/formats=..."
            url_zip = str(book["url_zip_file"])
            parts = url_zip.split("/")
            # index 0="https:", 1="", 2="archive.org", 3="compress", 4=identifier
            if len(parts) > 4:
                ia_id = parts[4]

        cover_url = ""
        for field in ("coverart", "cover"):
            if book.get(field):
                cover_url = str(book[field])
                break
        if cover_url.startswith("http://"):
            cover_url = cover_url.replace("http://", "https://", 1)
        # Use archive.org thumbnail service — always returns an image for any item
        if ia_id:
            cover_url = f"https://archive.org/services/img/{ia_id}"

        sample_audio_url = ""
        if ia_id:
            sample_audio_url = f"https://archive.org/download/{ia_id}/{ia_id}_01.mp3"

        return {
            "id": book_id,
            "title": title,
            "author": author,
            "duration": total_duration,
            "duration_formatted": duration_formatted,
            "language": book_language,
            "description": description,
            "cover_url": cover_url,
            "genre": book_genre or "",
            "sample_audio_url": sample_audio_url,
            "first_track_url": sample_audio_url,
        }
    except Exception:
        return None


@router.get("/search")
async def search_audiobooks(
    q: str = Query("", description="Search query"),
    language: Optional[str] = Query(None),
    genre: Optional[str] = Query(None),
    min_duration: Optional[int] = Query(None, ge=0),
    max_duration: Optional[int] = Query(None, ge=0),
    narrator_type: Optional[str] = Query(None),
    sort: Optional[str] = Query("relevance"),
    limit: int = Query(25, ge=1, le=100),
):
    has_filters = bool(language or genre or min_duration is not None or max_duration is not None)
    search_query = q.strip() if q and q.strip() else ""

    if not search_query and not has_filters:
        return {"query": "", "count": 0, "results": [], "filters_applied": {
            "language": language, "genre": genre,
            "min_duration": min_duration, "max_duration": max_duration, "sort": sort,
        }}

    try:
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
        cache_key = f"{CACHE_VERSION}:search:{search_query.lower() or '*'}::{filter_str}:{limit}"

        cached = cache_get(cache_key)
        if cached:
            return cached

        fetch_limit = limit * 5 if not search_query and has_filters else limit
        query_clean = search_query or "*"

        data = None

        # Strategy 1: keyword search (broad, works for partial/lowercase matches)
        with tracer.start_as_current_span("search.strategy.keyword") as span:
            data = await librivox_get(
                {"format": "json", "keyword": query_clean, "extended": "1", "limit": fetch_limit},
                allow_404=True,
            )
            span.set_attribute("success", data is not None)

        # Strategy 2: exact title match
        if data is None:
            with tracer.start_as_current_span("search.strategy.title") as span:
                data = await librivox_get(
                    {"format": "json", "title": query_clean, "extended": "1", "limit": fetch_limit},
                    allow_404=True,
                )
                span.set_attribute("success", data is not None)

        # Strategy 3: no filter — return latest books (fallback for browse/empty query)
        if data is None and not search_query:
            with tracer.start_as_current_span("search.strategy.browse") as span:
                data = await librivox_get(
                    {"format": "json", "extended": "1", "limit": fetch_limit},
                    allow_404=True,
                )
                span.set_attribute("success", data is not None)

        if data is None:
            return {"query": search_query, "count": 0, "results": [], "filters_applied": {
                "language": language, "genre": genre,
                "min_duration": min_duration, "max_duration": max_duration, "sort": sort,
            }}

        books = []
        if isinstance(data, dict):
            books = data.get("books", []) if isinstance(data.get("books"), list) else []
        elif isinstance(data, list):
            books = data

        results = []
        for book in books:
            parsed = _parse_book(book)
            if not parsed:
                continue
            if language and parsed["language"].lower().strip() != language.lower().strip():
                continue
            if genre:
                requested = normalize_genre(genre)
                if not parsed["genre"] or normalize_genre(parsed["genre"]) != requested:
                    continue
            if min_duration is not None and parsed["duration"] < min_duration:
                continue
            if max_duration is not None and parsed["duration"] > max_duration:
                continue
            results.append(parsed)

        if sort == "title_az":
            results.sort(key=lambda x: x["title"].lower())
        elif sort == "author_az":
            results.sort(key=lambda x: x["author"].lower())
        elif sort == "longest":
            results.sort(key=lambda x: x["duration"], reverse=True)
        elif sort == "newest":
            results.sort(key=lambda x: int(x["id"]) if x["id"].isdigit() else 0, reverse=True)

        results = results[:limit]
        response_data = {
            "query": search_query,
            "count": len(results),
            "results": results,
            "filters_applied": {
                "language": language, "genre": genre,
                "min_duration": min_duration, "max_duration": max_duration, "sort": sort,
            },
        }
        cache_set(cache_key, response_data)
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")


@router.get("/filters")
async def get_filter_options():
    global FILTERS_CACHE
    if FILTERS_CACHE:
        expires_at, data = FILTERS_CACHE
        if time.time() < expires_at:
            return data
    filter_options = {
        "languages": ["English", "Spanish", "French", "German", "Italian", "Portuguese", "Russian"],
        "genres": [
            "Fiction (Classics)", "Fantasy", "Mystery & Crime", "Romance",
            "Science Fiction", "Horror", "History", "Philosophy",
            "Religion & Spirituality", "Children's Books",
        ],
        "durationBuckets": ["<1h", "1-3h", "3-10h", "10h+"],
        "sortOptions": ["relevance", "popular", "newest", "longest", "title_az", "author_az"],
    }
    FILTERS_CACHE = (time.time() + FILTERS_CACHE_TTL, filter_options)
    return filter_options


@router.get("/popular")
async def get_popular_audiobooks(
    limit: int = Query(10, ge=1, le=50),
):
    popular_titles = [
        "Pride and Prejudice",
        "Frankenstein",
        "Alice's Adventures in Wonderland",
        "The Adventures of Sherlock Holmes",
        "Moby Dick",
        "Dracula",
        "The Time Machine",
        "The War of the Worlds",
        "Treasure Island",
        "Jane Eyre",
        "Wuthering Heights",
        "A Christmas Carol",
        "Little Women",
        "The Secret Garden",
        "The Call of the Wild",
        "Anne of Green Gables",
        "The Wonderful Wizard of Oz",
        "The Adventures of Tom Sawyer",
        "Adventures of Huckleberry Finn",
        "The Picture of Dorian Gray",
        "The Strange Case of Dr. Jekyll and Mr. Hyde",
        "The Count of Monte Cristo",
        "Great Expectations",
        "A Tale of Two Cities",
        "Oliver Twist",
        "The Jungle Book",
        "Peter Pan",
        "Around the World in Eighty Days",
        "Robinson Crusoe",
        "The Invisible Man"
    ]

    def get_books_from_data(data):
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

        return books

    def convert_book(book):
        book_id_raw = book.get("id")
        book_id = str(book_id_raw) if book_id_raw is not None else ""

        if not book_id:
            return None

        title = book.get("title") or "Untitled"

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
                pass

        book_language = book.get("language") or "Unknown"

        book_genre = ""
        if "subject" in book and book["subject"]:
            book_genre = normalize_genre(str(book["subject"]))
        elif "genre" in book and book["genre"]:
            book_genre = normalize_genre(str(book["genre"]))
        elif "category" in book and book["category"]:
            book_genre = normalize_genre(str(book["category"]))

        description = book.get("description") or ""

        cover_url = ""
        if "coverart" in book and book["coverart"]:
            cover_url = str(book["coverart"])
        elif "cover" in book and book["cover"]:
            cover_url = str(book["cover"])
        elif "url_zip_file" in book and book["url_zip_file"]:
            cover_url = str(book["url_zip_file"]).replace(".zip", "_1200.jpg")

        if cover_url and cover_url.startswith("http://"):
            cover_url = cover_url.replace("http://", "https://", 1)

        sample_audio_url = ""
        if "sections" in book and isinstance(book["sections"], list) and len(book["sections"]) > 0:
            first_section = book["sections"][0]
            if isinstance(first_section, dict):
                sample_audio_url = first_section.get("listen_url") or ""

        if not sample_audio_url and book_id:
            sample_audio_url = f"https://archive.org/download/{book_id}/{book_id}_01.mp3"

        return {
            "id": book_id,
            "title": title,
            "author": author,
            "duration": total_duration,
            "duration_formatted": duration_formatted,
            "language": book_language,
            "description": description,
            "cover_url": cover_url,
            "genre": book_genre,
            "sample_audio_url": sample_audio_url,
            "first_track_url": sample_audio_url
        }

    try:
        cache_key = f"{CACHE_VERSION}:popular:{limit}"
        cached_result = cache_get(cache_key)

        if cached_result:
            print("[Audiobooks] Cache hit for popular audiobooks")
            return cached_result

        results = []
        seen_ids = set()

        for title_query in popular_titles:
            if len(results) >= limit:
                break

            search_attempts = [
                title_query,
                f"^{title_query}"
            ]

            for search_title in search_attempts:
                if len(results) >= limit:
                    break

                params = {
                    "format": "json",
                    "title": search_title,
                    "extended": "1",
                    "limit": 5
                }

                data = await librivox_get(
                    params,
                    timeout_total=12.0,
                    timeout_connect=5.0,
                    allow_404=True
                )

                if data is None:
                    continue

                books = get_books_from_data(data)

                for book in books:
                    if not isinstance(book, dict):
                        continue

                    try:
                        converted_book = convert_book(book)

                        if not converted_book:
                            continue

                        book_id = converted_book["id"]

                        if book_id in seen_ids:
                            continue

                        results.append(converted_book)
                        seen_ids.add(book_id)
                        break

                    except Exception as book_err:
                        print(f"[Audiobooks] Error parsing popular book {book.get('id', 'unknown')}: {book_err}")
                        continue

        if len(results) < limit:
            fallback_params = {
                "format": "json",
                "extended": "1",
                "limit": 100
            }

            fallback_data = await librivox_get(
                fallback_params,
                timeout_total=12.0,
                timeout_connect=5.0,
                allow_404=True
            )

            if fallback_data is not None:
                fallback_books = get_books_from_data(fallback_data)

                for book in fallback_books:
                    if len(results) >= limit:
                        break

                    if not isinstance(book, dict):
                        continue

                    try:
                        converted_book = convert_book(book)

                        if not converted_book:
                            continue

                        book_id = converted_book["id"]

                        if book_id in seen_ids:
                            continue

                        results.append(converted_book)
                        seen_ids.add(book_id)

                    except Exception as book_err:
                        print(f"[Audiobooks] Error parsing fallback popular book {book.get('id', 'unknown')}: {book_err}")
                        continue

        response_data = {
            "query": "popular",
            "count": len(results),
            "results": results,
            "filters_applied": {
                "language": None,
                "genre": None,
                "min_duration": None,
                "max_duration": None,
                "sort": "popular"
            }
        }

        cache_set(cache_key, response_data)
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Audiobooks] Popular audiobooks error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Popular audiobooks failed: {str(e)}")


@router.get("/stream")
@router.head("/stream")
async def stream_audiobook(
    request: Request,
    url: str = Query(..., description="Audio file URL to stream"),
):
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=True,
            verify=VERIFY_SSL,
        ) as client:
            if request.method == "HEAD":
                resp = await client.head(url)
                return Response(
                    status_code=resp.status_code,
                    headers={
                        k: v for k, v in resp.headers.items()
                        if k.lower() in ("content-type", "content-length", "accept-ranges")
                    },
                )

            headers = {}
            if "range" in request.headers:
                headers["Range"] = request.headers["range"]

            async with client.stream("GET", url, headers=headers) as resp:
                response_headers = {
                    "Accept-Ranges": "bytes",
                }
                if resp.headers.get("content-length"):
                    response_headers["Content-Length"] = resp.headers["content-length"]
                if resp.headers.get("content-range"):
                    response_headers["Content-Range"] = resp.headers["content-range"]

                # Force audio/mpeg for MP3 URLs — some servers return
                # application/octet-stream which browsers reject for <audio>.
                ct = resp.headers.get("content-type", "audio/mpeg")
                if url.lower().endswith(".mp3") and "audio" not in ct:
                    ct = "audio/mpeg"
                return StreamingResponse(
                    resp.aiter_bytes(chunk_size=65536),
                    status_code=resp.status_code,
                    media_type=ct,
                    headers=response_headers,
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stream failed: {e}")


@router.get("/cover")
async def get_cover_fallback(
    title: str = Query(...),
    author: str = Query(""),
):
    cache_key = f"cover:{title.lower()}:{author.lower()}"
    cached_item = COVER_CACHE.get(cache_key)
    if cached_item:
        expires_at, cover_url = cached_item
        if time.time() < expires_at:
            return {"cover_url": cover_url}

    cover_url = None
    try:
        query = f"{title} {author}".strip()
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            resp = await client.get(
                "https://openlibrary.org/search.json",
                params={"q": query, "limit": "1", "fields": "cover_i"},
            )
            data = resp.json()
            docs = data.get("docs", [])
            if docs and docs[0].get("cover_i"):
                cover_id = docs[0]["cover_i"]
                cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
    except Exception:
        pass

    COVER_CACHE[cache_key] = (time.time() + COVER_CACHE_TTL, cover_url)
    return {"cover_url": cover_url}


@router.get("/cover-proxy")
async def proxy_cover_image(
    url: str = Query(..., description="Cover image URL to proxy"),
):
    try:
        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=True, verify=VERIFY_SSL
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return Response(
                content=resp.content,
                media_type=resp.headers.get("content-type", "image/jpeg"),
            )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cover proxy failed: {e}")


@router.get("/{book_id}")
async def get_audiobook_details(book_id: str):
    cache_key = f"{CACHE_VERSION}:book:{book_id}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    data = await librivox_get(
        {"format": "json", "id": book_id, "extended": "1"},
        allow_404=True,
    )

    if not data:
        raise HTTPException(404, "Book not found")

    books = data.get("books", []) if isinstance(data, dict) else []
    if not books:
        raise HTTPException(404, "Book not found")

    parsed = _parse_book(books[0])
    if not parsed:
        raise HTTPException(500, "Failed to parse book data")

    # Also include full sections/chapters if available
    raw = books[0]
    sections = []
    if isinstance(raw.get("sections"), list):
        for s in raw["sections"]:
            if isinstance(s, dict):
                audio_url = s.get("listen_url", "")
                # Normalise archive.org http → https so proxy doesn't get redirects
                if audio_url.startswith("http://"):
                    audio_url = audio_url.replace("http://", "https://", 1)
                sections.append({
                    "id": str(s.get("id") or s.get("section_number") or len(sections) + 1),
                    "title": s.get("title", f"Chapter {len(sections) + 1}"),
                    "duration": s.get("playtime", ""),
                    "audio_url": audio_url,
                    "reader": s.get("reader_name", ""),
                })

    # Fallback: if LibriVox returned no sections, synthesise one chapter from first_track_url
    if not sections and parsed.get("first_track_url"):
        sections.append({
            "id": "1",
            "title": parsed["title"],
            "duration": parsed.get("duration_formatted", ""),
            "audio_url": parsed["first_track_url"],
            "reader": "",
        })

    parsed["chapters"] = sections

    cache_set(cache_key, parsed, ttl=3600)
    return parsed
