// frontend_reactNative/src/api/client.ts
import { API_BASE } from "../config";

export async function fetchStatus() {
  try {
    const res = await fetch(`${API_BASE}/status`);
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error("Error fetching status:", err);
    throw err;
  }
}
