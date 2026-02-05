# Audiobooks Feature Documentation

## Overview

The Audiobooks feature provides a comprehensive audiobook search, discovery, and playback system integrated with LibriVox's free public domain audiobook library. The feature is designed with accessibility in mind, supporting screen readers and voice input for visually impaired users.

## Features

### Core Functionality
- **Search**: Search audiobooks by title, author, or keywords
- **Filters**: Filter by language (150+ languages), genre (10 standardized genres), duration, and sort options
- **Voice Search**: Microphone input for hands-free search
- **Streaming**: Stream audiobook chapters with HTTP range request support (206 Partial Content)
- **Player**: Full-featured audio player with progress tracking, chapter navigation, and playback controls
- **Favorites**: Save favorite audiobooks for quick access
- **Listen Later**: Queue audiobooks for later listening
- **History**: Track listening history
- **User Guide**: First-time user guide with FAQs

### Accessibility Features
- Screen reader-friendly UI with proper accessibility labels
- Text-to-speech announcements for book titles when opened
- Voice search for hands-free operation
- Keyboard navigation support
- High contrast UI elements

## Backend API Endpoints

### Base Path
All endpoints are prefixed with `/audiobooks`

### Endpoints

#### `GET /audiobooks/filters`
Returns available filter options.

**Response:**
```json
{
  "languages": ["English", "Spanish", ...],
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
```

**Caching:** 10 minutes

#### `GET /audiobooks/search`
Search for audiobooks with optional filters.

**Query Parameters:**
- `q` (optional): Search query string
- `language` (optional): Filter by language
- `genre` (optional): Filter by genre (from standardized list)
- `min_duration` (optional): Minimum duration in seconds
- `max_duration` (optional): Maximum duration in seconds
- `sort` (optional): Sort option (from sortOptions)
- `limit` (optional): Results limit (default: 25)

**Response:**
```json
{
  "results": [
    {
      "id": "12345",
      "title": "Book Title",
      "author": "Author Name",
      "language": "English",
      "total_time": 3600,
      "cover_url": "https://...",
      "url_librivox": "https://..."
    }
  ],
  "total": 100,
  "filters_applied": {
    "language": "English",
    "genre": "Science Fiction"
  }
}
```

**Caching:** 30 minutes (keyed by query + filters + sort + limit)

#### `GET /audiobooks/{book_id}`
Get detailed information about a specific audiobook.

**Response:**
```json
{
  "id": "12345",
  "title": "Book Title",
  "author": "Author Name",
  "language": "English",
  "total_time": 3600,
  "total_time_formatted": "1h 0m",
  "description": "Book description...",
  "cover_url": "https://...",
  "chapters": [
    {
      "id": "chapter_1",
      "title": "Chapter 1",
      "duration": 1800,
      "duration_formatted": "30m",
      "audio_url": "https://..."
    }
  ]
}
```

#### `GET /audiobooks/{book_id}/stream/{chapter_id}`
Stream an audiobook chapter with HTTP range request support.

**Headers:**
- `Range` (optional): `bytes=start-end` for partial content requests

**Response:**
- `200 OK`: Full audio file
- `206 Partial Content`: Partial audio file (range request)
- `Content-Type`: `audio/mpeg` or appropriate audio type
- `Content-Length`: File size
- `Accept-Ranges`: `bytes`

**Features:**
- Retry logic with exponential backoff
- HTTP to HTTPS URL conversion
- Proper CORS headers
- Range request support for seeking

#### `GET /audiobooks/popular`
Get popular audiobooks.

**Query Parameters:**
- `limit` (optional): Number of results (default: 10)

**Response:**
Same format as `/audiobooks/search`

## Frontend Components

### Main Screen (`app/(tabs)/audiobooks.tsx`)
- Search bar with voice input
- Filter bar with chips (Language, Genre, Duration, Sort)
- Search results list
- Popular books display
- User guide button
- Menu with favorites, history, listen later

### Player Screen (`app/audiobooks-player.tsx`)
- Audio playback controls
- Chapter list and navigation
- Progress tracking
- Playback speed control
- TTS announcement of book title

### Filter Components
- **FilterBar**: Displays active filters as chips
- **FilterModal**: Bottom sheet modal for selecting filter options
- **UserGuideModal**: User guide and FAQs

### Utility Files
- **audiobookStorage.ts**: Local storage for favorites, history, listen later
- **webTTS.ts**: Web platform TTS utilities

