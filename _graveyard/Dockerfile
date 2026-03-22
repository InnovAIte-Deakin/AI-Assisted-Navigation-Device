FROM node:20-bullseye

WORKDIR /app

# Copy manifest first for better caching
COPY frontend_reactNative/package.json frontend_reactNative/package-lock.json* ./

# Preinstall ngrok to avoid interactive tunnel prompt inside Docker
RUN npm install --no-audit --no-fund --save-dev @expo/ngrok@^4.1.0 && \
    (npm ci || npm install)

# Copy the rest of the app
COPY frontend_reactNative/. .

# Helpful env defaults for container usage
ENV EXPO_NO_TELEMETRY=1
ENV EXPO_NO_WEB=1
ENV EXPO_USE_LIGHTNINGCSS=off

EXPOSE 19000 19001 19002 19006 8081

# Start via compose (we still run npm install in compose to hydrate after bind-mount)
CMD ["npm", "run", "start"]
