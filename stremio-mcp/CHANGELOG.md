# Changelog

## [1.2.0] - Home Assistant Ingress & Web Interface

- Added Home Assistant Ingress support for sidebar access
- Added built-in web test interface with:
  - Search functionality for movies and TV shows
  - Playback controls (play/pause, stop, skip, rewind, fast forward)
  - Volume controls (up, down, mute, set level)
  - Navigation D-pad (up, down, left, right, OK, back, home)
  - Power controls (wake, sleep, status)
  - Real-time output logging
- Server now accessible via HA sidebar panel
- Added `/api/call-tool` endpoint for web interface
- Added `/api/status` endpoint for connection status

## [1.1.0] - SSE Transport Support

- Added SSE (Server-Sent Events) transport support for remote MCP access
- SSE mode is now the default, enabling direct HTTP-based connections
- Added configurable `mcp_transport` option (`sse` or `stdio`)
- Added configurable `mcp_port` option for SSE server (default: 9821)
- Updated documentation with SSE configuration examples for Claude Desktop
- Exposed port 9821 in Docker container for SSE connections

## [1.0.1] - ADB Authentication Improvements

- Added retry mechanism for ADB authentication to allow time for RSA key acceptance on Android TV
- Added configurable `adb_connect_retries` option (default: 10) for number of authentication retries
- Added configurable `adb_retry_delay` option (default: 5 seconds) for delay between retries
- Improved logging during ADB connection process

## [1.0.0] - Initial Release

- Initial Home Assistant addon release
- ADB integration for Android TV control
- TMDB API integration for movie/TV show search
- Stremio library access (optional)
- UI-configurable options
