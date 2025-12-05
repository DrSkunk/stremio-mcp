#!/usr/bin/env python3
"""
Stremio MCP Server - Control Stremio on Android TV via ADB

Supports both stdio and SSE (Server-Sent Events) transports.
Set MCP_TRANSPORT=sse and MCP_PORT=9821 for SSE mode.
"""

import argparse
import asyncio
import logging
import os
from typing import Any, Optional

import requests
from adb_shell.adb_device import AdbDeviceTcp
from adb_shell.auth.sign_pythonrsa import PythonRSASigner
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stremio-mcp")

# Configuration
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
ANDROID_TV_HOST = os.getenv("ANDROID_TV_HOST", "")
ANDROID_TV_PORT = int(os.getenv("ANDROID_TV_PORT", "5555"))
STREMIO_AUTH_KEY = os.getenv("STREMIO_AUTH_KEY", "")
ADB_KEY_PATH = os.path.expanduser("~/.android/adbkey")

class StremioController:
    """Controller for Stremio on Android TV via ADB"""

    def __init__(self, host: str, port: int = 5555):
        self.host = host
        self.port = port
        self.device: Optional[AdbDeviceTcp] = None
        self.signer: Optional[PythonRSASigner] = None

    async def connect(self) -> bool:
        """Connect to Android TV via ADB"""
        try:
            # Load ADB keys for authentication
            signer = None
            if os.path.exists(ADB_KEY_PATH):
                try:
                    with open(ADB_KEY_PATH) as f:
                        priv_key = f.read()
                    with open(ADB_KEY_PATH + '.pub') as f:
                        pub_key = f.read()
                    signer = PythonRSASigner(pub_key, priv_key)
                    logger.debug("Loaded ADB keys for authentication")
                except Exception as e:
                    logger.warning(f"Could not load ADB keys: {e}")

            # Connect to device
            self.device = AdbDeviceTcp(self.host, self.port, default_transport_timeout_s=9.0)

            # Run connection in thread to avoid blocking
            loop = asyncio.get_event_loop()
            auth_args = [signer] if signer else []
            await loop.run_in_executor(None, lambda: self.device.connect(auth_timeout_s=10, auth_callback=None, rsa_keys=auth_args))

            logger.info(f"Connected to Android TV at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Android TV: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Android TV"""
        if self.device:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.device.close)
                logger.info("Disconnected from Android TV")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")

    async def send_intent(self, uri: str) -> bool:
        """Send an intent to open a Stremio deep link"""
        if not self.device:
            await self.connect()

        try:
            cmd = f'am start -a android.intent.action.VIEW -d "{uri}"'
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.device.shell, cmd)
            logger.info(f"Sent intent: {uri}")
            logger.debug(f"Result: {result}")
            return True
        except Exception as e:
            logger.error(f"Failed to send intent: {e}")
            return False

    async def send_key_event(self, keycode: int, delay: float = 0.5) -> bool:
        """Send a key event to Android TV"""
        if not self.device:
            await self.connect()

        try:
            # Wait a bit before sending key
            await asyncio.sleep(delay)
            cmd = f'input keyevent {keycode}'
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.device.shell, cmd)
            logger.debug(f"Sent keycode {keycode}: {result}")
            return True
        except Exception as e:
            logger.error(f"Failed to send key event: {e}")
            return False

    async def send_shell_command(self, command: str) -> str:
        """Send a shell command to Android TV and return output"""
        if not self.device:
            await self.connect()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.device.shell, command)
            return result.strip() if result else ""
        except Exception as e:
            logger.error(f"Failed to send shell command: {e}")
            return ""

    # Volume Controls
    async def volume_up(self) -> bool:
        """Increase volume"""
        return await self.send_key_event(24, delay=0)  # KEYCODE_VOLUME_UP

    async def volume_down(self) -> bool:
        """Decrease volume"""
        return await self.send_key_event(25, delay=0)  # KEYCODE_VOLUME_DOWN

    async def volume_mute(self) -> bool:
        """Mute/unmute volume"""
        return await self.send_key_event(164, delay=0)  # KEYCODE_VOLUME_MUTE

    async def set_volume(self, level: int) -> bool:
        """Set volume to specific level (0-15)"""
        if not 0 <= level <= 15:
            logger.error("Volume level must be between 0 and 15")
            return False

        cmd = f"media volume --stream 3 --set {level}"
        result = await self.send_shell_command(cmd)
        return result is not None

    # Playback Controls
    async def play_pause(self) -> bool:
        """Toggle play/pause"""
        return await self.send_key_event(85, delay=0)  # KEYCODE_MEDIA_PLAY_PAUSE

    async def media_play(self) -> bool:
        """Play media"""
        return await self.send_key_event(126, delay=0)  # KEYCODE_MEDIA_PLAY

    async def media_pause(self) -> bool:
        """Pause media"""
        return await self.send_key_event(127, delay=0)  # KEYCODE_MEDIA_PAUSE

    async def media_stop(self) -> bool:
        """Stop media"""
        return await self.send_key_event(86, delay=0)  # KEYCODE_MEDIA_STOP

    async def media_next(self) -> bool:
        """Skip to next"""
        return await self.send_key_event(87, delay=0)  # KEYCODE_MEDIA_NEXT

    async def media_previous(self) -> bool:
        """Go to previous"""
        return await self.send_key_event(88, delay=0)  # KEYCODE_MEDIA_PREVIOUS

    async def fast_forward(self) -> bool:
        """Fast forward"""
        return await self.send_key_event(90, delay=0)  # KEYCODE_MEDIA_FAST_FORWARD

    async def rewind(self) -> bool:
        """Rewind"""
        return await self.send_key_event(89, delay=0)  # KEYCODE_MEDIA_REWIND

    # Navigation Controls
    async def nav_up(self) -> bool:
        """Navigate up"""
        return await self.send_key_event(19, delay=0)  # KEYCODE_DPAD_UP

    async def nav_down(self) -> bool:
        """Navigate down"""
        return await self.send_key_event(20, delay=0)  # KEYCODE_DPAD_DOWN

    async def nav_left(self) -> bool:
        """Navigate left"""
        return await self.send_key_event(21, delay=0)  # KEYCODE_DPAD_LEFT

    async def nav_right(self) -> bool:
        """Navigate right"""
        return await self.send_key_event(22, delay=0)  # KEYCODE_DPAD_RIGHT

    async def nav_select(self) -> bool:
        """Select/OK"""
        return await self.send_key_event(23, delay=0)  # KEYCODE_DPAD_CENTER

    async def nav_back(self) -> bool:
        """Go back"""
        return await self.send_key_event(4, delay=0)  # KEYCODE_BACK

    async def nav_home(self) -> bool:
        """Go to home screen"""
        return await self.send_key_event(3, delay=0)  # KEYCODE_HOME

    # Power Controls
    async def tv_wake(self) -> bool:
        """Wake TV"""
        return await self.send_key_event(224, delay=0)  # KEYCODE_WAKEUP

    async def tv_sleep(self) -> bool:
        """Sleep TV"""
        return await self.send_key_event(223, delay=0)  # KEYCODE_SLEEP

    async def tv_power(self) -> bool:
        """Toggle TV power"""
        return await self.send_key_event(26, delay=0)  # KEYCODE_POWER

    async def get_tv_state(self) -> str:
        """Check if TV screen is on or off"""
        result = await self.send_shell_command("dumpsys power | grep 'Display Power: state='")
        if "state=ON" in result:
            return "on"
        elif "state=OFF" in result:
            return "off"
        return "unknown"

    async def get_playback_status(self) -> dict:
        """Get current playback status from media session"""
        result = await self.send_shell_command("dumpsys media_session")

        status = {
            "playing": False,
            "app": None,
            "title": None,
            "position": None,
            "duration": None,
            "state": "stopped"
        }

        if not result:
            return status

        # Parse the output
        lines = result.split('\n')
        for i, line in enumerate(lines):
            # Check if Stremio is active
            if "com.stremio.one" in line and "active=true" in result:
                status["app"] = "Stremio"

            # Get playback state
            if "state=PlaybackState" in line:
                # state=3 means playing, state=2 means paused
                if "state=3" in line:
                    status["playing"] = True
                    status["state"] = "playing"
                elif "state=2" in line:
                    status["state"] = "paused"

                # Extract position (in milliseconds)
                if "position=" in line:
                    try:
                        pos_str = line.split("position=")[1].split(",")[0]
                        status["position"] = int(pos_str)
                    except:
                        pass

                # Extract buffered position as duration estimate
                if "buffered position=" in line:
                    try:
                        buf_str = line.split("buffered position=")[1].split(",")[0]
                        status["duration"] = int(buf_str)
                    except:
                        pass

            # Get metadata (title)
            if "metadata:" in line and "description=" in line:
                # Title is in the same line: "metadata: size=9, description=Title, null, null"
                try:
                    desc = line.split("description=")[1].split(",")[0]
                    status["title"] = desc.strip()
                except:
                    pass
            elif "metadata:" in line:
                # Check next line for description
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if "description=" in next_line:
                        try:
                            desc = next_line.split("description=")[1].split(",")[0]
                            status["title"] = desc.strip()
                        except:
                            pass

        return status

    async def play_content(self, content_type: str, imdb_id: str,
                          season: Optional[int] = None,
                          episode: Optional[int] = None,
                          auto_press_play: bool = True) -> bool:
        """Play content in Stremio using deep links"""

        if content_type == "movie":
            # For movies: stremio:///detail/movie/{imdb_id}/{imdb_id}
            video_id = imdb_id
            uri = f"stremio:///detail/movie/{imdb_id}/{video_id}"
        elif content_type == "series":
            # For series: stremio:///detail/series/{imdb_id}/{imdb_id}:{season}:{episode}
            if season is None or episode is None:
                raise ValueError("Season and episode are required for TV shows")
            video_id = f"{imdb_id}:{season}:{episode}"
            uri = f"stremio:///detail/series/{imdb_id}/{video_id}"
        else:
            raise ValueError(f"Unsupported content type: {content_type}")

        # Send the intent to open the detail page
        success = await self.send_intent(uri)

        if success and auto_press_play:
            # Wait for Stremio to load, then simulate pressing the center/OK button
            # This will click the "Play" button if it's focused
            logger.info("Waiting for Stremio to load, then simulating play button press...")
            await self.send_key_event(23, delay=2.5)  # KEYCODE_DPAD_CENTER = 23

        return success


