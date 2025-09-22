import Constants from "expo-constants";

const API = Constants.expoConfig?.extra?.apiBaseUrl;

export async function fetchStatus() {
  try {
    const res = await fetch(`${API}/status`);
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error("Error fetching status:", err);
    throw err;
  }
}
