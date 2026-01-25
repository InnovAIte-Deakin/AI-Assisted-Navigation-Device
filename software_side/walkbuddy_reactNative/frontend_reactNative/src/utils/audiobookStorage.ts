// Audiobook storage utilities for favorites, history, and listen later
import AsyncStorage from '@react-native-async-storage/async-storage';

const FAVORITES_KEY = '@audiobooks_favorites';
const HISTORY_KEY = '@audiobooks_history';
const LISTEN_LATER_KEY = '@audiobooks_listen_later';

export interface AudiobookItem {
  id: string;
  title: string;
  author: string;
  duration: number;
  duration_formatted: string;
  language: string;
  description: string;
  cover_url: string;
  addedAt: number; // timestamp when added
}

// ========== FAVORITES ==========

export async function getFavorites(): Promise<AudiobookItem[]> {
  try {
    const raw = await AsyncStorage.getItem(FAVORITES_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export async function addFavorite(book: Omit<AudiobookItem, 'addedAt'>): Promise<void> {
  try {
    const favorites = await getFavorites();
    // Check if already exists
    const exists = favorites.some(f => f.id === book.id);
    if (!exists) {
      favorites.push({
        ...book,
        addedAt: Date.now(),
      });
      await AsyncStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites));
    }
  } catch (error) {
    console.error('Failed to add favorite:', error);
    throw error;
  }
}

export async function removeFavorite(bookId: string): Promise<void> {
  try {
    const favorites = await getFavorites();
    const filtered = favorites.filter(f => f.id !== bookId);
    await AsyncStorage.setItem(FAVORITES_KEY, JSON.stringify(filtered));
  } catch (error) {
    console.error('Failed to remove favorite:', error);
    throw error;
  }
}

export async function isFavorite(bookId: string): Promise<boolean> {
  try {
    const favorites = await getFavorites();
    return favorites.some(f => f.id === bookId);
  } catch {
    return false;
  }
}

// ========== HISTORY ==========

export async function getHistory(): Promise<AudiobookItem[]> {
  try {
    const raw = await AsyncStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export async function addToHistory(book: Omit<AudiobookItem, 'addedAt'>): Promise<void> {
  try {
    const history = await getHistory();
    // Remove if already exists (to move to top)
    const filtered = history.filter(h => h.id !== book.id);
    // Add to beginning
    filtered.unshift({
      ...book,
      addedAt: Date.now(),
    });
    // Keep only last 100 items
    const limited = filtered.slice(0, 100);
    await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(limited));
  } catch (error) {
    console.error('Failed to add to history:', error);
    throw error;
  }
}

export async function removeFromHistory(bookId: string): Promise<void> {
  try {
    const history = await getHistory();
    const filtered = history.filter(h => h.id !== bookId);
    await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(filtered));
  } catch (error) {
    console.error('Failed to remove from history:', error);
    throw error;
  }
}

export async function clearHistory(): Promise<void> {
  try {
    await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify([]));
  } catch (error) {
    console.error('Failed to clear history:', error);
    throw error;
  }
}

// ========== LISTEN LATER ==========

export async function getListenLater(): Promise<AudiobookItem[]> {
  try {
    const raw = await AsyncStorage.getItem(LISTEN_LATER_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export async function addToListenLater(book: Omit<AudiobookItem, 'addedAt'>): Promise<void> {
  try {
    const listenLater = await getListenLater();
    // Check if already exists
    const exists = listenLater.some(l => l.id === book.id);
    if (!exists) {
      listenLater.push({
        ...book,
        addedAt: Date.now(),
      });
      await AsyncStorage.setItem(LISTEN_LATER_KEY, JSON.stringify(listenLater));
    }
  } catch (error) {
    console.error('Failed to add to listen later:', error);
    throw error;
  }
}

export async function removeFromListenLater(bookId: string): Promise<void> {
  try {
    const listenLater = await getListenLater();
    const filtered = listenLater.filter(l => l.id !== bookId);
    await AsyncStorage.setItem(LISTEN_LATER_KEY, JSON.stringify(filtered));
  } catch (error) {
    console.error('Failed to remove from listen later:', error);
    throw error;
  }
}

export async function isInListenLater(bookId: string): Promise<boolean> {
  try {
    const listenLater = await getListenLater();
    return listenLater.some(l => l.id === bookId);
  } catch {
    return false;
  }
}
