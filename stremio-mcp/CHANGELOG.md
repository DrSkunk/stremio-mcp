# Changelog

## [1.2.7] - Code Refactoring & ADB Stability Improvements

- Refactored code structure for improved readability and maintainability
- Enhanced ADB authentication handling with duplicate device detection
- Improved ADB connection logic with proper error handling
- Fixed RSA key acceptance flow for more reliable Android TV connections

## [1.2.0] - Home Assistant Addon & Web Interface

- Added Home Assistant addon support for easier installation and configuration
- Added built-in web test interface with:
  - Search functionality for movies and TV shows
  - Playback controls (play/pause, stop, skip, rewind, fast forward)
  - Volume controls (up, down, mute, set level)
  - Navigation D-pad (up, down, left, right, OK, back, home)
  - Power controls (wake, sleep, status)
  - Real-time output logging
- Added `playback_status` tool to get current playback information
- Added `/api/call-tool` endpoint for web interface
- Added `/api/status` endpoint for connection status
- Enhanced ADB retry mechanism for RSA key acceptance on Android TV
- Added configurable `adb_connect_retries` option (default: 10)
- Added configurable `adb_retry_delay` option (default: 5 seconds)
- Improved tool descriptions for better LLM clarity
- Optimized tools into 4 consolidated functions (search, control, status, library)

## [1.1.0] - Android TV Remote Control & Stremio Integration

- Added comprehensive Android TV remote control features:
  - D-pad navigation
  - Media playback controls
  - Volume control
  - Power management
- Added Stremio library access for browsing watched content
- Improved continue watching logic for better context
- Added ADB installation instructions to README
- Removed unused dependencies for cleaner codebase

## [1.0.0] - Initial Release

- Initial Stremio MCP Server for Android TV
- ADB integration for Android TV control
- TMDB API integration for movie/TV show search
- Basic remote control functionality
- Initial tool set for Stremio control