class TMDBClient:
    """Client for TMDB API to search for movies and TV shows"""

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()

    def search_movie(self, query: str, year: Optional[int] = None) -> list:
        """Search for movies"""
        params = {
            "api_key": self.api_key,
            "query": query,
            "include_adult": False
        }
        if year:
            params["year"] = year

        try:
            response = self.session.get(f"{self.BASE_URL}/search/movie", params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except Exception as e:
            logger.error(f"TMDB movie search failed: {e}")
            return []

    def search_tv(self, query: str, year: Optional[int] = None) -> list:
        """Search for TV shows"""
        params = {
            "api_key": self.api_key,
            "query": query,
            "include_adult": False
        }
        if year:
            params["first_air_date_year"] = year

        try:
            response = self.session.get(f"{self.BASE_URL}/search/tv", params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except Exception as e:
            logger.error(f"TMDB TV search failed: {e}")
            return []

    def get_external_ids(self, content_type: str, tmdb_id: int) -> dict:
        """Get external IDs including IMDb ID"""
        try:
            endpoint = "movie" if content_type == "movie" else "tv"
            response = self.session.get(
                f"{self.BASE_URL}/{endpoint}/{tmdb_id}/external_ids",
                params={"api_key": self.api_key}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get external IDs: {e}")
            return {}

    def get_tv_details(self, tmdb_id: int) -> dict:
        """Get TV show details including seasons"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/tv/{tmdb_id}",
                params={"api_key": self.api_key}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get TV details: {e}")
            return {}

    def get_season_details(self, tmdb_id: int, season_number: int) -> dict:
        """Get season details including episodes"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/tv/{tmdb_id}/season/{season_number}",
                params={"api_key": self.api_key}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get season details: {e}")
            return {}


class StremioAPIClient:
    """Client for Stremio API to access user library"""

    API_URL = "https://api.strem.io"

    def __init__(self, auth_key: str):
        self.auth_key = auth_key
        self.session = requests.Session()

    def _make_request(self, method: str, params: dict = None) -> dict:
        """Make a request to Stremio API"""
        # Flatten params into the main payload
        payload = {
            "authKey": self.auth_key,
            **(params or {})
        }

        try:
            response = self.session.post(
                f"{self.API_URL}/api/{method}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()

            if data.get("error"):
                logger.error(f"Stremio API error: {data['error']}")
                return {}

            return data.get("result", {})
        except Exception as e:
            logger.error(f"Stremio API request failed: {e}")
            return {}

    def get_library(self) -> list:
        """Get user's library items"""
        try:
            result = self._make_request("datastoreGet", {
                "collection": "libraryItem",
                "all": True
            })

            items = []
            if isinstance(result, list):
                items = result
            elif isinstance(result, dict) and "libraryItem" in result:
                items = result["libraryItem"]

            logger.info(f"Retrieved {len(items)} library items")
            return items
        except Exception as e:
            logger.error(f"Failed to get library: {e}")
            return []

    def get_continue_watching(self) -> list:
        """Get items user is currently watching (not finished)"""
        library = self.get_library()
        continue_watching = []

        for item in library:
            state = item.get("state", {})
            video_id = state.get("video_id", "")

            # Include items that have been started (have video_id and lastWatched)
            # Exclude items that are fully watched (flaggedWatched == 1 for movies)
            # For series, check if there's a video_id (meaning they're mid-episode or mid-series)
            if video_id and state.get("lastWatched"):
                # For movies, skip if flaggedWatched is 1 (fully watched)
                if item.get("type") == "movie" and state.get("flaggedWatched") == 1:
                    continue
                continue_watching.append(item)

        # Sort by most recently watched
        continue_watching.sort(key=lambda x: x.get("state", {}).get("lastWatched", ""), reverse=True)

        return continue_watching

    def search_library(self, query: str) -> list:
        """Search user's library for matching titles"""
        library = self.get_library()
        query_lower = query.lower()

        results = []
        for item in library:
            name = item.get("name", "").lower()
            if query_lower in name:
                results.append(item)

        return results


# Initialize server
app = Server("stremio-mcp")

# Global instances
controller: Optional[StremioController] = None
tmdb_client: Optional[TMDBClient] = None
stremio_client: Optional[StremioAPIClient] = None


def initialize():
    """Initialize controller and clients"""
    global controller, tmdb_client, stremio_client

    if not ANDROID_TV_HOST:
        logger.warning("ANDROID_TV_HOST not set. Please configure it.")
    else:
        controller = StremioController(ANDROID_TV_HOST, ANDROID_TV_PORT)

    if not TMDB_API_KEY:
        logger.warning("TMDB_API_KEY not set. Search functionality will be limited.")
    else:
        tmdb_client = TMDBClient(TMDB_API_KEY)

    if not STREMIO_AUTH_KEY:
        logger.warning("STREMIO_AUTH_KEY not set. Library access will be disabled.")
    else:
        stremio_client = StremioAPIClient(STREMIO_AUTH_KEY)
        logger.info("Stremio library access enabled")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="search",
            description="Search for movies or TV shows. Returns results with IMDb IDs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Title to search for"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["movie", "tv", "auto"],
                        "description": "movie, tv, or auto (searches both)",
                        "default": "auto"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Optional year filter"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="play",
            description="Play movies or TV episodes. Use 'query' to search by title, or 'imdb_id' to play directly.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Title to search and play"
                    },
                    "imdb_id": {
                        "type": "string",
                        "description": "IMDb ID (e.g., tt0111161)",
                        "pattern": "^tt[0-9]+$"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["movie", "tv"],
                        "description": "movie or tv (required with query)"
                    },
                    "season": {
                        "type": "integer",
                        "description": "Season number (for TV)",
                        "minimum": 1
                    },
                    "episode": {
                        "type": "integer",
                        "description": "Episode number (for TV)",
                        "minimum": 1
                    },
                    "source": {
                        "type": "string",
                        "enum": ["search", "library"],
                        "description": "search (TMDB) or library (Stremio)",
                        "default": "search"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Optional year filter"
                    },
                    "auto_play": {
                        "type": "boolean",
                        "description": "Automatically start playback with first available source",
                        "default": True
                    }
                }
            }
        ),
        Tool(
            name="library",
            description="Access Stremio library. Actions: list (all items), continue (currently watching), search (find by title).",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "continue", "search"],
                        "description": "list, continue, or search"
                    },
                    "query": {
                        "type": "string",
                        "description": "Title to search (for search action)"
                    }
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="tv_control",
            description="Control Android TV. volume: up/down/mute/set. playback: play/pause/toggle/stop/next/previous/forward/rewind. navigate: up/down/left/right/select/back/home. power: wake/sleep/toggle/status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["volume", "playback", "navigate", "power"],
                        "description": "volume, playback, navigate, or power"
                    },
                    "action": {
                        "type": "string",
                        "description": "Action name (see tool description for valid actions per category)"
                    },
                    "value": {
                        "description": "Value for 'set' actions (e.g., volume 0-15)"
                    }
                },
                "required": ["category", "action"]
            }
        ),
        Tool(
            name="playback_status",
            description="Get current playback status. Returns app, title, state (playing/paused/stopped), position, and duration.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""

    try:
        if name == "search":
            if not tmdb_client:
                return [TextContent(type="text", text="Error: TMDB_API_KEY not configured.")]

            query = arguments["query"]
            search_type = arguments.get("type", "auto")
            year = arguments.get("year")

            output = []

            # Search movies
            if search_type in ["movie", "auto"]:
                results = tmdb_client.search_movie(query, year)
                for movie in results[:5]:
                    tmdb_id = movie["id"]
                    external_ids = tmdb_client.get_external_ids("movie", tmdb_id)
                    imdb_id = external_ids.get("imdb_id", "N/A")
                    output.append(
                        f"• [MOVIE] {movie['title']} ({movie.get('release_date', 'N/A')[:4]})\n"
                        f"  IMDb ID: {imdb_id}\n"
                        f"  {movie.get('overview', 'No overview')[:100]}...\n"
                    )

            # Search TV shows
            if search_type in ["tv", "auto"]:
                results = tmdb_client.search_tv(query, year)
                for show in results[:5]:
                    tmdb_id = show["id"]
                    external_ids = tmdb_client.get_external_ids("tv", tmdb_id)
                    imdb_id = external_ids.get("imdb_id", "N/A")
                    output.append(
                        f"• [TV] {show['name']} ({show.get('first_air_date', 'N/A')[:4]})\n"
                        f"  IMDb ID: {imdb_id} | TMDB ID: {tmdb_id}\n"
                        f"  {show.get('overview', 'No overview')[:100]}...\n"
                    )

            return [TextContent(type="text", text="\n".join(output) if output else "No results found.")]

        elif name == "play":
            if not controller:
                return [TextContent(type="text", text="Error: ANDROID_TV_HOST not configured.")]

            source = arguments.get("source", "search")
            content_type = arguments.get("type")
            season = arguments.get("season")
            episode = arguments.get("episode")
            imdb_id = arguments.get("imdb_id")
            query = arguments.get("query")
            year = arguments.get("year")
            auto_play = arguments.get("auto_play", True)

            # If IMDb ID provided, play directly
            if imdb_id:
                if season and episode:
                    success = await controller.play_content("series", imdb_id, season, episode, auto_press_play=auto_play)
                    msg = f"S{season:02d}E{episode:02d}" if success else "episode"
                else:
                    success = await controller.play_content("movie", imdb_id, auto_press_play=auto_play)
                    msg = imdb_id if success else "movie"

                return [TextContent(type="text",
                    text=f"{'Now playing' if success else 'Failed to play'}: {msg}")]

            # Search and play
            if not query or not content_type:
                return [TextContent(type="text", text="Error: Need 'query' and 'type' or 'imdb_id'.")]

            if source == "library":
                if not stremio_client:
                    return [TextContent(type="text", text="Error: STREMIO_AUTH_KEY not configured.")]

                results = stremio_client.search_library(query)
                if not results:
                    return [TextContent(type="text", text=f"'{query}' not found in library.")]

                item = results[0]
                name = item.get("name", "Unknown")
                item_type = item.get("type")
                item_id = item.get("_id", "")
                parts = item_id.split(":")
                imdb_id = parts[0]

                if item_type == "series":
                    state = item.get("state", {})
                    video_id = state.get("video_id", "")
                    if video_id and ":" in video_id:
                        vid_parts = video_id.split(":")
                        season = int(vid_parts[1]) if len(vid_parts) > 1 else 1
                        episode = int(vid_parts[2]) if len(vid_parts) > 2 else 1
                    else:
                        season = season or 1
                        episode = episode or 1

                    success = await controller.play_content("series", imdb_id, season, episode, auto_press_play=auto_play)
                    return [TextContent(type="text",
                        text=f"{'Now playing' if success else 'Failed to play'}: {name} S{season:02d}E{episode:02d}")]
                else:
                    success = await controller.play_content("movie", imdb_id, auto_press_play=auto_play)
                    return [TextContent(type="text",
                        text=f"{'Now playing' if success else 'Failed to play'}: {name}")]

            else:  # source == "search"
                if not tmdb_client:
                    return [TextContent(type="text", text="Error: TMDB_API_KEY not configured.")]

                if content_type == "movie":
                    results = tmdb_client.search_movie(query, year)
                    if not results:
                        return [TextContent(type="text", text=f"No movies found for '{query}'.")]

                    tmdb_id = results[0]["id"]
                    external_ids = tmdb_client.get_external_ids("movie", tmdb_id)
                    imdb_id = external_ids.get("imdb_id")

                    if not imdb_id:
                        return [TextContent(type="text", text=f"Found '{results[0]['title']}' but no IMDb ID.")]

                    success = await controller.play_content("movie", imdb_id, auto_press_play=auto_play)
                    return [TextContent(type="text",
                        text=f"{'Now playing' if success else 'Failed to play'}: {results[0]['title']}")]

                elif content_type == "tv":
                    if not season or not episode:
                        return [TextContent(type="text", text="TV shows need season and episode numbers.")]

                    results = tmdb_client.search_tv(query, year)
                    if not results:
                        return [TextContent(type="text", text=f"No TV shows found for '{query}'.")]

                    tmdb_id = results[0]["id"]
                    external_ids = tmdb_client.get_external_ids("tv", tmdb_id)
                    imdb_id = external_ids.get("imdb_id")

                    if not imdb_id:
                        return [TextContent(type="text", text=f"Found '{results[0]['name']}' but no IMDb ID.")]

                    success = await controller.play_content("series", imdb_id, season, episode, auto_press_play=auto_play)
                    return [TextContent(type="text",
                        text=f"{'Now playing' if success else 'Failed to play'}: {results[0]['name']} S{season:02d}E{episode:02d}")]

        elif name == "library":
            if not stremio_client:
                return [TextContent(type="text", text="Error: STREMIO_AUTH_KEY not configured.")]

            action = arguments["action"]

            if action == "list":
                library = stremio_client.get_library()
                if not library:
                    return [TextContent(type="text", text="Your library is empty or unavailable.")]

                output = [f"Found {len(library)} items:\n"]
                for item in library[:20]:
                    name = item.get("name", "Unknown")
                    content_type = item.get("type", "unknown")
                    output.append(f"• {name} ({content_type})")

                if len(library) > 20:
                    output.append(f"\n... and {len(library) - 20} more")

                return [TextContent(type="text", text="\n".join(output))]

            elif action == "continue":
                items = stremio_client.get_continue_watching()
                if not items:
                    return [TextContent(type="text", text="No items currently in progress.")]

                output = ["Currently watching:\n"]
                for item in items:
                    name = item.get("name", "Unknown")
                    content_type = item.get("type", "unknown")
                    state = item.get("state", {})
                    video_id = state.get("video_id", "")

                    if ":" in video_id:
                        parts = video_id.split(":")
                        season = parts[1] if len(parts) > 1 else "?"
                        episode = parts[2] if len(parts) > 2 else "?"
                        output.append(f"• {name} - S{season}E{episode}")
                    else:
                        output.append(f"• {name} ({content_type})")

                return [TextContent(type="text", text="\n".join(output))]

            elif action == "search":
                query = arguments.get("query")
                if not query:
                    return [TextContent(type="text", text="Search action requires 'query' parameter.")]

                results = stremio_client.search_library(query)
                if not results:
                    return [TextContent(type="text", text=f"No results for '{query}' in library.")]

                output = [f"Found {len(results)} match(es):\n"]
                for item in results:
                    name = item.get("name", "Unknown")
                    content_type = item.get("type", "unknown")
                    imdb_id = item.get("_id", "").split(":")[0]
                    output.append(f"• {name} ({content_type}) - IMDb: {imdb_id}")

                return [TextContent(type="text", text="\n".join(output))]

        elif name == "tv_control":
            if not controller:
                return [TextContent(type="text", text="Error: ANDROID_TV_HOST not configured.")]

            category = arguments["category"]
            action = arguments["action"]
            value = arguments.get("value")

            if category == "volume":
                if action == "up":
                    success = await controller.volume_up()
                    msg = "Volume increased" if success else "Failed"
                elif action == "down":
                    success = await controller.volume_down()
                    msg = "Volume decreased" if success else "Failed"
                elif action == "mute":
                    success = await controller.volume_mute()
                    msg = "Muted" if success else "Failed"
                elif action == "set":
                    if value is None or not (0 <= int(value) <= 15):
                        return [TextContent(type="text", text="Set requires value 0-15")]
                    success = await controller.set_volume(int(value))
                    msg = f"Volume set to {value}" if success else "Failed"
                else:
                    return [TextContent(type="text", text=f"Unknown volume action: {action}")]

                return [TextContent(type="text", text=msg)]

            elif category == "playback":
                actions_map = {
                    "play": controller.media_play,
                    "pause": controller.media_pause,
                    "toggle": controller.play_pause,
                    "stop": controller.media_stop,
                    "next": controller.media_next,
                    "previous": controller.media_previous,
                    "forward": controller.fast_forward,
                    "rewind": controller.rewind
                }

                if action not in actions_map:
                    return [TextContent(type="text", text=f"Unknown playback action: {action}")]

                success = await actions_map[action]()
                return [TextContent(type="text", text=f"Playback: {action}" if success else "Failed")]

            elif category == "navigate":
                actions_map = {
                    "up": controller.nav_up,
                    "down": controller.nav_down,
                    "left": controller.nav_left,
                    "right": controller.nav_right,
                    "select": controller.nav_select,
                    "back": controller.nav_back,
                    "home": controller.nav_home
                }

                if action not in actions_map:
                    return [TextContent(type="text", text=f"Unknown navigate action: {action}")]

                success = await actions_map[action]()
                return [TextContent(type="text", text=f"Navigate: {action}" if success else "Failed")]

            elif category == "power":
                if action == "wake":
                    success = await controller.tv_wake()
                    msg = "TV waking up" if success else "Failed"
                elif action == "sleep":
                    success = await controller.tv_sleep()
                    msg = "TV going to sleep" if success else "Failed"
                elif action == "toggle":
                    success = await controller.tv_power()
                    msg = "Power toggled" if success else "Failed"
                elif action == "status":
                    state = await controller.get_tv_state()
                    return [TextContent(type="text", text=f"TV is {state}")]
                else:
                    return [TextContent(type="text", text=f"Unknown power action: {action}")]

                return [TextContent(type="text", text=msg)]

        elif name == "playback_status":
            status = await controller.get_playback_status()

            if not status["app"]:
                return [TextContent(type="text", text="No active media session found")]

            # Format position and duration
            position_str = "Unknown"
            duration_str = "Unknown"

            if status["position"] is not None:
                # Convert milliseconds to MM:SS
                pos_seconds = status["position"] // 1000
                position_str = f"{pos_seconds // 60}:{pos_seconds % 60:02d}"

            if status["duration"] is not None:
                dur_seconds = status["duration"] // 1000
                duration_str = f"{dur_seconds // 60}:{dur_seconds % 60:02d}"

            response = f"""**Playback Status**

App: {status["app"]}
Title: {status["title"] or "Unknown"}
State: {status["state"]}
Position: {position_str} / {duration_str}"""

            return [TextContent(type="text", text=response)]

        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]

    except Exception as e:
        logger.error(f"Error in tool '{name}': {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def handle_tool_call(name: str, arguments: dict) -> list[TextContent]:
    """Wrapper to call tools from the web interface"""
    return await call_tool(name, arguments)


async def run_stdio():
    """Run server with stdio transport"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


# HTML template for the test interface
TEST_INTERFACE_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stremio MCP Test Interface</title>
    <link rel="icon" type="image/png" href="icon.png">
    <style>
        :root {
            --primary: #7b5bf5;
            --primary-dark: #6247c7;
            --bg: #1a1a2e;
            --card-bg: #16213e;
            --text: #eaeaea;
            --text-muted: #a0a0a0;
            --success: #4caf50;
            --error: #f44336;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; align-items: center; justify-content: center; gap: 15px; margin-bottom: 10px; }
        .header img { width: 48px; height: 48px; }
        h1 { color: var(--primary); margin: 0; }
        .subtitle { text-align: center; color: var(--text-muted); margin-bottom: 30px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card {
            background: var(--card-bg);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .card h2 { color: var(--primary); margin-bottom: 15px; font-size: 1.2em; }
        .btn-group { display: flex; flex-wrap: wrap; gap: 8px; }
        button {
            background: var(--primary);
            color: white;
            border: none;
            padding: 10px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s;
        }
        button:hover { background: var(--primary-dark); }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        input, select {
            width: 100%;
            padding: 10px;
            border: 1px solid #333;
            border-radius: 8px;
            background: var(--bg);
            color: var(--text);
            margin-bottom: 10px;
        }
        .output {
            background: #0d1117;
            border-radius: 8px;
            padding: 15px;
            margin-top: 20px;
            font-family: monospace;
            font-size: 13px;
            max-height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-word;
        }
        .status { padding: 10px; border-radius: 8px; margin-bottom: 15px; }
        .status.connected { background: rgba(76,175,80,0.2); color: var(--success); }
        .status.disconnected { background: rgba(244,67,54,0.2); color: var(--error); }
        .status.connecting { background: rgba(255,193,7,0.2); color: #ffc107; }
        .sse-info { background: var(--card-bg); padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .sse-info code { background: var(--bg); padding: 2px 6px; border-radius: 4px; }
        .log-entry { border-bottom: 1px solid #333; padding: 5px 0; }
        .log-entry:last-child { border-bottom: none; }
        .log-time { color: var(--text-muted); font-size: 11px; }
        .log-success { color: var(--success); }
        .log-error { color: var(--error); }
        .search-results { margin-top: 15px; max-height: 400px; overflow-y: auto; }
        .search-result {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: var(--bg);
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .search-result:hover { background: #1a1a2e; }
        .result-info { flex: 1; margin-right: 10px; }
        .result-title { font-weight: bold; color: var(--text); }
        .result-meta { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
        .result-type { 
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            margin-right: 8px;
        }
        .result-type.movie { background: #e91e63; color: white; }
        .result-type.tv { background: #2196f3; color: white; }
        .play-btn {
            background: #4caf50;
            padding: 8px 16px;
            font-size: 14px;
            white-space: nowrap;
        }
        .play-btn:hover { background: #45a049; }
        .search-row { display: flex; gap: 10px; margin-bottom: 10px; }
        .search-row input { flex: 1; margin-bottom: 0; }
        .search-row select { width: 120px; margin-bottom: 0; }
        .search-row button { white-space: nowrap; }
        .no-results { color: var(--text-muted); text-align: center; padding: 20px; }
        .tv-episode-select { display: flex; gap: 8px; margin-top: 8px; align-items: center; flex-wrap: wrap; }
        .tv-episode-select select { width: auto; min-width: 120px; max-width: 200px; padding: 6px 8px; margin: 0; font-size: 13px; }
        .tv-episode-select button { padding: 6px 12px; font-size: 12px; }
        .checkbox-row { display: flex; align-items: center; gap: 8px; margin-top: 10px; }
        .checkbox-row input[type="checkbox"] { width: auto; margin: 0; }
        .checkbox-row label { color: var(--text-muted); font-size: 14px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="icon.png" alt="Stremio Logo">
            <h1>Stremio MCP Server</h1>
        </div>
        <p class="subtitle">Test Interface for MCP Tools</p>
        
        <div class="sse-info">
            <strong>SSE Endpoint:</strong> <code id="sseEndpoint"></code><br>
            <small>Use this URL to connect MCP clients (e.g., Claude Desktop)</small>
        </div>
        
        <div id="status" class="status disconnected">● Disconnected</div>
        
        <div class="grid">
            <div class="card" style="grid-column: 1 / -1;">
                <h2>🔍 Search & Play</h2>
                <div class="search-row">
                    <input type="text" id="searchQuery" placeholder="Search movies or TV shows..." onkeypress="if(event.key==='Enter')doSearch()">
                    <select id="searchType">
                        <option value="auto">All</option>
                        <option value="movie">Movies</option>
                        <option value="tv">TV Shows</option>
                    </select>
                    <button onclick="doSearch()">🔍 Search</button>
                </div>
                <div class="checkbox-row">
                    <input type="checkbox" id="autoPlay" checked>
                    <label for="autoPlay">🚀 Auto-play first available source (press OK after 2.5s to start playback)</label>
                </div>
                <div id="searchResults" class="search-results"></div>
            </div>
            
            <div class="card">
                <h2>📺 Playback Control</h2>
                <div class="btn-group">
                    <button onclick="callTool('tv_control', {category: 'playback', action: 'toggle'})">⏯️ Play/Pause</button>
                    <button onclick="callTool('tv_control', {category: 'playback', action: 'stop'})">⏹️ Stop</button>
                    <button onclick="callTool('tv_control', {category: 'playback', action: 'next'})">⏭️ Next</button>
                    <button onclick="callTool('tv_control', {category: 'playback', action: 'previous'})">⏮️ Previous</button>
                    <button onclick="callTool('tv_control', {category: 'playback', action: 'forward'})">⏩ Forward</button>
                    <button onclick="callTool('tv_control', {category: 'playback', action: 'rewind'})">⏪ Rewind</button>
                </div>
            </div>
            
            <div class="card">
                <h2>🔊 Volume</h2>
                <div class="btn-group">
                    <button onclick="callTool('tv_control', {category: 'volume', action: 'up'})">🔊 Up</button>
                    <button onclick="callTool('tv_control', {category: 'volume', action: 'down'})">🔉 Down</button>
                    <button onclick="callTool('tv_control', {category: 'volume', action: 'mute'})">🔇 Mute</button>
                </div>
                <input type="range" id="volumeLevel" min="0" max="15" value="10" style="margin-top: 10px;">
                <button onclick="callTool('tv_control', {category: 'volume', action: 'set', value: parseInt(document.getElementById('volumeLevel').value)})" style="margin-top: 5px;">Set Volume</button>
            </div>
            
            <div class="card">
                <h2>🎮 Navigation</h2>
                <div class="btn-group" style="justify-content: center;">
                    <button onclick="callTool('tv_control', {category: 'navigate', action: 'up'})" style="width: 60px;">⬆️</button>
                </div>
                <div class="btn-group" style="justify-content: center; margin-top: 5px;">
                    <button onclick="callTool('tv_control', {category: 'navigate', action: 'left'})" style="width: 60px;">⬅️</button>
                    <button onclick="callTool('tv_control', {category: 'navigate', action: 'select'})" style="width: 60px;">OK</button>
                    <button onclick="callTool('tv_control', {category: 'navigate', action: 'right'})" style="width: 60px;">➡️</button>
                </div>
                <div class="btn-group" style="justify-content: center; margin-top: 5px;">
                    <button onclick="callTool('tv_control', {category: 'navigate', action: 'down'})" style="width: 60px;">⬇️</button>
                </div>
                <div class="btn-group" style="justify-content: center; margin-top: 10px;">
                    <button onclick="callTool('tv_control', {category: 'navigate', action: 'back'})">↩️ Back</button>
                    <button onclick="callTool('tv_control', {category: 'navigate', action: 'home'})">🏠 Home</button>
                </div>
            </div>
            
            <div class="card">
                <h2>📱 Status</h2>
                <div class="btn-group">
                    <button onclick="callTool('playback_status', {})">📊 Playback Status</button>
                </div>
            </div>
            
            <div class="card">
                <h2>⚡ Power</h2>
                <div class="btn-group">
                    <button onclick="callTool('tv_control', {category: 'power', action: 'wake'})">💡 Wake</button>
                    <button onclick="callTool('tv_control', {category: 'power', action: 'sleep'})">😴 Sleep</button>
                    <button onclick="callTool('tv_control', {category: 'power', action: 'status'})">📋 Status</button>
                </div>
            </div>
        </div>
        
        <div class="card" style="margin-top: 20px;">
            <h2>📋 Output Log</h2>
            <button onclick="document.getElementById('output').innerHTML = ''" style="margin-bottom: 10px;">Clear Log</button>
            <div id="output" class="output">Ready to execute commands...</div>
        </div>
    </div>
    
    <script>
        // Get the base path for API calls (works with HA Ingress)
        const basePath = window.location.pathname.replace(/\/$/, '');
        const baseUrl = window.location.origin + basePath;
        document.getElementById('sseEndpoint').textContent = baseUrl + '/sse';
        
        let requestId = 1;
        
        function log(message, type = 'info') {
            const output = document.getElementById('output');
            const time = new Date().toLocaleTimeString();
            const className = type === 'success' ? 'log-success' : type === 'error' ? 'log-error' : '';
            output.innerHTML += `<div class="log-entry"><span class="log-time">[${time}]</span> <span class="${className}">${message}</span></div>`;
            output.scrollTop = output.scrollHeight;
        }
        
        function updateStatus(status, text) {
            const el = document.getElementById('status');
            el.className = 'status ' + status;
            el.textContent = (status === 'connected' ? '●' : status === 'connecting' ? '○' : '●') + ' ' + text;
        }
        
        async function callTool(name, args) {
            log(`Calling tool: ${name} with args: ${JSON.stringify(args)}`);
            updateStatus('connecting', 'Executing...');
            
            try {
                const response = await fetch(basePath + '/api/call-tool', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, arguments: args })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    log(`Result: ${JSON.stringify(result.result, null, 2)}`, 'success');
                    updateStatus('connected', 'Connected');
                    return result.result;
                } else {
                    log(`Error: ${result.error}`, 'error');
                    updateStatus('disconnected', 'Error');
                    return null;
                }
            } catch (err) {
                log(`Request failed: ${err.message}`, 'error');
                updateStatus('disconnected', 'Disconnected');
                return null;
            }
        }
        
        async function doSearch() {
            const query = document.getElementById('searchQuery').value.trim();
            const type = document.getElementById('searchType').value;
            const resultsDiv = document.getElementById('searchResults');
            
            if (!query) {
                resultsDiv.innerHTML = '<div class="no-results">Enter a search term</div>';
                return;
            }
            
            resultsDiv.innerHTML = '<div class="no-results">Searching...</div>';
            
            const result = await callTool('search', { query, type });
            
            if (!result || result.length === 0) {
                resultsDiv.innerHTML = '<div class="no-results">No results found</div>';
                return;
            }
            
            // Parse the result text into structured data
            const text = result[0] || '';
            const items = parseSearchResults(text);
            
            if (items.length === 0) {
                resultsDiv.innerHTML = '<div class="no-results">No results found</div>';
                return;
            }
            
            resultsDiv.innerHTML = items.map(item => {
                if (item.type === 'tv') {
                    return `
                        <div class="search-result" id="result-${item.imdbId}">
                            <div class="result-info">
                                <div class="result-title">
                                    <span class="result-type tv">TV</span>
                                    ${escapeHtml(item.title)}
                                </div>
                                <div class="result-meta">${escapeHtml(item.overview)}</div>
                                <div class="tv-episode-select">
                                    <select id="season-${item.imdbId}" onchange="loadEpisodes('${item.imdbId}', '${item.tmdbId}', this.value)">
                                        <option value="">Loading seasons...</option>
                                    </select>
                                    <select id="episode-${item.imdbId}">
                                        <option value="">Select season first</option>
                                    </select>
                                    <button class="play-btn" onclick="playTV('${item.imdbId}')">▶️ Play</button>
                                </div>
                            </div>
                        </div>
                    `;
                } else {
                    return `
                        <div class="search-result">
                            <div class="result-info">
                                <div class="result-title">
                                    <span class="result-type movie">MOVIE</span>
                                    ${escapeHtml(item.title)}
                                </div>
                                <div class="result-meta">${escapeHtml(item.overview)}</div>
                            </div>
                            <button class="play-btn" onclick="playMovie('${item.imdbId}')">▶️ Play</button>
                        </div>
                    `;
                }
            }).join('');
            
            // Load seasons for TV shows
            items.filter(i => i.type === 'tv' && i.tmdbId).forEach(item => {
                loadSeasons(item.imdbId, item.tmdbId);
            });
        }
        
        function parseSearchResults(text) {
            const items = [];
            const lines = text.split('\n');
            let current = null;
            
            for (const line of lines) {
                const movieMatch = line.match(/^• \[MOVIE\] (.+?) \((\d{4})\)/);
                const tvMatch = line.match(/^• \[TV\] (.+?) \((\d{4})\)/);
                const imdbMatch = line.match(/IMDb ID: (tt\d+)/);
                const tmdbMatch = line.match(/TMDB ID: (\d+)/);
                const overviewLine = line.trim();
                
                if (movieMatch) {
                    if (current) items.push(current);
                    current = { type: 'movie', title: `${movieMatch[1]} (${movieMatch[2]})`, imdbId: '', tmdbId: '', overview: '' };
                } else if (tvMatch) {
                    if (current) items.push(current);
                    current = { type: 'tv', title: `${tvMatch[1]} (${tvMatch[2]})`, imdbId: '', tmdbId: '', overview: '' };
                } else if (imdbMatch && current) {
                    current.imdbId = imdbMatch[1];
                } else if (tmdbMatch && current) {
                    current.tmdbId = tmdbMatch[1];
                } else if (current && overviewLine && !overviewLine.startsWith('•') && !overviewLine.startsWith('IMDb') && !overviewLine.includes('TMDB ID')) {
                    current.overview = overviewLine;
                }
            }
            if (current) items.push(current);
            
            // Filter out items without IMDb ID
            return items.filter(item => item.imdbId);
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text || '';
            return div.innerHTML;
        }
        
        function getAutoPlay() {
            return document.getElementById('autoPlay').checked;
        }
        
        async function loadSeasons(imdbId, tmdbId) {
            const seasonSelect = document.getElementById(`season-${imdbId}`);
            if (!seasonSelect) return;
            
            try {
                const response = await fetch(`${basePath}/api/seasons?tmdb_id=${tmdbId}`);
                const data = await response.json();
                
                if (data.success && data.seasons.length > 0) {
                    seasonSelect.innerHTML = data.seasons.map(s => 
                        `<option value="${s.season_number}">${s.name} (${s.episode_count} eps)</option>`
                    ).join('');
                    
                    // Load episodes for first season
                    loadEpisodes(imdbId, tmdbId, data.seasons[0].season_number);
                } else {
                    seasonSelect.innerHTML = '<option value="1">Season 1</option>';
                }
            } catch (e) {
                console.error('Failed to load seasons:', e);
                seasonSelect.innerHTML = '<option value="1">Season 1</option>';
            }
        }
        
        async function loadEpisodes(imdbId, tmdbId, seasonNumber) {
            const episodeSelect = document.getElementById(`episode-${imdbId}`);
            if (!episodeSelect) return;
            
            episodeSelect.innerHTML = '<option value="">Loading...</option>';
            
            try {
                const response = await fetch(`${basePath}/api/episodes?tmdb_id=${tmdbId}&season=${seasonNumber}`);
                const data = await response.json();
                
                if (data.success && data.episodes.length > 0) {
                    episodeSelect.innerHTML = data.episodes.map(e => 
                        `<option value="${e.episode_number}">E${e.episode_number}: ${escapeHtml(e.name)}</option>`
                    ).join('');
                } else {
                    episodeSelect.innerHTML = '<option value="1">Episode 1</option>';
                }
            } catch (e) {
                console.error('Failed to load episodes:', e);
                episodeSelect.innerHTML = '<option value="1">Episode 1</option>';
            }
        }
        
        async function playMovie(imdbId) {
            const autoPlay = getAutoPlay();
            log(`Playing movie: ${imdbId} (auto_play: ${autoPlay})`);
            await callTool('play', { imdb_id: imdbId, type: 'movie', auto_play: autoPlay });
        }
        
        async function playTV(imdbId) {
            const seasonSelect = document.getElementById(`season-${imdbId}`);
            const episodeSelect = document.getElementById(`episode-${imdbId}`);
            const season = parseInt(seasonSelect.value) || 1;
            const episode = parseInt(episodeSelect.value) || 1;
            const autoPlay = getAutoPlay();
            log(`Playing TV: ${imdbId} S${season}E${episode} (auto_play: ${autoPlay})`);
            await callTool('play', { imdb_id: imdbId, type: 'tv', season, episode, auto_play: autoPlay });
        }
        
        // Check connection on load
        fetch(basePath + '/api/status')
            .then(r => r.json())
            .then(data => {
                updateStatus('connected', 'Connected - ' + (data.android_tv_connected ? 'Android TV Ready' : 'Android TV Not Connected'));
                log('Server status: ' + JSON.stringify(data));
            })
            .catch(() => updateStatus('disconnected', 'Cannot reach server'));
    </script>
</body>
</html>
"""


def create_sse_app(ingress_port: int = None):
    """Create ASGI app for SSE transport with web interface"""
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import Response, HTMLResponse, JSONResponse, FileResponse
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    import json

    sse = SseServerTransport("/messages/")
    
    # Path to icon file
    icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
    if not os.path.exists(icon_path):
        # Try /app path (Docker)
        icon_path = "/app/icon.png"
    
    # Middleware to handle ingress path prefix
    class IngressMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            # Home Assistant ingress may add a path prefix, handle it gracefully
            return await call_next(request)

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await app.run(
                streams[0],
                streams[1],
                app.create_initialization_options()
            )
        return Response()

    async def handle_messages(request):
        await sse.handle_post_message(request.scope, request.receive, request._send)
        return Response()
    
    async def handle_index(request):
        """Serve the test interface"""
        return HTMLResponse(TEST_INTERFACE_HTML)
    
    async def handle_status(request):
        """Return server status"""
        return JSONResponse({
            "status": "ok",
            "android_tv_host": ANDROID_TV_HOST,
            "android_tv_connected": controller is not None,
            "tmdb_configured": bool(TMDB_API_KEY),
            "stremio_library": stremio_client is not None,
        })
    
    async def handle_call_tool(request):
        """Handle tool calls from the web interface"""
        try:
            body = await request.json()
            tool_name = body.get("name")
            tool_args = body.get("arguments", {})
            
            if not tool_name:
                return JSONResponse({"success": False, "error": "Missing tool name"}, status_code=400)
            
            # Import the handle_tool_call function
            result = await handle_tool_call(tool_name, tool_args)
            
            # Extract text content from result
            if result and len(result) > 0:
                text_results = [r.text for r in result if hasattr(r, 'text')]
                return JSONResponse({"success": True, "result": text_results})
            
            return JSONResponse({"success": True, "result": []})
            
        except Exception as e:
            logger.error(f"Error in call_tool API: {e}", exc_info=True)
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def handle_icon(request):
        """Serve the Stremio icon"""
        if os.path.exists(icon_path):
            return FileResponse(icon_path, media_type="image/png")
        return Response(status_code=404)

    async def handle_get_seasons(request):
        """Get available seasons for a TV show"""
        try:
            tmdb_id = request.query_params.get("tmdb_id")
            if not tmdb_id:
                return JSONResponse({"success": False, "error": "Missing tmdb_id"}, status_code=400)
            
            if not tmdb_client:
                return JSONResponse({"success": False, "error": "TMDB not configured"}, status_code=500)
            
            details = tmdb_client.get_tv_details(int(tmdb_id))
            if not details:
                return JSONResponse({"success": False, "error": "Failed to get TV details"}, status_code=500)
            
            seasons = []
            for season in details.get("seasons", []):
                # Skip season 0 (specials) unless it has episodes
                season_num = season.get("season_number", 0)
                episode_count = season.get("episode_count", 0)
                if season_num > 0 or episode_count > 0:
                    seasons.append({
                        "season_number": season_num,
                        "name": season.get("name", f"Season {season_num}"),
                        "episode_count": episode_count,
                        "air_date": season.get("air_date", "")
                    })
            
            return JSONResponse({"success": True, "seasons": seasons})
            
        except Exception as e:
            logger.error(f"Error getting seasons: {e}", exc_info=True)
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def handle_get_episodes(request):
        """Get available episodes for a TV season"""
        try:
            tmdb_id = request.query_params.get("tmdb_id")
            season_number = request.query_params.get("season")
            
            if not tmdb_id or not season_number:
                return JSONResponse({"success": False, "error": "Missing tmdb_id or season"}, status_code=400)
            
            if not tmdb_client:
                return JSONResponse({"success": False, "error": "TMDB not configured"}, status_code=500)
            
            details = tmdb_client.get_season_details(int(tmdb_id), int(season_number))
            if not details:
                return JSONResponse({"success": False, "error": "Failed to get season details"}, status_code=500)
            
            episodes = []
            for ep in details.get("episodes", []):
                episodes.append({
                    "episode_number": ep.get("episode_number", 0),
                    "name": ep.get("name", f"Episode {ep.get('episode_number', 0)}"),
                    "air_date": ep.get("air_date", ""),
                    "overview": ep.get("overview", "")[:100]
                })
            
            return JSONResponse({"success": True, "episodes": episodes})
            
        except Exception as e:
            logger.error(f"Error getting episodes: {e}", exc_info=True)
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    return Starlette(
        debug=True,
        middleware=[Middleware(IngressMiddleware)],
        routes=[
            Route("/", endpoint=handle_index),
            Route("/icon.png", endpoint=handle_icon),
            Route("/sse", endpoint=handle_sse),
            Route("/messages/", endpoint=handle_messages, methods=["POST"]),
            Route("/api/status", endpoint=handle_status),
            Route("/api/call-tool", endpoint=handle_call_tool, methods=["POST"]),
            Route("/api/seasons", endpoint=handle_get_seasons),
            Route("/api/episodes", endpoint=handle_get_episodes),
        ],
    )


def run_sse(host: str = "0.0.0.0", port: int = 9821, ingress_port: int = None):
    """Run server with SSE transport"""
    import uvicorn
    
    logger.info(f"Starting SSE server on {host}:{port}")
    logger.info(f"Connect using SSE endpoint: http://{host}:{port}/sse")
    logger.info(f"Web interface available at: http://{host}:{port}/")
    if ingress_port:
        logger.info(f"Ingress port: {ingress_port}")
    
    asgi_app = create_sse_app(ingress_port)
    uvicorn.run(asgi_app, host=host, port=port, log_level="info")


def main():
    """Main entry point with transport selection"""
    parser = argparse.ArgumentParser(description="Stremio MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport type (default: stdio, or set MCP_TRANSPORT env var)"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "0.0.0.0"),
        help="Host to bind SSE server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "9821")),
        help="Port for SSE server (default: 9821, or set MCP_PORT env var)"
    )
    
    args = parser.parse_args()
    
    initialize()
    
    if args.transport == "sse":
        run_sse(host=args.host, port=args.port)
    else:
        asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
if __name__ == "__main__":
    asyncio.run(main())
