#!/usr/bin/env bash
set -e

CONFIG_PATH=/data/options.json

# Read configuration from Home Assistant addon options
TMDB_API_KEY=$(jq -r '.tmdb_api_key' "$CONFIG_PATH")
ANDROID_TV_HOST=$(jq -r '.android_tv_host' "$CONFIG_PATH")
ANDROID_TV_PORT=$(jq -r '.android_tv_port' "$CONFIG_PATH")
STREMIO_AUTH_KEY=$(jq -r '.stremio_auth_key // empty' "$CONFIG_PATH")

# Export environment variables
export TMDB_API_KEY
export ANDROID_TV_HOST
export ANDROID_TV_PORT
export STREMIO_AUTH_KEY

echo "Starting Stremio MCP Server..."
echo "Android TV: ${ANDROID_TV_HOST}:${ANDROID_TV_PORT}"

# Initialize ADB connection if host is configured
if [ -n "$ANDROID_TV_HOST" ]; then
    echo "Connecting to Android TV via ADB..."
    adb connect "${ANDROID_TV_HOST}:${ANDROID_TV_PORT}" || echo "ADB connection failed - will retry when needed"
fi

# Run the MCP server
cd /app
exec python3 stremio_mcp.py
