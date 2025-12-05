# Stremio MCP Server

MCP (Model Context Protocol) server for controlling Stremio on Android TV via ADB.

## Configuration

The addon can be configured through the Home Assistant UI with the following options:

| Option | Required | Description |
|--------|----------|-------------|
| `tmdb_api_key` | Yes | Your TMDB API key for searching movies/TV shows. Get one free at https://www.themoviedb.org/settings/api |
| `android_tv_host` | Yes | IP address of your Android TV |
| `android_tv_port` | No | ADB port (default: 5555) |
| `stremio_auth_key` | No | Your Stremio authentication key for library access |
| `external_api_key` | No | API key for external access via port 9821 (Siri Shortcuts, automations). Generate a random string. |
| `adb_connect_retries` | No | Number of times to retry ADB authentication (default: 3, range: 2-10) |
| `adb_retry_delay` | No | Seconds to wait between ADB authentication retries (default: 30, range: 30-60) |
| `mcp_transport` | No | Transport type: `sse` (default) or `stdio` |
| `mcp_port` | No | Port for external SSE server (default: 9821) |

## External API Access (Siri, Shortcuts, Automations)

There are two ways to access the API externally:

### Option 1: Direct Access via Port 9821 (Recommended for Siri)

This is the simplest method. Set an `external_api_key` in the addon configuration, then access the API directly on port 9821.

1. Set `external_api_key` in the addon configuration (any random string, e.g., `my-secret-key-12345`)
2. Restart the addon
3. Access via port 9821 with your API key

```bash
# Using X-API-Key header (recommended)
curl -X POST "http://YOUR_HA_IP:9821/api/call-tool" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"name": "play", "arguments": {"query": "Wicked", "type": "movie", "auto_play": true}}'

# Or using Authorization Bearer header
curl -X POST "http://YOUR_HA_IP:9821/api/call-tool" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"name": "play", "arguments": {"query": "Wicked", "type": "movie", "auto_play": true}}'

# Or using query parameter
curl -X POST "http://YOUR_HA_IP:9821/api/call-tool?api_key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "play", "arguments": {"query": "Wicked", "type": "movie", "auto_play": true}}'
```

**Note**: You may need to forward port 9821 on your router for external access.

### Siri Shortcut Example

1. Open the **Shortcuts** app on iOS
2. Create a new Shortcut
3. Add **Dictate Text** action → save to variable `MovieName`
4. Add **Get Contents of URL**:
   - URL: `http://YOUR_HA_IP:9821/api/call-tool`
   - Method: POST
   - Headers: 
     - `Content-Type: application/json`
     - `X-API-Key: YOUR_API_KEY`
   - Request Body (JSON):
     ```json
     {
       "name": "play",
       "arguments": {
         "query": "[MovieName variable]",
         "type": "movie",
         "auto_play": true
       }
     }
     ```
5. Add the shortcut to Siri with a phrase like "Play a movie on Stremio"

### Option 2: Using Home Assistant REST Command (Internal Only)

For automations that run within Home Assistant, create a REST command in your `configuration.yaml`:

```yaml
rest_command:
  stremio_play:
    url: "http://127.0.0.1:8099/api/call-tool"
    method: POST
    content_type: "application/json"
    payload: '{"name": "play", "arguments": {"query": "{{ query }}", "type": "{{ type | default(''movie'') }}", "auto_play": true}}'
```

Then call it from automations or scripts:
```yaml
service: rest_command.stremio_play
data:
  query: "Wicked"
  type: "movie"
```

## Web Interface (Ingress)

The addon includes a built-in web interface accessible directly from the Home Assistant sidebar. Click on "Stremio MCP" in the sidebar to access the test interface.

The web interface allows you to:
- **Search** for movies and TV shows
- **Control playback** (play/pause, stop, skip, rewind, fast forward)
- **Adjust volume** (up, down, mute, set level)
- **Navigate** using D-pad controls (up, down, left, right, OK, back, home)
- **Power control** (wake, sleep, status)
- **Launch Stremio** and check playback status

## Transport Modes

The addon supports two transport modes for MCP communication:

### SSE Mode (Default, Recommended for Remote Access)

SSE (Server-Sent Events) mode exposes an HTTP endpoint that MCP clients can connect to remotely. This is the recommended mode for most use cases.

- **Ingress URL**: Available via Home Assistant sidebar
- **External Endpoint**: `http://<homeassistant-ip>:9821/sse`

### Stdio Mode

Stdio mode uses standard input/output for communication. This is useful for local subprocess communication or SSH-based access.

## Getting Your TMDB API Key

1. Create an account at https://www.themoviedb.org/
2. Go to https://www.themoviedb.org/settings/api
3. Request an API key (choose "Developer" option)
4. Copy your API key

## Getting Your Stremio Auth Key (Optional)

1. Go to https://web.stremio.com and login
2. Open browser console (F12)
3. Run: `JSON.parse(localStorage.getItem("profile")).auth.key`
4. Copy the output value

## Android TV Setup

1. Enable Developer Mode on your Android TV:
   - Go to **Settings** > **Device Preferences** > **About**
   - Click on **Build** 7 times to enable Developer Mode
2. Enable ADB debugging:
   - Go back to **Device Preferences** > **Developer Options**
   - Enable **USB Debugging** and **Network Debugging**
3. Note your Android TV's IP address from Settings > Network & Internet

## ADB Key Persistence

ADB authentication keys are stored in `/share/.android/` which persists across add-on updates. This means:

- **First connection**: You'll need to approve the ADB connection on your Android TV
- **After updates**: The same keys are reused, so no re-approval is needed

If you ever need to reset the ADB keys (e.g., if you get authentication errors), you can delete the `/share/.android/` directory through the File Editor add-on or SSH.

## Usage

### Using the Web Interface (Recommended)

1. Open Home Assistant
2. Click on "Stremio MCP" in the sidebar
3. Use the buttons to control your Stremio/Android TV

### Using with Claude Desktop (SSE Mode)

With SSE mode enabled (default), configure Claude Desktop to connect via SSE:

```json
{
  "mcpServers": {
    "stremio": {
      "url": "http://homeassistant.local:9821/sse"
    }
  }
}
```

Replace `homeassistant.local` with your Home Assistant IP address.

### Using with Home Assistant Assist

This addon can be integrated with Home Assistant's Assist feature to control Stremio via voice commands.

### Using with Claude Desktop (Stdio Mode via SSH)

If using stdio mode, configure the MCP server to connect to the Home Assistant addon via SSH:

```json
{
  "mcpServers": {
    "stremio": {
      "command": "ssh",
      "args": [
        "homeassistant.local",
        "docker",
        "exec",
        "-i",
        "addon_local_stremio-mcp",
        "python3",
        "/app/stremio_mcp.py",
        "--transport",
        "stdio"
      ]
    }
  }
}
```

Replace `homeassistant.local` with your Home Assistant IP address.

**Note**: The container name `addon_local_stremio-mcp` is for local addon installations. If installed from a repository, run `docker ps` on your Home Assistant to find the actual container name.
