import AsyncStorage from "@react-native-async-storage/async-storage";

export type PlaceKind = "I" | "E";

export type PlaceItem = {
  id: string;
  kind: PlaceKind;
  title: string;
  isFav: boolean;
  createdAt: number;
  lastUsed: number;
};

const KEY = "wb:places_v2";

async function readAll(): Promise<PlaceItem[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

async function writeAll(list: PlaceItem[]) {
  await AsyncStorage.setItem(KEY, JSON.stringify(list));
}

export function sortPlaces(items: PlaceItem[]) {
  const favs = items
    .filter((p) => p.isFav)
    .sort((a, b) => (b.lastUsed || b.createdAt) - (a.lastUsed || a.createdAt));

  const recents = items
    .filter((p) => !p.isFav && p.lastUsed > 0)
    .sort((a, b) => b.lastUsed - a.lastUsed);

  const others = items
    .filter((p) => !p.isFav && p.lastUsed === 0)
    .sort((a, b) => b.createdAt - a.createdAt);

  return [...favs, ...recents, ...others];
}

export async function getPlacesSorted() {
  const list = await readAll();
  return sortPlaces(list);
}

export async function saveCurrentLocation(
  title: string,
  kind: PlaceKind = "E"
) {
  const list = await readAll();
  const now = Date.now();

  const normalizedTitle = title.trim().toLowerCase();

  const existingIndex = list.findIndex(
    (p) =>
      p.kind === kind &&
      p.title.trim().toLowerCase() === normalizedTitle
  );

  if (existingIndex !== -1) {
    const updated = list.map((p, idx) =>
      idx === existingIndex ? { ...p, createdAt: now } : p
    );

    await writeAll(updated);
    return { status: "exists" as const, item: updated[existingIndex] };
  }

  const item: PlaceItem = {
    id: `${now}-${Math.random().toString(36).slice(2, 8)}`,
    kind,
    title,
    isFav: false,
    createdAt: now,
    lastUsed: 0,
  };

  await writeAll([item, ...list]);
  return { status: "saved" as const, item };
}

export async function toggleFavourite(id: string) {
  const list = await readAll();
  const updated = list.map((p) =>
    p.id === id ? { ...p, isFav: !p.isFav } : p
  );

  await writeAll(updated);
  return sortPlaces(updated);
}

export async function markUsed(id: string) {
  const list = await readAll();
  const now = Date.now();

  const updated = list.map((p) =>
    p.id === id ? { ...p, lastUsed: now } : p
  );

  await writeAll(updated);
  return sortPlaces(updated);
}
