// src/lib/config.ts
// For browser testing: keep localhost
// Later for phone, replace with your LAN IP (e.g. 192.168.x.x)
export const SERVER_HOST = "localhost"; // browser testing. Change to LAN IP for phones later.
export const API_PORT = 8000;           // FastAPI (main.py)
export const GRADIO_PORT = 7860;        // Gradio UI

export const API_BASE = `http://${SERVER_HOST}:${API_PORT}`;
export const GRADIO_URL = `http://${SERVER_HOST}:${GRADIO_PORT}`;

