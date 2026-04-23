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
const MAX_PLACES = 50;

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

function normalizeTitle(title: string) {
  return title.trim().toLowerCase();
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

  const normalizedTitle = normalizeTitle(title);

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

  await writeAll([item, ...list].slice(0, MAX_PLACES));
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

export async function upsertPlaceUsed(title: string, kind: PlaceKind) {
  const list = await readAll();
  const now = Date.now();
  const normalizedTitle = normalizeTitle(title);

  const existingIndex = list.findIndex(
    (p) => p.kind === kind && normalizeTitle(p.title) === normalizedTitle
  );

  let updated: PlaceItem[];
  if (existingIndex !== -1) {
    updated = list.map((p, idx) =>
      idx === existingIndex ? { ...p, title: title.trim(), lastUsed: now } : p
    );
  } else {
    const item: PlaceItem = {
      id: `${now}-${Math.random().toString(36).slice(2, 8)}`,
      kind,
      title: title.trim(),
      isFav: false,
      createdAt: now,
      lastUsed: now,
    };
    updated = [item, ...list].slice(0, MAX_PLACES);
  }

  await writeAll(updated);
  return sortPlaces(updated);
}

export async function getRecentPlaces(limit = 6) {
  const list = await readAll();
  return list
    .filter((p) => p.lastUsed > 0)
    .sort((a, b) => b.lastUsed - a.lastUsed)
    .slice(0, Math.max(0, limit));
}

export async function dismissRecentPlace(id: string) {
  const list = await readAll();

  const existing = list.find((p) => p.id === id);
  if (!existing) return sortPlaces(list);

  const updated = existing.isFav
    ? list.map((p) => (p.id === id ? { ...p, lastUsed: 0 } : p))
    : list.filter((p) => p.id !== id);

  await writeAll(updated);
  return sortPlaces(updated);
}
