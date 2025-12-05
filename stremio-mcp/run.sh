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
MCP_TRANSPORT=$(jq -r '.mcp_transport // "sse"' "$CONFIG_PATH")
MCP_PORT=$(jq -r '.mcp_port // 9821' "$CONFIG_PATH")

# Export environment variables
export TMDB_API_KEY
export ANDROID_TV_HOST
export ANDROID_TV_PORT
export STREMIO_AUTH_KEY
export MCP_TRANSPORT
export MCP_PORT

echo "Starting Stremio MCP Server..."
echo "Android TV: ${ANDROID_TV_HOST}:${ANDROID_TV_PORT}"
echo "MCP Transport: ${MCP_TRANSPORT}"

# Set up persistent ADB keys in /share directory (survives add-on updates)
ADB_KEYS_DIR="/share/.android"
mkdir -p "$ADB_KEYS_DIR"

# If keys don't exist in persistent storage, generate them
if [ ! -f "$ADB_KEYS_DIR/adbkey" ]; then
    echo "Generating new ADB keys in persistent storage..."
    # Generate keys using adb (it auto-generates on first use)
    HOME="/share" adb start-server 2>/dev/null || true
    adb kill-server 2>/dev/null || true
    
    # If keys still don't exist, create them manually
    if [ ! -f "$ADB_KEYS_DIR/adbkey" ]; then
        # Use openssl to generate RSA key pair
        openssl genrsa -out "$ADB_KEYS_DIR/adbkey" 2048 2>/dev/null
        openssl rsa -in "$ADB_KEYS_DIR/adbkey" -pubout -out "$ADB_KEYS_DIR/adbkey.pub" 2>/dev/null
        echo "Generated new ADB keys"
    fi
else
    echo "Using existing ADB keys from persistent storage"
fi

# Copy keys to the expected location for adb
mkdir -p /root/.android
cp "$ADB_KEYS_DIR/adbkey" /root/.android/adbkey 2>/dev/null || true
cp "$ADB_KEYS_DIR/adbkey.pub" /root/.android/adbkey.pub 2>/dev/null || true

# Also set ADB_VENDOR_KEYS to use our persistent keys
export ADB_VENDOR_KEYS="$ADB_KEYS_DIR/adbkey"
export HOME="/share"

# For ingress, we always use port 8099
# The external SSE port (default 9821) is also available for direct MCP client connections
INGRESS_PORT=8099
echo "Ingress Port: ${INGRESS_PORT}"
if [ "$MCP_TRANSPORT" = "sse" ]; then
    echo "External SSE Port: ${MCP_PORT}"
fi

# Function to check if ADB is connected and authenticated
check_adb_connection() {
    local target="${ANDROID_TV_HOST}:${ANDROID_TV_PORT}"
    local status
    # Use grep -F for exact literal string matching to avoid partial hostname matches
    # Use head -1 to handle potential duplicate entries in adb devices output
    status=$(adb devices 2>/dev/null | grep -F "$target" | head -1 | awk '{print $2}')
    
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

# Run the MCP server with specified transport
# Use ingress port (8099) for the main server - HA ingress proxies to this
cd /app
exec python3 stremio_mcp.py --transport "$MCP_TRANSPORT" --port "$INGRESS_PORT"
