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

## Usage with Claude Desktop

Add this to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "stremio": {
      "command": "nc",
      "args": ["homeassistant.local", "3000"]
    }
  }
}
```

Replace `homeassistant.local` with your Home Assistant IP address.
