# Changelog

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
