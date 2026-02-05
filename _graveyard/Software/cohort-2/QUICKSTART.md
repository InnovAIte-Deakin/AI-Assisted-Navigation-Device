# 🚀 WalkBuddy QuickStart Guide

This guide helps you get **WalkBuddy** up and running as fast as possible.  
Follow these steps to run the **backend**, **frontend**, and optionally the **mobile setup**.

---

# 🧠 Backend Setup (Python + FastAPI)

### 1. Navigate to the backend folder
```bash
cd backend
```

### 2. Create a virtual environment
```bash
python3 -m venv venv
```

### 3. Activate the environment  
macOS / Linux:
```bash
source venv/bin/activate
```

Windows:
```powershell
venv\Scripts\activate
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

### 5. Run the backend
```bash
python main.py
```

The backend will now run at:

```
http://localhost:8000
```

---

# 📱 Frontend Setup (React Native + Expo)

### 1. Navigate to the frontend folder
```bash
cd frontend_reactNative
```

### 2. Install dependencies
```bash
npm install
```

### 3. Start the app
```bash
npm run dev
```

Expo will open automatically.  
You can run the app on:

- iOS Simulator  
- Android Emulator  
- Physical device via Expo Go (if on same network)  

---

# 📲 Optional: Running the App on a Physical Phone (Cloudflare Tunnel)

If your phone cannot access your computer’s localhost, use this method.

### 1. Install Cloudflare Tunnel

macOS:
```bash
brew install cloudflared
```

Windows:
```powershell
winget install cloudflare.cloudflared
```

### 2. Start a tunnel (backend must be running)
```bash
cloudflared tunnel --url http://localhost:8000
```

Cloudflare will print a URL like:
```
https://example-12345.trycloudflare.com
```

### 3. Configure the frontend `.env` file

In `frontend_reactNative/`, rename:
```
env-template → .env
```

Add:
```
EXPO_PUBLIC_API_BASE_URL=https://your-cloudflare-url-here
```

### 4. Restart the frontend
```bash
npm run dev
```

Your phone can now communicate with the backend through Cloudflare.

---

# 🧪 Verifying Everything Works

### Backend check
Visit:
```
http://localhost:8000/health
```

Expected response:
```json
{"ok":true}
```

### Frontend check
- The app loads in Expo  
- The camera opens  
- Vision Assist / OCR modes function  
- Requests reach your backend  

---

# 🛠️ Common Issues

### App cannot reach backend
- Wrong URL in `.env`
- Cloudflare tunnel not running
- Expo not restarted after updating env variables

### Backend won’t start
- Virtual environment not activated
- Missing dependencies → reinstall:
  ```bash
  pip install -r requirements.txt
  ```

### Camera errors
- Permissions not granted in Expo Go
- Another app using the camera

---

# 🎉 You’re Ready to Develop!

WalkBuddy should now be fully operational in local development mode.
