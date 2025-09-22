// app/lib/favourites.ts
import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'wb:favourites';

export type Favourite = {
  id: string;        // unique id
  title: string;     // e.g., "Science"
  distance: string;  // e.g., "40 ft"
  clock: string;     // e.g., "9 o'clock"
  savedAt: number;   // timestamp
};

async function read(): Promise<Favourite[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

async function write(list: Favourite[]) {
  await AsyncStorage.setItem(KEY, JSON.stringify(list));
}

export async function getFavourites() {
  return read();
}

export async function addFavourite(data: Omit<Favourite, 'id'|'savedAt'>) {
  const list = await read();
  const exists = list.some(f => f.title.toLowerCase() === data.title.toLowerCase());
  if (!exists) {
    list.push({
      id: `${Date.now()}-${Math.random().toString(36).slice(2,8)}`,
      savedAt: Date.now(),
      ...data,
    });
    await write(list);
  }
}

export async function removeFavourite(id: string) {
  const list = await read();
  await write(list.filter(f => f.id !== id));
}

export async function clearFavourites() {
  await write([]);
}
