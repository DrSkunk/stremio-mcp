#!/usr/bin/env python3
"""
Stremio MCP Server - Control Stremio on Android TV via ADB
"""

import asyncio
import json
import logging
import os
from typing import Any, Optional
from urllib.parse import quote

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
            name="search_movie",
            description="Search for a movie by title and optionally year. Returns a list of matching movies with their IMDb IDs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The movie title to search for"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Optional release year to narrow results"
                    }
                },
                "required": ["title"]
            }
        ),
        Tool(
            name="search_tv_show",
            description="Search for a TV show by title and optionally year. Returns a list of matching TV shows with their IMDb IDs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The TV show title to search for"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Optional first air date year to narrow results"
                    }
                },
                "required": ["title"]
            }
        ),
        Tool(
            name="play_movie",
            description="Play a movie on Stremio using its IMDb ID. The movie will start playing on your Android TV.",
            inputSchema={
                "type": "object",
                "properties": {
                    "imdb_id": {
                        "type": "string",
                        "description": "The IMDb ID of the movie (e.g., tt0111161)",
                        "pattern": "^tt[0-9]+$"
                    }
                },
                "required": ["imdb_id"]
            }
        ),
        Tool(
            name="play_tv_episode",
            description="Play a specific episode of a TV show on Stremio using its IMDb ID, season, and episode numbers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "imdb_id": {
                        "type": "string",
                        "description": "The IMDb ID of the TV show (e.g., tt0903747)",
                        "pattern": "^tt[0-9]+$"
                    },
                    "season": {
                        "type": "integer",
                        "description": "Season number",
                        "minimum": 1
                    },
                    "episode": {
                        "type": "integer",
                        "description": "Episode number",
                        "minimum": 1
                    }
                },
                "required": ["imdb_id", "season", "episode"]
            }
        ),
        Tool(
            name="play_content",
            description="Combined tool: Search for a movie or TV show and play it immediately. Provide either a movie title or TV show title with season/episode.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the movie or TV show"
                    },
                    "content_type": {
                        "type": "string",
                        "enum": ["movie", "tv"],
                        "description": "Type of content: 'movie' or 'tv'"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Optional year to narrow search results"
                    },
                    "season": {
                        "type": "integer",
                        "description": "Season number (required for TV shows)",
                        "minimum": 1
                    },
                    "episode": {
                        "type": "integer",
                        "description": "Episode number (required for TV shows)",
                        "minimum": 1
                    }
                },
                "required": ["title", "content_type"]
            }
        ),
        Tool(
            name="get_library",
            description="Get all items from your Stremio library. Returns movies and TV shows you've added to your library.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_continue_watching",
            description="Get items you're currently watching (not finished). Perfect for resuming where you left off.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="search_library",
            description="Search your Stremio library for specific titles.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find in your library"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="play_from_library",
            description="Play content directly from your Stremio library by title. Searches your library and plays the first match.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the content in your library"
                    }
                },
                "required": ["title"]
            }
        ),

        # Android TV Control Tools
        Tool(
            name="tv_volume",
            description="Control TV volume. Can increase, decrease, mute, or set to specific level (0-15).",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["up", "down", "mute", "set"],
                        "description": "Volume action to perform"
                    },
                    "level": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 15,
                        "description": "Volume level (0-15, only for 'set' action)"
                    }
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="tv_playback",
            description="Control media playback. Supports play, pause, toggle, stop, next, previous, fast-forward, rewind.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["play", "pause", "toggle", "stop", "next", "previous", "forward", "rewind"],
                        "description": "Playback action to perform"
                    }
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="tv_navigate",
            description="Navigate the TV interface using D-pad controls (up/down/left/right/select) or system buttons (back/home).",
            inputSchema={
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "left", "right", "select", "back", "home"],
                        "description": "Navigation direction or button"
                    }
                },
                "required": ["direction"]
            }
        ),
        Tool(
            name="tv_power",
            description="Control TV power state. Can wake, sleep, toggle power, or check current state.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["wake", "sleep", "toggle", "status"],
                        "description": "Power action to perform"
                    }
                },
                "required": ["action"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""

    if not tmdb_client and name in ["search_movie", "search_tv_show", "play_content"]:
        return [TextContent(
            type="text",
            text="Error: TMDB_API_KEY not configured. Please set it in your environment."
        )]

    if not controller and name in ["play_movie", "play_tv_episode", "play_content"]:
        return [TextContent(
            type="text",
            text="Error: ANDROID_TV_HOST not configured. Please set it in your environment."
        )]

    try:
        if name == "search_movie":
            results = tmdb_client.search_movie(
                arguments["title"],
                arguments.get("year")
            )

            output = []
            for movie in results[:5]:  # Limit to top 5 results
                tmdb_id = movie["id"]
                external_ids = tmdb_client.get_external_ids("movie", tmdb_id)
                imdb_id = external_ids.get("imdb_id", "N/A")

                output.append(
                    f"• {movie['title']} ({movie.get('release_date', 'N/A')[:4]})\n"
                    f"  IMDb ID: {imdb_id}\n"
                    f"  Overview: {movie.get('overview', 'No overview available')[:100]}...\n"
                )

            return [TextContent(
                type="text",
                text="\n".join(output) if output else "No results found."
            )]

        elif name == "search_tv_show":
            results = tmdb_client.search_tv(
                arguments["title"],
                arguments.get("year")
            )

            output = []
            for show in results[:5]:  # Limit to top 5 results
                tmdb_id = show["id"]
                external_ids = tmdb_client.get_external_ids("tv", tmdb_id)
                imdb_id = external_ids.get("imdb_id", "N/A")

                output.append(
                    f"• {show['name']} ({show.get('first_air_date', 'N/A')[:4]})\n"
                    f"  IMDb ID: {imdb_id}\n"
                    f"  Overview: {show.get('overview', 'No overview available')[:100]}...\n"
                )

            return [TextContent(
                type="text",
                text="\n".join(output) if output else "No results found."
            )]

        elif name == "play_movie":
            imdb_id = arguments["imdb_id"]
            success = await controller.play_content("movie", imdb_id)

            if success:
                return [TextContent(
                    type="text",
                    text=f"Successfully sent play command for movie {imdb_id} to Stremio on Android TV."
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"Failed to play movie {imdb_id}. Check Android TV connection and Stremio installation."
                )]

        elif name == "play_tv_episode":
            imdb_id = arguments["imdb_id"]
            season = arguments["season"]
            episode = arguments["episode"]

            success = await controller.play_content("series", imdb_id, season, episode)

            if success:
                return [TextContent(
                    type="text",
                    text=f"Successfully sent play command for {imdb_id} S{season:02d}E{episode:02d} to Stremio on Android TV."
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"Failed to play episode. Check Android TV connection and Stremio installation."
                )]

        elif name == "play_content":
            title = arguments["title"]
            content_type = arguments["content_type"]
            year = arguments.get("year")

            # Search for content
            if content_type == "movie":
                results = tmdb_client.search_movie(title, year)
                if not results:
                    return [TextContent(
                        type="text",
                        text=f"No movies found matching '{title}'."
                    )]

                # Get IMDb ID for first result
                tmdb_id = results[0]["id"]
                external_ids = tmdb_client.get_external_ids("movie", tmdb_id)
                imdb_id = external_ids.get("imdb_id")

                if not imdb_id:
                    return [TextContent(
                        type="text",
                        text=f"Found '{results[0]['title']}' but no IMDb ID available."
                    )]

                # Play the movie
                success = await controller.play_content("movie", imdb_id)

                if success:
                    return [TextContent(
                        type="text",
                        text=f"Now playing: {results[0]['title']} ({results[0].get('release_date', 'N/A')[:4]}) on Stremio."
                    )]
                else:
                    return [TextContent(
                        type="text",
                        text=f"Found the movie but failed to play it on Android TV."
                    )]

            elif content_type == "tv":
                season = arguments.get("season")
                episode = arguments.get("episode")

                if season is None or episode is None:
                    return [TextContent(
                        type="text",
                        text="Season and episode numbers are required for TV shows."
                    )]

                results = tmdb_client.search_tv(title, year)
                if not results:
                    return [TextContent(
                        type="text",
                        text=f"No TV shows found matching '{title}'."
                    )]

                # Get IMDb ID for first result
                tmdb_id = results[0]["id"]
                external_ids = tmdb_client.get_external_ids("tv", tmdb_id)
                imdb_id = external_ids.get("imdb_id")

                if not imdb_id:
                    return [TextContent(
                        type="text",
                        text=f"Found '{results[0]['name']}' but no IMDb ID available."
                    )]

                # Play the episode
                success = await controller.play_content("series", imdb_id, season, episode)

                if success:
                    return [TextContent(
                        type="text",
                        text=f"Now playing: {results[0]['name']} S{season:02d}E{episode:02d} on Stremio."
                    )]
                else:
                    return [TextContent(
                        type="text",
                        text=f"Found the show but failed to play it on Android TV."
                    )]

        elif name == "get_library":
            if not stremio_client:
                return [TextContent(
                    type="text",
                    text="Error: STREMIO_AUTH_KEY not configured. Please set it to access your library."
                )]

            library = stremio_client.get_library()

            if not library:
                return [TextContent(
                    type="text",
                    text="Your Stremio library is empty or could not be retrieved."
                )]

            output = [f"Found {len(library)} items in your library:\n"]
            for item in library[:20]:  # Limit to 20 items
                name = item.get("name", "Unknown")
                content_type = item.get("type", "unknown")
                imdb_id = item.get("_id", "").replace(":", "/")

                output.append(f"• {name} ({content_type})")

            if len(library) > 20:
                output.append(f"\n... and {len(library) - 20} more items")

            return [TextContent(
                type="text",
                text="\n".join(output)
            )]

        elif name == "get_continue_watching":
            if not stremio_client:
                return [TextContent(
                    type="text",
                    text="Error: STREMIO_AUTH_KEY not configured. Please set it to access your library."
                )]

            continue_watching = stremio_client.get_continue_watching()

            if not continue_watching:
                return [TextContent(
                    type="text",
                    text="No items currently in progress."
                )]

            output = [f"You're currently watching {len(continue_watching)} items:\n"]
            for item in continue_watching[:10]:
                name = item.get("name", "Unknown")
                content_type = item.get("type", "unknown")
                state = item.get("state", {})
                video_id = state.get("video_id", "")

                output.append(f"• {name} ({content_type}) - {video_id}")

            return [TextContent(
                type="text",
                text="\n".join(output)
            )]

        elif name == "search_library":
            if not stremio_client:
                return [TextContent(
                    type="text",
                    text="Error: STREMIO_AUTH_KEY not configured. Please set it to access your library."
                )]

            query = arguments["query"]
            results = stremio_client.search_library(query)

            if not results:
                return [TextContent(
                    type="text",
                    text=f"No items found in your library matching '{query}'."
                )]

            output = [f"Found {len(results)} items matching '{query}':\n"]
            for item in results:
                name = item.get("name", "Unknown")
                content_type = item.get("type", "unknown")
                imdb_id = item.get("_id", "").split(":")[0]

                output.append(f"• {name} ({content_type}) - IMDb: {imdb_id}")

            return [TextContent(
                type="text",
                text="\n".join(output)
            )]

        elif name == "play_from_library":
            if not stremio_client:
                return [TextContent(
                    type="text",
                    text="Error: STREMIO_AUTH_KEY not configured. Please set it to access your library."
                )]

            if not controller:
                return [TextContent(
                    type="text",
                    text="Error: ANDROID_TV_HOST not configured."
                )]

            title = arguments["title"]
            results = stremio_client.search_library(title)

            if not results:
                return [TextContent(
                    type="text",
                    text=f"'{title}' not found in your library."
                )]

            # Get the first result
            item = results[0]
            name = item.get("name", "Unknown")
            content_type = item.get("type", "unknown")
            item_id = item.get("_id", "")

            # Parse the ID (format: tt1234567:1:1 for series, tt1234567 for movies)
            parts = item_id.split(":")
            imdb_id = parts[0]

            if content_type == "series" and len(parts) >= 3:
                # For series, use the video from state if available
                state = item.get("state", {})
                video_id = state.get("video_id", "")

                if video_id and ":" in video_id:
                    vid_parts = video_id.split(":")
                    if len(vid_parts) >= 3:
                        season = int(vid_parts[1])
                        episode = int(vid_parts[2])
                        success = await controller.play_content("series", imdb_id, season, episode)
                    else:
                        season = int(parts[1]) if len(parts) > 1 else 1
                        episode = int(parts[2]) if len(parts) > 2 else 1
                        success = await controller.play_content("series", imdb_id, season, episode)
                else:
                    season = int(parts[1]) if len(parts) > 1 else 1
                    episode = int(parts[2]) if len(parts) > 2 else 1
                    success = await controller.play_content("series", imdb_id, season, episode)

                if success:
                    return [TextContent(
                        type="text",
                        text=f"Now playing: {name} S{season:02d}E{episode:02d} from your library."
                    )]
            else:
                # For movies
                success = await controller.play_content("movie", imdb_id)

                if success:
                    return [TextContent(
                        type="text",
                        text=f"Now playing: {name} from your library."
                    )]

            return [TextContent(
                type="text",
                text=f"Found '{name}' but failed to play it."
            )]

        elif name == "tv_volume":
            if not controller:
                return [TextContent(
                    type="text",
                    text="Error: ANDROID_TV_HOST not configured."
                )]

            action = arguments["action"]
            level = arguments.get("level")

            if action == "up":
                success = await controller.volume_up()
                message = "Volume increased" if success else "Failed to increase volume"
            elif action == "down":
                success = await controller.volume_down()
                message = "Volume decreased" if success else "Failed to decrease volume"
            elif action == "mute":
                success = await controller.volume_mute()
                message = "Volume muted/unmuted" if success else "Failed to mute volume"
            elif action == "set":
                if level is None:
                    return [TextContent(type="text", text="Error: Level required for 'set' action")]
                success = await controller.set_volume(level)
                message = f"Volume set to {level}" if success else f"Failed to set volume to {level}"
            else:
                return [TextContent(type="text", text=f"Unknown action: {action}")]

            return [TextContent(type="text", text=message)]

        elif name == "tv_playback":
            if not controller:
                return [TextContent(
                    type="text",
                    text="Error: ANDROID_TV_HOST not configured."
                )]

            action = arguments["action"]

            if action == "play":
                success = await controller.media_play()
                message = "Playback started" if success else "Failed to start playback"
            elif action == "pause":
                success = await controller.media_pause()
                message = "Playback paused" if success else "Failed to pause playback"
            elif action == "toggle":
                success = await controller.play_pause()
                message = "Playback toggled" if success else "Failed to toggle playback"
            elif action == "stop":
                success = await controller.media_stop()
                message = "Playback stopped" if success else "Failed to stop playback"
            elif action == "next":
                success = await controller.media_next()
                message = "Skipped to next" if success else "Failed to skip to next"
            elif action == "previous":
                success = await controller.media_previous()
                message = "Went to previous" if success else "Failed to go to previous"
            elif action == "forward":
                success = await controller.fast_forward()
                message = "Fast forwarding" if success else "Failed to fast forward"
            elif action == "rewind":
                success = await controller.rewind()
                message = "Rewinding" if success else "Failed to rewind"
            else:
                return [TextContent(type="text", text=f"Unknown action: {action}")]

            return [TextContent(type="text", text=message)]

        elif name == "tv_navigate":
            if not controller:
                return [TextContent(
                    type="text",
                    text="Error: ANDROID_TV_HOST not configured."
                )]

            direction = arguments["direction"]

            if direction == "up":
                success = await controller.nav_up()
                message = "Navigated up" if success else "Failed to navigate up"
            elif direction == "down":
                success = await controller.nav_down()
                message = "Navigated down" if success else "Failed to navigate down"
            elif direction == "left":
                success = await controller.nav_left()
                message = "Navigated left" if success else "Failed to navigate left"
            elif direction == "right":
                success = await controller.nav_right()
                message = "Navigated right" if success else "Failed to navigate right"
            elif direction == "select":
                success = await controller.nav_select()
                message = "Selected" if success else "Failed to select"
            elif direction == "back":
                success = await controller.nav_back()
                message = "Went back" if success else "Failed to go back"
            elif direction == "home":
                success = await controller.nav_home()
                message = "Went to home" if success else "Failed to go to home"
            else:
                return [TextContent(type="text", text=f"Unknown direction: {direction}")]

            return [TextContent(type="text", text=message)]

        elif name == "tv_power":
            if not controller:
                return [TextContent(
                    type="text",
                    text="Error: ANDROID_TV_HOST not configured."
                )]

            action = arguments["action"]

            if action == "wake":
                success = await controller.tv_wake()
                message = "TV woken up" if success else "Failed to wake TV"
            elif action == "sleep":
                success = await controller.tv_sleep()
                message = "TV put to sleep" if success else "Failed to sleep TV"
            elif action == "toggle":
                success = await controller.tv_power()
                message = "TV power toggled" if success else "Failed to toggle TV power"
            elif action == "status":
                state = await controller.get_tv_state()
                return [TextContent(type="text", text=f"TV is {state}")]
            else:
                return [TextContent(type="text", text=f"Unknown action: {action}")]

            return [TextContent(type="text", text=message)]

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


async def main():
    """Main entry point"""
    initialize()

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
