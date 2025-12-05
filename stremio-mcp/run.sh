#!/usr/bin/env bash
set -e

CONFIG_PATH=/data/options.json

# Read configuration from Home Assistant addon options
TMDB_API_KEY=$(jq -r '.tmdb_api_key' "$CONFIG_PATH")
ANDROID_TV_HOST=$(jq -r '.android_tv_host' "$CONFIG_PATH")
ANDROID_TV_PORT=$(jq -r '.android_tv_port' "$CONFIG_PATH")
STREMIO_AUTH_KEY=$(jq -r '.stremio_auth_key // ""' "$CONFIG_PATH")
ADB_CONNECT_RETRIES=$(jq -r '.adb_connect_retries // 10' "$CONFIG_PATH")
ADB_RETRY_DELAY=$(jq -r '.adb_retry_delay // 5' "$CONFIG_PATH")

# Export environment variables
export TMDB_API_KEY
export ANDROID_TV_HOST
export ANDROID_TV_PORT
export STREMIO_AUTH_KEY

echo "Starting Stremio MCP Server..."
echo "Android TV: ${ANDROID_TV_HOST}:${ANDROID_TV_PORT}"

# Function to check if ADB is connected and authenticated
check_adb_connection() {
    local target="${ANDROID_TV_HOST}:${ANDROID_TV_PORT}"
    local status
    # Use grep -F for exact literal string matching to avoid partial hostname matches
    status=$(adb devices 2>/dev/null | grep -F "$target" | awk '{print $2}')
    
    if [ "$status" = "device" ]; then
        return 0  # Connected and authenticated
    else
        return 1  # Not connected or not authenticated
    fi
}

# Initialize ADB connection if host is configured
if [ -n "$ANDROID_TV_HOST" ]; then
    echo "Connecting to Android TV via ADB..."
    
    # Initial connection attempt
    adb connect "${ANDROID_TV_HOST}:${ANDROID_TV_PORT}" || true
    
    # Wait for authentication with retries
    echo "Waiting for ADB authentication (retrying up to ${ADB_CONNECT_RETRIES} times, ${ADB_RETRY_DELAY}s delay)..."
    echo "If this is the first connection, please accept the RSA key on your Android TV."
    
    for i in $(seq 1 "$ADB_CONNECT_RETRIES"); do
        if check_adb_connection; then
            echo "ADB connected and authenticated successfully!"
            break
        fi
        
        if [ "$i" -eq "$ADB_CONNECT_RETRIES" ]; then
            echo "Warning: ADB authentication not completed after ${ADB_CONNECT_RETRIES} attempts."
            echo "The server will continue, but ADB commands may fail."
            echo "Please ensure you accept the RSA key prompt on your Android TV."
        else
            echo "Attempt $i/${ADB_CONNECT_RETRIES}: Waiting for authentication... (${ADB_RETRY_DELAY}s)"
            sleep "$ADB_RETRY_DELAY"
            # Retry connection in case it dropped
            adb connect "${ANDROID_TV_HOST}:${ANDROID_TV_PORT}" 2>/dev/null || true
        fi
    done
fi

# Run the MCP server
cd /app
exec python3 stremio_mcp.py
