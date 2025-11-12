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


# Initialize server
app = Server("stremio-mcp")

# Global instances
controller: Optional[StremioController] = None
tmdb_client: Optional[TMDBClient] = None


def initialize():
    """Initialize controller and clients"""
    global controller, tmdb_client

    if not ANDROID_TV_HOST:
        logger.warning("ANDROID_TV_HOST not set. Please configure it.")
    else:
        controller = StremioController(ANDROID_TV_HOST, ANDROID_TV_PORT)

    if not TMDB_API_KEY:
        logger.warning("TMDB_API_KEY not set. Search functionality will be limited.")
    else:
        tmdb_client = TMDBClient(TMDB_API_KEY)


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
