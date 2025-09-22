import { API_BASE } from "../config";

export async function switchMode(mode: "gradio" | "ocr") {
  const res = await fetch(`${API_BASE}/switch/${mode}`, { method: "GET" });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<{ status: string; mode: string; url: string }>;
}

export async function stopAll() {
  const res = await fetch(`${API_BASE}/stop`, { method: "GET" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