## Setup Instructions

### Backend Setup

1. Install dependencies:
```bash
cd backend
pip install fastapi uvicorn httpx
```

2. Ensure `backend/routers/audiobooks.py` is in place

3. The router is automatically included in `backend/main.py`:
```python
from routers import audiobooks as audiobooks_router
app.include_router(audiobooks_router.router)
```

4. Start the backend:
```bash
python main.py
```

### Frontend Setup

1. Install dependencies (if not already installed):
```bash
cd frontend_reactNative
npm install
```

2. Required packages:
- `@react-native-async-storage/async-storage`
- `expo-av`
- `expo-speech`
- `@react-native-community/slider`

3. The audiobooks tab is automatically added to `app/(tabs)/_layout.tsx`

4. Start the frontend:
```bash
npm start
```

## Testing

### Backend Testing

1. **Test filters endpoint:**
```bash
curl http://localhost:8000/audiobooks/filters
```

2. **Test search:**
```bash
curl "http://localhost:8000/audiobooks/search?q=science&language=English&limit=5"
```

3. **Test book details:**
```bash
curl http://localhost:8000/audiobooks/12345
```

4. **Test streaming:**
```bash
curl -H "Range: bytes=0-1023" http://localhost:8000/audiobooks/12345/stream/chapter_1
```

### Frontend Testing

1. **Search Test:**
   - Open the Audiobooks tab
   - Type a search query (e.g., "science fiction")
   - Verify results appear

2. **Filter Test:**
   - Click on filter chips (Language, Genre, Duration, Sort)
   - Select filter options
   - Click "Search Audiobooks" button
   - Verify filtered results

3. **Voice Search Test:**
   - Click microphone icon in search bar
   - Speak a book title
   - Verify text appears in search bar
   - Verify search is triggered automatically

4. **Player Test:**
   - Click on an audiobook
   - Verify TTS announcement plays
   - Click play button
   - Verify audio plays
   - Test chapter navigation
   - Test progress slider

5. **Favorites/History/Listen Later:**
   - Add a book to favorites
   - Navigate to Favorites screen
   - Verify book appears
   - Play a book and verify it's added to history

## Genre Normalization

The backend normalizes various genre names from LibriVox to 10 standardized genres:

- **Fiction (Classics)**: fiction, classics, literature, novel, literary fiction
- **Fantasy**: fantasy, fantasy fiction, magic, mythology
- **Mystery & Crime**: mystery, crime, detective, thriller, suspense, murder
- **Romance**: romance, romantic, love story
- **Science Fiction**: science fiction, sci-fi, scifi, sf, speculative fiction
- **Horror**: horror, gothic, ghost story, supernatural, vampire, zombie
- **History**: history, historical, historical fiction, biography, autobiography, memoir, war, military
- **Philosophy**: philosophy, philosophical, ethics, metaphysics, logic
- **Religion & Spirituality**: religion, spirituality, religious, theology, bible, christian, islam, judaism, buddhism, hinduism, prayer, meditation
- **Children's Books**: children, children's, childrens, juvenile, young adult, ya, kids, fairy tale, fairy tales, nursery rhyme

## Caching Strategy

- **Search Results**: 30 minutes TTL, keyed by query + filters + sort + limit
- **Filter Options**: 10 minutes TTL
- **Open Library Covers**: 24 hours TTL

## Error Handling

- All endpoints return helpful error messages
- No 500 errors - all exceptions are caught and return appropriate HTTP status codes
- Frontend displays user-friendly error messages
- Retry logic for streaming endpoints with exponential backoff

## Performance Optimizations

- Parallel loading of filters and popular books on frontend
- Request timeouts (8s for filters, 10s for popular)
- Debounced search input (500ms)
- Optimized FlatList rendering (initialNumToRender, maxToRenderPerBatch)
- AbortController for canceling stale requests

## Accessibility

- All interactive elements have `accessibilityLabel` props
- Screen reader announcements for book titles
- Voice search for hands-free operation
- Keyboard navigation support
- High contrast UI elements
- Focus management in modals

## Notes

- LibriVox API is used for audiobook data (free, public domain)
- Open Library API is used for book cover images
- Streaming supports HTTP range requests for seeking
- All URLs are converted from HTTP to HTTPS for security
- First-time users see a welcome guide automatically
